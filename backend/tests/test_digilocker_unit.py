import pytest

from services.digilocker import (
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    _settings,
    get_digilocker_session_status,
)


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


@pytest.mark.asyncio
async def test_digilocker_rejects_unsafe_session_id():
    with pytest.raises(DigiLockerProviderError):
        await get_digilocker_session_status("../credentials")


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
