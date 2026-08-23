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


def test_distance_and_duration_labels_are_deterministic():
    assert maps._fmt_distance(850) == "850 m"
    assert maps._fmt_distance(1250) == "1.2 km"
    assert maps._fmt_duration(600) == "10 min"
    assert maps._fmt_duration(3900) == "1h 5m"
