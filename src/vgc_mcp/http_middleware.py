"""Pure-ASGI middleware for the hosted HTTP transport.

Implemented as raw ASGI (not Starlette's ``BaseHTTPMiddleware``) because the
``/mcp`` and ``/sse`` endpoints stream responses — ``BaseHTTPMiddleware``
buffers the full response body and would break streaming.

Both middlewares are **opt-in via environment variables** so the default
(local / current hosted) behavior is unchanged:

- ``VGC_MCP_API_KEY`` — when set, require ``Authorization: Bearer <key>`` on
  MCP endpoints. Unset ⇒ no auth (local dev, backward compatible).
- ``VGC_MCP_RATE_LIMIT`` — max requests per IP per window (default window 60s).
  Unset or ``0`` ⇒ no rate limiting.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Awaitable, Callable, Iterable

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


async def _send_json(send: Send, status: int, payload: dict) -> None:
    import json

    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BearerAuthMiddleware:
    """Require a bearer token on protected paths when an API key is configured.

    Exempt paths (health/root) and CORS preflight (``OPTIONS``) always pass so
    monitoring and browser preflight keep working.
    """

    def __init__(
        self,
        app: ASGIApp,
        api_key: str | None,
        exempt_paths: Iterable[str] = ("/", "/health"),
    ) -> None:
        self.app = app
        self.api_key = api_key or None
        self.exempt_paths = set(exempt_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.api_key is None:
            return await self.app(scope, receive, send)
        if scope.get("method") == "OPTIONS" or scope.get("path") in self.exempt_paths:
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"authorization", b"").decode()
        expected = f"Bearer {self.api_key}"
        if provided == expected:
            return await self.app(scope, receive, send)

        await _send_json(
            send,
            401,
            {"error": "unauthorized", "detail": "Missing or invalid bearer token."},
        )


class RateLimitMiddleware:
    """Fixed-window per-IP rate limiter.

    ``limit`` requests per ``window`` seconds per client IP. ``limit <= 0``
    disables it. Exempt paths (health/root) are never limited so monitoring
    can't be throttled.
    """

    def __init__(
        self,
        app: ASGIApp,
        limit: int,
        window: float = 60.0,
        exempt_paths: Iterable[str] = ("/", "/health"),
    ) -> None:
        self.app = app
        self.limit = limit
        self.window = window
        self.exempt_paths = set(exempt_paths)
        self._lock = Lock()
        # ip -> (window_start, count)
        self._buckets: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    def _client_ip(self, scope: Scope) -> str:
        # Honor X-Forwarded-For (Render/Fly put the real client here) then fall
        # back to the socket peer.
        headers = dict(scope.get("headers") or [])
        xff = headers.get(b"x-forwarded-for")
        if xff:
            return xff.decode().split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    def _allowed(self, ip: str, now: float) -> bool:
        with self._lock:
            start, count = self._buckets[ip]
            if now - start >= self.window:
                self._buckets[ip] = (now, 1)
                return True
            if count >= self.limit:
                return False
            self._buckets[ip] = (start, count + 1)
            return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or self.limit <= 0
            or scope.get("path") in self.exempt_paths
        ):
            return await self.app(scope, receive, send)

        ip = self._client_ip(scope)
        if self._allowed(ip, time.monotonic()):
            return await self.app(scope, receive, send)

        await _send_json(
            send,
            429,
            {"error": "rate_limited", "detail": "Too many requests; slow down."},
        )
