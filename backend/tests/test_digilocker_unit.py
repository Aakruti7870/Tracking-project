import asyncio
import pytest
import httpx

from services.digilocker import (
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    _settings,
    provider_settings,
    get_digilocker_session_status,
    get_digilocker_user_profile,
    normalize_verified_name,
    _provider_error,
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
    monkeypatch.delenv("KYC_BASE_URL", raising=False)
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


def test_digilocker_rejects_base_url_with_path(monkeypatch):
    monkeypatch.setenv("KYC_API_KEY", "key")
    monkeypatch.setenv("KYC_API_SECRET", "secret")
    monkeypatch.setenv("KYC_BASE_URL", "https://test-api.sandbox.co.in/kyc")
    monkeypatch.setenv("KYC_REDIRECT_URL", "https://trackmyrmc.com/kyc/return")
    with pytest.raises(DigiLockerConfigurationError):
        _settings()


def test_split_provider_hosts_are_explicit(monkeypatch):
    monkeypatch.setenv("KYC_API_KEY", "key")
    monkeypatch.setenv("KYC_API_SECRET", "secret")
    monkeypatch.delenv("KYC_BASE_URL", raising=False)
    monkeypatch.setenv("KYC_AUTH_BASE_URL", "https://test-api.sandbox.co.in")
    monkeypatch.setenv("KYC_INIT_BASE_URL", "https://test-api.sandbox.co.in")
    monkeypatch.setenv("KYC_READ_BASE_URL", "https://api.sandbox.co.in")
    monkeypatch.setenv("KYC_REDIRECT_URL", "https://trackmyrmc.com/kyc/return")

    config = provider_settings()
    assert config.auth_base_url == "https://test-api.sandbox.co.in"
    assert config.init_base_url == "https://test-api.sandbox.co.in"
    assert config.read_base_url == "https://api.sandbox.co.in"


def test_production_rejects_preview_callback(monkeypatch):
    monkeypatch.setenv("KYC_API_KEY", "key")
    monkeypatch.setenv("KYC_API_SECRET", "secret")
    monkeypatch.setenv("KYC_BASE_URL", "https://api.sandbox.co.in")
    monkeypatch.setenv("KYC_REDIRECT_URL", "https://preview.invalid/kyc/return")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(DigiLockerConfigurationError):
        provider_settings()


def test_provider_404_diagnostic_redacts_session_and_secrets(caplog):
    error = _provider_error(
        "status fetch",
        "https://test-api.sandbox.co.in/kyc/digilocker/sessions/private-session/status?token=secret",
        404,
    )
    assert error.status_code == 404
    assert str(error) == "DigiLocker status fetch failed (404)."
    output = caplog.text
    assert "host=test-api.sandbox.co.in" in output
    assert "path=/kyc/digilocker/sessions/[redacted]/status" in output
    assert "private-session" not in output
    assert "token" not in output
    assert "secret" not in output


class _ProviderClient:
    responses = []

    def __init__(self, *args, **kwargs):
        self.queue = list(self.responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def _response(self, method, url, **kwargs):
        status, payload = self.queue.pop(0)
        return httpx.Response(status, json=payload, request=httpx.Request(method, url))

    async def post(self, url, **kwargs):
        return await self._response("POST", url, **kwargs)

    async def get(self, url, **kwargs):
        return await self._response("GET", url, **kwargs)


def _provider_env(monkeypatch):
    monkeypatch.setenv("KYC_API_KEY", "key")
    monkeypatch.setenv("KYC_API_SECRET", "secret")
    monkeypatch.setenv("KYC_BASE_URL", "https://test-api.sandbox.co.in")
    for name in ("KYC_AUTH_BASE_URL", "KYC_INIT_BASE_URL", "KYC_READ_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KYC_REDIRECT_URL", "https://trackmyrmc.com/kyc/return")
    monkeypatch.setattr("services.digilocker.httpx.AsyncClient", _ProviderClient)


def test_authentication_404(monkeypatch):
    from services.digilocker import initiate_digilocker_session
    _provider_env(monkeypatch)
    _ProviderClient.responses = [(404, {"error": "not found"})]
    with pytest.raises(DigiLockerProviderError, match="authentication") as caught:
        asyncio.run(initiate_digilocker_session())
    assert caught.value.status_code == 404


def test_initiation_404(monkeypatch):
    from services.digilocker import initiate_digilocker_session
    _provider_env(monkeypatch)
    _ProviderClient.responses = [
        (200, {"data": {"access_token": "private-token"}}),
        (404, {"error": "not found"}),
    ]
    with pytest.raises(DigiLockerProviderError, match="session initiation") as caught:
        asyncio.run(initiate_digilocker_session())
    assert caught.value.status_code == 404


def test_initiation_success(monkeypatch):
    from services.digilocker import initiate_digilocker_session
    _provider_env(monkeypatch)
    _ProviderClient.responses = [
        (200, {"data": {"access_token": "private-token"}}),
        (200, {"data": {"session_id": "session", "authorization_url": "https://example.invalid/consent"}}),
    ]
    assert asyncio.run(initiate_digilocker_session())["session_id"] == "session"


@pytest.mark.parametrize("operation,call", [
    ("status fetch", lambda: get_digilocker_session_status("session")),
    ("profile fetch", lambda: get_digilocker_user_profile("session")),
])
def test_status_404_and_profile_404(monkeypatch, operation, call):
    _provider_env(monkeypatch)
    _ProviderClient.responses = [
        (200, {"data": {"access_token": "private-token"}}),
        (404, {"error": "not found"}),
    ]
    with pytest.raises(DigiLockerProviderError, match=operation) as caught:
        asyncio.run(call())
    assert caught.value.status_code == 404
