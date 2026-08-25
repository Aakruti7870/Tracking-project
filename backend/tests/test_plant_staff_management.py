"""RBAC regression coverage for Plant Staff Management."""
import pytest
from pydantic import ValidationError

from roles import Role
from routers.business_ui import (
    ADMIN_STAFF_ROLES,
    OWNER_STAFF_ROLES,
    CreatePlantStaffBody,
)


def test_owner_can_create_every_non_driver_plant_staff_role():
    assert OWNER_STAFF_ROLES == {
        Role.ADMIN.value,
        Role.DISPATCHER.value,
        Role.OPERATOR.value,
        Role.SUPERVISOR.value,
        Role.ACCOUNTANT.value,
        Role.QUALITY_ENGINEER.value,
        Role.FLEET_MANAGER.value,
        Role.STORE_MANAGER.value,
    }
    assert Role.DRIVER.value not in OWNER_STAFF_ROLES
    assert Role.PLANT_OWNER.value not in OWNER_STAFF_ROLES
    assert Role.AUTHORITY.value not in OWNER_STAFF_ROLES
    assert Role.CENTRAL_ADMIN.value not in OWNER_STAFF_ROLES


def test_admin_cannot_create_another_admin():
    assert Role.ADMIN.value not in ADMIN_STAFF_ROLES
    assert Role.OPERATOR.value in ADMIN_STAFF_ROLES
    assert Role.DISPATCHER.value in ADMIN_STAFF_ROLES


def test_staff_creation_requires_identity_fields():
    body = CreatePlantStaffBody(
        name="Plant Operator",
        email="operator@concreteking.example",
        role=Role.OPERATOR.value,
    )
    assert body.role == Role.OPERATOR.value

    with pytest.raises(ValidationError):
        CreatePlantStaffBody(name="", email="operator@example.com", role=Role.OPERATOR.value)
