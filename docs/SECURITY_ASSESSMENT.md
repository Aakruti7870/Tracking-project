# TrackMyRMC Security Assessment

**Scope:** all tracked repository files, local source/unit tests, and passive deployment configuration review. No production, provider, or third-party requests were made. The review was performed on `security/full-application-hardening` on 2026-09-01.

## Threat model and attack surface

### Entry points

The public FastAPI health, policy, account-deletion, onboarding, authentication, Google OAuth, Play reviewer, Cashfree webhook/return, KYC return, and Android Asset Links endpoints cross directly into backend code. Authenticated entry points include customer, driver, owner, staff, authority, central-admin, HR/workforce/payroll, maps, notification, upload/download, order, challan, invoice, payment, KYC, location, and tracking routes. Expo Router supplies browser/mobile routes and custom `trackmyrmc://` deep links; Android accepts the verified HTTPS `/kyc/return` App Link. Startup migrations/index creation and repository cron scripts are scheduled/background entry points. Firebase Cloud Messaging, Google Maps, DigiLocker, Cashfree, Google OAuth, GCS/Emergent object storage, and MongoDB are external integrations.

### Trust boundaries and assets

Untrusted mobile/web/admin clients cross the API authentication and runtime-validation boundary. The API crosses boundaries to MongoDB and every provider above; Cashfree webhook signatures and DigiLocker/Google provider responses are security assertions. Android App Links cross Google Play signing/domain verification. Public payment/KYC return pages cross into custom-scheme navigation. Protected assets are session/JWT/MFA/passkey material, customer and workforce PII, KYC state, plant tenancy, privileged accounts, orders, quotations, challans, invoices, payroll, payment/entitlement state, POD uploads, precise driver/tracking location, provider credentials, and audit records.

### Principal abuse cases

The highest-risk paths are fixed/reusable reviewer credentials, privilege assignment, stale session use, OTP/passkey replay, request-body role or tenant identifiers, object IDs crossing customer/plant/driver boundaries, provider callback forgery/replay, payment amount/order mismatch, arbitrary uploads/reads, maps/object-store SSRF, and deep-link confusion. Frontend route hiding is explicitly not considered a control; backend dependencies and tenant-qualified queries are the enforcement points.

## Validated findings

### TM-001 — Critical — permanent fixed OTP privileged login (fixed)

* **Affected code/endpoints:** former `backend/routers/permanent_access.py` overrides of `/api/auth/request-otp`, `/api/auth/verify-otp`, `/api/auth/staff/request-otp`, and `/api/auth/staff/verify-otp`.
* **Prerequisite/path:** unauthenticated attacker submits a repository-visible reviewer phone/email and the hard-coded `123456`; the Authority identity yielded an ordinary privileged session without the configured reviewer-access switch, per-challenge expiry, attempt tracking, or staff MFA.
* **Impact/evidence:** strongly proven by direct control-flow analysis and the former unit test asserting the constant. This enabled Authority impersonation and KYC administration. Confidence: high.
* **Fix:** removed all route overrides, fixed identifiers/code, and automatic privileged-account bootstrap. Reviewer access now has one explicit, disabled-by-default endpoint using the deployment secret. Regression tests enumerate the compatibility router and reject reintroduction of privileged bootstrap constants.

### TM-002 — High — startup privilege assignment to hard-coded support emails (fixed)

* **Affected code:** former `_ensure_authority` startup path in `backend/routers/permanent_access.py`.
* **Prerequisite/path:** control of, or successful OTP delivery to, either hard-coded mailbox after startup silently created/upgraded it to Authority and active status.
* **Impact/evidence:** strongly proven by unconditional startup call and Mongo `$set`/`$addToSet`; this was a persistent privilege grant outside an audited admin provisioning workflow. Confidence: high.
* **Fix:** removed privileged bootstrap and its startup invocation. Existing database identities require a one-time operational review/revocation because source changes do not delete production records.

## Authentication, OTP/MFA, and sessions

Normal OTPs use cryptographic randomness, keyed hashes bound to a challenge and normalized identifier, expiry, atomic consumption, resend uniqueness, and maximum attempts. JWT decoding pins HS256 and requires subject/session/expiry; authorization reloads the current database role rather than trusting the JWT role. Sessions are database-backed, checked for revocation/account suspension, and constrained to the newest session. Logout revocation and staff bootstrap-only MFA routing are present. Staff TOTP/passkey code has dedicated replay/enrollment tests. The remaining explicit Play review endpoint is disabled by default and constant-time compares a minimum-length environment secret, but reusable reviewer access remains an accepted operational exception and must be enabled only during review windows, rate-limited at the edge, monitored, and revoked afterward.

## Authorization, privilege escalation, and BOLA/IDOR

