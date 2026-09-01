"""Pure unit coverage for PR32 workforce reporting/payroll helpers and hotfix guards."""
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.routing import iter_route_contexts

from routers.payroll_concurrency_hotfix import (
    _cas_filter,
    _finance_payment_matches,
    _owner_mutation_filter,
    _payment_reservation_filter,
)
from routers.workforce_reports import month_bounds, overlap_days, payroll_net
from server import app


def test_month_bounds_handles_leap_year_and_rejects_invalid_format():
    first, last = month_bounds("2028-02")
    assert first == date(2028, 2, 1)
    assert last == date(2028, 2, 29)
    with pytest.raises(HTTPException):
        month_bounds("2028-13")
    with pytest.raises(HTTPException):
        month_bounds("02-2028")


def test_overlap_days_clips_leave_to_report_month():
    first, last = month_bounds("2026-08")
    assert overlap_days("2026-07-30", "2026-08-03", first, last) == 3
    assert overlap_days("2026-08-10", "2026-08-12", first, last) == 3
    assert overlap_days("2026-09-01", "2026-09-02", first, last) == 0


def test_payroll_net_uses_explicit_components_only():
    assert payroll_net(25000, 2000, 1500, 500) == 28000
    assert payroll_net(0, 0, 0, 0) == 0
    assert payroll_net(1000, 0, 0, 1500) == -500


def test_legacy_direct_payroll_write_fails_closed_before_finance_route():
    routes = [
        route for route in iter_route_contexts(app.routes)
        if route.path == "/api/ops/plants/{plant_id}/payroll"
        and "PUT" in route.methods
    ]
    assert len(routes) >= 2
    assert routes[0].endpoint.__name__ == "retired_direct_payroll_write"


def test_pr32_mutations_are_shadowed_by_concurrency_safe_routes():
    expected = {
        ("/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/draft", "PUT"): "prepare_payroll_draft_safe",
        ("/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/owner-decision", "POST"): "owner_payroll_decision_safe",
        ("/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/mark-paid", "POST"): "mark_payroll_paid_safe",
    }
    for (path, method), endpoint_name in expected.items():
        routes = [
            route for route in iter_route_contexts(app.routes)
            if route.path == path and method in route.methods
        ]
        assert len(routes) >= 2
        assert routes[0].endpoint.__name__ == endpoint_name


def test_compare_and_set_filters_protect_owner_approval_and_payment_reservation():
    stamp = datetime(2026, 8, 26, 3, 0, tzinfo=timezone.utc)
    draft = {"_id": "payroll-1", "status": "DRAFT", "updated_at": stamp}
    approved = {"_id": "payroll-1", "status": "APPROVED", "updated_at": stamp}

    assert _cas_filter(draft) == {
        "_id": "payroll-1",
        "status": "DRAFT",
        "updated_at": stamp,
    }
    assert _owner_mutation_filter(approved) == {
        "_id": "payroll-1",
        "status": "APPROVED",
        "updated_at": stamp,
        "payment_lock": {"$exists": False},
    }
    assert _payment_reservation_filter(approved) == {
        "_id": "payroll-1",
        "status": "APPROVED",
        "updated_at": stamp,
        "payment_lock": {"$exists": False},
    }


def test_finance_payment_fingerprint_accepts_exact_retry():
    lock = {
        "payment_reference": "UTR-12345",
        "payment_method": "bank_transfer",
        "paid_on": "2026-08-26",
    }
    finance_doc = {
        "source": "PAYROLL",
        "amount": 28500.0,
        "reference": "UTR-12345",
        "payment_method": "bank_transfer",
        "expense_date": "2026-08-26",
    }

    assert _finance_payment_matches(finance_doc, 28500.0, lock) is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reference", "UTR-DIFFERENT"),
        ("payment_method", "upi"),
        ("expense_date", "2026-08-27"),
        ("amount", 28501.0),
        ("source", "MANUAL"),
    ],
)
def test_finance_payment_fingerprint_rejects_mismatched_orphaned_expense(field, value):
    lock = {
        "payment_reference": "UTR-12345",
        "payment_method": "bank_transfer",
        "paid_on": "2026-08-26",
    }
    finance_doc = {
        "source": "PAYROLL",
        "amount": 28500.0,
        "reference": "UTR-12345",
        "payment_method": "bank_transfer",
        "expense_date": "2026-08-26",
    }
    finance_doc[field] = value

    assert _finance_payment_matches(finance_doc, 28500.0, lock) is False


def test_finance_payment_fingerprint_rejects_missing_lock_or_document():
    lock = {
        "payment_reference": "UTR-12345",
        "payment_method": "bank_transfer",
        "paid_on": "2026-08-26",
    }
    finance_doc = {
        "source": "PAYROLL",
        "amount": 28500.0,
        "reference": "UTR-12345",
        "payment_method": "bank_transfer",
        "expense_date": "2026-08-26",
    }

    assert _finance_payment_matches(None, 28500.0, lock) is False
    assert _finance_payment_matches(finance_doc, 28500.0, None) is False
