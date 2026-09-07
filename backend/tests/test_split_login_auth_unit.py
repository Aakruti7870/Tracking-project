"""Regression coverage for the User / Plant User authentication split."""

import pytest
from fastapi import HTTPException

from roles import GOOGLE_LOGIN_ROLES, MOBILE_OTP_ROLES, ROLE_LOGIN_CHANNELS, Role
from routers.auth import _assert_account_available, _login_identifier_keys
from security import identifier_key


def test_only_customer_and_driver_can_use_mobile_otp():
    assert MOBILE_OTP_ROLES == {Role.CUSTOMER.value, Role.DRIVER.value}
    assert ROLE_LOGIN_CHANNELS == {
        Role.CUSTOMER.value: {"sms"},
        Role.DRIVER.value: {"sms"},
    }


def test_plant_staff_google_roles_exclude_privileged_platform_admins():
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
    }
    assert GOOGLE_LOGIN_ROLES == expected
    assert Role.AUTHORITY.value not in GOOGLE_LOGIN_ROLES
    assert Role.CENTRAL_ADMIN.value not in GOOGLE_LOGIN_ROLES
    assert not (GOOGLE_LOGIN_ROLES & MOBILE_OTP_ROLES)


def test_plus_91_mobile_lookup_preserves_legacy_identifiers():
    keys = _login_identifier_keys("sms", "+919876543210")
    assert identifier_key("+919876543210") in keys
    assert identifier_key("919876543210") in keys
    assert identifier_key("9876543210") in keys
    assert len(keys) == 3


def test_email_lookup_does_not_generate_phone_aliases():
    email = "owner@example.com"
    assert _login_identifier_keys("email", email) == [identifier_key(email)]


def test_plant_scoped_staff_still_fail_closed_without_plant():
    with pytest.raises(HTTPException) as exc:
        _assert_account_available(
            {
                "status": "active",
                "primary_role": Role.DISPATCHER.value,
                "plant_id": None,
            }
        )
    assert exc.value.status_code == 403
    assert "Plant assignment" in str(exc.value.detail)


def test_plant_owner_does_not_require_user_plant_id_field():
    # Owner tenancy is resolved through plants.owner_id, not users.plant_id.
    _assert_account_available(
        {
            "status": "active",
            "primary_role": Role.PLANT_OWNER.value,
            "plant_id": None,
        }
    )
