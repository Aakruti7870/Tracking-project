"""Focused regression coverage for Plant Staff email OTP and onboarding."""

from pydantic import ValidationError
import pytest

from roles import Role
from routers.plant_onboarding import PlantOnboardingBody
from routers.staff_auth import STAFF_EMAIL_ROLES, _staff_role_allowed


def test_all_plant_and_platform_staff_can_use_staff_email_otp():
    expected = {
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.DISPATCHER.value,
        Role.OPERATOR.value,
        Role.SUPERVISOR.value,
        Role.ACCOUNTANT.value,
        Role.QUALITY_ENGINEER.value,
        Role.FLEET_MANAGER.value,
        Role.STORE_MANAGER.value,
        Role.AUTHORITY.value,
        Role.CENTRAL_ADMIN.value,
    }
    assert STAFF_EMAIL_ROLES == expected
    assert all(_staff_role_allowed(role) for role in expected)


def test_customer_and_driver_cannot_use_staff_email_otp():
    assert _staff_role_allowed(Role.CUSTOMER.value) is False
    assert _staff_role_allowed(Role.DRIVER.value) is False
    assert _staff_role_allowed(None) is False


def test_onboarding_requires_real_coordinates_and_identity_fields():
    request = PlantOnboardingBody(
        owner_name="Plant Owner",
        email="owner@example.com",
        mobile="+919876543210",
        plant_name="Example RMC",
        address="Panvel, Maharashtra",
        lat=18.9894,
        lng=73.1175,
    )
    assert request.plant_name == "Example RMC"
    assert request.google_place_id is None

    with pytest.raises(ValidationError):
        PlantOnboardingBody(
            owner_name="Plant Owner",
            email="owner@example.com",
            mobile="+919876543210",
            plant_name="Example RMC",
            address="Panvel, Maharashtra",
            lat=181,
            lng=73.1175,
        )
