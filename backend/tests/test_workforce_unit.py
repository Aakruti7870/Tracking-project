"""Unit coverage for PR31 workforce validation and access boundaries."""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from roles import Role
from routers.workforce import (
    EMPLOYEE_ROLES,
    ExpenseClaimBody,
    LeaveRequestBody,
    LocationEvidence,
    VisitRequestBody,
    _aware,
)


def test_workforce_employee_roles_fail_closed_for_platform_and_customer_accounts():
    assert Role.DRIVER.value in EMPLOYEE_ROLES
    assert Role.ACCOUNTANT.value in EMPLOYEE_ROLES
    assert Role.CUSTOMER.value not in EMPLOYEE_ROLES
    assert Role.PLANT_OWNER.value not in EMPLOYEE_ROLES
    assert Role.AUTHORITY.value not in EMPLOYEE_ROLES
    assert Role.CENTRAL_ADMIN.value not in EMPLOYEE_ROLES


def test_location_evidence_rejects_invalid_coordinates():
    evidence = LocationEvidence(lat=19.033, lng=73.029, accuracy_m=12)
    assert evidence.accuracy_m == 12
    with pytest.raises(ValidationError):
        LocationEvidence(lat=91, lng=73)
    with pytest.raises(ValidationError):
        LocationEvidence(lat=19, lng=181)


def test_leave_schema_accepts_supported_leave_types_only():
    request = LeaveRequestBody(
        leave_type="CASUAL",
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 28),
        reason="Family work",
    )
    assert request.leave_type == "CASUAL"
    with pytest.raises(ValidationError):
        LeaveRequestBody(
            leave_type="UNKNOWN",
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 28),
            reason="Family work",
        )


def test_expense_claim_amount_is_positive_and_bounded():
    claim = ExpenseClaimBody(
        category="TRAVEL",
        amount=1250.50,
        expense_date=date(2026, 8, 26),
        description="Client visit travel",
    )
    assert claim.amount == 1250.50
    with pytest.raises(ValidationError):
        ExpenseClaimBody(
            category="TRAVEL",
            amount=0,
            expense_date=date(2026, 8, 26),
            description="Client visit travel",
        )


def test_visit_schedule_normalizes_naive_datetime_to_utc():
    body = VisitRequestBody(
        client_name="Example Client",
        purpose="Site coordination",
        scheduled_for=datetime(2026, 8, 27, 10, 30),
        site_address="Panvel, Maharashtra",
    )
    assert _aware(body.scheduled_for).tzinfo == timezone.utc
