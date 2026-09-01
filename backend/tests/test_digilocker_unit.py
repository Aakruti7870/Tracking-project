import asyncio
import pytest

from services.digilocker import (
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    _settings,
    get_digilocker_session_status,
    get_digilocker_user_profile,
    normalize_verified_name,
)


def test_normalize_verified_name_trims_and_collapses_whitespace():
    assert normalize_verified_name("  Rajesh   Kumar  ") == "Rajesh Kumar"
    assert normalize_verified_name("\tPriya\nSharma ") == "Priya Sharma"


def test_normalize_verified_name_preserves_real_spelling():
    # Real verified spelling (incl. non-ASCII) must not be altered.
    assert normalize_verified_name("D'Souza Anné") == "D'Souza Anné"
    assert normalize_verified_name("Kaival Mehta") == "Kaival Mehta"


def test_normalize_verified_name_rejects_blank_or_missing():
    for value in ("", "   ", None, 123, {"name": "x"}, ["Rajesh"]):
        assert normalize_verified_name(value) == ""


def test_get_user_profile_rejects_unsafe_session_id():
    # Path-traversal / injection attempts must never reach the provider.
    with pytest.raises(DigiLockerProviderError):
        asyncio.run(get_digilocker_user_profile("../../secrets"))
    with pytest.raises(DigiLockerProviderError):
        asyncio.run(get_digilocker_user_profile(""))


def test_digilocker_requires_runtime_secrets(monkeypatch):
    monkeypatch.delenv("KYC_API_KEY", raising=False)
    monkeypatch.delenv("KYC_API_SECRET", raising=False)
    monkeypatch.delenv("KYC_REDIRECT_URL", raising=False)
    with pytest.raises(DigiLockerConfigurationError):
        _settings()


def test_digilocker_rejects_non_https_urls(monkeypatch):
    monkeypatch.setenv("KYC_API_KEY", "key")
    monkeypatch.setenv("KYC_API_SECRET", "secret")
    monkeypatch.setenv("KYC_BASE_URL", "http://provider.invalid")
    monkeypatch.setenv("KYC_REDIRECT_URL", "https://trackmyrmc.com/kyc/return")
    with pytest.raises(DigiLockerConfigurationError):
        _settings()


def test_digilocker_rejects_unsafe_session_id():
    with pytest.raises(DigiLockerProviderError):
        asyncio.run(get_digilocker_session_status("../credentials"))


def test_digilocker_accepts_https_configuration(monkeypatch):
    monkeypatch.setenv("KYC_API_KEY", "key")
    monkeypatch.setenv("KYC_API_SECRET", "secret")
    monkeypatch.setenv("KYC_BASE_URL", "https://test-api.sandbox.co.in/")
    monkeypatch.setenv("KYC_REDIRECT_URL", "https://trackmyrmc.com/kyc/return")
    api_key, api_secret, base_url, redirect_url = _settings()
    assert api_key == "key"
    assert api_secret == "secret"
    assert base_url == "https://test-api.sandbox.co.in"
    assert redirect_url == "https://trackmyrmc.com/kyc/return"
