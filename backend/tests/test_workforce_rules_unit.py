"""Pure unit coverage for PR33 shift/roster/geofence helpers."""
from datetime import date, datetime, timezone

from routers.workforce_rules import classify_attendance, haversine_m, shift_bounds


def test_haversine_distance_is_zero_and_detects_real_distance():
    assert haversine_m(19.0, 73.0, 19.0, 73.0) == 0.0
    assert 1000 < haversine_m(19.0, 73.0, 19.01, 73.0) < 1200


def test_overnight_shift_bounds_roll_end_to_next_day():
    start, end = shift_bounds(
        date(2026, 8, 26),
        {"start_time": "20:00", "end_time": "06:00"},
        "Asia/Kolkata",
    )
    assert start.date().isoformat() == "2026-08-26"
    assert end.date().isoformat() == "2026-08-27"
    assert int((end - start).total_seconds() // 3600) == 10


def test_attendance_classification_uses_worked_minutes_and_weekoff():
    doc = {
        "date": "2026-08-26",
        "check_in": datetime(2026, 8, 26, 3, 40, tzinfo=timezone.utc),
        "check_out": datetime(2026, 8, 26, 7, 10, tzinfo=timezone.utc),
    }
    shift = {
        "start_time": "09:00",
        "end_time": "18:00",
        "grace_minutes": 10,
        "half_day_minutes": 240,
        "overtime_after_minutes": 540,
    }
    result = classify_attendance(doc, None, shift, "Asia/Kolkata")
    assert result["classification"] == "HALF_DAY"
    assert result["worked_minutes"] == 210
    assert result["late_minutes"] == 0

    weekoff = classify_attendance(doc, {"week_off": True}, shift, "Asia/Kolkata")
    assert weekoff["classification"] == "WEEK_OFF_WORK"
