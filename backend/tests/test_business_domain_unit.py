"""Regression coverage for the expanded plant-business domain schemas."""
from datetime import date

import pytest
from pydantic import ValidationError

from business_models import (
    CustomerSiteBody,
    DieselTransactionBody,
    MixDesignBody,
    OrderLoadBody,
    PayrollRecordBody,
    PlantBusinessProfileBody,
    PurchaseReceiptBody,
    QuotationBody,
    RateCardBody,
)


def test_rate_card_and_mix_design_accept_real_rmc_grades():
    rate = RateCardBody(grade="M25", rate_per_m3=5100, effective_from=date(2026, 8, 23))
    assert rate.grade == "M25"
    design = MixDesignBody(
        grade="M45 PILE",
        version=1,
        cement_kg=410,
        fly_ash_kg=130,
        c_sand_kg=700,
        aggregate_10mm_kg=450,
        aggregate_20mm_kg=700,
        admixture_kg=5,
        water_litre=170,
    )
    assert design.grade == "M45 PILE"


def test_rate_card_rejects_invalid_date_window():
    with pytest.raises(ValidationError):
        RateCardBody(
            grade="M20",
            rate_per_m3=4900,
            effective_from=date(2026, 8, 23),
            effective_to=date(2026, 8, 22),
        )


def test_business_profile_validates_gstin_and_ifsc():
    profile = PlantBusinessProfileBody(
        legal_name="Example RMC Pvt Ltd",
        gstin="27ABCDE1234F1Z5",
        billing_address="Panvel, Navi Mumbai, Maharashtra",
        ifsc="HDFC0001234",
    )
    assert profile.gstin.startswith("27")
    with pytest.raises(ValidationError):
        PlantBusinessProfileBody(
            legal_name="Example RMC Pvt Ltd",
            gstin="BAD-GST",
            billing_address="Panvel, Navi Mumbai, Maharashtra",
        )


def test_customer_site_coordinates_are_bounded():
    site = CustomerSiteBody(name="Site A", address="Sector 1, Panvel", lat=19.0, lng=73.0)
    assert site.lat == 19.0
    with pytest.raises(ValidationError):
        CustomerSiteBody(name="Site A", address="Sector 1, Panvel", lat=100, lng=73)


def test_quotation_and_payroll_are_bounded():
    quote = QuotationBody(
        customer_name="Customer",
        site_name="Tower A",
        site_address="Panvel, Maharashtra",
        grade="M30",
        quantity_m3=25,
        rate_per_m3=5200,
        valid_until=date(2026, 9, 1),
    )
    assert quote.quantity_m3 == 25
    payroll = PayrollRecordBody(
        user_id="staff-1",
        month="2026-08",
        basic_amount=25000,
        paid_days=31,
    )
    assert payroll.month == "2026-08"
    with pytest.raises(ValidationError):
        PayrollRecordBody(user_id="staff-1", month="2026-13", basic_amount=25000)


def test_purchase_requires_at_least_one_line():
    with pytest.raises(ValidationError):
        PurchaseReceiptBody(
            supplier_id="supplier-1",
            receipt_number="GRN-1",
            receipt_date=date(2026, 8, 23),
            lines=[],
        )


def test_load_quantity_and_diesel_transaction_are_validated():
    load = OrderLoadBody(quantity_m3=6.0)
    assert load.quantity_m3 == 6.0
    with pytest.raises(ValidationError):
        OrderLoadBody(quantity_m3=0)
    diesel = DieselTransactionBody(transaction_type="OUT", litres=20)
    assert diesel.litres == 20
