"""Regression coverage for permanent Play review credentials and support platform-admin identities."""

from roles import Role
from routers.permanent_access import (
    DEMO_CUSTOMER_PHONE,
    DEMO_DRIVER_PHONE,
    DEMO_OTP,
    DEMO_OWNER_EMAIL,
    PERMANENT_AUTHORITY_EMAILS,
    PERMANENT_CENTRAL_ADMIN_EMAILS,
    demo_mobile_role,
    demo_staff_role,
    permanent_platform_role,
)


def test_permanent_demo_otp_is_the_play_console_code():
    assert DEMO_OTP == "123456"


def test_customer_demo_number_routes_only_to_customer():
    assert DEMO_CUSTOMER_PHONE == "+919000009901"
    assert demo_mobile_role(DEMO_CUSTOMER_PHONE) == Role.CUSTOMER.value
    assert demo_mobile_role("9000009901") == Role.CUSTOMER.value


def test_driver_demo_number_routes_only_to_driver():
    assert DEMO_DRIVER_PHONE == "+919000009902"
    assert demo_mobile_role(DEMO_DRIVER_PHONE) == Role.DRIVER.value
    assert demo_mobile_role("9000009902") == Role.DRIVER.value


def test_owner_demo_email_is_the_only_staff_demo_allowlist_entry():
    assert demo_staff_role(DEMO_OWNER_EMAIL) == Role.PLANT_OWNER.value
    assert demo_staff_role("play-review-authority@trackmyrmc.test") is None
    assert demo_staff_role("someone@trackmyrmc.test") is None


def test_support_platform_admins_never_inherit_demo_otp_allowlist():
    assert PERMANENT_AUTHORITY_EMAILS == ("support@goldetech.com",)
    assert PERMANENT_CENTRAL_ADMIN_EMAILS == ("support@trackmyrmc.com",)
    for email in (*PERMANENT_AUTHORITY_EMAILS, *PERMANENT_CENTRAL_ADMIN_EMAILS):
        assert demo_staff_role(email) is None


def test_trackmyrmc_support_is_full_central_admin():
    assert permanent_platform_role("support@trackmyrmc.com") == Role.CENTRAL_ADMIN.value
    assert permanent_platform_role(" SUPPORT@TRACKMYRMC.COM ") == Role.CENTRAL_ADMIN.value
    assert permanent_platform_role("support@goldetech.com") == Role.AUTHORITY.value
    assert permanent_platform_role("unknown@trackmyrmc.com") is None
