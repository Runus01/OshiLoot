"""One JSON log line per request: method, route template, status, duration.

The route template (/api/anime/users/{username}/list) is logged instead of the
real path, so usernames never reach the logs.
"""

import json
import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("oshiloot.request")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            logger.info(
                json.dumps(
                    {
                        "method": scope["method"],
                        "route": getattr(route, "path", "unmatched"),
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                )
            )
