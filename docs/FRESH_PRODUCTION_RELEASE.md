# Fresh production release invariant

This release must not publish, validate, or package any legacy TrackMyRMC/Concrete King website candidate.

## Canonical web

- `https://trackmyrmc.com/` must serve the current Expo web shell and route the fresh start to `/login`.
- `https://www.trackmyrmc.com/` must resolve successfully to the same fresh web experience (directly or by a safe redirect).
- Human-facing production routes must contain the current Expo shell marker and must not contain the legacy landing copy `Built for every pour` or `Ready-Mix Concrete Tracking & RMC Plant Discovery`.
- `/api/*`, `/health`, and `/.well-known/assetlinks.json` remain backend-owned machine routes.

## Pre-AAB candidate

- Candidate validation must check out the exact dispatched ref or pushed `main` SHA. It must never fall back to an older feature branch.
- Production Android builds are pinned to `https://trackmyrmc.com`; the legacy `https://api.trackmyrmc.com` origin is rejected from the built bundle.
- Current Play candidate: `com.trackmyrmc.concreteking`, version `2.0.26`, versionCode `84`.
- Bundletool validation, package/version checks, upload signing, and production asset-links availability are mandatory before publishing the AAB artifact.

## Passkey ceremony

The AuthContext passkey completion callback is stable across hydration/re-renders so the one-time URL-fragment capability cannot be consumed by a restarted effect before navigation completes.
