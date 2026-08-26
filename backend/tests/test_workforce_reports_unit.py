"""Pure unit coverage for PR32 workforce reporting/payroll helpers."""
from datetime import date

import pytest
from fastapi import HTTPException

from routers.workforce_reports import month_bounds, overlap_days, payroll_net


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
