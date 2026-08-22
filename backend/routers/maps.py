"""Google Maps proxy — keeps the API key server-side.

The key is read from the GOOGLE_MAPS_KEY env var. When it is absent the service
reports NOT_CONFIGURED and the frontend gracefully falls back to manual entry /
the map placeholder. When a server-usable key is provided, Places autocomplete,
place details and geocoding activate automatically — no code change needed.
"""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from security import current_user

router = APIRouter(prefix="/api/maps", tags=["maps"])


def _key() -> str | None:
    k = os.environ.get("GOOGLE_MAPS_KEY", "").strip()
    return k or None


@router.get("/status")
async def status(ctx: dict = Depends(current_user)):
    return {"configured": _key() is not None}


@router.get("/autocomplete")
async def autocomplete(
    input: str = Query(min_length=1),
    session_token: str = Query(default="rmc"),
    ctx: dict = Depends(current_user),
):
    key = _key()
    if not key:
        return {"configured": False, "suggestions": []}
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.post(
            "https://places.googleapis.com/v1/places:autocomplete",
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": key},
            json={"input": input, "sessionToken": session_token, "includedRegionCodes": ["in"]},
        )
    if r.status_code >= 400:
        raise HTTPException(502, "Places request failed")
    data = r.json()
    out = []
    for s in data.get("suggestions", []):
        p = s.get("placePrediction")
        if p:
            out.append({"place_id": p.get("placeId"), "text": p.get("text", {}).get("text")})
    return {"configured": True, "suggestions": out}


@router.get("/place/{place_id}")
async def place_details(place_id: str, session_token: str = Query(default="rmc"), ctx: dict = Depends(current_user)):
    key = _key()
    if not key:
        raise HTTPException(409, "Maps NOT_CONFIGURED")
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(
            f"https://places.googleapis.com/v1/places/{place_id}",
            params={"sessionToken": session_token},
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "id,formattedAddress,location"},
        )
    if r.status_code >= 400:
        raise HTTPException(502, "Place details failed")
    d = r.json()
    loc = d.get("location", {})
    return {"address": d.get("formattedAddress"), "lat": loc.get("latitude"), "lng": loc.get("longitude")}


@router.get("/geocode")
async def geocode(address: str = Query(min_length=1), ctx: dict = Depends(current_user)):
    key = _key()
    if not key:
        return {"configured": False}
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": key, "region": "in"},
        )
    if r.status_code >= 400:
        raise HTTPException(502, "Geocode failed")
    data = r.json()
    if data.get("status") != "OK" or not data.get("results"):
        return {"configured": True, "lat": None, "lng": None}
    top = data["results"][0]
    loc = top["geometry"]["location"]
    return {"configured": True, "address": top.get("formatted_address"), "lat": loc["lat"], "lng": loc["lng"]}
