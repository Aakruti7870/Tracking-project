# TrackMyRMC — Build Report
_Last updated: 2026-06_

A production-grade **Ready Mix Concrete (RMC)** platform. One common OTP login →
backend resolves the user's role → routes to a role-specific dashboard. Strict
server-side RBAC, order/trip state machines, challan, POD, live tracking pipeline,
billing and role dashboards for **all 13 roles**.

**Stack:** Expo (React Native) + expo-router · FastAPI · MongoDB · JWT passwordless OTP.

---

## 1. What's built (feature by feature)

### Authentication & RBAC
- One common OTP login screen. Backend detects channel (email vs mobile), resolves
  the account, enforces channel-per-role policy, issues a JWT session (revocable).
- Customers/drivers → mobile OTP; all staff/authority/admin → email OTP.
- Every protected API authorizes server-side. Unknown mobile self-registers as Customer.

### Customer app (Home / Orders / Plants / More)
- Browse verified plants, KYC gating, create order (plant + grade + quantity + date/time
  + site details), save draft, order detail with a vertical status timeline, cancel,
  live tracking screen, view challan.

### Plant Owner app (Home / Orders / Operations / More)
- KPI dashboard, approve/reject orders, full **dispatch workflow**: assign Transit
  Mixer → assign Driver → generate digital **Challan** → Dispatch.
- **Production board** (start → batches → complete), **Invoice & Ledger** (rate card +
  18% GST, record payments, billed/received/outstanding), **Incidents** (driver SOS).

### Driver app (Home / Trips / Attendance / More)
- Active trip + **trip state machine**: Start → Reached Site → Unloading → Delivered.
- **Proof of Delivery**: receiver, delivered qty, site photo (Emergent Object Storage)
  + drawn signature. **SOS** (emergency/accident/breakdown/safety + GPS). Daily attendance.
- Live location endpoint feeding the customer tracking screen.

### 🆕 All 10 staff role dashboards (this build)
Each role has its own email-OTP login and a bottom-tab dashboard with real, plant-scoped data:

| Role | Home KPIs | Tabs |
|------|-----------|------|
| **Admin** | Total/Pending/In-Transit/Delivered | Home · Orders · Fleet · More |
| **Dispatcher** | Ready · Dispatched today · En route · Available TMs | Home · Dispatch · Fleet · More |
| **Operator** | To produce · In production · Produced today · Completed | Home · Production · More |
| **Supervisor** | Active deliveries · Open incidents · Delivered today · Dispatched | Home · Operations · Incidents · More |
| **Accountant** | Billed · Received · Outstanding · Invoices | Home · Billing · Ledger · More |
| **Quality Engineer** | Delivered · Grades · Active batches · Volume | Home · Quality · More |
| **Fleet Manager** | Total/Available/On-trip TMs · Drivers | Home · Fleet · Drivers · More |
| **Store Manager** | Materials · Low stock · Reorder alerts · SKUs OK | Home · Stock · More |
| **Authority** | Plants · Verified · Pending KYC · Customers | Home · Plants · KYC · More |
| **Central Admin** | Plants · Users · Orders · Open incidents | Home · Plants · Users · More |

- Plant-scoped roles see their plant only; **Authority & Central Admin** see the whole platform.
- Store Manager has a real **materials** inventory (6 SKUs, with LOW/OK stock badges).

---

## 2. Architecture

**Backend** (`/app/backend`): layered `config → database → models → security/rbac →
services (audit, notifications) → routers`.
- Routers: `auth, me, customer, owner, driver, staff, storage`.
- `staff.py` is DRY: one role-aware `home` + one generic `collection/{kind}` endpoint
  power all 10 dashboards from existing collections.

**Frontend** (`/app/frontend`): expo-router file-based routing. Explicit role folders
`app/{role}/` (no route groups) to avoid URL collisions across 13 roles. Shared
`src/screens/StaffTabs|StaffHome|StaffCollection|StaffMore` keep per-role files tiny.
Custom charcoal + electric-lime theme, glass bottom tab bar, light/dark modes.

**Key collections:** users, sessions, otps, plants, orders, order_status_history,
vehicles, driver_trips, challans, proof_of_delivery, attendance, driver_incidents,
invoices, payments, production_batches, vehicle_locations, **materials**, kyc_profiles.

---

## 3. Test accounts (dev OTP auto-returned)
Customer `+919000000001` · Driver `+919000000002` · Owner `owner@trackmyrmc.test`.
Staff (email): admin / dispatcher / operator / supervisor / accountant / quality /
fleet / store / authority / central `@trackmyrmc.test`. Full list in
`/app/memory/test_credentials.md`.

---

## 4. Test status
- **Backend:** 36/36 pytest pass for staff dashboards (+ prior phases green).
- **Frontend:** login→dashboard→tabs→logout verified E2E for representative roles;
  all roles share the same verified shell.

## 5. Known limitations / pending
- **Live Google Maps:** blocked — the provided API key is HTTP-referrer restricted and
  cannot be used server-side or from the preview domain. Needs a server-usable key
  (Application restriction None/IP + Places New, Geocoding, Routes enabled). Tracking
  uses the on-brand placeholder meanwhile.
- **Notifications:** SMS/Email adapter is provider-agnostic and currently NOT_CONFIGURED
  (logs only). Real delivery pending user keys/provider choice.
- **KYC review actions:** Authority sees KYC requests read-only; approve/reject UI deferred.
- **Styling:** minor non-blocking RN-web `shadow*` → `boxShadow` cleanup outstanding.
