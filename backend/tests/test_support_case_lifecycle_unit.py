import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from routers import assistant
from models import CreateOrderBody


class Cursor:
    def __init__(self, rows): self.rows = rows
    def sort(self, *_): return self
    async def to_list(self, _): return self.rows


class Cases:
    def __init__(self, rows): self.rows = rows
    def find(self, query):
        return Cursor([r for r in self.rows if all(r.get(k) == v for k, v in query.items())])
    async def find_one(self, query):
        return next((r for r in self.rows if all(r.get(k) == v for k, v in query.items())), None)
    async def update_one(self, query, update):
        row = await self.find_one({k: v for k, v in query.items() if not isinstance(v, dict)})
        if not row or row.get("status") not in query.get("status", {}).get("$in", [row.get("status")]):
            return SimpleNamespace(modified_count=0, matched_count=0)
        row.update(update.get("$set", {})); row.setdefault("messages", []).append(update.get("$push", {}).get("messages")) if update.get("$push") else None
        return SimpleNamespace(modified_count=1, matched_count=1)
    async def insert_one(self, document):
        document["_id"] = f"case-{len(self.rows) + 1}"
        self.rows.append(document)
        return SimpleNamespace(inserted_id=document["_id"])


def row(owner="customer-1"):
    return {"_id": "case-1", "case_number": "SUP-1", "customer_id": owner,
            "category": "GENERAL", "status": "OPEN", "created_at": datetime.now(timezone.utc),
            "messages": [{"message": "Visible reply", "internal": False},
                         {"message": "Private staff note", "internal": True}]}


def test_customer_lists_only_owned_cases_and_private_notes_are_removed(monkeypatch):
    monkeypatch.setattr(assistant, "support_cases", Cases([row(), row("customer-2")]))
    result = asyncio.run(assistant.list_my_cases({"user_id": "customer-1"}))
    assert len(result["cases"]) == 1
    assert [m["message"] for m in result["cases"][0]["messages"]] == ["Visible reply"]
    assert "Private staff note" not in repr(result)


def test_legacy_case_message_is_preserved_in_public_projection():
    created = datetime.now(timezone.utc)
    legacy = {"_id": "legacy-1", "case_number": "SUP-LEGACY", "customer_id": "customer-1",
              "category": "LOGIN", "status": "OPEN", "created_at": created,
              "message": "Legacy login issue"}
    public = assistant._public_case(legacy)
    staff = assistant._public_case(legacy, staff=True)
    for projected in (public, staff):
        assert projected["latest_note"] == "Legacy login issue"
        assert projected["messages"] == [{"message": "Legacy login issue", "author": "CUSTOMER",
                                            "internal": False, "created_at": created}]


def test_customer_cannot_view_another_customers_case(monkeypatch):
    monkeypatch.setattr(assistant, "support_cases", Cases([row("customer-2")]))
    with pytest.raises(assistant.HTTPException) as denied:
        asyncio.run(assistant.get_my_case("case-1", {"user_id": "customer-1"}))
    assert denied.value.status_code == 404


def test_customer_cannot_add_internal_note(monkeypatch):
    monkeypatch.setattr(assistant, "support_cases", Cases([row()]))
    with pytest.raises(assistant.HTTPException) as denied:
        asyncio.run(assistant.reply_to_my_case("case-1", assistant.CaseReplyBody(message="x", internal=True), {"user_id": "customer-1"}))
    assert denied.value.status_code == 403


def test_escalation_is_idempotent_and_audited_once(monkeypatch):
    cases = Cases([]); audits = []
    async def audit(*args): audits.append(args)
    monkeypatch.setattr(assistant, "support_cases", cases)
    monkeypatch.setattr(assistant, "write_audit", audit)
    body = assistant.SupportBody(category="GENERAL", message="App navigation issue",
                                 escalate=True, request_id="request-123456")
    first = asyncio.run(assistant.support(body, {"user_id": "customer-1"}))
    second = asyncio.run(assistant.support(body, {"user_id": "customer-1"}))
    assert first["case_id"] == second["case_id"]
    assert len(cases.rows) == 1
    assert len(audits) == 1


def test_support_messages_reject_embedded_credentials_and_separator_bypasses():
    unsafe_messages = [
        "my otp is 123456", "OTP 123456", "otp equals 123456", "OTP code 12 34 56",
        "password = example-value", "password equals hunter2", "password hunter2",
        "passkey: example-value", "PIN: 1234", "PIN 1234", "CVV = 123", "CVV 123",
        "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature",
        "authorization token: example-token-value", "authorization_token example-token-value",
        "api key: example-key-value", "api_key example-key-value",
        "access token = example-access-value", "access_token=example-access-value",
        "refresh token: example-refresh-value", "refresh_token equals example-refresh-value",
        "secret key: example-secret-value", "secret_key example-secret-value",
        "recovery code 1234-5678", "recovery_code equals ABCD EFGH",
        "-----BEGIN " + "PRIVATE KEY-----", "card number 4111 1111 1111 1111",
    ]
    for message in unsafe_messages:
        with pytest.raises(ValueError, match=assistant.SAFE_SECRET_MESSAGE):
            assistant.SupportBody(category="LOGIN", message=message)
        with pytest.raises(ValueError, match=assistant.SAFE_SECRET_MESSAGE):
            assistant.CaseReplyBody(message=message)

    safe_messages = [
        "My password reset screen is blank.",
        "The OTP verification screen is blank.",
        "The access token page will not load.",
        "I forgot my password and need login help.",
    ]
    for message in safe_messages:
        safe = assistant.SupportBody(category="LOGIN", message=message)
        assert safe.message == message


