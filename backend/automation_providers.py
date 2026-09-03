"""Optional, authenticated provider adapters for claimed automation events.

Adapters receive an already allowlisted event. They cannot access or mutate order
state. The dispatcher returns normalized metadata suitable for the queue audit.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi.encoders import jsonable_encoder


class ProviderConfigurationError(RuntimeError):
    pass


class ProviderDeliveryError(RuntimeError):
    pass


def _https_url(name: str) -> str:
    value = os.getenv(name, "").strip()
    parsed = urlparse(value)
    if not value or parsed.scheme != "https" or not parsed.netloc:
        raise ProviderConfigurationError(f"{name} must be an HTTPS URL")
    return value


def _secret(name: str, minimum: int = 24) -> str:
    value = os.getenv(name, "").strip()
    if len(value) < minimum:
        raise ProviderConfigurationError(f"{name} is not configured")
    return value


@dataclass(frozen=True)
class DeliveryResult:
    provider: str
    provider_id: str
    status: str

    def as_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "provider_id": self.provider_id, "status": self.status}


class N8nWebhookAdapter:
    name = "n8n"

    async def send(self, event: dict, client: httpx.AsyncClient | None = None) -> DeliveryResult:
        url = _https_url("N8N_WEBHOOK_URL")
        secret = _secret("N8N_WEBHOOK_SIGNING_SECRET", 32)
        body = json.dumps(jsonable_encoder(event), sort_keys=True, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        owned = client is None
        client = client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.post(url, content=body, headers={
                "Content-Type": "application/json",
                "X-TrackMyRMC-Timestamp": timestamp,
                "X-TrackMyRMC-Signature": f"sha256={signature}",
                "Idempotency-Key": str(event["source_history_id"]),
            })
            if not 200 <= response.status_code < 300:
                raise ProviderDeliveryError(f"n8n returned HTTP {response.status_code}")
            data = response.json() if response.content else {}
            return DeliveryResult(self.name, str(data.get("delivery_id") or event["source_history_id"]), "accepted")
        finally:
            if owned:
                await client.aclose()


class VapiCallAdapter:
    name = "vapi"

    async def send(self, event: dict, phone: str, client: httpx.AsyncClient | None = None) -> DeliveryResult:
        key = _secret("VAPI_API_KEY", 24)
        assistant_id = _secret("VAPI_ASSISTANT_ID", 8)
        if not phone.startswith("+") or not phone[1:].isdigit():
            raise ProviderDeliveryError("Vapi destination must be E.164")
        payload = {
            "assistantId": assistant_id,
            "customer": {"number": phone},
            "assistantOverrides": {"variableValues": {
                "orderNumber": event.get("payload", {}).get("order_number", ""),
                "orderStatus": event["to_status"],
                "message": event.get("delivery", {}).get("template", {}).get("en", ""),
            }},
        }
        owned = client is None
        client = client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.post("https://api.vapi.ai/call", json=payload, headers={
                "Authorization": f"Bearer {key}", "Idempotency-Key": str(event["source_history_id"]),
            })
            if not 200 <= response.status_code < 300:
                raise ProviderDeliveryError(f"Vapi returned HTTP {response.status_code}")
            data = response.json()
            provider_id = str(data.get("id") or "")
            if not provider_id:
                raise ProviderDeliveryError("Vapi response omitted call id")
            return DeliveryResult(self.name, provider_id, str(data.get("status") or "queued"))
        finally:
            if owned:
                await client.aclose()


class CodConfirmationService:
    """Part A entry point; Part B delegates COD confirmation here."""

    async def trigger(self, event: dict, phone: str,
                      client: httpx.AsyncClient | None = None) -> DeliveryResult:
        return await vapi.send(event, phone, client)


class TwilioMessageAdapter:
    """SMS/WhatsApp boundary using Twilio's authenticated REST API."""
    name = "twilio"

    async def send(self, channel: str, destination: str, message: str,
                   client: httpx.AsyncClient | None = None) -> DeliveryResult:
        if channel not in {"sms", "whatsapp"}:
            raise ProviderDeliveryError("Unsupported Twilio channel")
        sid = _secret("TWILIO_ACCOUNT_SID", 8)
        token = _secret("TWILIO_AUTH_TOKEN", 24)
        sender_name = "TWILIO_WHATSAPP_FROM" if channel == "whatsapp" else "TWILIO_FROM_NUMBER"
        sender = _secret(sender_name, 8)
        prefix = "whatsapp:" if channel == "whatsapp" else ""
        owned = client is None
        client = client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                data={"To": prefix + destination, "From": prefix + sender, "Body": message},
                auth=(sid, token),
            )
            if not 200 <= response.status_code < 300:
                raise ProviderDeliveryError(f"Twilio returned HTTP {response.status_code}")
            data = response.json()
            return DeliveryResult(f"twilio_{channel}", str(data.get("sid") or ""), str(data.get("status") or "queued"))
        finally:
            if owned:
                await client.aclose()


n8n = N8nWebhookAdapter()
vapi = VapiCallAdapter()
cod_confirmation = CodConfirmationService()
twilio_messages = TwilioMessageAdapter()
