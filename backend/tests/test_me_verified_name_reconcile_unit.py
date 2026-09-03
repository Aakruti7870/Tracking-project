"""Regression coverage for verified DigiLocker customer names on /api/me."""
import asyncio

import routers.customer as customer
import routers.me as me_routes


class FakeCollection:
    def __init__(self, docs=None):
        self._docs = [dict(d) for d in (docs or [])]

    async def find_one(self, query):
        for doc in self._docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return dict(doc)
        return None


def test_verified_customer_missing_kyc_name_is_reconciled_on_profile_load(monkeypatch):
    kyc = FakeCollection([
        {
            "_id": "kyc1",
            "user_id": "user1",
            "purpose": "CUSTOMER",
            "status": "VERIFIED",
            "provider": "DIGILOCKER",
            "provider_session_id": "sess-1",
        }
    ])
    refreshed_user = {
        "_id": "user1",
        "name": "Rajesh Kumar",
        "phone": "+919000000001",
        "roles": ["customer"],
        "primary_role": "customer",
        "status": "active",
    }
    users = FakeCollection([refreshed_user])
    monkeypatch.setattr(me_routes, "kyc_profiles", kyc)
    monkeypatch.setattr(me_routes, "users", users)

    calls = []

    async def sync_name(uid, kyc_doc):
        calls.append((uid, kyc_doc["_id"]))
        return True

    monkeypatch.setattr(customer, "_sync_customer_verified_name", sync_name)

    original_user = dict(refreshed_user)
    original_user["name"] = "Customer"
    result = asyncio.run(me_routes.me(ctx={
        "user_id": "user1",
        "user": original_user,
        "role": "customer",
        "roles": ["customer"],
        "plant_id": None,
    }))

    assert calls == [("user1", "kyc1")]
    assert result["kyc_status"] == "VERIFIED"
    assert result["name"] == "Rajesh Kumar"
