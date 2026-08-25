"""Google Maps/Places proxy — keeps server API credentials off the mobile client.

The server key is read from GOOGLE_MAPS_KEY. Missing/disabled Google services
always degrade safely; distances, routes and business listings are never
fabricated.
"""
from datetime import datetime, timezone
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from audit import write_audit
from database import plant_listing_requests, plants
from roles import Role
from security import current_user, require_role

router = APIRouter(prefix="/api/maps", tags=["maps"])
authority_only = require_role(Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value)


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


def _address_component(place: dict, *wanted_types: str) -> str | None:
    wanted = set(wanted_types)
    for component in place.get("addressComponents") or []:
        if wanted.intersection(component.get("types") or []):
            return component.get("longText") or component.get("shortText")
    return None


def _place_summary(place: dict) -> dict | None:
    """Normalize one Google Place into the small shape used by TrackMyRMC."""
    place_id = str(place.get("id") or "").strip()
    display = place.get("displayName") or {}
    name = str(display.get("text") or "").strip()
    location = place.get("location") or {}
    lat = location.get("latitude")
    lng = location.get("longitude")
    if not place_id or not name or lat is None or lng is None:
        return None
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None
    if not _valid_coords(lat, lng):
        return None

    city = _address_component(place, "locality", "postal_town", "sublocality_level_1")
    taluka = _address_component(place, "administrative_area_level_3", "sublocality_level_1")
    district = _address_component(place, "administrative_area_level_2")
    state = _address_component(place, "administrative_area_level_1")
    return {
        "place_id": place_id,
        "name": name,
        "address": place.get("formattedAddress"),
        "city": city,
        "taluka": taluka,
        "district": district,
        "state": state,
        "lat": lat,
        "lng": lng,
        "contact_phone": place.get("nationalPhoneNumber"),
        "google_maps_uri": place.get("googleMapsUri"),
        "business_status": place.get("businessStatus"),
    }


async def _fetch_place_detail(place_id: str) -> dict:
    key = _key()
    if not key:
        raise HTTPException(409, "Maps NOT_CONFIGURED")
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(
            f"https://places.googleapis.com/v1/places/{place_id}",
            params={"languageCode": "en", "regionCode": "IN"},
            headers={
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": (
                    "id,displayName,formattedAddress,location,nationalPhoneNumber,"
                    "googleMapsUri,businessStatus,addressComponents"
                ),
            },
        )
    if r.status_code >= 400:
        raise HTTPException(502, "Place details failed")
    summary = _place_summary(r.json())
    if not summary:
        raise HTTPException(502, "Place details returned incomplete location data")
    return summary


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


@router.get("/rmc-plants")
async def discover_rmc_plants(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=50, gt=0, le=50),
    q: str = Query(default="ready mix concrete RMC plant", min_length=2, max_length=120),
    ctx: dict = Depends(current_user),
):
    """Find real RMC businesses in Google Places around the user's location.

    Search is deliberately user-initiated from the client so opening the Plants
    screen does not create a Places API bill on every render.
    """
    key = _key()
    if not key:
        return {"configured": False, "places": []}

    radius_m = min(50000.0, max(1000.0, radius_km * 1000.0))
    body = {
        "textQuery": q.strip(),
        "pageSize": 20,
        "languageCode": "en",
        "regionCode": "IN",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_m,
            }
        },
    }
    async with httpx.AsyncClient(timeout=12) as http:
        r = await http.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": (
                    "places.id,places.displayName,places.formattedAddress,places.location,"
                    "places.googleMapsUri,places.businessStatus,places.addressComponents"
                ),
            },
            json=body,
        )
    if r.status_code >= 400:
        raise HTTPException(502, "Google RMC discovery failed")

    summaries = [s for p in (r.json().get("places") or []) if (s := _place_summary(p))]
    ids = [s["place_id"] for s in summaries]
    registered: dict[str, dict] = {}
    requests: dict[str, dict] = {}
    if ids:
        plant_docs = await plants.find({"google_place_id": {"$in": ids}}).to_list(100)
        registered = {p.get("google_place_id"): p for p in plant_docs if p.get("google_place_id")}
        request_docs = await plant_listing_requests.find({"google_place_id": {"$in": ids}}).to_list(100)
        requests = {d.get("google_place_id"): d for d in request_docs if d.get("google_place_id")}

    out = []
    for summary in summaries:
        pid = summary["place_id"]
        plant = registered.get(pid)
        request = requests.get(pid)
        out.append(
            {
                **summary,
                "registered": plant is not None,
                "plant_id": str(plant["_id"]) if plant else None,
                "request_status": request.get("status") if request else None,
            }
        )
    return {"configured": True, "places": out}


