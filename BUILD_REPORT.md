# TrackMyRMC — Build Report
_Last updated: 2026-06_

A production-grade **Ready Mix Concrete (RMC)** platform. One common OTP login →
the backend resolves the user's role → routes to a role-specific dashboard. Strict
server-side RBAC, order/trip state machines, digital challan, Proof of Delivery, live
map tracking, billing, and dashboards for **all 13 roles**.

**Stack:** Expo (React Native) + expo-router · FastAPI · MongoDB · JWT passwordless OTP.

---

## 1. Feature summary (by area)

### Authentication & RBAC
- One common OTP login. Backend auto-detects channel (customers/drivers = **mobile OTP**,
  all staff/authority/admin = **email OTP**), issues a revocable JWT session, enforces
  channel-per-role. Every protected API authorizes server-side.

### Customer app
- Browse verified plants, **KYC-gated** order creation with **Google Places address
  autocomplete + geocoding** (pins exact site lat/lng), drafts, order detail with a status
  timeline, cancel, **live map tracking**, digital challan, and **Proof of Delivery** view
  (photo, receiver, delivered qty, signature, time) once delivered.

### Plant Owner app
- KPI dashboard + **"This Week" insights chart** (Ordered vs Delivered volume + payments).
- Approve/reject orders, full **dispatch workflow** (assign Transit Mixer → Driver →
  generate **Challan** → Dispatch), **production board**, **Invoice & Ledger** (rate card +
  18% GST, payments, outstanding), and **incidents** (driver SOS).

### Driver app
- Active trip + **trip state machine** (Start → Reached → Unloading → Delivered), live GPS
  location feed, **Proof of Delivery** capture (site photo via Object Storage + signature),
  **SOS** (emergency/accident/breakdown/safety + GPS), daily attendance.

### All 13 role dashboards
- Customer, Driver, Plant Owner **plus** the 10 staff roles below — each with its own login,
  KPI grid, list tabs, notifications bell, and role-appropriate **actions**:

| Role | Can do |
|------|--------|
| **Admin** | View all orders + fleet |
| **Dispatcher** | Assign mixer → driver → challan → **dispatch** (self-service) |
| **Operator** | Start / Complete production |
| **Supervisor** | Monitor operations + incidents |
| **Accountant** | Record payments against invoices |
| **Quality Engineer** | Record quality tests (slump, 7/28-day cube, water/cement, Pass/Fail) |
| **Fleet Manager** | Add mixers, toggle Available/Maintenance, view drivers |
| **Store Manager** | Add materials, Stock In/Out (with over-issue guard) |
| **Authority** | Approve/Reject pending KYC, view plants |
| **Central Admin** | Suspend/Activate users, platform-wide view |

- Plant-scoped roles see only their plant; **Authority & Central Admin** see the whole platform.
- **Search box + status filter chips** on big lists (Orders, Users, etc.).

### Cross-cutting
- **In-app notifications** feed (bell + unread badge on every dashboard).
- **Live tracking map** (real Google map: mixer marker, site marker, route polyline) with
  Live ETA + remaining distance + last-update time; stops at DELIVERED.

---

## 2. Live integrations
- **Google Maps** ✅ LIVE — address autocomplete (Places New) + geocoding + live map display.
  Key stored server-side (`GOOGLE_MAPS_KEY`) and client (`EXPO_PUBLIC_GOOGLE_MAPS_KEY`).
- **Twilio SMS** ✅ LIVE — real OTP delivery + **idempotent** DISPATCHED and DELIVERED
  customer alerts (order ref, mixer, live-tracking link / delivery-proof link). Best-effort:
  an SMS failure never blocks a status change; one SMS per event via an atomic claim flag.
- **Emergent Object Storage** ✅ — POD photos.

## 3. Gated / pending (external, on user)
- 🔴 **Google Routes API DISABLED** on the user's project → Live ETA/distance/route line are
  built but hidden (graceful) until the user enables Routes API. No code change needed after.
- 🟡 **SendGrid email** — adapter dormant; activates on `EMAIL_PROVIDER_API_KEY`.
- 🟡 **DigiLocker KYC** — current KYC is a **manual Authority review flow** (not an automated
  API). `KYC_API_KEY` stored; real DigiLocker needs its API/OAuth details.
- 🟡 **Maps key lock-down** — set to open during setup; should be domain-restricted for prod.

---

## 4. Architecture
- **Backend** (`/app/backend`): `config → database → models → security/rbac → services
  (audit, notifications, order_service) → routers`. Routers: `auth, me, customer, owner,
  driver, staff, notify, maps, storage`. `staff.py` is DRY — one role-aware `home` + one
  generic `collection/{kind}` + action endpoints power all 10 staff dashboards.
- **Frontend** (`/app/frontend`): expo-router file-based routing; explicit `app/{role}/`
  folders (no route groups) to avoid URL collisions across 13 roles. Shared
  `src/screens/Staff*` + reusable components (`OwnerDispatchPanel` with `basePath`,
  `LiveMap`, `WeeklyInsights`). Charcoal + electric-lime theme, glass tab bar, light/dark.
- **Order state machine** is the single choke point for status changes, notifications and
  milestone SMS — nothing sets status directly from the client.

## 5. Test accounts (dev OTP auto-returned)
Customer `+919000000001` · Driver `+919000000002` · Owner `owner@trackmyrmc.test` ·
staff emails: admin / dispatcher / operator / supervisor / accountant / quality / fleet /
store / authority / central `@trackmyrmc.test`. (See `/app/memory/test_credentials.md`.)

## 6. Test status
- Backend: staff dashboards 36/36; actions 21/22 (1 skip); dispatcher flow + RBAC verified;
  SMS idempotency verified (1 dispatch + 1 delivered, flags set); maps endpoints verified.
- Frontend: iterations 8–11 green — dashboards, actions, dispatcher, search/filter, insights,
  Google Maps autocomplete + live map render, POD card compiles.

## 7. What's next (suggested)
- Enable Routes API (user) → Live ETA. · Downloadable PDF delivery receipt. · Post-delivery
  star rating. · Real DigiLocker KYC. · Lock Maps key to production domain.
