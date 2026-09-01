"""Unit coverage for the customer DigiLocker auto-verify + verified-name sync.

These tests exercise routers.customer.get_kyc and _sync_customer_verified_name
with in-memory fake collections and mocked provider calls, so the state machine
and profile persistence are validated deterministically without a live provider.
"""
import asyncio

import pytest

import routers.customer as customer
from services.digilocker import DigiLockerProviderError


class _Result:
    def __init__(self, modified_count):
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, docs=None):
        self._docs = [dict(d) for d in (docs or [])]

    @staticmethod
    def _match(doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def find_one(self, query):
        for d in self._docs:
            if self._match(d, query):
                return dict(d)
        return None

    async def update_one(self, query, update, upsert=False):
        for d in self._docs:
            if self._match(d, query):
                for k, v in update.get("$set", {}).items():
                    d[k] = v
                for k in update.get("$unset", {}):
                    d.pop(k, None)
                return _Result(1)
        if upsert:
            new = dict(query)
            new.update(update.get("$setOnInsert", {}))
            new.update(update.get("$set", {}))
            self._docs.append(new)
            return _Result(1)
        return _Result(0)

    def doc(self, _id):
        for d in self._docs:
            if d.get("_id") == _id:
                return d
        return None


@pytest.fixture
def env(monkeypatch):
    kyc = FakeCollection([
        {
            "_id": "kyc1", "user_id": "user1", "purpose": "CUSTOMER",
            "status": "IN_PROGRESS", "provider": "DIGILOCKER",
            "provider_session_id": "sess-1",
        }
    ])
    users = FakeCollection([
        {"_id": "user1", "name": "Placeholder One"},
        {"_id": "user2", "name": "Other Customer"},
    ])
    monkeypatch.setattr(customer, "kyc_profiles", kyc)
    monkeypatch.setattr(customer, "users", users)

    async def _noop_audit(*a, **k):
        return None

    monkeypatch.setattr(customer, "write_audit", _noop_audit)
    return kyc, users


def _run(ctx):
    return asyncio.run(customer.get_kyc(ctx=ctx))


def test_provider_success_auto_verifies_and_persists_name(env, monkeypatch):
    kyc, users = env

    async def status(_sid):
        return {"status": "SUCCEEDED", "provider_status": "success", "transaction_id": "t1"}

    async def profile(_sid):
        return {"name": "Rajesh Kumar"}

    monkeypatch.setattr(customer, "get_digilocker_session_status", status)
    monkeypatch.setattr(customer, "get_digilocker_user_profile", profile)

    result = _run({"user_id": "user1"})

    assert result["status"] == "VERIFIED"
    assert users.doc("user1")["name"] == "Rajesh Kumar"
    assert kyc.doc("kyc1")["status"] == "VERIFIED"
    assert kyc.doc("kyc1")["kyc_name"] == "Rajesh Kumar"
    assert kyc.doc("kyc1")["name_sync_pending"] is False
    # Ownership: another user's profile is never touched.
    assert users.doc("user2")["name"] == "Other Customer"


def test_name_fetch_failure_keeps_verified_and_defers_sync(env, monkeypatch):
    kyc, users = env

    async def status(_sid):
        return {"status": "SUCCEEDED", "provider_status": "success", "transaction_id": "t1"}

    async def profile(_sid):
        raise DigiLockerProviderError("provider temporarily unavailable")

    monkeypatch.setattr(customer, "get_digilocker_session_status", status)
    monkeypatch.setattr(customer, "get_digilocker_user_profile", profile)

    result = _run({"user_id": "user1"})

    # Provider success is authoritative: VERIFIED holds, no fabricated name.
    assert result["status"] == "VERIFIED"
    assert users.doc("user1")["name"] == "Placeholder One"
    assert kyc.doc("kyc1")["name_sync_pending"] is True
    assert "kyc_name" not in kyc.doc("kyc1")


def test_verified_reconciliation_retries_name_without_reverifying(env, monkeypatch):
    kyc, users = env
    kyc.doc("kyc1")["status"] = "VERIFIED"
    kyc.doc("kyc1")["name_sync_pending"] = True

    async def status(_sid):
        raise AssertionError("session status must not be polled once VERIFIED")

    async def profile(_sid):
        return {"name": "Priya Sharma"}

    monkeypatch.setattr(customer, "get_digilocker_session_status", status)
    monkeypatch.setattr(customer, "get_digilocker_user_profile", profile)

    result = _run({"user_id": "user1"})

    assert result["status"] == "VERIFIED"
    assert users.doc("user1")["name"] == "Priya Sharma"
    assert kyc.doc("kyc1")["name_sync_pending"] is False


def test_provider_failure_requires_reverification_and_no_name_change(env, monkeypatch):
    kyc, users = env

    async def status(_sid):
        return {"status": "FAILED", "provider_status": "cancelled", "transaction_id": "t1"}

    async def profile(_sid):
        raise AssertionError("profile must not be fetched on a failed session")

    monkeypatch.setattr(customer, "get_digilocker_session_status", status)
    monkeypatch.setattr(customer, "get_digilocker_user_profile", profile)

    result = _run({"user_id": "user1"})

    assert result["status"] == "REQUIRES_REVERIFICATION"
    assert users.doc("user1")["name"] == "Placeholder One"


def test_provider_refresh_error_stays_in_progress(env, monkeypatch):
    kyc, users = env

    async def status(_sid):
        raise DigiLockerProviderError("upstream down")

    monkeypatch.setattr(customer, "get_digilocker_session_status", status)

    result = _run({"user_id": "user1"})

    assert result["status"] == "IN_PROGRESS"
    assert result.get("refresh_failed") is True
    assert kyc.doc("kyc1")["status"] == "IN_PROGRESS"
