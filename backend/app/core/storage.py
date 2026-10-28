"""Key-value cache and append-only event log, backed by memory (local/tests) or DynamoDB."""

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

import anyio
import boto3

from app.core.config import Settings


class KeyValueStore(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def put(self, key: str, value: Any, ttl_seconds: int) -> None: ...


class EventLog(Protocol):
    async def append(self, event: dict[str, Any]) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None or item[0] < time.time():
            return None
        return item[1]

    async def put(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._items[key] = (time.time() + ttl_seconds, value)


class MemoryEventLog:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def append(self, event: dict[str, Any]) -> None:
        self.events.append(event)


class DynamoStore:
    """One item per key: {pk, value (JSON string), ttl (epoch seconds)}."""

    def __init__(self, table: Any) -> None:
        self._table = table

    async def get(self, key: str) -> Any | None:
        response = await anyio.to_thread.run_sync(lambda: self._table.get_item(Key={"pk": key}))
        item = response.get("Item")
        # DynamoDB deletes expired items lazily, so check the TTL ourselves.
        if item is None or int(item["ttl"]) < time.time():
            return None
        return json.loads(item["value"])

    async def put(self, key: str, value: Any, ttl_seconds: int) -> None:
        item = {"pk": key, "value": json.dumps(value), "ttl": int(time.time()) + ttl_seconds}
        await anyio.to_thread.run_sync(lambda: self._table.put_item(Item=item))


class DynamoEventLog:
    """Partitioned by UTC day so one day's events can be queried together."""

    def __init__(self, table: Any) -> None:
        self._table = table

    async def append(self, event: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        item = {
            "pk": now.strftime("%Y-%m-%d"),
            "sk": f"{now.isoformat()}#{uuid.uuid4().hex[:8]}",
            **{k: str(v) for k, v in event.items()},
        }
        await anyio.to_thread.run_sync(lambda: self._table.put_item(Item=item))


def _dynamodb(settings: Settings) -> Any:
    return boto3.resource(
        "dynamodb", region_name=settings.aws_region, endpoint_url=settings.dynamodb_endpoint
    )


def ensure_local_tables(settings: Settings) -> None:
    """Create tables in DynamoDB Local. In AWS, CDK creates them instead."""
    db = _dynamodb(settings)
    existing = {t.name for t in db.tables.all()}
    specs = {
        settings.cache_table: [("pk", "HASH")],
        settings.clicks_table: [("pk", "HASH"), ("sk", "RANGE")],
    }
    for name, keys in specs.items():
        if name in existing:
            continue
        db.create_table(
            TableName=name,
            KeySchema=[{"AttributeName": a, "KeyType": t} for a, t in keys],
            AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a, _ in keys],
            BillingMode="PAY_PER_REQUEST",
        )


def build_storage(settings: Settings) -> tuple[KeyValueStore, EventLog]:
    if settings.storage == "memory":
        return MemoryStore(), MemoryEventLog()
    if settings.dynamodb_endpoint:
        ensure_local_tables(settings)
    db = _dynamodb(settings)
    cache = DynamoStore(db.Table(settings.cache_table))
    clicks = DynamoEventLog(db.Table(settings.clicks_table))
    return cache, clicks
