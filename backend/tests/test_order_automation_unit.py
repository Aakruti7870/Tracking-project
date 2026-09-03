from datetime import datetime, timezone

from bson import ObjectId

from order_automation import (
    AUTOMATION_POLICIES,
    CANONICAL_STATUSES,
    ORDER_STATUS_CHANGED,
    _safe_provider_result,
    build_order_status_event,
)


def test_all_canonical_statuses_have_localized_non_spam_policy():
    assert set(AUTOMATION_POLICIES) == set(CANONICAL_STATUSES)
    voice = {status for status, policy in AUTOMATION_POLICIES.items() if "vapi" in policy["channels"]}
    assert voice == {"REJECTED", "CANCELLED", "DELIVERED"}
    for status, policy in AUTOMATION_POLICIES.items():
        assert policy["routing_key"] == f"order.status.{status.lower()}"
        assert policy["template"]["en"]
        assert policy["respect_opt_out"] is True
        assert policy["max_attempts"] == 5


def test_provider_result_and_event_never_persist_secrets_or_actor_notes():
    result = _safe_provider_result({"provider": "vapi", "provider_id": "call-1", "status": "sent",
                                    "token": "secret", "raw_response": {"phone": "+910000000000"}})
    assert result == {"provider": "vapi", "provider_id": "call-1", "status": "sent"}
    event = build_order_status_event({"_id": ObjectId(), "order_id": "o1", "to_status": "REJECTED",
                                      "actor_id": "private", "note": "internal"}, {})
    assert "actor_id" not in event
    assert "note" not in event


def test_build_order_status_event_has_deterministic_route_and_safe_payload():
    history_id = ObjectId()
    order_id = ObjectId()
    created_at = datetime(2026, 9, 3, 4, 0, tzinfo=timezone.utc)
    history = {
        "_id": history_id,
        "order_id": str(order_id),
        "from_status": "READY_TO_DISPATCH",
        "to_status": "DISPATCHED",
        "actor_id": "dispatcher-1",
        "note": "Mixer left plant",
        "created_at": created_at,
    }
    order = {
        "_id": order_id,
        "order_number": "TMRMC-1001",
        "customer_id": "customer-1",
        "plant_id": "plant-1",
        "site_id": "site-1",
        "site_name": "Panvel Site",
        "grade": "M30",
        "quantity": 25,
        "tm_number": "MH46-AB-1234",
        "payment_status": "UNPAID",
        # These fields must never be copied into automation payloads.
        "contact_mobile": "+919999999999",
        "contact_person": "Private Name",
        "otp": "123456",
    }

    event = build_order_status_event(history, order)

    assert event["_id"] == history_id
    assert event["event_type"] == ORDER_STATUS_CHANGED
    assert event["routing_key"] == "order.status.dispatched"
    assert event["aggregate_id"] == str(order_id)
    assert event["from_status"] == "READY_TO_DISPATCH"
    assert event["to_status"] == "DISPATCHED"
    assert event["occurred_at"] == created_at
    assert event["payload"]["order_number"] == "TMRMC-1001"
    assert event["payload"]["grade"] == "M30"
    assert "contact_mobile" not in event["payload"]
    assert "contact_person" not in event["payload"]
    assert "otp" not in event["payload"]


def test_build_order_status_event_supports_initial_order_status():
    history = {
        "_id": ObjectId(),
        "order_id": "order-1",
        "from_status": None,
        "to_status": "PENDING",
        "actor_id": "customer-1",
    }

    event = build_order_status_event(history, None)

    assert event["from_status"] is None
    assert event["to_status"] == "PENDING"
    assert event["routing_key"] == "order.status.pending"
    assert event["aggregate_id"] == "order-1"
