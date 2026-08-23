"""Firebase Cloud Messaging (HTTP v1) delivery and device-token persistence.

The Android app supplies its native FCM registration token after login. Server
credentials are read only from deployment environment variables; no Firebase
Admin private key is stored in the repository or shipped to the mobile app.
"""
import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from database import db

logger = logging.getLogger("push_notifications")

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
device_push_tokens = db.device_push_tokens


async def ensure_push_indexes() -> None:
    """Create the small, isolated index set used by push-token registration."""
    await device_push_tokens.create_index("token", unique=True, name="unique_push_token")
    await device_push_tokens.create_index(
        [("user_id", 1), ("active", 1), ("updated_at", -1)],
        name="push_tokens_by_user",
    )


class FirebasePushAdapter:
    """Best-effort direct FCM sender using Google OAuth + FCM HTTP v1."""

    name = "firebase_fcm_v1"

    def __init__(self) -> None:
        self._credentials = None
        self._credential_marker: str | None = None
        self._credential_lock = asyncio.Lock()

    def _raw_service_account(self) -> str:
        raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if raw:
            return raw
        encoded = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64", "").strip()
        if not encoded:
            return ""
        try:
            return base64.b64decode(encoded, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning("Firebase service credential base64 is invalid (%s)", type(exc).__name__)
            return ""

    def _service_account_info(self) -> dict[str, Any] | None:
        raw = self._raw_service_account()
        if not raw:
            return None
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Firebase service credential is not valid JSON")
            return None
        required = ("project_id", "client_email", "private_key", "token_uri")
        if not isinstance(info, dict) or info.get("type") != "service_account" or any(not info.get(k) for k in required):
            logger.warning("Firebase service credential is incomplete")
            return None
        return info

    @property
    def configured(self) -> bool:
        return self._service_account_info() is not None

    def _access_token_sync(self, info: dict[str, Any]) -> str:
        marker = f"{info.get('project_id')}:{info.get('client_email')}:{info.get('private_key_id', '')}"
        if self._credentials is None or self._credential_marker != marker:
            self._credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=[FCM_SCOPE],
            )
            self._credential_marker = marker
        if not self._credentials.valid:
            self._credentials.refresh(GoogleAuthRequest())
        if not self._credentials.token:
            raise RuntimeError("Firebase OAuth token was not issued")
        return self._credentials.token

    async def _access_token(self, info: dict[str, Any]) -> str:
        async with self._credential_lock:
            return await asyncio.to_thread(self._access_token_sync, info)

    @staticmethod
    def _stringify_data(data: dict[str, Any] | None) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in (data or {}).items():
            if value is None:
                continue
            if isinstance(value, bool):
                result[str(key)] = "true" if value else "false"
            elif isinstance(value, (dict, list)):
                result[str(key)] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            else:
                result[str(key)] = str(value)
        return result

    @classmethod
    def _message_payload(
        cls,
        token: str,
        title: str,
        body: str,
        data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "message": {
                "token": token,
                "notification": {"title": title, "body": body},
                "data": cls._stringify_data(data),
                "android": {
                    "priority": "high",
                    "notification": {"channel_id": "default", "sound": "default"},
                },
            }
        }

    @staticmethod
    def _fcm_error_code(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return None
        for detail in error.get("details") or []:
            if isinstance(detail, dict) and detail.get("errorCode"):
                return str(detail["errorCode"])
        status = error.get("status")
        return str(status) if status else None

    async def _send_one(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        access_token: str,
        token_doc: dict[str, Any],
        title: str,
        body: str,
        data: dict[str, Any] | None,
    ) -> None:
        token = str(token_doc.get("token") or "")
        if not token:
            return
        try:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=self._message_payload(token, title, body, data),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("FCM request failed (%s)", type(exc).__name__)
            return
        if 200 <= response.status_code < 300:
            return
        error_code = self._fcm_error_code(response)
        if error_code == "UNREGISTERED":
            await device_push_tokens.update_one(
                {"_id": token_doc["_id"]},
                {"$set": {"active": False, "invalidated_at": datetime.now(timezone.utc)}},
            )
        logger.warning("FCM delivery failed (status=%s code=%s)", response.status_code, error_code or "unknown")

    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Attempt delivery to all active devices for a user without raising."""
        info = self._service_account_info()
        if not info:
            return
        project_id = os.environ.get("FIREBASE_PROJECT_ID", "").strip() or str(info.get("project_id") or "")
        if not project_id:
            logger.warning("Firebase project id is missing")
            return
        token_docs = await device_push_tokens.find(
            {"user_id": user_id, "active": True}
        ).sort("updated_at", -1).to_list(20)
        if not token_docs:
            return
        try:
            access_token = await self._access_token(info)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Firebase OAuth refresh failed (%s)", type(exc).__name__)
            return
        endpoint = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        async with httpx.AsyncClient(timeout=12.0) as client:
            await asyncio.gather(
                *(
                    self._send_one(client, endpoint, access_token, doc, title, body, data)
                    for doc in token_docs
                ),
                return_exceptions=True,
            )


push = FirebasePushAdapter()
