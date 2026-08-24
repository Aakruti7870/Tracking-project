import pytest

from roles import Role
from seed import _preview_accounts


def test_preview_authority_email_is_seeded_from_environment(monkeypatch):
    monkeypatch.setenv("PREVIEW_AUTHORITY_EMAIL", "Authority.Example@TrackMyRMC.com")
    monkeypatch.setenv("PREVIEW_AUTHORITY_NAME", "KYC Authority")
    matches = [
        account
        for account in _preview_accounts()
        if account.get("email") == "authority.example@trackmyrmc.com"
    ]
    assert matches == [{
        "name": "KYC Authority",
        "email": "authority.example@trackmyrmc.com",
        "role": Role.AUTHORITY.value,
    }]


def test_preview_authority_email_is_optional(monkeypatch):
    monkeypatch.delenv("PREVIEW_AUTHORITY_EMAIL", raising=False)
    assert not any(
        account.get("name") == "Preview Authority"
        for account in _preview_accounts()
    )


def test_preview_authority_email_fails_closed_when_invalid(monkeypatch):
    monkeypatch.setenv("PREVIEW_AUTHORITY_EMAIL", "not-an-email")
    with pytest.raises(RuntimeError, match="valid email"):
        _preview_accounts()
