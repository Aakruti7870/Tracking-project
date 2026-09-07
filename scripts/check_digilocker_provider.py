#!/usr/bin/env python3
"""Safe, read-only DigiLocker configuration/authentication diagnostic.

This probe deliberately does not initiate a consent session and never prints
credentials, tokens, response bodies, session identifiers, or personal data.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx

from services.digilocker import (  # noqa: E402
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    _authenticate,
    provider_settings,
)


async def main() -> int:
    try:
        config = provider_settings()
    except DigiLockerConfigurationError:
        print("CONFIGURED=no")
        print("AUTH_HOST=unavailable")
        print("INIT_HOST=unavailable")
        print("READ_HOST=unavailable")
        print("AUTH=FAIL")
        print("INIT_ENDPOINT=NOT_TESTED")
        print("CALLBACK_URL_VALID=FAIL")
        return 1

    print("CONFIGURED=yes")
    print(f"AUTH_HOST={urlparse(config.auth_base_url).hostname}")
    print(f"INIT_HOST={urlparse(config.init_base_url).hostname}")
    print(f"READ_HOST={urlparse(config.read_base_url).hostname}")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            await _authenticate(client, config.api_key, config.api_secret, config.auth_base_url)
    except (httpx.HTTPError, DigiLockerProviderError):
        print("AUTH=FAIL")
        result = 1
    else:
        print("AUTH=PASS")
        result = 0
    # A POST is the only documented initiation operation; probing it would
    # create a real consent session, so reachability remains intentionally idle.
    print("INIT_ENDPOINT=NOT_TESTED")
    print("CALLBACK_URL_VALID=PASS")
    return result


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
