"""Google Maps proxy — keeps the API key server-side.

The key is read from GOOGLE_MAPS_KEY. Missing/disabled Google services degrade
gracefully; ETA/distance/polyline are never fabricated.
"""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from security import current_user

router = APIRouter(prefix="/api/maps", tags=["maps"])


def _key() -> str | None:
    k = os.environ.get("GOOGLE_MAPS_KEY", "").strip()
    return k or None


def _valid_coords(lat: float, lng: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lng <= 180


def _fmt_duration(seconds: int) -> str:
    m = max(1, round(seconds / 60))
    if m < 60:
        return f"{m} min"
    return f"{m // 60}h {m % 60}m"


def _fmt_distance(meters: int) -> str:
    if meters < 1000:
        return f"{meters} m"
    return f"{meters / 1000:.1f} km"


async def compute_route(olat: float, olng: float, dlat: float, dlng: float) -> dict | None:
    """Google Routes driving route. None means unavailable, never estimated."""
    key = _key()
    if not key or not _valid_coords(olat, olng) or not _valid_coords(dlat, dlng):
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
                },
                json={
                    "origin": {"location": {"latLng": {"latitude": olat, "longitude": olng}}},
                    "destination": {"location": {"latLng": {"latitude": dlat, "longitude": dlng}}},
                    "travelMode": "DRIVE",
                    "routingPreference": "TRAFFIC_AWARE",
                },
            )
        if r.status_code >= 400:
            return None
        routes = r.json().get("routes") or []
        if not routes:
            return None
        top = routes[0]
        secs = int(str(top.get("duration", "0s")).rstrip("s") or 0)
        dist = int(top.get("distanceMeters", 0))
        if secs <= 0 or dist < 0:
            return None
        return {
            "eta_seconds": secs,
            "eta_text": _fmt_duration(secs),
            "distance_m": dist,
            "distance_text": _fmt_distance(dist),
            "polyline": (top.get("polyline") or {}).get("encodedPolyline"),
        }
    except Exception:
        return None


@router.get("/status")
async def status(ctx: dict = Depends(current_user)):
    return {"configured": _key() is not None}


@router.get("/route")
async def route(
    olat: float = Query(ge=-90, le=90),
    olng: float = Query(ge=-180, le=180),
    dlat: float = Query(ge=-90, le=90),
    dlng: float = Query(ge=-180, le=180),
    ctx: dict = Depends(current_user),
):
    r = await compute_route(olat, olng, dlat, dlng)
    if r is None:
        return {"configured": _key() is not None, "route_available": False}
    return {"configured": True, "route_available": True, **r}


@router.get("/autocomplete")
async def autocomplete(
    input: str = Query(min_length=1, max_length=200),
    session_token: str = Query(default="rmc", min_length=1, max_length=128),
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
    for s in data.get("suggestions", [])[:20]:
        p = s.get("placePrediction")
        if p:
            out.append({"place_id": p.get("placeId"), "text": p.get("text", {}).get("text")})
    return {"configured": True, "suggestions": out}


@router.get("/place/{place_id}")
async def place_details(
    place_id: str = Path(min_length=1, max_length=512, pattern=r"^[A-Za-z0-9._:-]+$"),
    session_token: str = Query(default="rmc", min_length=1, max_length=128),
    ctx: dict = Depends(current_user),
):
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
    lat, lng = loc.get("latitude"), loc.get("longitude")
    if lat is not None and lng is not None and not _valid_coords(lat, lng):
        raise HTTPException(502, "Place details returned invalid coordinates")
    return {"address": d.get("formattedAddress"), "lat": lat, "lng": lng}


@router.get("/geocode")
async def geocode(
    address: str = Query(min_length=1, max_length=500),
    ctx: dict = Depends(current_user),
):
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
    if not _valid_coords(loc["lat"], loc["lng"]):
        raise HTTPException(502, "Geocode returned invalid coordinates")
    return {
        "configured": True,
        "address": top.get("formatted_address"),
        "lat": loc["lat"],
        "lng": loc["lng"],
    }
