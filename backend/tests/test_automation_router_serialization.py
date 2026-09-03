"""Regression coverage for JSON-safe automation worker claim responses."""
from bson import ObjectId

from routers.automation import _json_safe


def test_json_safe_converts_object_ids_recursively():
    event_id = ObjectId()
    nested_id = ObjectId()
    payload = {
        "_id": event_id,
        "aggregate_id": "order-1",
        "nested": {"provider_id": nested_id},
        "items": [event_id, {"other_id": nested_id}],
    }

    result = _json_safe(payload)

    assert result["_id"] == str(event_id)
    assert result["nested"]["provider_id"] == str(nested_id)
    assert result["items"][0] == str(event_id)
    assert result["items"][1]["other_id"] == str(nested_id)
