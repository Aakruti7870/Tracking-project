# TrackMyRMC secure administration portal

Dedicated React + TypeScript frontend for `https://control.trackmyrmc.com`. It is intentionally independent of the public/mobile application surface.

## Configuration

Set `VITE_API_URL=https://<api-host>/api` at build time. The FastAPI deployment must explicitly include `https://control.trackmyrmc.com` in `CORS_ORIGINS`; production configuration rejects wildcards.

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

Central Admin accounts cannot self-register here. A Control Center administrator must already be explicitly provisioned with the `central_admin` role, be approved for Control Center access, have a valid permission set (root recovery identities retain the existing full-admin default), and complete Authenticator MFA. First-time email verification or recovery can create only a short-lived MFA-enrollment bootstrap; successful enrollment revokes that bootstrap and requires a fresh `/api/admin/auth/verify-totp` sign-in before `control_center_web` provenance exists.

**Authority is not migrated to Central Admin authentication.** Authority remains an approved operational Plant Staff identity using the existing Plant Staff email OTP/MFA flow. Plant Owner and the normal Plant Staff roles also retain that flow. Customer and Driver continue mobile OTP. None of those sessions receives Control Center provenance.

The Control Center bearer session is held in React runtime memory only and disappears on reload; it is never persisted in browser storage. Sensitive actions use `/api/admin/auth/step-up`; successful confirmation is server-recorded for five minutes and audited. `/api/admin/auth/logout-all` revokes active sessions for the signed-in Central Admin.
