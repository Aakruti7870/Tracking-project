"""Price and permission invariants for Premium and Plant Promotion."""
import pytest
from fastapi import HTTPException

from routers.plant_plans import QuoteBody, product_price, quote_amount


def test_promotion_prices_are_fixed_and_separate():
    assert product_price(QuoteBody(plant_id="x", product="PROMOTION", duration_days=7)) == (2500, "7_DAYS")
    assert product_price(QuoteBody(plant_id="x", product="PROMOTION", duration_days=15)) == (4000, "15_DAYS")
    assert product_price(QuoteBody(plant_id="x", product="PROMOTION", duration_days=30)) == (6000, "30_DAYS")


def test_premium_prices_are_not_promotion_prices():
    assert product_price(QuoteBody(plant_id="x", product="PREMIUM", premium_plan="LAUNCH")) == (64500, "LAUNCH")
    assert product_price(QuoteBody(plant_id="x", product="PREMIUM", premium_plan="GROWTH")) == (129000, "GROWTH")
    assert product_price(QuoteBody(plant_id="x", product="PREMIUM", premium_plan="SIGNATURE")) == (258000, "SIGNATURE")


def test_discount_is_bounded_and_supports_free_code():
    assert quote_amount(6000, {"discount_type": "PERCENT", "discount_value": 25}) == (4500, 1500)
    assert quote_amount(6000, {"discount_type": "PERCENT", "discount_value": 100}) == (0, 6000)
    assert quote_amount(2500, {"discount_type": "FIXED", "discount_value": 9000}) == (0, 2500)


def test_unknown_duration_is_rejected():
    with pytest.raises(HTTPException) as exc:
        product_price(QuoteBody(plant_id="x", product="PROMOTION", duration_days=10))
    assert exc.value.status_code == 422
