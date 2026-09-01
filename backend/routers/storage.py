"""Authenticated object-storage helpers and upload/serve routes.

Production supports Google Cloud Storage with Cloud Run application-default
credentials. The legacy Emergent remote object store remains available for
compatibility, while CI/development may opt into STORAGE_MODE=local for
deterministic tests without external credentials.

POD uploads are bound to an authenticated driver + active trip and persisted in
Mongo metadata for object-level authorization. File downloads require the
Authorization header; JWTs are never accepted from query strings.
"""
from datetime import datetime, timezone
from io import BytesIO
import mimetypes
import os
from pathlib import Path, PurePosixPath
import uuid

import requests
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from config import settings
from database import driver_trips, orders, plants, proof_of_delivery, storage_objects
from roles import Role
from security import current_user

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_MODE = os.environ.get("STORAGE_MODE", "remote").strip().lower()
GCS_BUCKET = os.environ.get("GCS_BUCKET", "").strip()
LOCAL_STORAGE_DIR = Path(os.environ.get("LOCAL_STORAGE_DIR", "/tmp/trackmyrmc-storage"))
APP_NAME = "trackmyrmc"
ALLOWED_IMAGE_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}

_storage_key = None
_gcs_client = None
_gcs_bucket = None


def init_storage():
    global _storage_key, _gcs_client, _gcs_bucket
    if STORAGE_MODE == "local":
        if not settings.is_dev:
            raise RuntimeError("Local object storage is development/test only")
        LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        return "local"

    if STORAGE_MODE == "gcs":
        if not GCS_BUCKET:
            raise RuntimeError("GCS_BUCKET is not configured")
        if _gcs_bucket is not None:
            return _gcs_bucket
        try:
            from google.cloud import storage as gcs_storage
        except ImportError as exc:
            raise RuntimeError("Google Cloud Storage client is not installed") from exc
        _gcs_client = gcs_storage.Client()
        _gcs_bucket = _gcs_client.bucket(GCS_BUCKET)
        return _gcs_bucket

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


def _validate_object_path(path: str) -> None:
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts:
        raise HTTPException(404, "File not found")
    if len(p.parts) < 3 or p.parts[0] != APP_NAME or p.parts[1] not in {"pod", "uploads"}:
        raise HTTPException(404, "File not found")


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

    if STORAGE_MODE == "gcs":
        bucket = init_storage()
        blob = bucket.blob(path)
        blob.upload_from_string(
            data,
            content_type=content_type,
            if_generation_match=0,
        )
        return {"path": path, "content_type": content_type, "bucket": GCS_BUCKET}

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

    if STORAGE_MODE == "gcs":
        bucket = init_storage()
        blob = bucket.blob(path)
        blob.reload()
        content_type = blob.content_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        return blob.download_as_bytes(), content_type

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


def _validate_image(data: bytes) -> tuple[bytes, str, str]:
    if not data:
        raise HTTPException(422, "Empty image upload")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image exceeds the configured upload limit")
    try:
        with Image.open(BytesIO(data)) as image:
            fmt = (image.format or "").upper()
            if image.width * image.height > settings.MAX_IMAGE_PIXELS:
                raise HTTPException(413, "Image dimensions exceed the configured limit")
            image.load()
            if fmt not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(422, "Only JPEG, PNG or WebP images are allowed")
            # Re-encoding, rather than retaining attacker-controlled bytes,
            # strips metadata and any trailing polyglot/code payload.
            clean = BytesIO()
            save_image = image.convert("RGB") if fmt == "JPEG" else image.copy()
            save_image.save(clean, format=fmt)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "Invalid image file")
    ext, content_type = ALLOWED_IMAGE_FORMATS[fmt]
    return clean.getvalue(), ext, content_type


async def _read_upload_limited(file: UploadFile) -> bytes:
    chunks = []
    size = 0
    while chunk := await file.read(64 * 1024):
        size += len(chunk)
        if size > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image exceeds the configured upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _oid(value: str | None):
    if value is None:
        return None
    try:
        return ObjectId(value)
    except Exception:
        return value


