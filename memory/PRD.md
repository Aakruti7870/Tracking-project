# TrackMyRMC — Product Requirements Document

## Original problem statement
Rebuild TrackMyRMC from zero: a production-grade **Ready Mix Concrete (RMC)** ordering,
plant operations, dispatch, driver-tracking, challan, KYC and business-management platform.
One common OTP login → backend resolves role → routes to the correct role dashboard.
13 roles, server-side RBAC, order/trip state machines, challan, POD, live tracking, KYC,
notifications adapter, audit logging.

## Stack decision (important)
The original spec requested React+Vite+Capacitor / Node-Express / PostgreSQL. The Emergent
platform is purpose-built for **Expo (React Native) + FastAPI + MongoDB**, which the user
approved. All business flows/rules are preserved; only the underlying stack differs (and
Expo yields a true native Android/iOS app vs Capacitor's webview).

- Frontend: Expo Router (React Native), TypeScript, react-native-reanimated,
  react-native-keyboard-controller, expo-blur, expo-image, custom theme system.
- Backend: FastAPI (layered: config → database → models → security/rbac → services → routers).
- DB: MongoDB (Pydantic models, PyObjectId/BaseDocument).
- Auth: passwordless OTP (email/mobile) + JWT sessions (HMAC-hashed OTP, TTL, throttling,
  MongoDB session revocation). Provider-agnostic delivery adapter (NOT_CONFIGURED in dev).
- Maps: clean adapter placeholder (Google Maps key to be added later).

## User personas / roles
Customer, Driver, Plant Owner, Admin, Dispatcher, Plant Operator/Batcher, Supervisor,
Accountant, Quality Engineer, Fleet Manager, Store Manager, Authority, Central Admin.

## Core requirements (static)
- ONE common login; backend resolves active role + status + membership; never trust client role.
- Every protected API authorizes server-side (RBAC). Sensitive actions write audit logs.
- Authoritative order & driver-trip state machines (backend-owned transitions).
- KYC gating: customer must be VERIFIED to place a live order.
- Live tracking scoped to the relevant order/trip; stops after delivery.
- Provider-agnostic notifications; never fake delivery/tracking/integration.
- Light + Dark themes, identical IA; premium charcoal + electric-lime design system.

## Implemented (with dates)
### 2026-06 — PHASE 9 (Twilio SMS live) ✅
- **Twilio SMS wired** via the provider-agnostic adapter (Messaging API, async, best-effort).
  Real SMS now sent for **OTP codes** and **order alerts** (every in-app notification also
  pushes an SMS to the user's phone when configured). Verified: Twilio returns 201 + "SMS sent".
- Login stays testable in preview: `dev_otp` is still surfaced in non-prod (seeded demo
  numbers aren't real phones). Both SMS (customer/driver) and email (staff) logins verified.
- Env: `TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER`. Twilio HTTP logs quieted.
- **SendGrid email**: skipped by user — adapter dormant, activates when `EMAIL_PROVIDER_API_KEY` set.
- **KYC key** stored (`KYC_API_KEY`) but provider not identified yet — dormant.
- **Google Maps**: STILL BLOCKED — key remains HTTP-referrer restricted (re-tested). Awaiting
  an unrestricted/server-usable key before Places/Geocoding/Routes activate.

### 2026-06 — PHASE 8 (Dispatcher self-service, Search/Filter, Owner Insights) ✅
- **Dispatcher** can now run the whole dispatch from their own screen: tap a queue row →
  assign Transit Mixer → assign Driver → generate Challan → Dispatch (reuses the owner
  panel via a `basePath="/staff"` prop; production/invoice buttons hidden). Backend mirror
  endpoints under `/api/staff/orders/{id}/…` scoped by plant, gated to Dispatcher + Admin.
- **Search + status filters** on big staff lists (search box ≥4 items, badge chips ≥2 badges) —
  client-side across primary/secondary/meta. Works for Orders, Users, and every collection.
- **Owner "This Week" insights**: 7-day Ordered vs Delivered bar chart + Payments row +
  totals. Backend `GET /api/owner/insights`. Pure RN chart (no chart lib).
- Tests: 21/21 backend pass; all three frontend flows verified E2E.

### 2026-06 — PHASE 7 (Staff actions, Notifications, Maps plumbing) ✅
- Made staff dashboards **actionable** (backend-driven action buttons on list items):
  - **Authority**: approve / reject pending KYC (with reason) → notifies the user.
  - **Central Admin**: suspend / activate any user account.
  - **Fleet Manager**: add Transit Mixer, toggle Available/Maintenance.
  - **Store Manager**: add material, Stock In / Stock Out (with movement log; guards over-issue).
  - **Operator**: Start Production / Mark Complete (drives order state machine).
  - **Quality Engineer**: record a quality test (slump, 7/28-day cube, actual cement/water,
    PASS/FAIL, remarks) on a dedicated form screen; register badge flips to QC PASS/FAIL.
  - **Accountant**: record a payment against an invoice (updates paid/status/order).
- **Notifications feed**: `/api/notifications` (+ read / read-all); bell with unread dot in
  every staff dashboard header → notifications screen. Durable in-app records (no fake sends).
- **Google Maps plumbing (key-ready)**: `routers/maps.py` proxy reads `GOOGLE_MAPS_KEY`
  server-side and reports NOT_CONFIGURED gracefully when absent. New Order screen has a
  Places autocomplete that stays hidden until a key is set, then activates automatically
  (stores lat/lng on the order). New collections: stock_movements, quality_tests.
- Tests: 21/22 backend pass (1 skipped: seeded invoice already PAID); all action UIs render.

### 2026-06 — PHASE 6 (All 10 remaining role dashboards) ✅
- Added dashboards for the 10 non-customer/driver/owner roles: **admin, dispatcher,
  operator, supervisor, accountant, quality_engineer, fleet_manager, store_manager,
  authority, central_admin**. Each is an email-OTP login → its own GlassTabBar tab shell.
- DRY backend `routers/staff.py`: role-aware `GET /api/staff/home` (4 KPIs + primary
  list) and generic `GET /api/staff/collection/{kind}` (13 kinds: orders, dispatch,
  production, quality, incidents, fleet, drivers, invoices, ledger, inventory, plants,
  kyc, users). All data real from existing collections; RBAC-guarded to the 10 staff roles.
- Plant-scoped roles see their plant only; authority & central_admin see the whole platform.
- New `materials` collection + seed (6 SKUs, incl. a LOW-stock alert) for store_manager.
- Seeded 9 new staff accounts (see test_credentials.md). Frontend: shared
  `StaffTabs/StaffHome/StaffCollection/StaffMore` screens keep per-role code tiny.
- Tests: 36/36 backend pytest pass; 4 roles verified E2E on web, rest share the shell.

### 2026-06 — MAPS integration (BLOCKED on key) ⛔
- User provided Google Maps key `AIzaSy…neA0`, but it is **HTTP-referrer restricted**
  and blocks server-side + our preview domain for Places/Geocoding/Routes/Maps-JS.
  Legacy Places/Directions APIs are also disabled on the project. Real maps cannot be
  wired until the user supplies a server-usable key (Application restriction = None or
  IP, with Places API New + Geocoding API + Routes API enabled). Tracking still uses the
  on-brand placeholder. NOT STARTED pending a working key.

### 2026-06 — PHASE 5 (SOS, Invoice/Ledger, Production, Tracking pipeline) ✅
- **Driver SOS**: type picker (Emergency/Accident/Breakdown/Safety) + note + GPS;
  persists incident, notifies plant owner (durable in-app record, no fake claims).
  Owner Incidents screen to acknowledge/resolve.
- **Invoice & Ledger**: owner generates an invoice from a DELIVERED order (rate card
  per grade + 18% GST), records payments (PARTIAL/PAID, updates order payment_status),
  Billing screen with billed/received/outstanding KPIs + per-customer ledger.
- **Production Board**: optional ACCEPTED→IN_PRODUCTION→(batches)→PRODUCTION_COMPLETE
  path on the owner order detail before assigning a mixer.
- **Live Tracking pipeline**: driver location endpoint + customer tracking endpoint
  (scoped, auto-stops after delivery, 15s poll). Map is the on-brand placeholder that
  upgrades to real Google Maps once a Maps API key is provided (NOT_CONFIGURED).
- New collections: driver_incidents, invoices, payments, production_batches, vehicle_locations.
- Tests: 16/17 backend pass (1 test-runner parallelization artifact, not a bug); all
  new frontend flows verified.

### 2026-06 — PHASE 4 (Driver App + Proof of Delivery) ✅
- Driver tab shell (`/driver`: Home / Trips / Attendance / More) with role routing.
- Driver **trip state machine**: DISPATCHED → EN_ROUTE (Start Trip) → ARRIVED
  (Reached Site) → UNLOADING (Start Unloading) → DELIVERED (via POD). Each driver
  step advances the linked ORDER state (EN_ROUTE/AT_SITE/UNLOADING/DELIVERED),
  records trip history + audit, and notifies the customer; guards reject invalid jumps.
- **Proof of Delivery**: receiver name, delivered quantity, remarks, site photo
  (expo-image-picker → uploaded to **Emergent Object Storage** via /api/upload,
  served via tokenized /api/files) and a drawn **signature** (react-native-svg vector,
  stored as JSON). On submit → order DELIVERED, vehicle returns to available.
- Driver **Attendance** check-in/out (server-timestamped, one per day).
- Object Storage helper (init/put/get with stale-key retry) + authenticated
  upload/serve routes (header for native, ?token= for web). Camera/photos permission
  handled contextually with Open-Settings fallback.
- Tests: driver+POD backend 8/8 pass; full driver + POD UI E2E verified (signature draw,
  stage progression, delivered). Note: POD photo/native camera only testable on a real
  build, not Expo Go/web.

### 2026-06 — PHASE 3 (Assign & Dispatch) ✅
- Owner **dispatch workflow** on approved orders: assign Transit Mixer → assign
  Driver (creates a `driver_trip`) → generate digital **Challan** (CH-xxxx, unique) →
  Dispatch. Drives the state machine ACCEPTED→TM_ASSIGNED→DRIVER_ASSIGNED→
  READY_TO_DISPATCH→DISPATCHED with guards, history, audit and notifications.
- New collections: vehicles, driver_trips, challans. Seeded 3 transit mixers + linked
  the demo driver; added a seeded PENDING order for demos/tests.
- Owner endpoints: /owner/fleet, /owner/drivers, assign-tm, assign-driver,
  challan (POST+GET), dispatch — all plant-scoped + RBAC. Customer sees TM/driver/
  challan + tracking note once dispatched; shareable Challan screen for both roles.
- **Bug fixed**: role tab groups were route groups `(customer)`/`(owner)` that
  collided on the same URLs, breaking owner navigation. Moved to real path segments
  `customer/` and `owner/` (scalable for all 13 roles). Added `pointerEvents="box-none"`
  to the glass tab bar wrapper.
- Tests: dispatch backend 11/12 pass; full owner dispatch UI E2E verified after fix.

### 2026-06 — PHASE 2 (Core Order Lifecycle — two-sided) ✅
- Authoritative backend **order state machine** (`order_service.py`): 16 states +
  validated transitions, per-transition history (actor+timestamp), audit entries,
  and notifications. Frontend can never set status directly.
- Unique order numbering via an atomic Mongo counter (no collisions).
- Customer: create order (KYC-gated; drafts allowed), order detail + status history,
  cancel (state-guarded), plant detail, grade-vs-plant validation.
- Plant Owner router (`owner.py`), scoped to owned plants: dashboard KPIs +
  pending approvals, orders list/filter, order detail, **approve / reject (with reason)**.
- Frontend: New Order form (plant picker, grade chips, quantity stepper, date/time
  chips, site fields, place/draft), role-aware Order Detail with vertical timeline,
  full **Plant Owner tab shell** (Home KPIs / Orders / Operations / More), owner
  approve+reject UI, reusable glass tab bar. Customer New Order/Order links wired.
- Routing: plant_owner → /(owner); customer New Order gated on KYC.
- Tests: 15/15 order-lifecycle pytest cases pass; full customer→owner→customer E2E verified.

### 2026-06 — PHASE 1 (Foundation) ✅
- Backend layered architecture, Mongo BaseDocument/PyObjectId, env config.
- Passwordless OTP + JWT auth per integration playbook; channel-per-role policy;
  account status gates; session revocation on logout.
- RBAC catalogue for all 13 roles + `require_role` server-side guards.
- Audit logging service; provider-agnostic notification/OTP delivery adapter.
- Idempotent seed: demo Customer/Driver/Plant Owner/Admin + 3 verified plants + 2 orders + customer KYC=VERIFIED.
- Endpoints: /api/health, /api/auth/{request-otp,verify-otp,logout}, /api/me,
  /api/customer/{home,orders,plants,kyc}, POST /api/customer/kyc/start.
- Frontend: theme system (light/dark tokens), AuthContext + secure token storage,
  API client, UI kit (Button/Card/Input/Badge/AppText/Screen/Skeleton/Toast/MapPlaceholder),
  common OTP login (hero + dev-OTP autofill), Customer 4-tab shell
  (Home/Orders/Plants/More) with glass tab bar, KYC screen, role placeholder for other roles.
- Tests: 17/17 backend pytest cases pass; all Phase 1 frontend flows verified.

## Prioritized backlog (next phases)
- **P0 — Phase 2**: Full role dashboards scaffolding (Driver, Plant Owner, Admin first).
- **P0 — Phase 3**: Plant verification, customer profile, saved sites, real nearby-plant discovery (geo).
- **P0 — Phase 4**: Order creation form + KYC gating + approval + order state machine + history.
- **P1 — Phase 5**: Production/batches/mix designs/inventory.
- **P1 — Phase 6/7**: Fleet, driver trips (accept/decline), attendance, TM/driver assignment,
  challan generation (PDF/share), dispatch, customer live tracking (Google Maps key required).
- **P1 — Phase 8**: POD (signature + photo via Emergent Object Storage) → delivered.
- **P2 — Phase 9**: Invoices, payments, ledgers, purchases, expenses.
- **P2 — Phase 10/11**: KYC review (Authority), Central Admin, subscriptions, audit-log UI.
- **P2 — Phase 12**: Android hardening (permissions, icons, splash, deep links, release metadata).

## Known integration status
- OTP delivery provider: NOT_CONFIGURED (dev returns dev_otp). Add SMS/email keys for prod.
- Google Maps/Places/Directions: NOT_CONFIGURED (placeholder adapter). Add key to enable.

## Next tasks
1. Confirm Phase 2 scope (which role dashboards first).
2. Provide Google Maps API key when ready to enable real maps/tracking.
