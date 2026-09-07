"""Regression coverage for Central Admin web-only route isolation."""

import security
from roles import Role
from routers import staff_auth


def test_central_admin_control_center_allowlist_is_fail_closed():
    for path in (
        "/api/admin/auth/step-up",
        "/api/admin/portal/summary",
        "/api/control-center/capabilities",
        "/api/control-center/sessions/session-1/revoke",
        "/api/me",
        "/api/auth/logout",
    ):
        assert security._central_admin_path_allowed(path), path

    for path in (
        "/api/staff/users",
        "/api/plant-discovery/requests",
        "/api/assistant/support/staff/cases",
        "/api/auth/staff/mfa/reset-user",
        "/api/plant-plans/admin/activations",
        "/api/maps/authority/search",
        "/api/storage/pod/file",
    ):
        assert not security._central_admin_path_allowed(path), path


def test_authority_remains_in_real_plant_staff_email_auth_boundary():
    assert Role.AUTHORITY.value in staff_auth.STAFF_EMAIL_ROLES
    assert Role.PLANT_OWNER.value in staff_auth.STAFF_EMAIL_ROLES
    assert Role.CENTRAL_ADMIN.value not in staff_auth.STAFF_EMAIL_ROLES
