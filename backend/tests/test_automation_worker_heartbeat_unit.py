"""run_worker must record heartbeats around every cycle."""
import asyncio
from unittest.mock import AsyncMock

import pytest

import automation_worker as worker
from automation_heartbeat import STATUS_SUCCESS, STATUS_SUCCESS_IDLE, WORKER_NAME


def _config(**overrides):
    values = {"batch_size": 10, "max_events": 20, "lease_seconds": 300, "retry_after_seconds": 60}
    values.update(overrides)
    return worker.WorkerConfig(**values)


def _patch_heartbeat(monkeypatch):
    started = AsyncMock()
    success = AsyncMock()
    failure = AsyncMock()
    monkeypatch.setattr(worker, "record_started", started)
    monkeypatch.setattr(worker, "record_success", success)
    monkeypatch.setattr(worker, "record_failure", failure)
    return started, success, failure


def test_success_cycle_records_started_then_success(monkeypatch):
    started, success, failure = _patch_heartbeat(monkeypatch)
    event = {"_id": "evt-1", "lease_token": "lease-1"}
    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(worker, "_worker_id", lambda: "worker-test")
    monkeypatch.setattr(worker, "claim_order_status_events", AsyncMock(side_effect=[[event], []]))
    monkeypatch.setattr(worker, "deliver_claimed_event", AsyncMock(return_value={"status": "completed"}))
    monkeypatch.setattr(worker, "complete_order_status_event", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "fail_order_status_event", AsyncMock(return_value=True))

    summary = asyncio.run(worker.run_worker(_config()))

    assert summary == {"processed": 1, "completed": 1}
    started.assert_awaited_once()
    success.assert_awaited_once()
    # status argument reflects that real work was processed
    assert success.await_args.kwargs.get("status") == STATUS_SUCCESS
    failure.assert_not_awaited()


def test_idle_cycle_records_success_idle(monkeypatch):
    started, success, failure = _patch_heartbeat(monkeypatch)
    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(worker, "_worker_id", lambda: "worker-test")
    monkeypatch.setattr(worker, "claim_order_status_events", AsyncMock(return_value=[]))

    summary = asyncio.run(worker.run_worker(_config()))

    assert summary == {"processed": 0}
    assert success.await_args.kwargs.get("status") == STATUS_SUCCESS_IDLE
    failure.assert_not_awaited()


def test_disabled_cycle_still_records_success_idle(monkeypatch):
    started, success, failure = _patch_heartbeat(monkeypatch)
    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", False)
    claim = AsyncMock()
    monkeypatch.setattr(worker, "claim_order_status_events", claim)

    summary = asyncio.run(worker.run_worker(_config()))

    assert summary == {"disabled": 1, "processed": 0}
    started.assert_awaited_once()
    assert success.await_args.kwargs.get("status") == STATUS_SUCCESS_IDLE
    claim.assert_not_awaited()


def test_failed_cycle_records_failure_and_reraises(monkeypatch):
    started, success, failure = _patch_heartbeat(monkeypatch)
    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(worker, "_worker_id", lambda: "worker-test")
    monkeypatch.setattr(worker, "claim_order_status_events", AsyncMock(side_effect=RuntimeError("claim boom")))

    with pytest.raises(RuntimeError, match="claim boom"):
        asyncio.run(worker.run_worker(_config()))

    started.assert_awaited_once()
    failure.assert_awaited_once()
    assert failure.await_args.args[1] == "RuntimeError"
    success.assert_not_awaited()


def test_record_heartbeat_can_be_disabled(monkeypatch):
    started, success, failure = _patch_heartbeat(monkeypatch)
    monkeypatch.setattr(worker.settings, "AUTOMATION_ENABLED", False)
    monkeypatch.setattr(worker, "claim_order_status_events", AsyncMock())

    asyncio.run(worker.run_worker(_config(), record_heartbeat=False))

    started.assert_not_awaited()
    success.assert_not_awaited()
    failure.assert_not_awaited()
