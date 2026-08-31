"""Sandbox DigiLocker client.

All credentials stay in runtime secrets. This module never logs credentials,
authorization URLs, Aadhaar data, or document contents.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class DigiLockerConfigurationError(RuntimeError):
    pass


class DigiLockerProviderError(RuntimeError):
    pass


def _settings() -> tuple[str, str, str, str]:
    api_key = os.getenv("KYC_API_KEY", "").strip()
    api_secret = os.getenv("KYC_API_SECRET", "").strip()
    base_url = os.getenv("KYC_BASE_URL", "https://test-api.sandbox.co.in").strip().rstrip("/")
    redirect_url = os.getenv("KYC_REDIRECT_URL", "").strip()
    if not api_key or not api_secret or not redirect_url:
        raise DigiLockerConfigurationError(
            "DigiLocker is not configured. KYC_API_KEY, KYC_API_SECRET and "
            "KYC_REDIRECT_URL are required."
        )
    if not base_url.startswith("https://") or not redirect_url.startswith("https://"):
        raise DigiLockerConfigurationError("DigiLocker URLs must use HTTPS.")
    return api_key, api_secret, base_url, redirect_url


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
        raise DigiLockerProviderError(f"DigiLocker authentication failed ({response.status_code}).")
    token = _data(response.json()).get("access_token")
    if not isinstance(token, str) or not token:
        raise DigiLockerProviderError("DigiLocker did not return an access token.")
    return token


async def _headers(client: httpx.AsyncClient) -> tuple[dict[str, str], str, str]:
    api_key, api_secret, base_url, redirect_url = _settings()
    token = await _authenticate(client, api_key, api_secret, base_url)
    return {
        "authorization": token,
        "x-api-key": api_key,
        "x-api-version": "1.0.0",
        "content-type": "application/json",
        "accept": "application/json",
    }, base_url, redirect_url


async def initiate_digilocker_session() -> dict[str, str]:
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        headers, base_url, redirect_url = await _headers(client)
        response = await client.post(
            f"{base_url}/kyc/digilocker/sessions/init",
            headers=headers,
            json={
                "@entity": "in.co.sandbox.kyc.digilocker.session.request",
                "flow": "signin",
                "redirect_url": redirect_url,
                "doc_types": ["aadhaar"],
            },
        )
        if response.is_error:
            raise DigiLockerProviderError(f"Could not start DigiLocker ({response.status_code}).")
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
        headers, base_url, _ = await _headers(client)
        response = await client.get(
            f"{base_url}/kyc/digilocker/sessions/{session_id}/user/profile",
            headers=headers,
        )
        if response.is_error:
            raise DigiLockerProviderError(
                f"Could not read DigiLocker profile ({response.status_code})."
            )
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
        headers, base_url, _ = await _headers(client)
        response = await client.get(
            f"{base_url}/kyc/digilocker/sessions/{session_id}/status",
            headers=headers,
        )
        if response.is_error:
            raise DigiLockerProviderError(f"Could not read DigiLocker status ({response.status_code}).")
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
