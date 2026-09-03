import asyncio
import hashlib
import hmac
import json

import httpx
import pytest

from automation_providers import N8nWebhookAdapter, TwilioMessageAdapter, VapiCallAdapter
from routers.assistant import SUPPORT_ROUTES


def _event(status="DELIVERED"):
    return {"source_history_id": "history-1", "to_status": status,
            "payload": {"order_number": "RMC-1001"},
            "delivery": {"template": {"en": "Order delivered."}}}


def test_n8n_request_is_signed_safe_and_idempotent(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example.test/webhook/order")
    monkeypatch.setenv("N8N_WEBHOOK_SIGNING_SECRET", "s" * 32)

    def handler(request):
        timestamp = request.headers["X-TrackMyRMC-Timestamp"]
        expected = hmac.new(("s" * 32).encode(), timestamp.encode() + b"." + request.content,
                            hashlib.sha256).hexdigest()
        assert request.headers["X-TrackMyRMC-Signature"] == f"sha256={expected}"
        assert request.headers["Idempotency-Key"] == "history-1"
        assert "secret" not in json.loads(request.content)
        return httpx.Response(202, json={"delivery_id": "n8n-run-1"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await N8nWebhookAdapter().send(_event(), client)

    assert asyncio.run(run()).as_dict() == {
        "provider": "n8n", "provider_id": "n8n-run-1", "status": "accepted",
    }


def test_vapi_call_uses_bearer_idempotency_and_safe_variables(monkeypatch):
    monkeypatch.setenv("VAPI_API_KEY", "k" * 24)
    monkeypatch.setenv("VAPI_ASSISTANT_ID", "assistant-1")

    def handler(request):
        assert request.headers["Authorization"] == "Bearer " + "k" * 24
        assert request.headers["Idempotency-Key"] == "history-1"
        body = json.loads(request.content)
        assert body["customer"] == {"number": "+919876543210"}
        assert set(body["assistantOverrides"]["variableValues"]) == {"orderNumber", "orderStatus", "message"}
        return httpx.Response(201, json={"id": "call-1", "status": "queued"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await VapiCallAdapter().send(_event(), "+919876543210", client)

    assert asyncio.run(run()).provider_id == "call-1"


@pytest.mark.parametrize("channel,sender_env,prefix", [
    ("sms", "TWILIO_FROM_NUMBER", ""), ("whatsapp", "TWILIO_WHATSAPP_FROM", "whatsapp:")
])
def test_twilio_message_boundaries(monkeypatch, channel, sender_env, prefix):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC12345678")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t" * 24)
    monkeypatch.setenv(sender_env, "+910000000001")

    def handler(request):
        encoded_prefix = "whatsapp%3A" if prefix else ""
        assert f"To={encoded_prefix}%2B919876543210" in request.content.decode()
        return httpx.Response(201, json={"sid": "SM1", "status": "queued"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await TwilioMessageAdapter().send(channel, "+919876543210", "Safe update", client)

    assert asyncio.run(run()).provider == f"twilio_{channel}"


def test_every_support_category_has_a_distinct_safe_route():
    assert set(SUPPORT_ROUTES) == {"LOGIN", "KYC", "ORDER", "TRACKING", "PAYMENT",
                                   "ACCOUNT_DELETION", "PLANT_ONBOARDING", "GENERAL"}
    assert len({route["action"] for route in SUPPORT_ROUTES.values()}) == 8
    combined = " ".join(route["guidance"] for route in SUPPORT_ROUTES.values()).lower()
    assert "never share" in combined
