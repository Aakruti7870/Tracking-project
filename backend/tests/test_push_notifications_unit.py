import base64
import json

from push_notifications import FirebasePushAdapter


def _credential_fixture() -> dict:
    return {
        "type": "service_account",
        "project_id": "track-my-rmc",
        "private_key_id": "fixture-key-id",
        "private_key": "unit-test-key-material",
        "client_email": "fixture@track-my-rmc.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def test_firebase_push_is_unconfigured_without_server_credential(monkeypatch):
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_B64", raising=False)
    assert FirebasePushAdapter().configured is False


def test_firebase_service_account_supports_base64_secret(monkeypatch):
    raw = json.dumps(_credential_fixture()).encode("utf-8")
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_B64", base64.b64encode(raw).decode("ascii"))
    info = FirebasePushAdapter()._service_account_info()
    assert info is not None
    assert info["project_id"] == "track-my-rmc"


def test_fcm_message_payload_stringifies_data():
    payload = FirebasePushAdapter._message_payload(
        "device-token-value-that-is-long-enough",
        "Mixer dispatched",
        "Your concrete is on the way",
        {"route": "/notifications", "attempt": 2, "urgent": True, "skip": None},
    )
    message = payload["message"]
    assert message["data"] == {
        "route": "/notifications",
        "attempt": "2",
        "urgent": "true",
    }
    assert message["android"]["priority"] == "high"
    assert message["android"]["notification"]["channel_id"] == "default"
