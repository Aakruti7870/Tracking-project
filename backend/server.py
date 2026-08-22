"""TrackMyRMC API — FastAPI entrypoint.

Layered architecture: config -> database -> models -> security/rbac ->
services (notifications/audit) -> routers. All routes are mounted under /api.
"""
import logging

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from config import settings
from database import ensure_indexes
from notifications import provider_status
from routers import auth, customer, driver, maps, me, notify, owner, staff, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("trackmyrmc")

# Do not expose interactive API documentation by default in production.
app = FastAPI(
    title="TrackMyRMC API",
    version="1.0.0",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
    openapi_url="/openapi.json" if settings.is_dev else None,
)

# Health / meta
meta = APIRouter(prefix="/api")


@meta.get("/")
async def root():
    return {"service": "TrackMyRMC", "status": "ok"}


@meta.get("/health")
async def health():
    # Keep health useful without leaking production environment details.
    return {
        "status": "healthy",
        "notifications": provider_status(),
    }


app.include_router(meta)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(customer.router)
app.include_router(owner.router)
app.include_router(driver.router)
app.include_router(staff.router)
app.include_router(notify.router)
app.include_router(maps.router)
app.include_router(storage.router)

_is_wildcard_cors = "*" in settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    # Wildcard CORS is development-only and cannot be combined safely with
    # credentialed cross-origin requests. Native clients use Bearer auth.
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

        try:
            await run_seed()
        except Exception as exc:  # seed failures must be visible, never silent
            logger.exception("seed failed: %s", exc)
    logger.info("TrackMyRMC API started (env=%s)", settings.APP_ENV)
