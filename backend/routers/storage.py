"""Emergent Object Storage helpers + upload/serve routes."""
import os
import uuid

import requests
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from security import current_user, issue_jwt  # noqa: F401 (issue_jwt reused for tokens)

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
async def upload(file: UploadFile = File(...), ctx: dict = Depends(current_user)):
    ct = file.content_type or "application/octet-stream"
    if not ct.startswith("image/"):
        raise HTTPException(422, "Only image uploads are allowed")
    ext = (file.filename or "img.jpg").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 8MB)")
    path = f"{APP_NAME}/uploads/{ctx['user_id']}/{uuid.uuid4().hex}.{ext}"
    try:
        await run_in_threadpool(_put, path, data, ct)
    except Exception as exc:
        raise HTTPException(502, f"Upload failed: {exc}")
    return {"path": path}


@router.get("/files/{path:path}")
async def files(path: str, token: str = Query(default=""), authorization: str = ""):
    # Auth via header (native) OR ?token= (web <img>). Both resolve a valid session.
    from security import current_user as _cu
    auth_header = authorization or (f"Bearer {token}" if token else "")
    try:
        await _cu(authorization=auth_header)
    except HTTPException:
        raise HTTPException(401, "Unauthorized")
    try:
        content, ct = await run_in_threadpool(_get, path)
    except Exception:
        raise HTTPException(404, "File not found")
    return Response(content=content, media_type=ct)
