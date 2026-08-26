"""Unit coverage for PR36 employee master salary helpers."""
from datetime import date

from routers.hr_master import SalaryStructureBody, salary_totals


def test_salary_totals_aggregate_fixed_components():
    body = SalaryStructureBody(
        effective_from=date(2026, 8, 1),
        basic_amount=25000,
        hra_amount=5000,
        other_allowances=2000,
        fixed_deductions=500,
        employee_pf=1800,
        employee_esi=0,
        professional_tax=200,
        tds=500,
    )
    totals = salary_totals(body)
    assert totals["allowances"] == 7000
    assert totals["deductions"] == 3000
    assert totals["gross"] == 32000
    assert totals["net_before_overtime"] == 29000


def test_salary_totals_support_daily_basis_without_implicit_scaling():
    body = SalaryStructureBody(
        effective_from=date(2026, 8, 1),
        pay_basis="DAILY",
        basic_amount=900,
        other_allowances=100,
        fixed_deductions=50,
    )
    totals = salary_totals(body)
    assert totals["gross"] == 1000
    assert totals["net_before_overtime"] == 950


def test_salary_totals_can_expose_negative_net_for_api_validation():
    body = SalaryStructureBody(
        effective_from=date(2026, 8, 1),
        basic_amount=1000,
        fixed_deductions=1200,
    )
    assert salary_totals(body)["net_before_overtime"] == -200
