"""Security regression tests for Authority-controlled Plant Owner provisioning."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from roles import Role
from routers import plant_discovery


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


class _Users:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.inserted = None
        self.updated = None

    def find(self, _query):
        return _Cursor(self.rows)

    async def insert_one(self, doc):
        self.inserted = doc
        return SimpleNamespace(inserted_id="owner-new")

    async def update_one(self, query, update):
        self.updated = (query, update)


def test_authority_can_provision_new_owner_with_normalized_email(monkeypatch):
    fake = _Users()
    monkeypatch.setattr(plant_discovery, "users", fake)

    result = asyncio.run(
        plant_discovery._provision_plant_owner(
            plant_discovery.OwnerAssignmentBody(
                name="Concrete King Owner",
                email="OWNER@TrackMyRMC.com",
            )
        )
    )

    assert result == {"id": "owner-new", "created": True}
    assert fake.inserted["email"] == "owner@trackmyrmc.com"
    assert fake.inserted["primary_role"] == Role.PLANT_OWNER.value
    assert fake.inserted["roles"] == [Role.PLANT_OWNER.value]
    assert len(fake.inserted["identifier_keys"]) == 1


def test_owner_assignment_requires_email_or_mobile(monkeypatch):
    monkeypatch.setattr(plant_discovery, "users", _Users())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            plant_discovery._provision_plant_owner(
                plant_discovery.OwnerAssignmentBody(name="Owner Name")
            )
        )

    assert exc.value.status_code == 422


def test_existing_non_owner_account_is_not_silently_promoted(monkeypatch):
    fake = _Users([
        {
            "_id": "customer-1",
            "name": "Existing Customer",
            "primary_role": Role.CUSTOMER.value,
            "identifier_keys": ["existing"],
        }
    ])
    monkeypatch.setattr(plant_discovery, "users", fake)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            plant_discovery._provision_plant_owner(
                plant_discovery.OwnerAssignmentBody(
                    name="Attempted Owner",
                    email="existing@example.com",
                )
            )
        )

    assert exc.value.status_code == 409
    assert fake.inserted is None
    assert fake.updated is None


def test_existing_owner_can_be_reused_idempotently(monkeypatch):
    fake = _Users([
        {
            "_id": "owner-1",
            "name": "Existing Owner",
            "email": "owner@example.com",
            "primary_role": Role.PLANT_OWNER.value,
            "identifier_keys": ["existing"],
        }
    ])
    monkeypatch.setattr(plant_discovery, "users", fake)

    result = asyncio.run(
        plant_discovery._provision_plant_owner(
            plant_discovery.OwnerAssignmentBody(
                name="Updated Owner",
                email="owner@example.com",
            )
        )
    )

    assert result == {"id": "owner-1", "created": False}
    assert fake.updated is not None
