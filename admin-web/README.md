# TrackMyRMC secure administration portal

Dedicated React + TypeScript frontend for `https://control.trackmyrmc.com`. It is intentionally independent of `frontend/app` (the public Expo route tree).

## Configuration

Set `VITE_API_URL=https://<api-host>/api` at build time. The FastAPI deployment must explicitly include `https://control.trackmyrmc.com` in `CORS_ORIGINS`; production configuration rejects wildcards.

```bash
npm ci
npm run typecheck
npm run build
```

Admin accounts cannot register here. Only the three hard-coded approved email identities, provisioned with the `central_admin` role and Authenticator TOTP, can establish a web Control Center session. Authority, Plant Owner, Driver, Customer, normal staff, and mobile sessions are denied by the backend. Login errors are generic. The bearer session is held in React memory only and disappears on reload; it is never persisted in browser storage.

Sensitive actions should first call `/api/admin/auth/step-up`; successful confirmation is server-recorded for five minutes and audited. `/api/admin/auth/logout-all` revokes every active session for the administrator.
