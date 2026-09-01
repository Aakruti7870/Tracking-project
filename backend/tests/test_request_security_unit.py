"""Regression tests for bounded request-security middleware state and logging."""
import asyncio
import json
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError

from request_security import RateLimitMiddleware, validation_error_handler


async def _ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _scope(path="/api/auth/verify-otp"):
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [],
        "client": ("192.0.2.1", 1234),
    }


async def _invoke(middleware, body: bytes, *, receive=None):
    responses = []
    delivered = False

    async def default_receive():
        nonlocal delivered
        assert not delivered
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        responses.append(message)

    await middleware(_scope(), receive or default_receive, send)
    start = next(item for item in responses if item["type"] == "http.response.start")
    payload = next(item for item in responses if item["type"] == "http.response.body")
    return start["status"], json.loads(payload.get("body", b"{}") or b"{}")


def test_auth_body_is_bounded(monkeypatch):
    monkeypatch.setattr("request_security.settings.MAX_AUTH_BODY_BYTES", 8)
    middleware = RateLimitMiddleware(_ok_app)
    status, payload = asyncio.run(_invoke(middleware, b'{"identifier":"too-long"}'))
    assert status == 413
    assert payload == {"detail": "Request body is too large."}


def test_ip_rejection_does_not_read_body(monkeypatch):
    monkeypatch.setattr("request_security.settings.RATE_LIMIT_AUTH_IP", 1)
    middleware = RateLimitMiddleware(_ok_app)
    asyncio.run(_invoke(middleware, b"{}"))

    async def forbidden_receive():
        raise AssertionError("rate-limited request body was consumed")

    status, _ = asyncio.run(_invoke(middleware, b"", receive=forbidden_receive))
    assert status == 429


def test_sweep_evicts_inactive_identities(monkeypatch):
    monkeypatch.setattr("request_security.settings.RATE_LIMIT_WINDOW_SECONDS", 10)
    middleware = RateLimitMiddleware(_ok_app)
    middleware._check("old", 1, 1.0, True)
    middleware._check("old", 1, 2.0, True)
    middleware._sweep(20.0)
    assert "old" not in middleware.events
    assert "old" not in middleware.violations


def test_validation_log_redacts_rejected_input(caplog):
    secret = "credential-that-must-not-be-logged"
    error = RequestValidationError([
        {"type": "string_too_long", "loc": ("body", "code"), "input": secret}
    ])
    request = Request({"type": "http", "method": "POST", "path": "/api/auth", "headers": []})
    with caplog.at_level(logging.INFO, logger="trackmyrmc.security"):
        response = asyncio.run(validation_error_handler(request, error))
    assert response.status_code == 422
    assert secret not in caplog.text
    assert "string_too_long" in caplog.text


def test_upload_reencode_applies_exif_orientation_and_strips_metadata():
    from io import BytesIO

    from PIL import Image
    from routers.storage import _validate_image

    original = Image.new("RGB", (2, 1), "red")
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise for display.
    encoded = BytesIO()
    original.save(encoded, format="JPEG", exif=exif)

    clean, extension, content_type = _validate_image(encoded.getvalue())
    with Image.open(BytesIO(clean)) as result:
        assert result.size == (1, 2)
        assert not result.getexif()
    assert (extension, content_type) == ("jpg", "image/jpeg")
