"""Focused unit coverage for the privileged admin security boundary."""
from datetime import datetime, timedelta, timezone
import inspect

import pytest
from pydantic import ValidationError

from routers import account_deletion, admin_auth


def test_admin_login_schema_rejects_undeclared_fields():
    with pytest.raises(ValidationError):
        admin_auth.AdminLoginBody(
            identifier="admin@example.com",
            code="123456",
            requested_role="central_admin",
        )


def test_admin_step_up_window_fails_closed_when_missing_or_expired():
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    assert admin_auth._has_recent_admin_step_up({}, now=now) is False
    assert admin_auth._has_recent_admin_step_up(
        {
            "admin_step_up_at": now - timedelta(minutes=10),
            "admin_step_up_expires_at": now - timedelta(seconds=1),
        },
        now=now,
    ) is False
    assert admin_auth._has_recent_admin_step_up(
        {
            "admin_step_up_at": now - timedelta(minutes=1),
            "admin_step_up_expires_at": now + timedelta(minutes=4),
        },
        now=now,
    ) is True
    assert admin_auth._has_recent_admin_step_up(
        {
            "admin_step_up_at": now + timedelta(seconds=1),
            "admin_step_up_expires_at": now + timedelta(minutes=5),
        },
        now=now,
    ) is False


def test_account_deletion_completion_requires_recent_admin_step_up():
    dependency = inspect.signature(account_deletion.complete_deletion).parameters["_step_up"].default
    assert dependency.dependency is admin_auth.require_recent_admin_step_up
