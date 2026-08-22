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
from routers import auth, customer, driver, me, owner, staff, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("trackmyrmc")

app = FastAPI(title="TrackMyRMC API", version="1.0.0")

# Health / meta
meta = APIRouter(prefix="/api")


@meta.get("/")
async def root():
    return {"service": "TrackMyRMC", "status": "ok"}


@meta.get("/health")
async def health():
    return {
        "status": "healthy",
        "env": settings.APP_ENV,
        "notifications": provider_status(),
    }


app.include_router(meta)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(customer.router)
app.include_router(owner.router)
app.include_router(driver.router)
app.include_router(staff.router)
app.include_router(storage.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
