import hashlib
import hmac

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.meta_whatsapp import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_meta_webhook_verification_returns_challenge(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TOKEN", "TRACKMYRMC_META_VERIFY_2026")
    response = _client().get(
        "/api/meta/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "TRACKMYRMC_META_VERIFY_2026",
            "hub.challenge": "123456",
        },
    )
    assert response.status_code == 200
    assert response.text == "123456"


def test_meta_webhook_verification_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TOKEN", "TRACKMYRMC_META_VERIFY_2026")
    response = _client().get(
        "/api/meta/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "123456",
        },
    )
    assert response.status_code == 403


def test_meta_webhook_post_accepts_valid_signature(monkeypatch):
    app_secret = "meta-app-secret-for-test"
    monkeypatch.setenv("META_APP_SECRET", app_secret)
    body = b'{"object":"whatsapp_business_account"}'
    signature = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    response = _client().post(
        "/api/meta/whatsapp/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "received"}


def test_meta_webhook_post_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "meta-app-secret-for-test")
    response = _client().post(
        "/api/meta/whatsapp/webhook",
        content=b'{"object":"whatsapp_business_account"}',
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert response.status_code == 401
