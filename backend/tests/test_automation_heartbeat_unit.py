"""Unit coverage for the automation worker heartbeat + health evaluation.

These tests use an in-memory fake collection so they need no live MongoDB and
run deterministically. They cover heartbeat create/update, the healthy/warning/
failed/unknown thresholds, stale detection and the heartbeat-write-failure path.

The project does not use pytest-asyncio, so async paths are driven with
asyncio.run(...) to match the existing worker test style.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import automation_heartbeat as hb


class FakeCollection:
    """Minimal async Mongo collection double keyed by _id."""

    def __init__(self):
        self.docs = {}
        self.raise_on_update = False

    async def update_one(self, flt, update, upsert=False):
        if self.raise_on_update:
            raise RuntimeError("heartbeat store unavailable")
        key = flt["_id"]
        doc = self.docs.get(key, {"_id": key})
        doc.update(update.get("$set", {}))
        if key not in self.docs:
            doc.update(update.get("$setOnInsert", {}))
        self.docs[key] = doc
        return doc

    async def find_one(self, flt):
        return self.docs.get(flt["_id"])


@pytest.fixture
def fake_collection(monkeypatch):
    coll = FakeCollection()
    monkeypatch.setattr(hb, "automation_worker_heartbeats", coll)
    return coll


def _now():
    return datetime(2025, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def test_record_started_creates_document(fake_collection):
    asyncio.run(hb.record_started(hb.WORKER_NAME, "exec-1", now=_now()))
    doc = fake_collection.docs[hb.WORKER_NAME]
    assert doc["worker_name"] == hb.WORKER_NAME
    assert doc["last_started_at"] == _now()
    assert doc["last_execution_id"] == "exec-1"
    assert doc["created_at"] == _now()


def test_record_success_sets_last_success_and_clears_failure(fake_collection):
    asyncio.run(hb.record_failure(hb.WORKER_NAME, "BoomError", now=_now()))
    later = _now() + timedelta(seconds=5)
    asyncio.run(hb.record_success(hb.WORKER_NAME, "exec-2", {"processed": 3}, now=later))
    doc = fake_collection.docs[hb.WORKER_NAME]
    assert doc["last_success_at"] == later
    assert doc["last_status"] == hb.STATUS_SUCCESS
    assert doc["last_summary"] == {"processed": 3}
    assert doc["last_failure_reason"] is None


def test_record_failure_bounds_reason(fake_collection):
    asyncio.run(hb.record_failure(hb.WORKER_NAME, "x" * 1000, now=_now()))
    doc = fake_collection.docs[hb.WORKER_NAME]
    assert doc["last_status"] == hb.STATUS_FAILED
    assert len(doc["last_failure_reason"]) == 300
    assert doc["last_failure_at"] == _now()


def test_heartbeat_write_failure_propagates(fake_collection):
    fake_collection.raise_on_update = True
    with pytest.raises(RuntimeError, match="heartbeat store unavailable"):
        asyncio.run(hb.record_started(hb.WORKER_NAME, now=_now()))


def test_health_unknown_when_no_success():
    report = hb.evaluate_health(None, now=_now())
    assert report.status is hb.Health.UNKNOWN
    assert report.age_seconds is None


def test_health_healthy_within_threshold():
    hbdoc = {"worker_name": hb.WORKER_NAME, "last_success_at": _now() - timedelta(seconds=60)}
    report = hb.evaluate_health(hbdoc, now=_now(), healthy_seconds=180, warning_seconds=300)
    assert report.status is hb.Health.HEALTHY
    assert report.age_seconds == pytest.approx(60, abs=1)


def test_health_warning_between_thresholds():
    hbdoc = {"worker_name": hb.WORKER_NAME, "last_success_at": _now() - timedelta(seconds=240)}
    report = hb.evaluate_health(hbdoc, now=_now(), healthy_seconds=180, warning_seconds=300)
    assert report.status is hb.Health.WARNING


def test_health_failed_beyond_warning_threshold():
    hbdoc = {"worker_name": hb.WORKER_NAME, "last_success_at": _now() - timedelta(seconds=600)}
    report = hb.evaluate_health(hbdoc, now=_now(), healthy_seconds=180, warning_seconds=300)
    assert report.status is hb.Health.FAILED


def test_health_accepts_iso_string_timestamp():
    iso = (_now() - timedelta(seconds=30)).isoformat()
    report = hb.evaluate_health({"last_success_at": iso}, now=_now(), healthy_seconds=180, warning_seconds=300)
    assert report.status is hb.Health.HEALTHY


def test_worker_health_reads_store(fake_collection):
    asyncio.run(hb.record_success(hb.WORKER_NAME, now=_now()))
    report = asyncio.run(hb.worker_health(hb.WORKER_NAME, now=_now() + timedelta(seconds=10)))
    assert report.status is hb.Health.HEALTHY
    assert report.to_dict()["status"] == "HEALTHY"
