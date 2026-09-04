import asyncio
from unittest.mock import AsyncMock

import pytest

import automation_worker as worker


@pytest.fixture(autouse=True)
def _silence_heartbeat(monkeypatch):
    """These tests exercise claim/deliver/ack logic, not the heartbeat store.

    Patch the heartbeat hooks so run_worker does not attempt a real Mongo write.
    Dedicated heartbeat behavior is covered in test_automation_worker_heartbeat_unit.py.
    """
    monkeypatch.setattr(worker, "record_started", AsyncMock())
    monkeypatch.setattr(worker, "record_success", AsyncMock())
    monkeypatch.setattr(worker, "record_failure", AsyncMock())


def _config(**overrides):
    values = {
        "batch_size": 10,
        "max_events": 20,
        "lease_seconds": 300,
        "retry_after_seconds": 60,
    }
    values.update(overrides)
    return worker.WorkerConfig(**values)


def test_disabled_worker_does_not_claim(monkeypatch):
    claim = AsyncMock()
    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", False)
    monkeypatch.setattr(worker, "claim_order_status_events", claim)

    summary = asyncio.run(worker.run_worker(_config()))

    assert summary == {"disabled": 1, "processed": 0}
    claim.assert_not_awaited()


def test_worker_delivers_and_acks_claimed_event(monkeypatch):
    event = {"_id": "evt-1", "lease_token": "lease-1"}
    claim = AsyncMock(side_effect=[[event], []])
    deliver = AsyncMock(return_value={
        "provider": "multi",
        "status": "completed",
        "deliveries": [{"provider": "n8n", "status": "accepted"}],
    })
    complete = AsyncMock(return_value=True)
    fail = AsyncMock(return_value=True)

    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(worker, "_worker_id", lambda: "worker-test")
    monkeypatch.setattr(worker, "claim_order_status_events", claim)
    monkeypatch.setattr(worker, "deliver_claimed_event", deliver)
    monkeypatch.setattr(worker, "complete_order_status_event", complete)
    monkeypatch.setattr(worker, "fail_order_status_event", fail)

    summary = asyncio.run(worker.run_worker(_config()))

    assert summary == {"processed": 1, "completed": 1}
    deliver.assert_awaited_once_with("evt-1", "worker-test", "lease-1")
    complete.assert_awaited_once()
    fail.assert_not_awaited()


def test_worker_schedules_retry_without_leaking_provider_error(monkeypatch):
    event = {"_id": "evt-2", "lease_token": "lease-2"}
    claim = AsyncMock(side_effect=[[event], []])
    deliver = AsyncMock(side_effect=RuntimeError("provider response with sensitive detail"))
    complete = AsyncMock(return_value=True)
    fail = AsyncMock(return_value=True)

    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(worker, "_worker_id", lambda: "worker-test")
    monkeypatch.setattr(worker, "claim_order_status_events", claim)
    monkeypatch.setattr(worker, "deliver_claimed_event", deliver)
    monkeypatch.setattr(worker, "complete_order_status_event", complete)
    monkeypatch.setattr(worker, "fail_order_status_event", fail)

    summary = asyncio.run(worker.run_worker(_config(retry_after_seconds=75)))

    assert summary == {"processed": 1, "retry": 1}
    fail.assert_awaited_once_with(
        "evt-2", "worker-test", "RuntimeError", 75, "lease-2"
    )
    complete.assert_not_awaited()


def test_worker_reports_lost_lease_on_failed_ack(monkeypatch):
    event = {"_id": "evt-3", "lease_token": "lease-3"}
    claim = AsyncMock(side_effect=[[event], []])

    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(worker, "_worker_id", lambda: "worker-test")
    monkeypatch.setattr(worker, "claim_order_status_events", claim)
    monkeypatch.setattr(worker, "deliver_claimed_event", AsyncMock(return_value={"status": "completed"}))
    monkeypatch.setattr(worker, "complete_order_status_event", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "fail_order_status_event", AsyncMock(return_value=True))

    summary = asyncio.run(worker.run_worker(_config()))

    assert summary == {"processed": 1, "lease_lost": 1}


def test_worker_config_rejects_out_of_range_values(monkeypatch):
    monkeypatch.setenv("AUTOMATION_WORKER_BATCH_SIZE", "0")
    with pytest.raises(RuntimeError, match="AUTOMATION_WORKER_BATCH_SIZE"):
        worker.WorkerConfig.from_env()
