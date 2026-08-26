from routers.payroll_closure import (
    closure_readiness,
    mutation_guard_router,
    payslip_number,
    payslips_to_csv,
)


def _staff(uid: str):
    return {"_id": uid, "name": f"Employee {uid}"}


def _payroll(uid: str, status: str = "PAID", **extra):
    return {"user_id": uid, "status": status, **extra}


def test_closure_readiness_requires_every_active_employee_paid():
    result = closure_readiness(
        [_staff("u1"), _staff("u2"), _staff("u3")],
        [_payroll("u1"), _payroll("u2", "APPROVED")],
    )
    assert result["ready"] is False
    assert result["paid_count"] == 1
    assert result["missing_user_ids"] == ["u3"]
    assert result["unpaid"] == [{"user_id": "u2", "status": "APPROVED"}]


def test_closure_readiness_rejects_active_payment_lock_even_if_status_paid():
    result = closure_readiness(
        [_staff("u1")],
        [_payroll("u1", payment_lock={"id": "lock-1"})],
    )
    assert result["ready"] is False
    assert result["payment_locked_user_ids"] == ["u1"]


def test_closure_readiness_is_true_only_for_complete_paid_set():
    result = closure_readiness(
        [_staff("u1"), _staff("u2")],
        [_payroll("u1"), _payroll("u2")],
    )
    assert result["ready"] is True
    assert result["paid_count"] == 2
    assert result["missing_user_ids"] == []
    assert result["unpaid"] == []
    assert result["payment_locked_user_ids"] == []


def test_payslip_number_is_stable_and_uses_employee_code():
    assert payslip_number("2026-08", "plant-123456", "user-abcdef", "EMP-007") == "PS-202608-123456-EMP-007"


def test_csv_export_uses_snapshotted_payroll_values_and_escapes_text():
    csv_text = payslips_to_csv([
        {
            "payslip_number": "PS-1",
            "month": "2026-08",
            "employee_code": "EMP-1",
            "employee_name": "Bade, Krushna",
            "role": "accountant",
            "closure_version": 2,
            "payroll_snapshot": {
                "basic_amount": 30000,
                "allowances": 5000,
                "overtime_amount": 1200,
                "deductions": 1500,
                "paid_days": 31,
                "net_amount": 34700,
                "payment_method": "bank_transfer",
                "payment_reference": "TXN-123",
                "paid_on": "2026-08-31",
            },
        }
    ])
    assert "payslip_number,month" in csv_text
    assert '"Bade, Krushna"' in csv_text
    assert "34700" in csv_text
    assert "TXN-123" in csv_text


def test_closed_period_guard_shadows_all_three_payroll_mutations():
    paths = {route.path for route in mutation_guard_router.routes}
    assert "/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/draft" in paths
    assert "/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/owner-decision" in paths
    assert "/api/workforce-reports/plants/{plant_id}/payroll/{month}/{user_id}/mark-paid" in paths
