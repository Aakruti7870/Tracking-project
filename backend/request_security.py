"""Central request rate limiting and safe production error responses."""
from __future__ import annotations

from collections import deque
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

# Plant Staff authentication moved to approved-email bootstrap followed by
# Authenticator/passkey. The older Google OAuth endpoints remain in the legacy
# router for rollback archaeology only, but production HTTP traffic must never
# reach them because they can mint an ordinary staff bearer without the current
# MFA contract. Keep this boundary centralized and fail-closed until the dead
# routes are removed in a dedicated compatibility cleanup.
RETIRED_AUTH_PATH_PREFIXES = ("/api/auth/google/",)


def is_retired_auth_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in RETIRED_AUTH_PATH_PREFIXES)


class RateLimitMiddleware:
    """Configurable fixed-window limits with exponential auth backoff.

    Both the network address and a one-way account identifier are checked on
    authentication endpoints. This deliberately avoids hard lockouts: a client
    may retry after the bounded exponential delay.
    """

    def __init__(self, app):
        self.app = app
        self.events: dict[str, deque[float]] = {}
        self.violations: dict[str, tuple[int, float]] = {}
        self.last_sweep = 0.0

    def _sweep(self, now: float) -> None:
        """Discard inactive identities so attacker-controlled keys cannot leak memory."""
        if now - self.last_sweep < settings.RATE_LIMIT_WINDOW_SECONDS:
            return
        cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
        self.events = {
            key: events for key, events in self.events.items() if events and events[-1] > cutoff
        }
        self.violations = {
            key: value for key, value in self.violations.items() if value[1] > cutoff
        }
        self.last_sweep = now

    def _check(self, key: str, limit: int, now: float, auth: bool = False) -> int:
        events = self.events.setdefault(key, deque())
        cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) < limit:
            events.append(now)
            return 0
        count = self.violations.get(key, (0, now))[0] + 1
        self.violations[key] = (count, now)
        if auth:
            return min(
                settings.RATE_LIMIT_BACKOFF_MAX_SECONDS,
                settings.RATE_LIMIT_BACKOFF_BASE_SECONDS * 2 ** (count - 1),
            )
        return max(1, int(events[0] + settings.RATE_LIMIT_WINDOW_SECONDS - now))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")

        # Do not let legacy Google staff OAuth reach the router at all. This is
        # intentionally earlier than rate limiting and bearer inspection so no
        # OAuth state/code can be exchanged for a TrackMyRMC session.
        if is_retired_auth_path(path):
            response = JSONResponse(
                {
                    "detail": (
                        "Google Staff Sign-In has been retired. "
                        "Use the approved Plant Staff email, Authenticator, or passkey login."
                    )
                },
                status_code=410,
            )
            return await response(scope, receive, send)

        client = scope.get("client")
        ip = client[0] if client else "unknown"
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        now = time.monotonic()
        self._sweep(now)
        is_auth = (
            path.startswith("/api/auth")
            or path.startswith("/api/admin/auth")
            or path.startswith("/api/account-deletion")
        )
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

        # Do not buffer a request that is already rejected by its IP limit.
        if retry:
            return await self._reject(scope, receive, send, retry)

        body = b""
        if is_auth and scope.get("method") in {"POST", "PUT", "PATCH"}:
            # Preserve the ASGI body for FastAPI after deriving a non-reversible
            # per-account key. Invalid JSON is left for schema validation.
            chunks = bytearray()
            more = True
            while more:
                message = await receive()
                chunk = message.get("body", b"")
                if len(chunks) + len(chunk) > settings.MAX_AUTH_BODY_BYTES:
                    response = JSONResponse(
                        {"detail": "Request body is too large."}, status_code=413
                    )
                    return await response(scope, receive, send)
                chunks.extend(chunk)
                more = message.get("more_body", False)
            body = bytes(chunks)
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
            return await self._reject(scope, receive, send, retry)
        return await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send, retry: int) -> None:
        response = JSONResponse(
            {"detail": "Too many requests. Please try again later."},
            status_code=429,
            headers={"Retry-After": str(retry)},
        )
        await response(scope, receive, send)


async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error method=%s path=%s", request.method, request.url.path)
    return JSONResponse({"detail": "An unexpected error occurred."}, status_code=500)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    safe_errors = [
        {"type": error.get("type"), "loc": error.get("loc")}
        for error in exc.errors()
    ]
    logger.info(
        "Request validation failed method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        safe_errors,
    )
    return JSONResponse({"detail": "Request validation failed."}, status_code=422)
