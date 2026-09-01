"""Unit coverage for PR35 shift, roster and geofence attendance controls."""
from datetime import datetime, timezone

from routers.workforce_roster import classify_shift, haversine_distance_m, shift_window
from server import app


def _iter_registered_routes(routes):
    """Yield routes recursively across FastAPI included-router wrappers."""
    for route in routes:
        yield route
        nested = getattr(route, "routes", None)
        if nested:
            yield from _iter_registered_routes(nested)


def test_haversine_distance_handles_geofence_boundary_scale():
    # Roughly 111.2 m north at this latitude.
    distance = haversine_distance_m(19.0, 73.0, 19.001, 73.0)
    assert 105 <= distance <= 117
    assert haversine_distance_m(19.0, 73.0, 19.0, 73.0) == 0


def test_shift_window_supports_overnight_shift_in_plant_timezone():
    start, end = shift_window("2026-08-26", "20:00", "05:00", "Asia/Kolkata")
    assert start.isoformat().startswith("2026-08-26T20:00:00+05:30")
    assert end.isoformat().startswith("2026-08-27T05:00:00+05:30")
    assert (end - start).total_seconds() == 9 * 3600


def test_classify_shift_tracks_late_early_overtime_and_missing_checkout():
    scheduled_start = datetime(2026, 8, 26, 3, 30, tzinfo=timezone.utc)
    scheduled_end = datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc)
    check_in = datetime(2026, 8, 26, 3, 50, tzinfo=timezone.utc)
    missing = classify_shift(check_in, None, scheduled_start, scheduled_end, grace_minutes=5)
    assert missing["late_minutes"] == 15
    assert missing["missing_checkout"] is True

    check_out = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    completed = classify_shift(check_in, check_out, scheduled_start, scheduled_end, grace_minutes=5, half_day_threshold_minutes=300)
    assert completed["late_minutes"] == 15
    assert completed["early_departure_minutes"] == 30
    assert completed["overtime_minutes"] == 0
    assert completed["half_day_evidence"] is False

    overtime = classify_shift(scheduled_start, datetime(2026, 8, 26, 13, 15, tzinfo=timezone.utc), scheduled_start, scheduled_end)
    assert overtime["overtime_minutes"] == 45


def test_half_day_is_only_derived_when_owner_configures_threshold():
    start = datetime(2026, 8, 26, 3, 30, tzinfo=timezone.utc)
    end = datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc)
    short_out = datetime(2026, 8, 26, 6, 30, tzinfo=timezone.utc)
    assert classify_shift(start, short_out, start, end)["half_day_evidence"] is False
    assert classify_shift(start, short_out, start, end, half_day_threshold_minutes=240)["half_day_evidence"] is True


def test_geofence_attendance_routes_shadow_original_workforce_punch_routes():
    expected = {
        ("/api/workforce/attendance/punch-in", "POST"): "punch_in_with_roster",
        ("/api/workforce/attendance/punch-out", "POST"): "punch_out_with_roster",
    }
    for (path, method), endpoint_name in expected.items():
        routes = [
            route for route in _iter_registered_routes(app.routes)
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set())
        ]
        assert len(routes) >= 2
        assert routes[0].endpoint.__name__ == endpoint_name