Protected routers generally use `require_role` and plant/customer/driver-qualified database queries. Order, file, tracking, workforce, KYC, and payment tests contain negative-role/ownership cases. No additional confirmed BOLA was reproduced locally. This is not proof of absence: route-by-route dynamic cross-tenant testing was limited by the lack of a running isolated Mongo/provider stack. Highest residual targets are large staff/owner/workforce routers and any lookup followed by mutation where tenant predicates are checked separately.

## KYC and DigiLocker

DigiLocker calls use fixed server configuration, timeouts, no redirects, server-obtained provider tokens, server-side session IDs, and provider status before verification. Client code cannot directly submit `VERIFIED`. Authority decisions are backend role checked. Legacy migration only upgrades PENDING records that already contain provider and consent evidence. Residual risk: confirm provider transaction uniqueness and state/user binding against a sandbox provider, and retire the compatibility migration once deployed everywhere.

## Payments

Cashfree webhook processing verifies the signature over raw bytes and server secret before parsing, looks up a server-created order, and grants entitlement only on provider `SUCCESS`. Status reads are plant scoped. Entitlement activation is designed idempotently. Residual sandbox tests should cover timestamp freshness, duplicate `cf_payment_id`, amount/currency equality with the server order, and reconciliation; signature validity alone does not prove those business attributes. The unauthenticated return page displays server state and does not mutate it.

## Uploads, SSRF, injection, and secrets

Uploads require an authenticated assigned driver/trip, cap bytes, decode/verify allowlisted raster formats, use random server paths, store authorization metadata, reject traversal, and authorize downloads. Mongo access uses structured queries; no `$where`, shell-backed query construction, unsafe deserialization, or application command execution was identified. Provider destinations are configuration/static endpoints rather than direct arbitrary user URLs. Secrets are environment sourced. `google-services.json` contains Firebase client identifiers/API key, which are APK-public identifiers rather than server secrets; Firebase/Google API restrictions must be verified in cloud configuration. No private keys or live bearer credentials were confirmed by repository scan.

## Android and web

Android uses only an HTTPS auto-verified App Link for KYC return and does not declare cleartext traffic. Sensitive native auth storage uses the secure storage abstraction, while web necessarily uses browser storage and is therefore exposed to successful same-origin XSS. The embedded map WebView deserves continued origin/navigation hardening review. Production nginx supplies nosniff/referrer controls, but CSP, frame-ancestors/X-Frame-Options, Permissions-Policy, and HSTS should be verified at the final CDN/load-balancer response. Bearer-token APIs reduce classic cookie CSRF exposure; XSS remains capable of acting as the user. Deep-link inputs must remain hints only and be resolved through authorized APIs.

## Dependencies and supply chain

Python/npm manifests and GitHub Actions were statically inspected. Lockfiles are present. Automated destructive upgrades were not run. Dependency audit results are recorded in CI/test output for this change; advisories require controlled, tested upgrades. Release workflows should keep least-privilege `permissions` and pin third-party actions to immutable commit SHAs. No dependency-confusion exploit was validated.

## Rejected false positives

* Firebase Android API keys are public client identifiers, not confidential credentials by themselves; unrestricted cloud-side use would be the vulnerability.
* Bearer tokens stored in browser storage are not automatically a confirmed exploit without an XSS or malicious same-origin execution path.
* Public Cashfree/KYC return pages do not themselves alter trusted state.
* User-supplied map queries are sent to fixed Google endpoints and are not generic SSRF destinations.
* TypeScript types were not counted as runtime validation; backend Pydantic models and explicit checks provide the relevant boundary controls.

## Language-security assessment

Python/FastAPI remains appropriate for API orchestration because Pydantic boundary models, explicit dependencies, parameterized Mongo documents, and tests address the relevant risks. TypeScript/React/React Native remains appropriate for UI and client contracts; strict mode is enabled, but server validation remains authoritative. Shell/YAML/JavaScript are appropriate for CI/build plumbing when inputs remain repository-controlled. No file has a justified Rust/Go migration: there is no custom cryptographic primitive, untrusted binary parser beyond maintained imaging libraries, or isolated performance-critical security component with the tests/rollback plan required to justify migration.

## Coverage, patches, and remaining risk

Every tracked file is listed and classified in `docs/SECURITY_FILE_INVENTORY.md`; textual files were included in secret/dangerous-API searches and source groups were reviewed by entry point. Added security regression coverage blocks the confirmed authentication and privilege-bootstrap flaws. Remaining work requiring staging/provider infrastructure includes full cross-tenant endpoint mutation, OTP/rate-limit concurrency, Cashfree/DigiLocker replay tests, passkey origin ceremony tests on real Android, APK/manifest inspection of a release AAB, cloud IAM/API-key review, DAST, and manual browser CSP/caching verification. Existing hard-coded Authority rows and review fixtures in deployed databases must be inventoried and disabled outside a time-boxed review.
