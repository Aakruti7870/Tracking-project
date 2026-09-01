"""Central request rate limiting and safe production error responses."""
from __future__ import annotations

from collections import defaultdict, deque
from hashlib import sha256
import json
import logging
import time

import jwt
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import settings

logger = logging.getLogger("trackmyrmc.security")


class RateLimitMiddleware:
    """Configurable fixed-window limits with exponential auth backoff.

    Both the network address and a one-way account identifier are checked on
    authentication endpoints. This deliberately avoids hard lockouts: a client
    may retry after the bounded exponential delay.
    """

    def __init__(self, app):
        self.app = app
        self.events: dict[str, deque[float]] = defaultdict(deque)
        self.violations: dict[str, int] = defaultdict(int)

    def _check(self, key: str, limit: int, now: float, auth: bool = False) -> int:
        events = self.events[key]
        cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) < limit:
            events.append(now)
            return 0
        self.violations[key] += 1
        if auth:
            return min(
                settings.RATE_LIMIT_BACKOFF_MAX_SECONDS,
                settings.RATE_LIMIT_BACKOFF_BASE_SECONDS * 2 ** (self.violations[key] - 1),
            )
        return max(1, int(events[0] + settings.RATE_LIMIT_WINDOW_SECONDS - now))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        client = scope.get("client")
        ip = client[0] if client else "unknown"
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        now = time.monotonic()
        is_auth = path.startswith("/api/auth") or path.startswith("/api/account-deletion")
        authenticated = False
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        if authorization.lower().startswith("bearer "):
            try:
                jwt.decode(
                    authorization[7:].strip(),
                    settings.JWT_SECRET,
                    algorithms=[settings.JWT_ALGORITHM],
                    options={"require": ["exp", "sub"]},
                )
                authenticated = True
            except jwt.PyJWTError:
                pass
        retry = self._check(
            f"{'auth' if is_auth else 'api'}:ip:{ip}",
            settings.RATE_LIMIT_AUTH_IP if is_auth else (
                settings.RATE_LIMIT_AUTHENTICATED if authenticated else settings.RATE_LIMIT_PUBLIC
            ),
            now,
            is_auth,
        )

        body = b""
        if is_auth and scope.get("method") in {"POST", "PUT", "PATCH"}:
            # Preserve the ASGI body for FastAPI after deriving a non-reversible
            # per-account key. Invalid JSON is left for schema validation.
            more = True
            while more:
                message = await receive()
                body += message.get("body", b"")
                more = message.get("more_body", False)
            try:
                value = json.loads(body).get("identifier", "")
            except (ValueError, AttributeError):
                value = ""
            if isinstance(value, str) and value:
                account = sha256(value.strip().lower().encode()).hexdigest()
                retry = max(retry, self._check(
                    f"auth:account:{account}", settings.RATE_LIMIT_AUTH_ACCOUNT, now, True
                ))
            delivered = False

            async def replay():
                nonlocal delivered
                if delivered:
                    return {"type": "http.request", "body": b"", "more_body": False}
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}

            receive = replay

        if retry:
            response = JSONResponse(
                {"detail": "Too many requests. Please try again later."},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error method=%s path=%s", request.method, request.url.path)
    return JSONResponse({"detail": "An unexpected error occurred."}, status_code=500)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.info("Request validation failed method=%s path=%s errors=%s", request.method, request.url.path, exc.errors())
    return JSONResponse({"detail": "Request validation failed."}, status_code=422)
