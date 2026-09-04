"""Mongo-backed queue lifecycle evidence (the repository CI supplies Mongo 7)."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

import order_automation
from automation_providers import DeliveryResult, n8n
from order_automation import (
    CANONICAL_STATUSES,
    STATE_COMPLETED,
    STATE_DEAD_LETTER,
    STATE_PROCESSING,
    claim_order_status_events,
    complete_order_status_event,
    deliver_claimed_event,
    fail_order_status_event,
    materialize_history_event,
    settings,
)


@pytest.fixture
def run_isolated_automation(monkeypatch):
    """Run one automation integration scenario on one Motor client/event loop."""

    def _run(scenario):
        # MongoDB limits database names to 63 characters. Keep this prefix short
        # and retain enough UUID entropy for concurrent xdist workers.
        database_name = f"tmrmc_auto_{uuid4().hex[:24]}"
        isolated_client = AsyncIOMotorClient(settings.MONGO_URL)
        isolated_db = isolated_client[database_name]
        collections = {
            "orders": isolated_db.orders,
            "events": isolated_db.order_automation_events,
            "actions": isolated_db.order_automation_actions,
            "attempts": isolated_db.order_automation_attempts,
            "history": isolated_db.order_status_history,
        }

        monkeypatch.setattr(order_automation, "orders", collections["orders"])
        monkeypatch.setattr(order_automation, "order_automation_events", collections["events"])
        monkeypatch.setattr(order_automation, "order_automation_actions", collections["actions"])
        monkeypatch.setattr(order_automation, "order_automation_attempts", collections["attempts"])
        monkeypatch.setattr(order_automation, "order_status_history", collections["history"])

        async def _run_and_cleanup():
            try:
                await scenario(collections)
            finally:
                await isolated_client.drop_database(database_name)
                isolated_client.close()

        return asyncio.run(_run_and_cleanup())

    return _run


def test_history_event_worker_provider_result_retry_dedupe_lease_and_dead_letter(run_isolated_automation):
    run_isolated_automation(_exercise_queue_lifecycle)


def test_every_canonical_status_reaches_provider_mock_and_ack(monkeypatch, run_isolated_automation):
    monkeypatch.setattr(settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(settings, "AUTOMATION_N8N_ENABLED", True)
    monkeypatch.setattr(settings, "AUTOMATION_VOICE_ENABLED", False)
    monkeypatch.setattr(settings, "AUTOMATION_WHATSAPP_ENABLED", False)
    monkeypatch.setattr(settings, "AUTOMATION_SMS_ENABLED", False)
    monkeypatch.setattr(settings, "AUTOMATION_EMAIL_ENABLED", False)
    monkeypatch.setattr(settings, "AUTOMATION_PUSH_ENABLED", False)

    async def _accepted(event):
        return DeliveryResult("n8n", str(event["source_history_id"]), "accepted")

    send = AsyncMock(side_effect=_accepted)
    monkeypatch.setattr(n8n, "send", send)
    run_isolated_automation(_exercise_all_statuses)
    assert send.await_count == len(CANONICAL_STATUSES)


async def _exercise_all_statuses(collections):
    isolated_orders = collections["orders"]
    isolated_events = collections["events"]
    isolated_actions = collections["actions"]
    isolated_attempts = collections["attempts"]

    order_id = ObjectId()
    await isolated_orders.insert_one({
        "_id": order_id,
        "order_number": "AUTO-ALL-STATUSES",
        "grade": "M30",
        "quantity": 8,
    })

    for status in CANONICAL_STATUSES:
        history = {
            "_id": ObjectId(),
            "order_id": str(order_id),
            "from_status": None,
            "to_status": status,
            "created_at": datetime.now(timezone.utc),
        }
        event = await materialize_history_event(history)
        claimed = (await claim_order_status_events(f"worker-{status.lower()}", 1, 30))[0]
        assert claimed["_id"] == event["_id"]
        assert claimed["state"] == STATE_PROCESSING

        result = await deliver_claimed_event(
            claimed["_id"],
            claimed["worker_id"],
            claimed["lease_token"],
            ["n8n"],
        )
        assert result["status"] == "completed"
        assert result["deliveries"] == [{
            "provider": "n8n",
            "provider_id": str(history["_id"]),
            "status": "accepted",
        }]
        assert await complete_order_status_event(
            claimed["_id"], claimed["worker_id"], result, claimed["lease_token"]
        )

        completed = await isolated_events.find_one({"_id": claimed["_id"]})
        assert completed["state"] == STATE_COMPLETED
        action = await isolated_actions.find_one({
            "source_history_id": str(history["_id"]), "channel": "n8n"
        })
        assert action["state"] == STATE_COMPLETED
        assert action["provider_reference"] == str(history["_id"])

    assert await isolated_events.count_documents({"state": STATE_COMPLETED}) == len(CANONICAL_STATUSES)
    assert await isolated_attempts.count_documents({"action": "COMPLETED"}) == len(CANONICAL_STATUSES)


async def _exercise_queue_lifecycle(collections):
    isolated_orders = collections["orders"]
    isolated_events = collections["events"]
    isolated_actions = collections["actions"]
    isolated_attempts = collections["attempts"]
    isolated_history = collections["history"]

    order_id = ObjectId()
    await isolated_orders.insert_one({"_id": order_id, "order_number": "AUTO-E2E-1", "customer_id": "customer-e2e",
                                      "plant_id": "plant-e2e", "grade": "M30", "quantity": 8})
    history = {"order_id": str(order_id), "from_status": "PENDING", "to_status": "ACCEPTED",
               "actor_id": "must-not-leak", "note": "must-not-leak", "created_at": datetime.now(timezone.utc)}
    inserted = await isolated_history.insert_one(history)
    history["_id"] = inserted.inserted_id

    first = await materialize_history_event(history)
    second = await materialize_history_event(history)
    assert first["_id"] == second["_id"]
    assert await isolated_events.count_documents({"_id": first["_id"]}) == 1
    expected_actions = len(first["delivery"]["channels"])
    assert await isolated_actions.count_documents({"source_history_id": first["source_history_id"]}) == expected_actions

    claimed = (await claim_order_status_events("worker-a", 1, 30))[0]
    assert claimed["state"] == STATE_PROCESSING
    assert not await complete_order_status_event(claimed["_id"], "worker-a", {}, "wrong-token")
    assert await fail_order_status_event(claimed["_id"], "worker-a", "temporary", 15, claimed["lease_token"])

    await isolated_events.update_one({"_id": claimed["_id"]}, {"$set": {"next_attempt_at": datetime.now(timezone.utc)}})
    retried = (await claim_order_status_events("worker-b", 1, 30))[0]
    # The prior lease is fenced even after another worker reclaims the event.
    assert not await complete_order_status_event(retried["_id"], "worker-a", {}, claimed["lease_token"])
    assert await complete_order_status_event(
        retried["_id"], "worker-b",
        {"provider": "test", "provider_id": "message-1", "status": "sent", "raw_token": "secret"},
        retried["lease_token"],
    )
    completed = await isolated_events.find_one({"_id": retried["_id"]})
    assert completed["state"] == STATE_COMPLETED
    assert completed["provider_result"] == {"provider": "test", "provider_id": "message-1", "status": "sent"}

    dead_history = {"_id": ObjectId(), "order_id": str(order_id), "from_status": "ACCEPTED",
                    "to_status": "REJECTED", "created_at": datetime.now(timezone.utc)}
    dead = await materialize_history_event(dead_history)
    await isolated_events.update_one({"_id": dead["_id"]}, {"$set": {"attempts": 4}})
    final = (await claim_order_status_events("worker-dead", 1, 30))[0]
    assert await fail_order_status_event(final["_id"], "worker-dead", "permanent", 15, final["lease_token"])
    assert (await isolated_events.find_one({"_id": final["_id"]}))["state"] == STATE_DEAD_LETTER
    assert await isolated_attempts.count_documents({"event_id": str(final["_id"])}) >= 2
