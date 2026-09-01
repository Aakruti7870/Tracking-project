"""Application API — FastAPI entrypoint for the Tracking-project repository.

Layered architecture: config -> database -> models -> security/rbac -> services
-> routers. All product/business routes are mounted under /api.
"""
import logging
import os

from fastapi import APIRouter, Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware

from config import settings
from database import ensure_indexes
from notifications import provider_status
from roles import Role
from security import require_role
from request_security import RateLimitMiddleware, unhandled_error_handler, validation_error_handler
from routers import (
    account_deletion,
    auth,
    business_ui,
    customer,
    driver,
    finance_ops,
    hr_master,
    kyc_recovery,
    loads,
    maps,
    master_data,
    me,
    notify,
    operator_ops,
    owner,
    payroll_closure,
    payroll_concurrency_hotfix,
    payroll_guard,
    permanent_access,
    plant_plans,
    plant_discovery,
    plant_onboarding,
    play_review,
    public_policy,
    staff,
    staff_auth,
    staff_mfa,
    staff_passkeys,
    storage,
    workforce,
    workforce_reports,
    workforce_roster,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("trackmyrmc")

app = FastAPI(
    title="TrackMyRMC API",
    version="2.0.4",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
    openapi_url="/openapi.json" if settings.is_dev else None,
)
app.add_exception_handler(Exception, unhandled_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_middleware(RateLimitMiddleware)


@app.get("/.well-known/assetlinks.json", include_in_schema=False)
async def android_asset_links():
    fingerprint = os.getenv("PLAY_SIGNING_SHA256", "").strip().upper()
    if not fingerprint:
        return JSONResponse(status_code=503, content={"detail": "App Link verification is not configured"})
    return [{
        "relation": [
            "delegate_permission/common.handle_all_urls",
            "delegate_permission/common.get_login_creds",
        ],
        "target": {
            "namespace": "android_app",
            "package_name": "com.trackmyrmc.concreteking",
            "sha256_cert_fingerprints": [fingerprint],
        },
    }]


@app.get("/kyc/return", response_class=HTMLResponse, include_in_schema=False)
async def kyc_return():
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


app.include_router(public_policy.router)
app.include_router(meta)
# These exact-route overrides must be registered before the normal auth/customer
# routers so permanent Google Play demo credentials and DigiLocker finalization
# use the production login/UI paths on both web and Android.
app.include_router(permanent_access.router)
app.include_router(auth.router)
app.include_router(staff_auth.router)
app.include_router(staff_mfa.router)
app.include_router(staff_passkeys.router)
app.include_router(play_review.router)
app.include_router(me.router)
app.include_router(account_deletion.router)
app.include_router(customer.router)
app.include_router(owner.router)
app.include_router(plant_plans.router)
app.include_router(driver.router)
app.include_router(staff.router)
app.include_router(kyc_recovery.router)
app.include_router(operator_ops.router)
app.include_router(master_data.router)
app.include_router(payroll_guard.router)
app.include_router(finance_ops.router)
app.include_router(business_ui.router)
app.include_router(hr_master.router)
app.include_router(workforce_roster.attendance_router)
app.include_router(workforce.router)
app.include_router(workforce_roster.router)

payroll_period_guard_access = require_role(Role.PLANT_OWNER.value, Role.ACCOUNTANT.value)


async def ensure_payroll_mutation_period_open(
    plant_id: str,
    month: str,
    ctx: dict = Depends(payroll_period_guard_access),
):
    del ctx
    await payroll_closure._ensure_period_mutable(plant_id, month)


guarded_payroll_mutations = APIRouter(dependencies=[Depends(ensure_payroll_mutation_period_open)])
guarded_payroll_mutations.include_router(payroll_concurrency_hotfix.router)
app.include_router(guarded_payroll_mutations)
app.include_router(workforce_reports.router)
app.include_router(payroll_closure.router)
app.include_router(loads.router)
app.include_router(notify.router)
app.include_router(maps.router)
app.include_router(plant_discovery.router)
app.include_router(plant_onboarding.router)
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
    await hr_master.ensure_indexes()
    await workforce.ensure_indexes()
    await workforce_roster.ensure_indexes()
    await workforce_reports.ensure_indexes()
    await payroll_closure.ensure_indexes()
    # Production-safe and idempotent: registers the two permanent support
    # Authority identities and upgrades only legacy DigiLocker-success PENDING
    # records to VERIFIED. It does not grant the support accounts a demo OTP.
    await permanent_access.ensure_permanent_access()
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
