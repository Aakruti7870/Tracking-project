# Codex Production Hardening Handoff

## 1. Branch
`codex/production-hardening-parallel`

## 2. Base SHA
`0e67bec8d787d638badfed06f4f55ade719260e5` (the repository contained no `main` ref or remote; this was the only supplied branch tip).

## 3. Final SHA
See `git rev-parse HEAD` after the handoff commit (a commit cannot contain its own SHA).

## 4. Files changed
Backend database/models/order service, driver/staff/storage routers, focused unit tests; Expo config, trip/POD/order upload client; production-readiness CI.

## 5. Initial security findings
- ✅ already safe: customer order/detail/challan/tracking queries include `customer_id`; driver trip operations include `driver_id`; owner order/invoice queries use owned plant IDs.
- ⚠️ incomplete: state changes used read-before-write; validation was permissive; indexes covered only OTP/session expiration and identifiers.
- ❌ production blocker: staff without `plant_id` fell back to every plant; storage downloads required authentication but no object authorization; JWT query parameters were supported; POD was overwriteable; UI did not collect GPS.

## 6. RBAC findings
Staff tenant lookup now fails closed when a non-platform staff account lacks a plant. Existing scoped order, vehicle, driver, invoice, quality, material and inventory queries were retained. Authority and Central Admin remain explicitly platform scoped. Owner and customer guards already return generic 404s.

## 7. IDOR tests
Code audit covered customer order/POD/tracking/challan, driver trip/location/POD, plant order/vehicle/driver/payment/quality/inventory, and storage relationships. Automated validation regressions were added. Full HTTP IDOR matrix remains required because the supplied environment cannot install backend dependencies or start MongoDB.

## 8. Atomic state transition changes
Order transitions now compare-and-set `_id + expected status`; concurrent losers receive 409 unless the target is already reached. Driver transitions compare-and-set assigned driver and expected status, with a guarded compensation marker if the corresponding order transition fails on standalone MongoDB.

## 9. POD changes
POD submission claims the assigned active trip, bounds delivered quantity to 110% of the order, inserts rather than overwrites, rejects conflicting repeats, permits an identical finalized retry, and compensates guarded failures. Unique trip and order indexes prevent duplicate PODs.

## 10. Storage authorization changes
Uploads are limited to assigned drivers and active POD trips. JPEG/PNG/WebP MIME, extension, size and magic bytes are verified. Random object names and Mongo metadata bind owner, purpose, order, trip and plant. Downloads authorize owner, owning customer, owning plant owner, or same-plant staff, return generic errors, and reject JWT query strings.

## 11. Mongo indexes
Added query indexes for users/sessions/plants/orders/KYC/history/notifications/vehicles/trips/challans/POD/attendance/incidents/invoices/payments/batches/locations/materials/stock/quality/storage. Unique indexes cover KYC `(user,purpose)`, trip order, POD trip/order, challan order and attendance `(driver,date)`. Integration must assess/deduplicate legacy data before index creation.

## 12. GPS implementation
Expo Location foreground permission and service checks start one balanced-accuracy watcher for active trip states (15 seconds/25 metres), post to the assigned-trip endpoint, display last update/error, and remove the watcher on terminal/change/unmount/logout.

## 13. Android permission changes
Added only `ACCESS_FINE_LOCATION` and `ACCESS_COARSE_LOCATION`, plus foreground descriptions. No background permission or package-ID change.

## 14. CI changes
Added backend compile/pytest, frontend Yarn lint/TypeScript/Expo config/doctor, and tracked-secret filename rejection. No deploy, signing, AAB, or release step.

## 15. Exact test commands / 16. Results
- `python -m compileall -q backend` — PASS (0 errors).
- `python -m pip install -r backend/requirements.txt` — BLOCKED: dependency asset proxy returned HTTP 403.
- `PYTHONPATH=backend pytest -c /dev/null -q backend/tests/test_security_hardening_unit.py` — BLOCKED: Pydantic unavailable because installation failed (0 collected).
- `./node_modules/.bin/tsc --noEmit` (frontend) — FAIL: 20 pre-existing type errors plus missing newly declared `expo-location` because network installation was blocked.
- `npm run lint -- --max-warnings=0` (frontend) — FAIL: 3 existing errors, 29 warnings; one new missing-module error until install.
- `./node_modules/.bin/expo config --type public` (frontend) — BLOCKED: `expo-location` could not be downloaded in this environment.
- `yarn install` (frontend) — BLOCKED: registry proxy HTTP 403.

Pass/fail totals: 1 passed check; 2 failed codebase checks; 4 environment-blocked checks. Automated test cases added: 10 parameterized validation cases; not executed here.

## 17. External/device verification still required
- IMPLEMENTED — REQUIRES REAL DEVICE VERIFICATION: foreground GPS permission, lifecycle and transit updates.
- IMPLEMENTED — EXTERNAL SERVICE NOT VERIFIED: object storage, Twilio SMS state retry, Google Routes.
- Mongo replica-set transaction behavior was not assumed; compensation guards are used.

## 18. Integration conflicts to watch
Database unique indexes can fail on legacy duplicates. Integration branch changes to server startup must continue calling `ensure_indexes`. Storage metadata does not authorize historical unregistered objects; migrate them deliberately. Install `expo-location` and produce the canonical lockfile before merge.

## 19. Files intentionally not modified
`backend/config.py`, `backend/server.py`, Android package identifiers, visual theme, signing/deployment configuration, `test_result.md`, and `BUILD_REPORT.md`.

## Integration Agent Required Changes
- Confirm hardened production bootstrap still invokes `database.ensure_indexes()` and handle duplicate-data migration before unique indexes.
- Add a one-time migration/backfill for historical POD storage object metadata or intentionally make old objects inaccessible.
- Resolve existing frontend TypeScript/lint baseline errors and commit the Yarn lockfile after installing Expo Location.
- Run the full horizontal IDOR HTTP matrix and Mongo concurrency suite against an isolated database.

## 20. Recommended merge order
Merge this PR into `fix/production-readiness-final` after the integration agent's config/server work, resolve startup/index integration, run migration checks and full tests, then perform final architecture review. Do not merge to main until real-device GPS and external storage/SMS validation pass.
