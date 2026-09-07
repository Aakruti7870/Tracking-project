"""Sandbox DigiLocker client.

All credentials stay in runtime secrets. This module never logs credentials,
authorization URLs, Aadhaar data, or document contents.
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


class DigiLockerConfigurationError(RuntimeError):
    pass


logger = logging.getLogger(__name__)
APPROVED_SANDBOX_HOSTS = {"api.sandbox.co.in", "test-api.sandbox.co.in"}


@dataclass(frozen=True)
class DigiLockerSettings:
    api_key: str
    api_secret: str
    auth_base_url: str
    init_base_url: str
    read_base_url: str
    redirect_url: str


class DigiLockerProviderError(RuntimeError):
    """Sanitized provider failure safe to surface to application code."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _provider_error(operation: str, url: str, status_code: int) -> DigiLockerProviderError:
    parsed = urlparse(url)
    safe_path = parsed.path
    if "/sessions/" in safe_path:
        prefix, suffix = safe_path.split("/sessions/", 1)
        safe_path = f"{prefix}/sessions/[redacted]/" + suffix.split("/", 1)[-1]
    logger.warning(
        "DigiLocker provider request failed operation=%s host=%s path=%s status=%s",
        operation, parsed.hostname, safe_path, status_code,
    )
    return DigiLockerProviderError(
        f"DigiLocker {operation} failed ({status_code}).", status_code=status_code
    )


