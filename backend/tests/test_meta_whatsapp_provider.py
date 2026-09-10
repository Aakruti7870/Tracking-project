import asyncio
import json

import httpx
import pytest

from automation_providers import (
    MessageChannelRouter,
    MetaWhatsAppAdapter,
    ProviderConfigurationError,
    ProviderDeliveryError,
    TwilioMessageAdapter,
)


def test_meta_whatsapp_sends_direct_cloud_api_text(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_ACCESS_TOKEN", "EAA" + "x" * 64)
    monkeypatch.setenv("META_WHATSAPP_PHONE_NUMBER_ID", "1332590046601852")

    def handler(request):
        assert request.url == httpx.URL(
            "https://graph.facebook.com/v25.0/1332590046601852/messages"
        )
        assert request.headers["Authorization"] == "Bearer " + "EAA" + "x" * 64
        body = json.loads(request.content)
        assert body == {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": "919876543210",
            "type": "text",
            "text": {"preview_url": False, "body": "TrackMyRMC update"},
        }
        return httpx.Response(
            200,
            json={"messages": [{"id": "wamid.test", "message_status": "accepted"}]},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await MetaWhatsAppAdapter().send(
                "+919876543210", "TrackMyRMC update", client
            )

    result = asyncio.run(run())
    assert result.provider == "meta_whatsapp"
    assert result.provider_id == "wamid.test"
    assert result.status == "accepted"


def test_meta_whatsapp_rejects_invalid_destination_before_network(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_ACCESS_TOKEN", "EAA" + "x" * 64)
    monkeypatch.setenv("META_WHATSAPP_PHONE_NUMBER_ID", "1332590046601852")

    with pytest.raises(ProviderDeliveryError, match="destination must be E.164"):
        asyncio.run(MetaWhatsAppAdapter().send("not-a-phone", "test"))


def test_auto_router_prefers_meta_when_meta_secrets_exist(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_ACCESS_TOKEN", "EAA" + "x" * 64)
    monkeypatch.setenv("META_WHATSAPP_PHONE_NUMBER_ID", "1332590046601852")
    monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)

    def handler(request):
        assert request.url.host == "graph.facebook.com"
        return httpx.Response(200, json={"messages": [{"id": "wamid.meta"}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            router = MessageChannelRouter()
            return await router.send("whatsapp", "+919876543210", "Status update", client)

    assert asyncio.run(run()).provider == "meta_whatsapp"


def test_auto_router_falls_back_to_twilio_when_meta_rejects(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_ACCESS_TOKEN", "EAA" + "x" * 64)
    monkeypatch.setenv("META_WHATSAPP_PHONE_NUMBER_ID", "1332590046601852")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC12345678")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t" * 24)
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+910000000001")
    monkeypatch.setenv("WHATSAPP_TWILIO_FALLBACK", "true")

    def handler(request):
        if request.url.host == "graph.facebook.com":
            return httpx.Response(400, json={"error": {"message": "outside service window"}})
        assert request.url.host == "api.twilio.com"
        return httpx.Response(201, json={"sid": "SM-fallback", "status": "queued"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            router = MessageChannelRouter()
            return await router.send("whatsapp", "+919876543210", "Status update", client)

    result = asyncio.run(run())
    assert result.provider == "twilio_whatsapp"
    assert result.provider_id == "SM-fallback"


def test_explicit_meta_can_disable_twilio_fallback(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_ACCESS_TOKEN", "EAA" + "x" * 64)
    monkeypatch.setenv("META_WHATSAPP_PHONE_NUMBER_ID", "1332590046601852")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
    monkeypatch.setenv("WHATSAPP_TWILIO_FALLBACK", "false")

    def handler(_request):
        return httpx.Response(500, text="upstream body must not leak")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            router = MessageChannelRouter()
            return await router.send("whatsapp", "+919876543210", "Status update", client)

    with pytest.raises(ProviderDeliveryError, match="Meta WhatsApp returned HTTP 500") as caught:
        asyncio.run(run())
    assert "upstream body" not in str(caught.value)


def test_invalid_whatsapp_provider_fails_closed(monkeypatch):
    monkeypatch.setenv("WHATSAPP_PROVIDER", "unknown")
    router = MessageChannelRouter(twilio=TwilioMessageAdapter())

    with pytest.raises(ProviderConfigurationError, match="WHATSAPP_PROVIDER"):
        asyncio.run(router.send("whatsapp", "+919876543210", "Status update"))