def test_customer_reply_is_limited_to_owned_open_case(monkeypatch):
    cases = Cases([row()])
    monkeypatch.setattr(assistant, "support_cases", cases)
    received = asyncio.run(assistant.reply_to_my_case(
        "case-1", assistant.CaseReplyBody(message="The issue continues"), {"user_id": "customer-1"}))
    assert received == {"status": "RECEIVED"}
    assert cases.rows[0]["messages"][-1]["author"] == "CUSTOMER"

    cases.rows[0]["status"] = "CLOSED"
    with pytest.raises(assistant.HTTPException) as closed:
        asyncio.run(assistant.reply_to_my_case(
            "case-1", assistant.CaseReplyBody(message="Another update"), {"user_id": "customer-1"}))
    assert closed.value.status_code == 409


def test_staff_role_guard_allows_only_authority_and_central_admin():
    for role in ("authority", "central_admin"):
        assert asyncio.run(assistant.support_staff({"role": role})) == {"role": role}
    for role in ("customer", "driver", "admin", "plant_owner"):
        with pytest.raises(assistant.HTTPException) as denied:
            asyncio.run(assistant.support_staff({"role": role}))
        assert denied.value.status_code == 403


def test_staff_public_reply_internal_note_and_status_are_audited(monkeypatch):
    cases = Cases([row()]); audits = []
    async def audit(*args): audits.append(args)
    monkeypatch.setattr(assistant, "support_cases", cases)
    monkeypatch.setattr(assistant, "write_audit", audit)
    ctx = {"user_id": "authority-1"}
    asyncio.run(assistant.reply_to_support_case("case-1", assistant.CaseReplyBody(message="Public response"), ctx))
    asyncio.run(assistant.reply_to_support_case("case-1", assistant.CaseReplyBody(message="Internal context", internal=True), ctx))
    result = asyncio.run(assistant.set_support_case_status("case-1", assistant.CaseStatusBody(status="IN_PROGRESS"), ctx))
    assert result == {"status": "IN_PROGRESS"}
    assert [item["internal"] for item in cases.rows[0]["messages"][-2:]] == [False, True]
    assert len(audits) == 3


class SingleCollection:
    def __init__(self, value=None): self.value = value
    async def find_one(self, query):
        if self.value and all(self.value.get(key) == value for key, value in query.items()): return self.value
        return None
    async def update_one(self, query, update, upsert=False):
        if upsert and self.value is None: self.value = {**query, **update.get("$setOnInsert", {}), "_id": "intent-1"}
        elif self.value: self.value.update(update.get("$set", {}))
        return SimpleNamespace(modified_count=1, matched_count=1)


def sample_order(idempotency_key="assistant-order-123"):
    return CreateOrderBody(idempotency_key=idempotency_key, plant_id="plant-1", grade="M25",
                           quantity=6, site_name="Site", site_address="Address",
                           delivery_date="2026-09-05", delivery_time="10:00")


def test_prepare_requires_verified_kyc_and_idempotency(monkeypatch):
    monkeypatch.setattr(assistant, "kyc_profiles", SingleCollection({"user_id": "customer-1", "purpose": "CUSTOMER", "status": "PENDING"}))
    monkeypatch.setattr(assistant, "orders", SingleCollection())
    with pytest.raises(assistant.HTTPException) as denied:
        asyncio.run(assistant.prepare_order(assistant.PrepareOrderBody(order=sample_order()), {"user_id": "customer-1"}))
    assert denied.value.status_code == 403

    monkeypatch.setattr(assistant, "kyc_profiles", SingleCollection({"user_id": "customer-1", "purpose": "CUSTOMER", "status": "VERIFIED"}))
    with pytest.raises(assistant.HTTPException) as missing:
        asyncio.run(assistant.prepare_order(assistant.PrepareOrderBody(order=sample_order(None)), {"user_id": "customer-1"}))
    assert missing.value.status_code == 422


def test_confirm_requires_explicit_confirmation_and_replay_is_idempotent(monkeypatch):
    intent = {"_id": "intent-1", "token": "x" * 32, "customer_id": "customer-1",
              "order": sample_order().model_dump(), "state": "AWAITING_CONFIRMATION"}
    monkeypatch.setattr(assistant, "order_intents", SingleCollection(intent))
    created = {}
    async def create(body, ctx):
        key = body.idempotency_key
        created.setdefault(key, {"id": "order-1", "order_number": "RMC-1"})
        return created[key]
    monkeypatch.setattr(assistant, "create_order", create)
    with pytest.raises(assistant.HTTPException) as refused:
        asyncio.run(assistant.confirm_order(assistant.ConfirmOrderBody(intent_token="x" * 32, confirmed=False), {"user_id": "customer-1"}))
    assert refused.value.status_code == 409
    body = assistant.ConfirmOrderBody(intent_token="x" * 32, confirmed=True)
    first = asyncio.run(assistant.confirm_order(body, {"user_id": "customer-1"}))
    replay = asyncio.run(assistant.confirm_order(body, {"user_id": "customer-1"}))
    assert first == replay
    assert len(created) == 1
