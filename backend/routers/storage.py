"""Authenticated object-storage helpers and upload/serve routes.

Production uses the configured remote object store. CI/development may opt into
STORAGE_MODE=local for deterministic tests without external credentials.
"""
from io import BytesIO
import mimetypes
import os
from pathlib import Path, PurePosixPath
import uuid

import requests
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from config import settings
from database import orders, plants, proof_of_delivery
from security import current_user

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_MODE = os.environ.get("STORAGE_MODE", "remote").strip().lower()
LOCAL_STORAGE_DIR = Path(os.environ.get("LOCAL_STORAGE_DIR", "/tmp/trackmyrmc-storage"))
APP_NAME = "trackmyrmc"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}

_storage_key = None


def init_storage():
    global _storage_key
    if STORAGE_MODE == "local":
        if not settings.is_dev:
            raise RuntimeError("Local object storage is development/test only")
        LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        return "local"
    if STORAGE_MODE != "remote":
        raise RuntimeError("Unsupported STORAGE_MODE")
    if _storage_key:
        return _storage_key
    if not EMERGENT_KEY:
        raise RuntimeError("Object storage is not configured")
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _local_path(path: str) -> Path:
    _validate_object_path(path)
    candidate = (LOCAL_STORAGE_DIR / Path(*PurePosixPath(path).parts)).resolve()
    root = LOCAL_STORAGE_DIR.resolve()
    if root not in candidate.parents:
        raise RuntimeError("Invalid storage path")
    return candidate


def _put(path: str, data: bytes, content_type: str) -> dict:
    global _storage_key
    if STORAGE_MODE == "local":
        init_storage()
        destination = _local_path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return {"path": path, "content_type": content_type}

    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 503:
        _storage_key = None
        key = init_storage()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def _get(path: str) -> tuple[bytes, str]:
    global _storage_key
    if STORAGE_MODE == "local":
        init_storage()
        source = _local_path(path)
        if not source.is_file():
            raise FileNotFoundError(path)
        return source.read_bytes(), mimetypes.guess_type(source.name)[0] or "application/octet-stream"

    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60
    )
    if resp.status_code == 503:
        _storage_key = None
        key = init_storage()
        resp = requests.get(
            f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60
        )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def _validate_object_path(path: str) -> None:
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts:
        raise HTTPException(404, "File not found")
    if len(p.parts) < 4 or p.parts[0] != APP_NAME or p.parts[1] != "uploads":
        raise HTTPException(404, "File not found")


def _validate_image(data: bytes) -> tuple[str, str]:
    if not data:
        raise HTTPException(422, "Empty image upload")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 8MB)")
    try:
        with Image.open(BytesIO(data)) as image:
            fmt = (image.format or "").upper()
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "Invalid image file")
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(422, "Only JPEG, PNG or WebP images are allowed")
    return ALLOWED_IMAGE_FORMATS[fmt]


def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


async def _can_read_path(ctx: dict, path: str) -> bool:
    """Authorize file access using uploader ownership or the POD/order relation."""
    _validate_object_path(path)
    uploader_id = PurePosixPath(path).parts[2]
    if uploader_id == ctx["user_id"]:
        return True
    if ctx.get("role") == "central_admin":
        return True

    pod = await proof_of_delivery.find_one({"photo_path": path})
    if not pod:
        return False
    order = await orders.find_one({"_id": _oid(pod.get("order_id"))})
    if not order:
        return False

    role = ctx.get("role")
    if role == "customer":
        return order.get("customer_id") == ctx["user_id"]
    if role == "driver":
        return pod.get("driver_id") == ctx["user_id"]
    if role == "plant_owner":
        plant = await plants.find_one(
            {"_id": _oid(order.get("plant_id")), "owner_id": ctx["user_id"]}
        )
        return plant is not None

    return bool(ctx.get("plant_id") and ctx.get("plant_id") == order.get("plant_id"))


router = APIRouter(prefix="/api", tags=["storage"])


@router.post("/upload")
async def upload(file: UploadFile = File(...), ctx: dict = Depends(current_user)):
    data = await file.read()
    ext, detected_content_type = _validate_image(data)
    path = f"{APP_NAME}/uploads/{ctx['user_id']}/{uuid.uuid4().hex}.{ext}"
    try:
        await run_in_threadpool(_put, path, data, detected_content_type)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Upload service unavailable")
    return {"path": path}


@router.get("/files/{path:path}")
async def files(
    path: str,
    token: str = Query(default="", max_length=4096),
    authorization: str = Header(default=""),
):
    auth_header = authorization or (f"Bearer {token}" if token else "")
    try:
        ctx = await current_user(authorization=auth_header)
    except HTTPException:
        raise HTTPException(401, "Unauthorized")
    if not await _can_read_path(ctx, path):
        raise HTTPException(404, "File not found")
    try:
        content, ct = await run_in_threadpool(_get, path)
    except Exception:
        raise HTTPException(404, "File not found")
    return Response(
        content=content,
        media_type=ct,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )
