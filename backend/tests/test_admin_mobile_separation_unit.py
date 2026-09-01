"""Static security boundary regressions for public mobile and admin portal."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_privileged_expo_routes_are_absent():
    app = ROOT / "frontend" / "app"
    assert not (app / "authority").exists()
    assert not (app / "central_admin").exists()
    assert not (app / "account-deletion-admin.tsx").exists()


def test_mobile_role_router_has_no_platform_destination():
    source = (ROOT / "frontend" / "src" / "auth" / "roleRoutes.ts").read_text()
    assert "authority:" not in source
    assert "central_admin:" not in source
    assert "super_admin:" not in source


def test_mobile_reviewer_access_has_no_authority():
    screen = (ROOT / "frontend" / "app" / "review-access.tsx").read_text()
    assert 'role: "authority"' not in screen


def test_dedicated_portal_does_not_persist_tokens():
    portal = (ROOT / "admin-web" / "src" / "main.tsx").read_text()
    assert "localStorage" not in portal
    assert "sessionStorage" not in portal
