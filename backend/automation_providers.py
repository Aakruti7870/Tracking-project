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


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ProviderConfigurationError(f"{name} must be a boolean")


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
        auth_token = _secret("N8N_WEBHOOK_AUTH_TOKEN", 32)
        body = json.dumps(jsonable_encoder(event), sort_keys=True, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        owned = client is None
        client = client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.post(url, content=body, headers={
                "Content-Type": "application/json",
                "X-TrackMyRMC-Token": auth_token,
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


class MetaWhatsAppAdapter:
    """Direct Meta WhatsApp Cloud API transport for in-session text messages.

    Meta permits free-form text only inside the customer-service window. Proactive
    notifications outside that window require an approved template. The routing
    adapter below therefore retains the existing Twilio path as a cutover fallback
    until status-template delivery is enabled for every automation event.
    """

    name = "meta_whatsapp"
    graph_version = "v25.0"

    async def send(self, destination: str, message: str,
                   client: httpx.AsyncClient | None = None) -> DeliveryResult:
        access_token = _secret("META_WHATSAPP_ACCESS_TOKEN", 32)
        phone_number_id = _secret("META_WHATSAPP_PHONE_NUMBER_ID", 8)
        raw_destination = str(destination or "").strip()
        digits = raw_destination[1:] if raw_destination.startswith("+") else raw_destination
        if not digits.isdigit() or not 8 <= len(digits) <= 15:
            raise ProviderDeliveryError("Meta WhatsApp destination must be E.164")
        body = str(message or "").strip()
        if not body:
            raise ProviderDeliveryError("Meta WhatsApp message is empty")
        if len(body) > 4096:
            raise ProviderDeliveryError("Meta WhatsApp message exceeds 4096 characters")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": digits,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        owned = client is None
        client = client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.post(
                f"https://graph.facebook.com/{self.graph_version}/{phone_number_id}/messages",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            if not 200 <= response.status_code < 300:
                raise ProviderDeliveryError(f"Meta WhatsApp returned HTTP {response.status_code}")
            try:
                data = response.json()
            except Exception as exc:
                raise ProviderDeliveryError("Meta WhatsApp returned an invalid response") from exc
            messages = data.get("messages") or []
            first = messages[0] if messages and isinstance(messages[0], dict) else {}
            provider_id = str(first.get("id") or "")
            if not provider_id:
                raise ProviderDeliveryError("Meta WhatsApp response omitted message id")
            return DeliveryResult(
                self.name,
                provider_id,
                str(first.get("message_status") or "accepted"),
            )
        finally:
            if owned:
                await client.aclose()


class MessageChannelRouter:
    """Preserve SMS on Twilio while preferring Meta for WhatsApp cutover.

    ``WHATSAPP_PROVIDER`` accepts ``auto`` (default), ``meta`` or ``twilio``.
    In ``auto`` mode, the presence of the Meta access token and phone-number ID
    selects Meta. ``WHATSAPP_TWILIO_FALLBACK`` defaults to true so a Meta policy or
    transient delivery rejection does not interrupt existing order notifications.
    """

    def __init__(self, twilio: TwilioMessageAdapter | None = None,
                 meta: MetaWhatsAppAdapter | None = None):
        self.twilio = twilio or TwilioMessageAdapter()
        self.meta = meta or MetaWhatsAppAdapter()

    async def send(self, channel: str, destination: str, message: str,
                   client: httpx.AsyncClient | None = None) -> DeliveryResult:
        if channel == "sms":
            return await self.twilio.send(channel, destination, message, client)
        if channel != "whatsapp":
            raise ProviderDeliveryError("Unsupported message channel")

        provider = os.getenv("WHATSAPP_PROVIDER", "auto").strip().lower() or "auto"
        if provider not in {"auto", "meta", "twilio"}:
            raise ProviderConfigurationError("WHATSAPP_PROVIDER must be auto, meta or twilio")
        if provider == "twilio":
            return await self.twilio.send(channel, destination, message, client)

        meta_configured = bool(
            os.getenv("META_WHATSAPP_ACCESS_TOKEN", "").strip()
            and os.getenv("META_WHATSAPP_PHONE_NUMBER_ID", "").strip()
        )
        if provider == "auto" and not meta_configured:
            return await self.twilio.send(channel, destination, message, client)

        try:
            return await self.meta.send(destination, message, client)
        except (ProviderConfigurationError, ProviderDeliveryError):
            if not _bool_env("WHATSAPP_TWILIO_FALLBACK", True):
                raise
            return await self.twilio.send(channel, destination, message, client)


n8n = N8nWebhookAdapter()
vapi = VapiCallAdapter()
cod_confirmation = CodConfirmationService()
meta_whatsapp = MetaWhatsAppAdapter()
twilio_messages = MessageChannelRouter(meta=meta_whatsapp)
