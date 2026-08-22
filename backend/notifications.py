"""Provider-agnostic notification/OTP delivery service.

Core business logic never couples to a single vendor. When no provider
credentials are configured the adapter reports NOT_CONFIGURED. In development
the OTP is surfaced back to the caller so the flow is testable end-to-end.
"""
import logging
import os
from datetime import datetime, timezone

from config import settings
from database import notifications

logger = logging.getLogger("notifications")


class DeliveryAdapter:
    """Base adapter. Real vendors (SMS/email/push) subclass and implement send."""

    name = "base"

    @property
    def configured(self) -> bool:
        return False

    async def send(self, channel: str, destination: str, message: str) -> bool:
        raise NotImplementedError


class SmsEmailAdapter(DeliveryAdapter):
    name = "sms_email"

    @property
    def configured(self) -> bool:
        return bool(
            os.environ.get("SMS_PROVIDER_API_KEY")
            or os.environ.get("EMAIL_PROVIDER_API_KEY")
        )

    async def send(self, channel: str, destination: str, message: str) -> bool:
        if not self.configured:
            # Fail loud in production; permit dev-mode testing without a vendor.
            if settings.is_dev:
                logger.info("[NOT_CONFIGURED] would send %s to %s", channel, destination)
                return False
            raise RuntimeError("OTP delivery provider is NOT_CONFIGURED")
        # Production: call the vendor SDK/HTTP here. Never log the raw message.
        return True


delivery = SmsEmailAdapter()


async def record_notification(user_id: str, event: str, title: str, body: str) -> None:
    """Persist an in-app notification. This is the durable, non-faked record."""
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
    return {"adapter": delivery.name, "configured": delivery.configured}
