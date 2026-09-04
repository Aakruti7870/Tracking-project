from datetime import datetime, timezone

from bson import ObjectId

from order_automation import (
    AUTOMATION_POLICIES,
    CANONICAL_STATUSES,
    ORDER_STATUS_CHANGED,
    _safe_provider_result,
    build_order_status_event,
    _channel_enabled,
    provider_event,
    in_customer_quiet_hours,
)
from order_service import TRANSITIONS


def test_all_canonical_statuses_have_localized_non_spam_policy():
    assert set(AUTOMATION_POLICIES) == set(CANONICAL_STATUSES)
    voice = {status for status, policy in AUTOMATION_POLICIES.items() if "vapi" in policy["channels"]}
    assert voice == {"PENDING", "REJECTED", "CANCELLED", "DELIVERED"}
    for status, policy in AUTOMATION_POLICIES.items():
        assert policy["routing_key"] == f"order.status.{status.lower()}"
        assert policy["template"]["en"]
        assert policy["respect_opt_out"] is True
        assert policy["max_attempts"] == 5


def test_authoritative_state_machine_and_automation_contract_cannot_drift():
    canonical = set(CANONICAL_STATUSES)
    assert set(TRANSITIONS) == canonical
    for source, targets in TRANSITIONS.items():
        assert source in canonical
        assert set(targets) <= canonical


def test_every_canonical_status_builds_a_safe_routable_event():
    for status in CANONICAL_STATUSES:
        event = build_order_status_event(
            {
                "_id": ObjectId(),
                "order_id": "order-contract",
                "from_status": None,
                "to_status": status,
                "actor_id": "private-actor",
                "note": "private-note",
            },
            {
                "_id": "order-contract",
                "order_number": "AUTO-CONTRACT-1",
                "customer_id": "private-customer",
                "contact_mobile": "+919999999999",
                "otp": "123456",
            },
        )
        assert event["to_status"] == status
        assert event["routing_key"] == f"order.status.{status.lower()}"
        assert event["delivery"]["channels"] == AUTOMATION_POLICIES[status]["channels"]
        assert event["payload"] == {"order_number": "AUTO-CONTRACT-1"}
        assert "actor_id" not in event
        assert "note" not in event


def test_provider_result_and_event_never_persist_secrets_or_actor_notes():
    result = _safe_provider_result({"provider": "vapi", "provider_id": "call-1", "status": "sent",
                                    "token": "secret", "raw_response": {"phone": "+910000000000"}})
    assert result == {"provider": "vapi", "provider_id": "call-1", "status": "sent"}
    event = build_order_status_event({"_id": ObjectId(), "order_id": "o1", "to_status": "REJECTED",
                                      "actor_id": "private", "note": "internal"}, {})
    assert "actor_id" not in event
    assert "note" not in event
    assert "reason" not in event["payload"]


def test_provider_projection_excludes_queue_lease_and_customer_identifiers():
    event = build_order_status_event(
        {"_id": ObjectId(), "order_id": "o1", "to_status": "ACCEPTED"},
        {"order_number": "RMC-1", "customer_id": "private-customer", "site_name": "Private home"},
    )
    event.update({"worker_id": "worker-1", "lease_token": "secret-lease", "attempts": 2,
                  "last_error": "internal failure"})
    outbound = provider_event(event)
    assert set(outbound) == {"schema_version", "event_type", "routing_key", "aggregate_type",
                             "aggregate_id", "source_history_id", "from_status", "to_status",
                             "occurred_at", "payload", "delivery"}
    assert outbound["payload"] == {"order_number": "RMC-1"}
    serialized = str(outbound)
    assert "secret-lease" not in serialized
    assert "private-customer" not in serialized
    assert "Private home" not in serialized


def test_quiet_hours_support_overnight_local_windows_and_fail_open_on_bad_preferences():
    overnight = {"notification_quiet_hours_start": 22, "notification_quiet_hours_end": 7,
                 "timezone_offset_minutes": 330}
    assert in_customer_quiet_hours(overnight, datetime(2026, 9, 3, 18, 0, tzinfo=timezone.utc))
    assert not in_customer_quiet_hours(overnight, datetime(2026, 9, 3, 6, 0, tzinfo=timezone.utc))
    assert not in_customer_quiet_hours({"notification_quiet_hours_start": "secret"})


def test_global_and_individual_channel_feature_flags(monkeypatch):
    from order_automation import settings
    monkeypatch.setattr(settings, "AUTOMATION_ENABLED", False)
    monkeypatch.setattr(settings, "AUTOMATION_SMS_ENABLED", True)
    assert not _channel_enabled("sms")
    monkeypatch.setattr(settings, "AUTOMATION_ENABLED", True)
    assert _channel_enabled("sms")
    monkeypatch.setattr(settings, "AUTOMATION_SMS_ENABLED", False)
    assert not _channel_enabled("sms")


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
