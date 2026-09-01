# TrackMyRMC secure administration portal

Dedicated React + TypeScript frontend for `https://admin.trackmyrmc.com`. It is intentionally independent of `frontend/app` (the public Expo route tree).

## Configuration

Set `VITE_API_URL=https://<api-host>/api` at build time. The FastAPI deployment must explicitly include both `https://admin.trackmyrmc.com` and, where required, `https://trackmyrmc.com` in `CORS_ORIGINS`; production configuration rejects wildcards.

```bash
npm ci
npm run typecheck
npm run build
```

Admin accounts cannot register here. Existing explicitly provisioned `authority` and `central_admin` accounts must have Authenticator TOTP enabled. Login errors are generic. The bearer session is held in React memory only and disappears on reload; it is never persisted in browser storage. This reduces exposure under the existing API contract, but an HttpOnly cookie/CSRF backend migration remains recommended.

Sensitive actions should first call `/api/admin/auth/step-up`; successful confirmation is server-recorded for five minutes and audited. `/api/admin/auth/logout-all` revokes every active session for the administrator.
