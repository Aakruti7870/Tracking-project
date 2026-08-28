"""Public Plant Partner onboarding for unapproved Plant Staff emails.

Requests are inserted into the existing Authority plant-listing review queue so
there is still one approval source of truth. Approval never happens here.
"""
import asyncio
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from audit import write_audit
from database import next_sequence, plant_listing_requests, plants
from roles import Role
from routers.auth import _find_login_user
from routers.maps import _key, _place_summary
from security import normalize_identifier

router = APIRouter(prefix="/api/plant-onboarding", tags=["plant-onboarding"])


class PlantOnboardingBody(BaseModel):
    owner_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    mobile: str = Field(min_length=10, max_length=32)
    plant_name: str = Field(min_length=2, max_length=160)
    address: str = Field(min_length=3, max_length=500)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    google_place_id: str | None = Field(default=None, max_length=256)


async def _send_support_email(destination: str, subject: str, message: str) -> bool:
    api_key = os.getenv("EMAIL_PROVIDER_API_KEY", "").strip()
    sender = os.getenv("EMAIL_FROM", "").strip()
    if not api_key or not sender or not destination:
        return False
    payload = {
        "personalizations": [{"to": [{"email": destination}]}],
        "from": {"email": sender, "name": "TrackMyRMC"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": message}],
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        return 200 <= response.status_code < 300
    except Exception:
        return False


def _send_whatsapp_sync(destination: str, message: str) -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    sender = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
    if not sid or not token or not sender or not destination:
        return False
    try:
        from twilio.rest import Client

        client = Client(sid, token)
        to_value = destination if destination.startswith("whatsapp:") else f"whatsapp:+{destination.lstrip('+')}"
        from_value = sender if sender.startswith("whatsapp:") else f"whatsapp:{sender}"
        client.messages.create(to=to_value, from_=from_value, body=message)
        return True
    except Exception:
        return False


async def _notify_trackmyrmc(message: str) -> dict:
    support_email = os.getenv("ONBOARDING_SUPPORT_EMAIL", "support@trackmyrmc.com").strip()
    whatsapp_to = os.getenv("ONBOARDING_WHATSAPP_TO", "919594177870").strip()
    email_sent, whatsapp_sent = await asyncio.gather(
        _send_support_email(support_email, "New TrackMyRMC Plant Onboarding Request", message),
        asyncio.to_thread(_send_whatsapp_sync, whatsapp_to, message),
    )
    return {"email": bool(email_sent), "whatsapp": bool(whatsapp_sent)}


@router.get("/places")
async def search_places(
    q: str = Query(min_length=3, max_length=120),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
):
    """Public, bounded Places search used only by the onboarding form."""
    key = _key()
    if not key:
        return {"configured": False, "places": []}
    body: dict = {
        "textQuery": q.strip(),
        "pageSize": 6,
        "languageCode": "en",
        "regionCode": "IN",
    }
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 50000.0,
            }
        }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(
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
    if response.status_code >= 400:
        raise HTTPException(502, "Location search is temporarily unavailable")
    places = [summary for item in (response.json().get("places") or []) if (summary := _place_summary(item))]
    return {"configured": True, "places": places}


@router.post("/requests")
async def submit_onboarding(body: PlantOnboardingBody):
    email_channel, email = normalize_identifier(body.email)
    if email_channel != "email":
        raise HTTPException(422, "Enter a valid email address")

    mobile_input = body.mobile.strip()
    mobile_digits = "".join(ch for ch in mobile_input if ch.isdigit())
    if len(mobile_digits) == 10:
        mobile_input = f"+91{mobile_digits}"
    phone_channel, mobile = normalize_identifier(mobile_input)
    if phone_channel != "sms":
        raise HTTPException(422, "Enter a valid mobile number")

    existing_user = await _find_login_user("email", email)
    if existing_user:
        raise HTTPException(409, "This email already has a TrackMyRMC account. Use the appropriate login flow.")

    pending = await plant_listing_requests.find_one(
        {"source": "self_onboarding", "applicant_email": email, "status": "PENDING"}
    )
    if pending:
        return {
            "status": "PENDING",
            "request_id": pending.get("request_number") or str(pending["_id"]),
            "message": "Your onboarding request is already awaiting review.",
        }

    place_id = (body.google_place_id or "").strip() or None
    if place_id:
        if await plants.find_one({"google_place_id": place_id}):
            raise HTTPException(409, "This plant is already registered in TrackMyRMC")
        if await plant_listing_requests.find_one({"google_place_id": place_id, "status": {"$in": ["PENDING", "APPROVED"]}}):
            raise HTTPException(409, "This plant is already under TrackMyRMC review")

    sequence = await next_sequence("plant_onboarding_request")
    request_number = f"TMRMC-ONB-{sequence:06d}"
    review_place_id = place_id or f"onboarding:{request_number.lower()}"
    now = datetime.now(timezone.utc)
    document = {
        "request_number": request_number,
        "google_place_id": review_place_id,
        "name": body.plant_name.strip(),
        "address": body.address.strip(),
        "lat": body.lat,
        "lng": body.lng,
        "contact_phone": mobile,
        "source": "self_onboarding",
        "status": "PENDING",
        "requested_by": None,
        "requested_role": Role.PLANT_OWNER.value,
        "claim_requested": True,
        "applicant_owner_name": body.owner_name.strip(),
        "applicant_email": email,
        "applicant_mobile": mobile,
        "google_place_selected": bool(place_id),
        "created_at": now,
        "updated_at": now,
    }
    result = await plant_listing_requests.insert_one(document)
    request_db_id = str(result.inserted_id)

    await write_audit(
        "public:onboarding",
        "plant_onboarding.submit",
        "plant_listing_request",
        request_db_id,
        {"request_number": request_number, "source": "self_onboarding"},
    )

    support_message = (
        "New TrackMyRMC Plant Onboarding Request\n\n"
        f"Request ID: {request_number}\n"
        f"Owner: {body.owner_name.strip()}\n"
        f"Email: {email}\n"
        f"Mobile: {mobile}\n"
        f"Plant: {body.plant_name.strip()}\n"
        f"Address: {body.address.strip()}\n"
        f"Coordinates: {body.lat:.6f}, {body.lng:.6f}\n"
        "Status: PENDING Authority review"
    )
    delivery = await _notify_trackmyrmc(support_message)
    await plant_listing_requests.update_one(
        {"_id": result.inserted_id},
        {"$set": {"support_notification": delivery, "updated_at": datetime.now(timezone.utc)}},
    )

    return {
        "status": "PENDING",
        "request_id": request_number,
        "message": "Your TrackMyRMC onboarding request has been submitted for review.",
        "support_notified": delivery,
    }
