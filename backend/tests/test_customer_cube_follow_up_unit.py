from datetime import date, datetime, timedelta, timezone

from bson import ObjectId
import pytest
from pydantic import ValidationError

from business_models import CustomerCubeTestResultBody
from routers.customer import _serialize_receiving_record


def test_cube_result_schema_accepts_only_7_or_28_day_results():
    body = CustomerCubeTestResultBody(
        sample_id="CUBE-A1",
        age_days=7,
        tested_on=date.today(),
        result_mpa=31.5,
        lab_name="Approved laboratory",
        report_reference="LAB-2026-001",
    )
    assert body.age_days == 7
    assert body.result_mpa == 31.5

    with pytest.raises(ValidationError):
        CustomerCubeTestResultBody(
            sample_id="CUBE-A1",
            age_days=14,
            tested_on=date.today(),
            result_mpa=31.5,
        )


def test_receiving_serializer_marks_overdue_and_recorded_without_pass_fail():
    yesterday = date.today() - timedelta(days=1)
    tomorrow = date.today() + timedelta(days=1)
    doc = {
        "_id": ObjectId(),
        "cube_sample_ids": ["A1"],
        "cube_7d_date": yesterday.isoformat(),
        "cube_28d_date": tomorrow.isoformat(),
        "cube_test_results": [{
            "sample_id": "A1",
            "age_days": 7,
            "tested_on": yesterday.isoformat(),
            "result_mpa": 32.0,
            "acceptance_status": None,
            "recorded_at": datetime.now(timezone.utc),
        }],
    }

    row = _serialize_receiving_record(doc)
    statuses = {(item["sample_id"], item["age_days"]): item["status"] for item in row["cube_follow_up"]}
    assert statuses[("A1", 7)] == "RECORDED"
    assert statuses[("A1", 28)] == "UPCOMING"
    assert row["pending_cube_tests"] == 1
    assert row["overdue_cube_tests"] == 0
    assert row["cube_test_results"][0]["acceptance_status"] is None


def test_receiving_serializer_marks_missing_past_result_overdue():
    due = date.today() - timedelta(days=2)
    row = _serialize_receiving_record({
        "_id": ObjectId(),
        "cube_sample_ids": ["A1"],
        "cube_7d_date": due.isoformat(),
        "cube_28d_date": due.isoformat(),
        "cube_test_results": [],
    })
    assert row["pending_cube_tests"] == 2
    assert row["overdue_cube_tests"] == 2
