"""Google Maps/Places integration must fail closed and remain usable without keys."""
import asyncio

import pytest
from fastapi import HTTPException

from routers import maps


def test_maps_status_reports_unconfigured_without_server_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_KEY", raising=False)
    result = asyncio.run(maps.status(ctx={}))
    assert result == {"configured": False}


def test_route_never_fabricates_distance_without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_KEY", raising=False)
    result = asyncio.run(maps.route(19.033, 73.029, 19.218, 73.091, ctx={}))
    assert result == {"configured": False, "route_available": False}


def test_autocomplete_degrades_to_manual_address_entry_without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_KEY", raising=False)
    result = asyncio.run(maps.autocomplete("Panvel", "unit-session", ctx={}))
    assert result == {"configured": False, "suggestions": []}


def test_place_details_requires_maps_configuration(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(maps.place_details("place-123", "unit-session", ctx={}))
    assert exc.value.status_code == 409


def test_rmc_discovery_degrades_safely_without_server_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_KEY", raising=False)
    result = asyncio.run(
        maps.discover_rmc_plants(
            19.033,
            73.029,
            50,
            "ready mix concrete RMC plant",
            ctx={},
        )
    )
    assert result == {"configured": False, "places": []}


def test_request_listing_requires_server_places_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(maps.request_rmc_listing("place-123", ctx={"user_id": "u1", "role": "customer"}))
    assert exc.value.status_code == 409


def test_google_place_summary_normalizes_identity_location_and_address_parts():
    result = maps._place_summary(
        {
            "id": "ChIJ-rmc-1",
            "displayName": {"text": "Example Ready Mix Concrete"},
            "formattedAddress": "Taloja MIDC, Navi Mumbai, Maharashtra, India",
            "location": {"latitude": 19.076, "longitude": 73.119},
            "googleMapsUri": "https://maps.google.com/example",
            "businessStatus": "OPERATIONAL",
            "addressComponents": [
                {"longText": "Taloja", "types": ["locality"]},
                {"longText": "Raigad", "types": ["administrative_area_level_2"]},
            ],
        }
    )
    assert result is not None
    assert result["place_id"] == "ChIJ-rmc-1"
    assert result["name"] == "Example Ready Mix Concrete"
    assert result["city"] == "Taloja"
    assert result["district"] == "Raigad"
    assert result["lat"] == 19.076
    assert result["lng"] == 73.119


def test_google_place_summary_rejects_missing_or_invalid_coordinates():
    assert maps._place_summary({"id": "p", "displayName": {"text": "RMC"}}) is None
    assert maps._place_summary(
        {
            "id": "p",
            "displayName": {"text": "RMC"},
            "location": {"latitude": 999, "longitude": 73.0},
        }
    ) is None


def test_distance_and_duration_labels_are_deterministic():
    assert maps._fmt_distance(850) == "850 m"
    assert maps._fmt_distance(1250) == "1.2 km"
    assert maps._fmt_duration(600) == "10 min"
    assert maps._fmt_duration(3900) == "1h 5m"
