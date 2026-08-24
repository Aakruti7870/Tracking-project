"""Application API — FastAPI entrypoint for the Tracking-project repository.

Layered architecture: config -> database -> models -> security/rbac -> services
-> routers. All product/business routes are mounted under /api.
"""
import logging
import os

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware

from config import settings
from database import ensure_indexes
from notifications import provider_status
from routers import (
    account_deletion,
    auth,
    business_ui,
    customer,
    driver,
    finance_ops,
    loads,
    maps,
    master_data,
    me,
    notify,
    operator_ops,
    owner,
    plant_discovery,
    staff,
    storage,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("trackmyrmc")

app = FastAPI(
    title="TrackMyRMC API",
    version="2.0.3",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
    openapi_url="/openapi.json" if settings.is_dev else None,
)



@app.get("/.well-known/assetlinks.json", include_in_schema=False)
async def android_asset_links():
    fingerprint = os.getenv("PLAY_SIGNING_SHA256", "").strip().upper()
    if not fingerprint:
        return JSONResponse(status_code=503, content={"detail": "App Link verification is not configured"})
    return [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.trackmyrmc.concreteking",
            "sha256_cert_fingerprints": [fingerprint],
        },
    }]


@app.get("/kyc/return", response_class=HTMLResponse, include_in_schema=False)
async def kyc_return():
    # Android App Links open the installed app before this fallback is served.
    # This page remains useful when consent finishes in a browser without the app.
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Return to TrackMyRMC</title></head>
<body style="font-family:system-ui;background:#101010;color:#fff;display:grid;place-items:center;min-height:100vh;margin:0">
<main style="text-align:center;padding:24px"><h1>KYC consent received</h1>
<p>Return to TrackMyRMC and tap Refresh Status.</p>
<a href="trackmyrmc://kyc" style="color:#dfff62">Open TrackMyRMC</a></main></body></html>"""


@app.get("/health")
async def health_root():
    return {"status": "healthy"}


@app.get("/")
async def root_root():
    return {"service": "TrackMyRMC", "status": "ok"}


meta = APIRouter(prefix="/api")


@meta.get("/")
async def root():
    return {"service": "TrackMyRMC", "status": "ok"}


@meta.get("/health")
async def health():
    return {"status": "healthy", "notifications": provider_status()}


app.include_router(meta)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(account_deletion.router)
app.include_router(customer.router)
app.include_router(owner.router)
app.include_router(driver.router)
app.include_router(staff.router)
app.include_router(operator_ops.router)
app.include_router(master_data.router)
app.include_router(finance_ops.router)
app.include_router(business_ui.router)
app.include_router(loads.router)
app.include_router(notify.router)
app.include_router(maps.router)
app.include_router(plant_discovery.router)
app.include_router(storage.router)

_is_wildcard_cors = "*" in settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=not _is_wildcard_cors,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    try:
        from routers.storage import init_storage

        init_storage()
        logger.info("object storage initialized")
    except Exception as exc:
        logger.warning("object storage init failed (uploads may fail): %s", exc)
    if settings.is_dev:
        from seed import run_seed
        from seed_business import run_business_seed

        try:
            await run_seed()
            await run_business_seed()
        except Exception as exc:
            logger.exception("seed failed: %s", exc)
    logger.info("Tracking-project API started (env=%s)", settings.APP_ENV)