def _provider_origin(name: str, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise DigiLockerConfigurationError(f"{name} must be an HTTPS provider origin.")
    if parsed.hostname not in APPROVED_SANDBOX_HOSTS:
        raise DigiLockerConfigurationError(f"{name} is not an approved Sandbox hostname.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        raise DigiLockerConfigurationError(f"{name} must be an HTTPS provider origin.")
    return value.rstrip("/")


def provider_settings() -> DigiLockerSettings:
    api_key = os.getenv("KYC_API_KEY", "").strip()
    api_secret = os.getenv("KYC_API_SECRET", "").strip()
    compatibility_base = os.getenv("KYC_BASE_URL", "").strip()
    auth_base = os.getenv("KYC_AUTH_BASE_URL", "").strip() or compatibility_base
    init_base = os.getenv("KYC_INIT_BASE_URL", "").strip() or compatibility_base
    read_base = os.getenv("KYC_READ_BASE_URL", "").strip() or compatibility_base
    redirect_url = os.getenv("KYC_REDIRECT_URL", "").strip()
    if not api_key or not api_secret or not auth_base or not init_base or not read_base or not redirect_url:
        raise DigiLockerConfigurationError(
            "DigiLocker is not configured. KYC_API_KEY, KYC_API_SECRET and "
            "explicit provider base URLs and KYC_REDIRECT_URL are required."
        )
    auth_base = _provider_origin("KYC_AUTH_BASE_URL", auth_base)
    init_base = _provider_origin("KYC_INIT_BASE_URL", init_base)
    read_base = _provider_origin("KYC_READ_BASE_URL", read_base)
    parsed_redirect = urlparse(redirect_url)
    if parsed_redirect.scheme != "https" or not parsed_redirect.hostname:
        raise DigiLockerConfigurationError("KYC_REDIRECT_URL must use HTTPS.")
    environment = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").lower()
    if environment in {"production", "prod"} and parsed_redirect.hostname != "trackmyrmc.com":
        raise DigiLockerConfigurationError("Production KYC redirect must use trackmyrmc.com.")
    return DigiLockerSettings(api_key, api_secret, auth_base, init_base, read_base, redirect_url)


def _settings() -> tuple[str, str, str, str]:
    """Backward-compatible settings view for existing internal callers/tests."""
    config = provider_settings()
    if len({config.auth_base_url, config.init_base_url, config.read_base_url}) != 1:
        raise DigiLockerConfigurationError("Split provider hosts require provider_settings().")
    return config.api_key, config.api_secret, config.auth_base_url, config.redirect_url


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise DigiLockerProviderError("DigiLocker returned an invalid response.")
    return data


async def _authenticate(client: httpx.AsyncClient, api_key: str, api_secret: str, base_url: str) -> str:
    response = await client.post(
        f"{base_url}/authenticate",
        headers={
            "x-api-key": api_key,
            "x-api-secret": api_secret,
            "x-api-version": "1.0.0",
            "accept": "application/json",
        },
    )
    if response.is_error:
        raise _provider_error("authentication", str(response.request.url), response.status_code)
    token = _data(response.json()).get("access_token")
    if not isinstance(token, str) or not token:
        raise DigiLockerProviderError("DigiLocker did not return an access token.")
    return token


async def _headers(client: httpx.AsyncClient) -> tuple[dict[str, str], str, str, str]:
    config = provider_settings()
    token = await _authenticate(client, config.api_key, config.api_secret, config.auth_base_url)
    return {
        "authorization": token,
        "x-api-key": config.api_key,
        "x-api-version": "1.0.0",
        "content-type": "application/json",
        "accept": "application/json",
    }, config.init_base_url, config.read_base_url, config.redirect_url


async def initiate_digilocker_session() -> dict[str, str]:
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        headers, init_base_url, _, redirect_url = await _headers(client)
        response = await client.post(
            f"{init_base_url}/kyc/digilocker/sessions/init",
            headers=headers,
            json={
                "@entity": "in.co.sandbox.kyc.digilocker.session.request",
                "flow": "signin",
                "redirect_url": redirect_url,
                "doc_types": ["aadhaar"],
            },
        )
        if response.is_error:
            raise _provider_error("session initiation", str(response.request.url), response.status_code)
        payload = response.json()
        data = _data(payload)
        session_id = data.get("session_id")
        authorization_url = data.get("authorization_url")
        if not isinstance(session_id, str) or not session_id:
            raise DigiLockerProviderError("DigiLocker did not return a session ID.")
        if not isinstance(authorization_url, str) or not authorization_url.startswith("https://"):
            raise DigiLockerProviderError("DigiLocker did not return a safe authorization URL.")
        return {
            "session_id": session_id,
            "authorization_url": authorization_url,
            "transaction_id": str(payload.get("transaction_id") or ""),
        }


def normalize_verified_name(raw_name: Any) -> str:
    """Normalize a provider-supplied verified name.

    Trims leading/trailing whitespace, collapses internal runs of whitespace,
    preserves the customer's real verified spelling, and returns "" for any
    blank/missing/non-string value so callers can reject it safely.
    """
    if not isinstance(raw_name, str):
        return ""
    return " ".join(raw_name.split())


async def get_digilocker_user_profile(session_id: str) -> dict[str, str]:
    """Fetch the DigiLocker-verified identity for a consented session.

    Official Sandbox contract (non-SDK DigiLocker flow):
      GET {base_url}/kyc/digilocker/sessions/{session_id}/user/profile
      -> data.name holds the verified full name.

    This is only callable after the session status is SUCCEEDED and the user
    granted consent. The raw provider payload (name/DOB/mobile/etc.) is never
    logged. Returns only the normalized verified name.
    """
    if not session_id or "/" in session_id or ".." in session_id:
        raise DigiLockerProviderError("Invalid DigiLocker session ID.")
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        headers, _, read_base_url, _ = await _headers(client)
        response = await client.get(
            f"{read_base_url}/kyc/digilocker/sessions/{session_id}/user/profile",
            headers=headers,
        )
        if response.is_error:
            raise _provider_error("profile fetch", str(response.request.url), response.status_code)
        data = _data(response.json())
        # Verified full name lives at data.name per the Sandbox API reference.
        name = normalize_verified_name(data.get("name"))
        if not name:
            raise DigiLockerProviderError("DigiLocker profile did not include a verified name.")
        return {"name": name}


async def get_digilocker_session_status(session_id: str) -> dict[str, str]:
    if not session_id or "/" in session_id or ".." in session_id:
        raise DigiLockerProviderError("Invalid DigiLocker session ID.")
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        headers, _, read_base_url, _ = await _headers(client)
        response = await client.get(
            f"{read_base_url}/kyc/digilocker/sessions/{session_id}/status",
            headers=headers,
        )
        if response.is_error:
            raise _provider_error("status fetch", str(response.request.url), response.status_code)
        payload = response.json()
        data = _data(payload)
        raw = str(data.get("status") or "").lower()
        if raw in {"succeeded", "success", "completed"}:
            status = "SUCCEEDED"
        elif raw in {"failed", "failure", "cancelled", "canceled", "expired"}:
            status = "FAILED"
        else:
            status = "IN_PROGRESS"
        return {
            "status": status,
            "provider_status": raw or "unknown",
            "transaction_id": str(payload.get("transaction_id") or ""),
        }
