"""Schema regressions for immutable identity snapshots on old orders/drafts."""
from models import Order


def _legacy_order(**overrides):
    values = {
        "order_number": "RMC-OLD",
        "customer_id": "customer-1",
        "plant_id": "plant-1",
        "plant_name": "Plant",
        "grade": "M30",
        "quantity": 10,
        "site_name": "Site",
        "site_address": "Address",
        "delivery_date": "2026-09-07",
    }
    values.update(overrides)
    return Order(**values)


def test_historical_order_without_customer_name_loads():
    assert _legacy_order().customer_name is None


def test_historical_order_without_customer_mobile_loads():
    assert _legacy_order(customer_name="Verified Customer").customer_mobile is None


def test_draft_without_identity_loads():
    draft = _legacy_order(status="DRAFT")
    assert draft.status == "DRAFT"
    assert draft.customer_name is None
    assert draft.customer_mobile is None
    assert draft.customer_email is None
