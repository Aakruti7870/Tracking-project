# TrackMyRMC — Build Report

_Last reconciled: 2026-08-22_

TrackMyRMC is a Ready Mix Concrete platform built in this repository as **Expo / React Native + FastAPI + MongoDB** with one OTP entry flow and server-resolved role routing.

## Current branch

- Repository: `Aakruti7870/Tracking-project`
- Branch: `fix/production-readiness-final`
- PR: #1
- PR #2 (Codex hardening contribution): merged into this hardening branch and closed.
- No production deployment or Play upload has been performed from this branch.

## Core product coverage

The application contains the customer ordering flow, plant-owner operations, driver trip/POD/tracking flow, notifications, billing/ledger, production, inventory, quality, fleet, KYC review and the 13-role dashboard structure.

Roles:
Customer, Driver, Plant Owner, Admin, Dispatcher, Operator, Supervisor, Accountant, Quality Engineer, Fleet Manager, Store Manager, Authority and Central Admin.

Plant-scoped staff are enforced server-side. Authority and Central Admin retain platform-wide scope where intended.

## Production hardening in PR #1

- fail-closed production JWT/OTP/CORS configuration;
- OTP race, resend, attempts and provider-error hardening;
- server-side RBAC and plant tenant isolation;
- compare-and-set order transitions;
- hardened driver trip/POD finalization;
- authenticated object metadata and file authorization;
- input validation and security-safe provider errors/logging;
- Twilio SMS + SendGrid email adapters;
- Google Maps/Places/Geocoding/Routes server proxy;
- Expo Android trip location tracking support;
- Android identity alignment;
- repository secret/signing guards;
- backend/frontend/native Android CI.

## Verified build/test state

Backend full integration suite: **154 passed, 2 skipped, 0 failed**.

Frontend gates:
- TypeScript ✅
- lint ✅
- Expo Doctor ✅
- Expo public config ✅
- web preview build ✅

Android native gates:
- Expo Android prebuild ✅
- package `com.trackmyrmc.concreteking` ✅
- versionCode `61` ✅
- Gradle `assembleDebug` ✅

Repository security guard ✅

## Android release identity

- Version name: **2.0.3**
- Version code: **61**
- Package: **`com.trackmyrmc.concreteking`**

No new keystore is generated or stored in Git. Play signing/update lineage still requires Play Console verification before a signed release build.

## Backend/runtime wiring

Client API calls use `EXPO_PUBLIC_BACKEND_URL`.

CI preview runtime uses the repository variable `PREVIEW_BACKEND_URL`. When that variable is set, CI first requires `<url>/api/health` to return success. When it is not set, CI performs compile/build validation only and does not publish a misleading preview APK.

The old Emergent preview hostname referenced by historical tests returned HTTP 404 at `/api/health` during this hardening pass, so it is not accepted as the current backend.

The production template is `https://api.trackmyrmc.com`; it is not considered connected to this new FastAPI/Mongo backend until a real deployment maps it and health verification passes.

## What remains external

Before production release we still require:
- isolated preview backend deployment and stable HTTPS URL;
- connected preview + real-device testing;
- physical Android background GPS verification;
- production Mongo configuration;
- live SMS/email provider verification;
- Google Maps/Routes production configuration;
- Play signing/upload-key and final versionCode verification;
- automated DigiLocker only if that integration is explicitly required.

## Next step

Deploy **only an isolated preview backend** from `fix/production-readiness-final`. Do not merge, deploy production, change UI/theme, replace signing keys, or point the new app at the legacy backend. Return the stable backend URL and `/api/health` evidence. Then the connected preview APK can be built and reviewed.
