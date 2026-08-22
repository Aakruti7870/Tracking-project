# TrackMyRMC Production Readiness Report

> Branch: `fix/production-readiness-final`  
> PR: #1 (draft, not merged)  
> Scope: production hardening only; no production deploy or Play Console upload.

## Status legend
- ✅ PASS — implemented and verified by code/test evidence available in this branch.
- ⚠️ PARTIAL / EXTERNAL CONFIG REQUIRED — implemented or hardened, but external service/device/production verification remains.
- ❌ BLOCKER — must be resolved before release.

## 1. Architecture
**Status: ✅ PASS (repository architecture identified)**

- Mobile: Expo / React Native / expo-router.
- API: FastAPI.
- Persistence: MongoDB via Motor/PyMongo.
- Auth: passwordless OTP + JWT session records.
- Object media: authenticated object-storage abstraction.
- Maps: server-side Google Places / Geocoding / Routes proxy.

## 2. Role matrix

| Role | Scope | Hardening status |
|---|---|---|
| Customer | own account/orders/tracking/POD | ✅ server-side role + ownership paths present |
| Driver | assigned trips only | ✅ driver_id-scoped trip/location/POD paths |
| Plant Owner | owned plants | ✅ owner_id plant scoping present |
| Admin | assigned plant | ✅ central auth fails closed if plant missing |
| Dispatcher | assigned plant | ✅ central auth fails closed if plant missing |
| Operator | assigned plant | ✅ central auth fails closed if plant missing |
| Supervisor | assigned plant | ✅ central auth fails closed if plant missing |
| Accountant | assigned plant | ✅ central auth fails closed if plant missing |
| Quality Engineer | assigned plant | ✅ central auth fails closed if plant missing |
| Fleet Manager | assigned plant | ✅ central auth fails closed if plant missing |
| Store Manager | assigned plant | ✅ central auth fails closed if plant missing |
| Authority | platform KYC review | ✅ explicit Authority-only action gate present |
| Central Admin | platform user management | ✅ explicit Central-Admin-only action gate present |

**Residual verification:** full live API cross-role/IDOR suite must be green before release.

## 3. Authentication / OTP
**Status: ✅ IMPLEMENTED / TEST EXECUTION PENDING CI**

Hardening in this branch:
- production requires explicit JWT secret and OTP pepper;
- production refuses debug OTP;
- expired sessions are rejected;
- roles are resolved from server-side user data, not trusted from the client/JWT role claim;
- OTP codes expire and are single-use;
- attempts are atomically bounded;
- one active OTP per identifier is enforced;
- resend throttle is enforced;
- expired OTPs are explicitly consumed before resend so Mongo TTL-monitor delay cannot block a new code;
- production OTP request fails closed if provider delivery fails;
- SMS delivery uses Twilio when configured;
- staff email OTP uses SendGrid when `EMAIL_PROVIDER_API_KEY` + `EMAIL_FROM` are configured.

⚠️ Per-IP / distributed edge rate limiting is not implemented in this application layer. Provider/ingress rate limiting is recommended in production in addition to per-identifier controls.

## 4. RBAC / tenant isolation
**Status: ✅ IMPLEMENTED / TEST EXECUTION PENDING CI**

- Plant-scoped staff roles cannot authenticate into staff functionality without `plant_id`; request fails 403.
- Sampled staff order/fleet actions additionally query using plant scope.
- Driver endpoints filter by authenticated `driver_id`.
- Customer and owner endpoints retain ownership/plant scoping.
- Platform-wide access is reserved for Authority/Central Admin according to their modules.

A focused regression test was added for the unassigned-staff fail-closed rule.

## 5. Order state machine
**Status: ✅ IMPLEMENTED / TEST EXECUTION PENDING CI**

- Server remains authoritative.
- Order transitions now use compare-and-set on current status.
- Conflicting concurrent transitions return 409.
- Same-target replays are idempotent.
- Terminal states cannot transition through ordinary workflow edges.
- History/audit is written after successful status change.

⚠️ Order + driver-trip changes are separate Mongo documents. CAS guards reduce concurrency errors, but a process crash between documents can still require reconciliation. A multi-document transaction/reconciliation worker would provide stronger atomicity.

## 6. End-to-end order workflow
**Status: ⚠️ TEST EXECUTION PENDING CI**

Updated integration coverage exercises:
Customer create -> Owner approve -> mixer assign -> driver assign -> challan -> dispatch -> driver start -> location -> arrive -> unload -> POD photo/signature -> delivered -> vehicle available.

The result will only be promoted to PASS after the new CI suite executes successfully.

## 7. Mongo persistence / restart safety
**Status: ⚠️ PARTIAL**

Production-critical records are stored in Mongo collections. This branch adds indexes for auth/session lifecycle, users, plants, orders/history, KYC, notifications/audit, vehicles/trips/location/POD, attendance/incidents, challans, invoices/payments, production, materials/stock and quality.

Unique indexes enforce several application invariants, including one login identifier per account, one active OTP per identifier, one KYC profile per purpose, one trip per order, one POD per trip and one attendance record per driver/day.

⚠️ Production-cluster restart/recovery has not been verified from this repository session.

## 8. Android live GPS
**Status: ⚠️ IMPLEMENTED / REAL DEVICE VERIFICATION REQUIRED**