async def _authorized_for_relation(ctx: dict, *, owner_user_id: str | None, order_id: str | None, plant_id: str | None, driver_id: str | None = None) -> bool:
    role = ctx.get("role")
    if owner_user_id and owner_user_id == ctx["user_id"]:
        return True
    if role == Role.CENTRAL_ADMIN.value:
        return True
    if role == Role.DRIVER.value and driver_id:
        return driver_id == ctx["user_id"]

    order = await orders.find_one({"_id": _oid(order_id)}) if order_id else None
    if role == Role.CUSTOMER.value:
        return bool(order and order.get("customer_id") == ctx["user_id"])
    if role == Role.PLANT_OWNER.value:
        pid = plant_id or (order.get("plant_id") if order else None)
        if not pid:
            return False
        return bool(await plants.find_one({"_id": _oid(pid), "owner_id": ctx["user_id"]}))

    scoped_staff = {
        Role.ADMIN.value,
        Role.DISPATCHER.value,
        Role.OPERATOR.value,
        Role.SUPERVISOR.value,
        Role.ACCOUNTANT.value,
        Role.QUALITY_ENGINEER.value,
        Role.FLEET_MANAGER.value,
        Role.STORE_MANAGER.value,
    }
    if role in scoped_staff:
        relation_plant = plant_id or (order.get("plant_id") if order else None)
        return bool(ctx.get("plant_id") and relation_plant and ctx["plant_id"] == relation_plant)
    return False


async def _can_read_path(ctx: dict, path: str) -> bool:
    """Authorize new metadata-backed objects and legacy POD objects securely."""
    _validate_object_path(path)
    meta = await storage_objects.find_one({"path": path})
    if meta:
        return await _authorized_for_relation(
            ctx,
            owner_user_id=meta.get("owner_user_id"),
            order_id=meta.get("order_id"),
            plant_id=meta.get("plant_id"),
            driver_id=meta.get("owner_user_id") if meta.get("purpose") == "POD" else None,
        )

    # Compatibility for older POD rows created before storage metadata existed.
    pod = await proof_of_delivery.find_one({"photo_path": path})
    if not pod:
        return False
    order = await orders.find_one({"_id": _oid(pod.get("order_id"))})
    return await _authorized_for_relation(
        ctx,
        owner_user_id=pod.get("driver_id"),
        driver_id=pod.get("driver_id"),
        order_id=pod.get("order_id"),
        plant_id=order.get("plant_id") if order else None,
    )


router = APIRouter(prefix="/api", tags=["storage"])


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    purpose: str = Form(default="POD"),
    trip_id: str = Form(default=""),
    ctx: dict = Depends(current_user),
):
    if purpose != "POD" or ctx.get("role") != Role.DRIVER.value or not trip_id:
        raise HTTPException(403, "Upload is not permitted")

    trip = await driver_trips.find_one(
        {"_id": _oid(trip_id), "driver_id": ctx["user_id"]}
    )
    if not trip or trip.get("status") not in ("ARRIVED", "UNLOADING", "POD_PENDING"):
        raise HTTPException(404, "Active trip not found")

    data = await _read_upload_limited(file)
    data, ext, detected_content_type = _validate_image(data)
    supplied_type = (file.content_type or "").lower()
    if supplied_type and supplied_type not in {detected_content_type, "application/octet-stream"}:
        raise HTTPException(422, "File content does not match declared image type")

    path = f"{APP_NAME}/pod/{uuid.uuid4().hex}.{ext}"
    try:
        await run_in_threadpool(_put, path, data, detected_content_type)
        await storage_objects.insert_one(
            {
                "path": path,
                "owner_user_id": ctx["user_id"],
                "purpose": "POD",
                "trip_id": str(trip["_id"]),
                "order_id": trip.get("order_id"),
                "plant_id": trip.get("plant_id"),
                "content_type": detected_content_type,
                "size_bytes": len(data),
                "created_at": datetime.now(timezone.utc),
            }
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Upload service unavailable")
    return {"path": path}


@router.get("/files/{path:path}")
async def files(path: str, authorization: str = Header(default="")):
    try:
        ctx = await current_user(authorization=authorization)
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
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": "attachment",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )
