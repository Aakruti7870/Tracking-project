"""Provider-agnostic notification/OTP delivery service.

Core business logic never couples to a single vendor. SMS delivery uses Twilio
when its credentials are present; otherwise the adapter reports NOT_CONFIGURED.
In development the OTP is still surfaced back to the caller so the flow stays
testable even with a live provider (Twilio trial keys can only reach verified
numbers, and the seeded demo numbers are not real).
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

from config import settings
from database import notifications, users

logger = logging.getLogger("notifications")
# Twilio's HTTP client logs every request/response at INFO — keep logs readable.
logging.getLogger("twilio.http_client").setLevel(logging.WARNING)


class SmsEmailAdapter:
    """SMS via Twilio (Messaging API). Email left dormant until a key is set."""

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
    def sms_configured(self) -> bool:
        sid, tok, frm = self._twilio_creds
        return bool(sid and tok and frm)

    @property
    def configured(self) -> bool:
        return self.sms_configured or bool(os.environ.get("EMAIL_PROVIDER_API_KEY"))

    def _get_client(self):
        if self._client is None:
            from twilio.rest import Client

            sid, tok, _ = self._twilio_creds
            self._client = Client(sid, tok)
        return self._client

    def _send_sms_sync(self, destination: str, message: str) -> None:
        _, _, frm = self._twilio_creds
        self._get_client().messages.create(to=destination, from_=frm, body=message)

    async def send(self, channel: str, destination: str, message: str) -> bool:
        """Best-effort delivery. Never raises — a vendor failure (e.g. an
        unverified trial number) must not break the OTP/notification flow."""
        if channel == "sms" and self.sms_configured:
            try:
                await asyncio.to_thread(self._send_sms_sync, destination, message)
                logger.info("SMS sent to %s", destination)
                return True
            except Exception as exc:  # noqa: BLE001 — deliberately swallowed
                logger.warning("Twilio SMS failed for %s: %s", destination, exc)
                return False
        if settings.is_dev:
            logger.info("[NOT_CONFIGURED] would send %s to %s", channel, destination)
        return False


delivery = SmsEmailAdapter()


async def record_notification(user_id: str, event: str, title: str, body: str) -> None:
    """Persist an in-app notification (durable). SMS for specific customer
    events (dispatch/delivered) is sent from the order state machine so it is
    idempotent — not fired on every in-app notification."""
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
    return {"adapter": delivery.name, "configured": delivery.configured, "sms": delivery.sms_configured}
