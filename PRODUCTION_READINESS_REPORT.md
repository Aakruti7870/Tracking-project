# TrackMyRMC — Production Readiness Report

_Reconciled: 2026-08-22_

> Repository: `Aakruti7870/Tracking-project`  
> Hardening branch: `fix/production-readiness-final`  
> Pull request: #1  
> Scope: production hardening and build readiness only. No merge, production deploy, Play upload, or signing-key replacement is authorized by this report.

## 1. Readiness decision

### Code / CI readiness
**PASS for review / isolated preview deployment.**

The hardening branch now passes the repository-controlled validation gates for backend, frontend, secret hygiene, Expo native generation, Android identity/version generation, and a native Android debug compile.

### Runtime preview readiness
**EXTERNAL DEPLOYMENT REQUIRED.**

A working FastAPI + MongoDB preview backend URL does not currently exist in the repository configuration. The previously referenced Emergent preview host was tested and returned HTTP 404 for `/api/health`, so it was deliberately rejected instead of being embedded in a preview build.

### Production / Google Play readiness
**NOT YET AUTHORIZED.**

Production release still requires external verification of the real deployment, physical-device background GPS behavior, Google Play signing/update lineage, live provider credentials, and the final Play versionCode before a signed AAB is produced or uploaded.

## 2. Verified CI evidence

### Backend
- Python dependency installation: PASS.
- Python compile/import validation: PASS.
- Focused production-hardening unit tests: PASS.
- FastAPI boot + `/api/health`: PASS against CI MongoDB.
- Full backend integration suite: **154 passed, 2 skipped, 0 failed**.
- The suite covers authentication, OTP controls, customer/owner flows, staff dashboards/actions, dispatcher workflow/RBAC, order lifecycle, driver/POD, storage authorization, production, billing, tracking and related regression scenarios.

### Frontend
- TypeScript: PASS.
- Expo lint: PASS.
- Expo Doctor: PASS.
- Public Expo config validation: PASS.
- Expo web preview build: PASS.

### Android native
- Expo Android prebuild: PASS.
- Generated package check: **`com.trackmyrmc.concreteking`** PASS.
- Generated versionCode check: **61** PASS.
- Native Gradle `:app:assembleDebug`: PASS.
- APK publication is intentionally disabled until `PREVIEW_BACKEND_URL` points to a verified backend.

### Repository security
- Tracked secret/signing file guard: PASS.
- Private-key material scan: PASS.
- No unresolved PR review threads were present at reconciliation time.

## 3. Android identity

Current Android application configuration:

- App name: `TrackMyRMC`
- Version name: **2.0.3**
- Android package/application ID: **`com.trackmyrmc.concreteking`**
- Android versionCode: **61**
- App scheme: `trackmyrmc`

The package ID is only the Android application identity. It does not connect the app to a Concrete King website or webpage.

Before a Play release, the actual Play Console highest versionCode and existing upload/app-signing certificate lineage must still be verified. No new keystore is generated or committed by this branch.

## 4. Backend configuration model

The mobile/web client does not hardcode a runtime backend in application logic. It reads:

`EXPO_PUBLIC_BACKEND_URL`

For CI preview builds, the workflow reads the repository variable:

`PREVIEW_BACKEND_URL`

Behavior:
- if `PREVIEW_BACKEND_URL` is configured, CI calls `<url>/api/health` and fails if the backend is not healthy;
- if it is absent, CI performs build-only validation using a non-routable placeholder;
- an installable preview APK artifact is published only when a verified preview backend is configured.

The template production target is `https://api.trackmyrmc.com`, but it must not be treated as active for this new FastAPI/Mongo stack until that hostname is actually deployed/mapped and `/api/health` is verified.

## 5. Security / backend hardening completed

- Production fails closed for missing/unsafe JWT secret and OTP pepper.
- Debug OTP is forbidden in production.
- Production CORS requires explicit origins; wildcard production CORS is rejected.
- Roles are resolved server-side; client/JWT role claims are not trusted as authorization truth.
- Plant-scoped staff fail closed when no plant is assigned.
- Staff/driver/customer/owner access is server-scoped to the appropriate tenant/ownership relationship.
- Order status transitions use compare-and-set protections and reject conflicting transitions.
- Driver/POD flow has state guards, idempotency protections and compensation/rollback handling.
- POD photo/signature requirements are enforced.
- Object uploads are byte/type/size validated and authorized using stored object metadata.
- File reads require authenticated relationship-based authorization; JWT query-string file access is not used.
- Mongo indexes enforce critical uniqueness and query invariants.
- OTP resend/attempt/consumption races are hardened.
- Twilio SMS and SendGrid email adapters are present with safe error/log handling.
- Google Maps/Places/Geocoding/Routes proxy keeps server credentials server-side and does not fabricate ETA when Routes is unavailable.

## 6. Role coverage

All 13 roles remain represented:
Customer, Driver, Plant Owner, Admin, Dispatcher, Operator, Supervisor, Accountant, Quality Engineer, Fleet Manager, Store Manager, Authority and Central Admin.

Platform-wide roles remain Authority/Central Admin where intended; plant staff remain tenant-scoped.

## 7. GPS / Android permissions

The Android configuration includes foreground and background delivery-location support with a foreground service. The tracking task is registered at module scope and active-trip location updates are authenticated to the driver trip API.

**Still external:** a physical Android device test is required for background/minimized/locked-screen tracking and Google Play background-location policy compliance. A successful compile is not a substitute for this test.

## 8. KYC

Current KYC in this new stack is a **manual Authority review flow**. It must not be represented as automatic DigiLocker verification.

Authority-only review controls, server-side order gating, audit logging and KYC uniqueness are present. Real DigiLocker/Sandbox OAuth/API integration remains an external future integration unless explicitly added later.

## 9. External/runtime items intentionally not claimed as verified

The following require a deployed environment, provider account, device, or Play Console and therefore are not faked by repository CI:

1. Stable preview FastAPI/Mongo backend URL.
2. Production MongoDB deployment/restart/data-integrity verification.
3. Physical Android foreground/background GPS verification.
4. Live Twilio SMS delivery using production credentials.
5. Live SendGrid staff-email OTP using a verified sender.
6. Google Maps Platform production key restrictions/billing/API enablement, including Routes.
7. Google Play signing/upload-key lineage and final highest versionCode check.
8. Automated DigiLocker integration, if required.

## 10. Next controlled step

The next safe step is **isolated preview deployment only** from `fix/production-readiness-final` using the current FastAPI + MongoDB stack. The deployer must return one stable HTTPS backend base URL whose `/api/health` returns HTTP 200.

After that URL is available, set it as `PREVIEW_BACKEND_URL`, rerun Production Readiness, publish the connected debug APK artifact, and perform the visual/device preview. Production merge/deploy and Play upload remain separate explicit approvals.