- Added Expo Location + TaskManager.
- Added foreground/background Android location permissions and foreground location service configuration.
- Background task is registered at JS module scope.
- Active trip stores its trip ID and sends driver-authenticated coordinates to the API.
- Foreground fallback is used if background permission is unavailable.
- Tracking starts only for active delivery states.
- Backend refuses location before trip start and after terminal state.
- Tracking stops after successful POD, logout, or terminal trip state.
- Last-location timestamp is persisted.

❌ A physical Android device/background-process test is required before Play release.

## 9. POD / object media
**Status: ✅ IMPLEMENTED / TEST EXECUTION PENDING CI**

- Site photo + receiver signature are mandatory.
- Images are byte-validated and limited to JPEG/PNG/WebP, max 8 MB.
- Client upload failure no longer silently completes delivery.
- POD photo path must belong to the authenticated driver upload namespace.
- File GET requires an authenticated live session.
- Cross-user file access is authorized via uploader/POD/order/plant relationship.
- Unauthorized object access returns 404 rather than revealing existence.
- CI/dev can use local object storage; production rejects local mode.

## 10. KYC
**Status: ⚠️ PARTIAL / MANUAL AUTHORITY FLOW**

- Existing KYC is manual Authority review.
- Authority-only approve/reject gates are present.
- KYC profile uniqueness is enforced per `(user_id, purpose)`.
- Customer KYC remains server-side gated in the order flow.

⚠️ Real DigiLocker/Sandbox OAuth/API verification is not implemented in this new stack and must not be represented as automatic verified KYC.
⚠️ Reviewer metadata is available in the audit log; the KYC profile itself does not yet store a dedicated reviewer/timestamp transition record.

## 11. Maps / Routes
**Status: ⚠️ APPLICATION READY / GOOGLE CONFIG REQUIRED**

- Google key remains server-side.
- Route coordinates and Places/Geocode inputs are bounded.
- Routes failures return `route_available: false`; ETA/distance are not fabricated.
- Driver navigation opens Google Maps directions using the actual site address.

External requirements:
- enable required Google Maps Platform APIs;
- configure billing;
- restrict the server key appropriately;
- verify Routes API response in production.

## 12. SMS / email
**Status: ⚠️ IMPLEMENTED / LIVE PROVIDER VERIFICATION REQUIRED**

- Twilio SMS adapter is implemented.
- Dispatch/delivery SMS state is retry-aware and guards duplicate concurrent sends.
- SendGrid email OTP adapter is implemented for staff logins.
- Logs mask destination PII and do not expose credentials.

⚠️ Live Twilio and SendGrid delivery have not been verified with production credentials.

## 13. Frontend verification
**Status: ⚠️ CI PENDING**

CI gates added:
- TypeScript `tsc --noEmit`;
- Expo lint;
- Expo Doctor;
- public Expo config validation.

No intentional theme redesign is part of this branch.

## 14. Backend verification
**Status: ⚠️ CI PENDING**

CI gates added:
- clean public dependency installation;
- Python compile/import check;
- focused security regression tests;
- local Mongo-backed FastAPI boot/health;
- full backend integration suite in serial mode.

## 15. Android application identity
**Status: ⚠️ PARTIAL**

Android package is aligned in this branch to:

`com.trackmyrmc.concreteking`

App scheme is `trackmyrmc`.

❌ `versionCode` is intentionally not guessed. The highest code in Play Console must be verified and the next code set above it.
❌ Existing Google Play app-signing / upload-key lineage must be verified. Changing the package ID alone is not sufficient for an update.
❌ No new keystore is generated or committed by this branch.

The iOS bundle identifier remains the existing Emergent-generated identifier and is outside this Android-release hardening scope.

## 16. Secret / signing hygiene
**Status: ✅ IMPLEMENTED / CI PENDING**

- Real `.env` files remain ignored.
- credential/private-key/keystore extensions are ignored.
- `.env.example` templates are explicitly allowed.
- GitHub CI rejects tracked `.env`, credentials, private key and Android signing-store file types.

## 17. External dependencies still required

- Production MongoDB/hosting configuration.
- Twilio production credentials/phone sender.
- SendGrid API key + verified `EMAIL_FROM` for staff email OTP.
- Google Maps/Places/Geocoding/Routes configuration.
- Real-device Android location test.
- Google Play versionCode confirmation.
- Google Play signing/upload-key lineage verification.
- Real DigiLocker provider integration if automatic DigiLocker KYC is required.

## 18. Current blockers before release

1. ❌ CI has not yet produced a green execution result for this branch.
2. ❌ Real Android foreground/background GPS has not been verified on a physical production-style build.
3. ❌ Play Console highest versionCode and signing lineage are not verified.
4. ⚠️ Google Routes live production configuration is external and unverified.
5. ⚠️ Twilio/SendGrid live production delivery is external and unverified.
6. ⚠️ DigiLocker remains a future external integration; current KYC is manual Authority review.
7. ⚠️ Production Mongo restart/data-integrity validation remains external.

## 19. Release decision

**Current decision: NOT READY TO MERGE/DEPLOY/UPLOAD.**

This report will be updated with exact test counts, final branch HEAD and CI conclusions once the branch checks execute. A release should proceed only after all true blockers are closed or explicitly accepted with evidence.