@router.get("/authority/rmc-plants")
async def authority_discover_rmc_plants(
    state: str = Query(min_length=2, max_length=80),
    district: str = Query(min_length=2, max_length=80),
    taluka: str = Query(min_length=2, max_length=80),
    page_token: str | None = Query(default=None, max_length=2048),
    ctx: dict = Depends(authority_only),
):
    """Authority-initiated location search; results remain unregistered until review."""
    key = _key()
    if not key:
        return {"configured": False, "places": [], "next_page_token": None}
    query = f"ready mix concrete RMC plant in {taluka}, {district}, {state}, India"
    body = {
        "textQuery": query,
        "pageSize": 20,
        "languageCode": "en",
        "regionCode": "IN",
    }
    if page_token:
        body["pageToken"] = page_token
    async with httpx.AsyncClient(timeout=15) as http:
        response = await http.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": (
                    "places.id,places.displayName,places.formattedAddress,places.location,"
                    "places.googleMapsUri,places.businessStatus,places.addressComponents,nextPageToken"
                ),
            },
            json=body,
        )
    if response.status_code >= 400:
        raise HTTPException(502, "Google RMC discovery failed")
    payload = response.json()
    summaries = [s for place in (payload.get("places") or []) if (s := _place_summary(place))]
    ids = [row["place_id"] for row in summaries]
    registered = {}
    requests = {}
    if ids:
        registered_rows = await plants.find({"google_place_id": {"$in": ids}}).to_list(100)
        registered = {row.get("google_place_id"): row for row in registered_rows}
        request_rows = await plant_listing_requests.find({"google_place_id": {"$in": ids}}).to_list(100)
        requests = {row.get("google_place_id"): row for row in request_rows}
    places_out = []
    for row in summaries:
        place_id = row["place_id"]
        plant = registered.get(place_id)
        request = requests.get(place_id)
        places_out.append({
            **row,
            "registered": bool(plant),
            "plant_id": str(plant["_id"]) if plant else None,
            "request_status": request.get("status") if request else None,
        })
    return {
        "configured": True,
        "places": places_out,
        "next_page_token": payload.get("nextPageToken"),
        "query": query,
    }


@router.post("/rmc-plants/{place_id}/request-listing")
async def request_rmc_listing(
    place_id: str = Path(min_length=1, max_length=512, pattern=r"^[A-Za-z0-9._:-]+$"),
    ctx: dict = Depends(current_user),
):
    """Submit a Google RMC business for Authority review without auto-publishing it."""
    if not _key():
        raise HTTPException(409, "Maps NOT_CONFIGURED")

    plant = await plants.find_one({"google_place_id": place_id})
    if plant:
        return {"status": "REGISTERED", "plant_id": str(plant["_id"])}

    existing = await plant_listing_requests.find_one({"google_place_id": place_id})
    if existing and existing.get("status") in ("PENDING", "APPROVED"):
        return {"status": existing.get("status"), "request_id": str(existing["_id"])}

    detail = await _fetch_place_detail(place_id)
    now = datetime.now(timezone.utc)
    payload = {
        "google_place_id": place_id,
        "name": detail.get("name"),
        "address": detail.get("address"),
        "city": detail.get("city"),
        "district": detail.get("district"),
        "lat": detail.get("lat"),
        "lng": detail.get("lng"),
        "contact_phone": detail.get("contact_phone"),
        "google_maps_uri": detail.get("google_maps_uri"),
        "business_status": detail.get("business_status"),
        "source": "google_places",
        "status": "PENDING",
        "requested_by": ctx["user_id"],
        "requested_role": ctx.get("role"),
        "claim_requested": ctx.get("role") == "plant_owner",
        "updated_at": now,
    }
    if existing:
        await plant_listing_requests.update_one({"_id": existing["_id"]}, {"$set": payload})
        request_id = str(existing["_id"])
    else:
        payload["created_at"] = now
        result = await plant_listing_requests.insert_one(payload)
        request_id = str(result.inserted_id)

    await write_audit(
        ctx["user_id"],
        "plant_listing.request",
        "plant_listing_request",
        request_id,
        {"google_place_id": place_id},
    )
    return {"status": "PENDING", "request_id": request_id}


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
