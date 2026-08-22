"""Provider-agnostic notification/OTP delivery service.

SMS delivery uses Twilio. Staff email OTP delivery uses SendGrid when
EMAIL_PROVIDER_API_KEY and EMAIL_FROM are configured. Provider failures are
best-effort here; authentication decides whether a failed OTP delivery can be
accepted (development) or must fail closed (production).
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

from config import settings
from database import notifications

logger = logging.getLogger("notifications")
logging.getLogger("twilio.http_client").setLevel(logging.WARNING)


def _masked(destination: str) -> str:
    """Return a non-sensitive destination marker suitable for logs."""
    if "@" in destination:
        local, _, domain = destination.partition("@")
        return f"{local[:1]}***@{domain}"
    digits = "".join(ch for ch in destination if ch.isdigit())
    return f"***{digits[-4:]}" if digits else "***"


class SmsEmailAdapter:
    """SMS via Twilio; email via SendGrid REST API."""

    # Keep the existing public adapter name for compatibility with clients/tests.
    name = "twilio_sms"

    def __init__(self) -> None:
        self._client = None

    @property
    def _twilio_creds(self):
        return (
            os.environ.get("TWILIO_ACCOUNT_SID", "").strip(),
            os.environ.get("TWILIO_AUTH_TOKEN", "").strip(),
            os.environ.get("TWILIO_FROM_NUMBER", "").strip(),
        )

    @property
    def _email_creds(self):
        return (
            os.environ.get("EMAIL_PROVIDER_API_KEY", "").strip(),
            os.environ.get("EMAIL_FROM", "").strip(),
        )

    @property
    def sms_configured(self) -> bool:
        sid, tok, frm = self._twilio_creds
        return bool(sid and tok and frm)

    @property
    def email_configured(self) -> bool:
        key, sender = self._email_creds
        return bool(key and sender)

    @property
    def configured(self) -> bool:
        return self.sms_configured or self.email_configured

    def _get_client(self):
        if self._client is None:
            from twilio.rest import Client

            sid, tok, _ = self._twilio_creds
            self._client = Client(sid, tok)
        return self._client

    def _send_sms_sync(self, destination: str, message: str) -> None:
        _, _, frm = self._twilio_creds
        self._get_client().messages.create(to=destination, from_=frm, body=message)

    async def _send_email(self, destination: str, message: str) -> bool:
        api_key, sender = self._email_creds
        if not api_key or not sender:
            return False
        payload = {
            "personalizations": [{"to": [{"email": destination}]}],
            "from": {"email": sender, "name": "TrackMyRMC"},
            "subject": "Your TrackMyRMC verification code",
            "content": [{"type": "text/plain", "value": message}],
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if 200 <= response.status_code < 300:
                logger.info("Email sent to %s", _masked(destination))
                return True
            logger.warning("SendGrid email failed for %s (status=%s)", _masked(destination), response.status_code)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("SendGrid email failed for %s (%s)", _masked(destination), type(exc).__name__)
            return False

    async def send(self, channel: str, destination: str, message: str) -> bool:
        """Best-effort provider delivery without exposing credentials/PII."""
        if channel == "sms" and self.sms_configured:
            try:
                await asyncio.to_thread(self._send_sms_sync, destination, message)
                logger.info("SMS sent to %s", _masked(destination))
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Twilio SMS failed for %s (%s)", _masked(destination), type(exc).__name__)
                return False
        if channel == "email" and self.email_configured:
            return await self._send_email(destination, message)
        if settings.is_dev:
            logger.info("[NOT_CONFIGURED] %s delivery unavailable for %s", channel, _masked(destination))
        return False


delivery = SmsEmailAdapter()


async def record_notification(user_id: str, event: str, title: str, body: str) -> None:
    """Persist an in-app notification (durable)."""
    await notifications.insert_one(
        {
            "user_id": user_id,
            "event": event,
            "title": title,
            "body": body,
            "read": False,
            "created_at": datetime.now(timezone.utc),
        }
    )


def provider_status() -> dict:
    return {
        "adapter": delivery.name,
        "configured": delivery.configured,
        "sms": delivery.sms_configured,
        "email": delivery.email_configured,
    }
