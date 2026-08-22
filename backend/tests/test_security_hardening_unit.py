"""Fast regression tests for validation and compare-and-set state transitions."""
import pytest
from pydantic import ValidationError

from models import CreateOrderBody, LocationBody, PaymentBody, QualityTestBody, SosBody, VehicleStatusBody


@pytest.mark.parametrize("lat,lng", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_location_rejects_out_of_range_coordinates(lat, lng):
    with pytest.raises(ValidationError):
        LocationBody(lat=lat, lng=lng)


def test_location_rejects_negative_accuracy():
    with pytest.raises(ValidationError):
        LocationBody(lat=20, lng=73, accuracy=-1)


@pytest.mark.parametrize("model,kwargs", [
    (VehicleStatusBody, {"status": "destroyed"}),
    (QualityTestBody, {"order_id": "abc", "result": "MAYBE"}),
    (SosBody, {"type": "Anything"}),
    (PaymentBody, {"amount": 1, "method": "crypto"}),
])
def test_business_enums_reject_arbitrary_values(model, kwargs):
    with pytest.raises(ValidationError):
        model(**kwargs)


def test_order_quantity_and_grade_are_bounded():
    common = dict(plant_id="p", site_name="Site", site_address="Address", delivery_date="2026-08-22")
    with pytest.raises(ValidationError):
        CreateOrderBody(grade="DROP TABLE", quantity=1, **common)
    with pytest.raises(ValidationError):
        CreateOrderBody(grade="M20", quantity=10001, **common)
