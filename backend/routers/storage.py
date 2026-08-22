"""Emergent Object Storage helpers + upload/serve routes."""
import os
import uuid
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from database import driver_trips, orders, plants, storage_objects
from roles import Role
from security import current_user

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "trackmyrmc"

_storage_key = None


def init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _put(path: str, data: bytes, content_type: str) -> dict:
    global _storage_key
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if resp.status_code == 503:
        _storage_key = None
        key = init_storage()
        resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _get(path: str) -> tuple[bytes, str]:
    global _storage_key
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 503:
        _storage_key = None
        key = init_storage()
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


router = APIRouter(prefix="/api", tags=["storage"])


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    purpose: str = Form(default="POD"),
    trip_id: str = Form(default=""),
    ctx: dict = Depends(current_user),
):
    if purpose != "POD" or ctx["role"] != Role.DRIVER.value or not trip_id:
        raise HTTPException(403, "Upload is not permitted")
    trip = await driver_trips.find_one({"_id": _oid(trip_id), "driver_id": ctx["user_id"]})
    if not trip or trip.get("status") not in ("ARRIVED", "UNLOADING", "POD_PENDING"):
        raise HTTPException(404, "Active trip not found")
    ct = file.content_type or "application/octet-stream"
    allowed = {"image/jpeg": ("jpg", "jpeg"), "image/png": ("png",), "image/webp": ("webp",)}
    if ct not in allowed:
        raise HTTPException(422, "Only image uploads are allowed")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in allowed[ct]:
        raise HTTPException(422, "File extension does not match image type")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 8MB)")
    signatures = {
        "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
        "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    }
    if not signatures[ct](data):
        raise HTTPException(422, "Invalid image data")
    path = f"{APP_NAME}/pod/{uuid.uuid4().hex}.{ext}"
    try:
        await run_in_threadpool(_put, path, data, ct)
    except Exception:
        raise HTTPException(502, "Upload failed")
    await storage_objects.insert_one({
        "path": path, "owner_user_id": ctx["user_id"], "purpose": purpose,
        "trip_id": trip_id, "order_id": trip.get("order_id"),
        "plant_id": trip.get("plant_id"), "content_type": ct,
        "created_at": datetime.now(timezone.utc),
    })
    return {"path": path}


@router.get("/files/{path:path}")
async def files(path: str, authorization: str = Header(default="")):
    # Do not accept JWTs in query strings: URLs leak through history and logs.
    ctx = await current_user(authorization=authorization)
    meta = await storage_objects.find_one({"path": path})
    if not meta:
        raise HTTPException(404, "File not found")
    allowed = meta.get("owner_user_id") == ctx["user_id"]
    if ctx["role"] == Role.CUSTOMER.value:
        allowed = bool(await orders.find_one({"_id": _oid(meta.get("order_id")), "customer_id": ctx["user_id"]}))
    elif ctx["role"] in {Role.PLANT_OWNER.value, Role.ADMIN.value, Role.DISPATCHER.value,
                         Role.OPERATOR.value, Role.SUPERVISOR.value, Role.ACCOUNTANT.value,
                         Role.QUALITY_ENGINEER.value, Role.FLEET_MANAGER.value, Role.STORE_MANAGER.value}:
        if ctx["role"] == Role.PLANT_OWNER.value:
            allowed = bool(await plants.find_one({"_id": _oid(meta.get("plant_id")), "owner_id": ctx["user_id"]}))
        else:
            allowed = bool(ctx.get("plant_id") and ctx["plant_id"] == meta.get("plant_id"))
    if not allowed:
        raise HTTPException(404, "File not found")
    try:
        content, ct = await run_in_threadpool(_get, path)
    except Exception:
        raise HTTPException(404, "File not found")
    return Response(content=content, media_type=ct)


def _oid(value: str):
    from bson import ObjectId
    try:
        return ObjectId(value)
    except Exception:
        return value
