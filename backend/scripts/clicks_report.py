"""A month of store clicks from the live site, as a summary and optionally a CSV.

Every click out to a store goes through /go/, which saves the store, the anime and the
country in the clicks table, one partition per UTC day (see app.core.storage). Nothing
about the person who clicked is stored, so nothing about them is reported.

Run it from backend/, with the virtual environment active and AWS_PROFILE and AWS_REGION
set as in the README:

    python scripts/clicks_report.py                                 # this month so far
    python scripts/clicks_report.py --month 2026-11 --csv clicks-2026-11.csv
"""

import argparse
import csv
import json
import sys
import urllib.request
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

FIELDS = ["day", "time", "store", "anime_id", "country", "character_id", "theme_id"]


def month_days(month: str, today: date) -> list[str]:
    """The UTC days of a month ("2026-11") up to today, as table partition keys."""
    first = datetime.strptime(month, "%Y-%m").date()
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = min(next_month - timedelta(days=1), today)
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def _known(value: Any) -> str | None:
    # Events are stored as strings, so a missing value can arrive as "None".
    return None if value in (None, "", "None") else str(value)


def summarise(clicks: Iterable[dict[str, Any]]) -> dict[str, Counter[str]]:
    """Click counts by day, store, country and anime."""
    totals: dict[str, Counter[str]] = {
        "day": Counter(),
        "store": Counter(),
        "country": Counter(),
        "anime": Counter(),
    }
    for click in clicks:
        totals["day"][click["pk"]] += 1
        totals["store"][_known(click.get("store")) or "unknown"] += 1
        totals["country"][_known(click.get("country")) or "unknown"] += 1
        if anime := _known(click.get("anime_id")):
            totals["anime"][anime] += 1
    return totals


def csv_row(click: dict[str, Any]) -> dict[str, str]:
    return {
        "day": click["pk"],
        "time": click["sk"].split("#")[0],
        **{field: _known(click.get(field)) or "" for field in FIELDS[2:]},
    }


def _clicks_table(session: Any) -> Any:
    client = session.client("dynamodb")
    names = [
        name
        for page in client.get_paginator("list_tables").paginate()
        for name in page["TableNames"]
        if "ClicksTable" in name
    ]
    if not names:
        sys.exit("No clicks table found. Check AWS_PROFILE and AWS_REGION point at the site.")
    return session.resource("dynamodb").Table(names[0])


def _clicks_on(table: Any, day: str) -> Iterator[dict[str, Any]]:
    from boto3.dynamodb.conditions import Key

    query: dict[str, Any] = {"KeyConditionExpression": Key("pk").eq(day)}
    while True:
        page = table.query(**query)
        yield from page["Items"]
        if "LastEvaluatedKey" not in page:
            return
        query["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _title(site: str, anime_id: str) -> str:
    """The anime's title, from the site's own API; its ID if that doesn't answer."""
    try:
        with urllib.request.urlopen(f"{site}/api/anime/{anime_id}", timeout=5) as response:
            titles = json.load(response)["titles"]
        return titles.get("en") or titles["main"]
    except Exception:
        return f"anime {anime_id}"


def _print_table(heading: str, counts: Counter[str], label=lambda key: key, top: int = 10) -> None:
    print(f"\n{heading}")
    for key, count in counts.most_common(top):
        print(f"  {count:>6}  {label(key)}")


def main(argv: list[str] | None = None) -> int:
    today = datetime.now(UTC).date()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--month", default=today.strftime("%Y-%m"), help="e.g. 2026-11")
    parser.add_argument("--csv", help="also save every click to this CSV file")
    parser.add_argument("--site", default="https://oshiloot.com", help="for anime titles")
    args = parser.parse_args(argv)

    import boto3

    days = month_days(args.month, today)
    if not days:
        sys.exit(f"{args.month} hasn't started yet.")
    table = _clicks_table(boto3.Session())
    clicks = [click for day in days for click in _clicks_on(table, day)]
    totals = summarise(clicks)

    print(f"OshiLoot store clicks, {args.month} ({days[0]} to {days[-1]}, UTC)")
    print(f"Total: {len(clicks)} clicks, {len(clicks) / len(days):.1f} a day")
    _print_table("By store", totals["store"])
    _print_table("By country", totals["country"])
    _print_table("Top anime", totals["anime"], label=lambda key: _title(args.site, key))
    busiest = totals["day"].most_common(1)
    if busiest:
        print(f"\nBusiest day: {busiest[0][0]}, {busiest[0][1]} clicks")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(csv_row(click) for click in sorted(clicks, key=lambda c: c["sk"]))
        print(f"Saved {len(clicks)} clicks to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
