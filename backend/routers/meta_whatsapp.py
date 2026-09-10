import hashlib
import hmac
import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter(
    prefix="/api/meta/whatsapp",
    tags=["meta-whatsapp"],
)


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_meta_whatsapp_webhook(
    mode: str = Query(alias="hub.mode"),
    verify_token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
):
    expected = os.getenv("META_WHATSAPP_VERIFY_TOKEN", "").strip()

    if (
        mode == "subscribe"
        and expected
        and hmac.compare_digest(verify_token, expected)
    ):
        return PlainTextResponse(challenge, status_code=200)

    raise HTTPException(
        status_code=403,
        detail="Meta WhatsApp webhook verification failed",
    )


@router.post("/webhook")
async def receive_meta_whatsapp_webhook(request: Request):
    app_secret = os.getenv("META_APP_SECRET", "").strip()

    if not app_secret:
        raise HTTPException(
            status_code=503,
            detail="META_APP_SECRET is not configured",
        )

    raw_body = await request.body()
    received_signature = request.headers.get("X-Hub-Signature-256", "")
    expected_signature = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if (
        not received_signature
        or not hmac.compare_digest(received_signature, expected_signature)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Meta webhook signature",
        )

    return JSONResponse({"status": "received"}, status_code=200)
