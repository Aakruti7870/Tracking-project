# Plant Staff Authenticator MFA

This change upgrades approved Plant Staff accounts from recurring email OTP to TOTP Authenticator App login.

## Production secret

Add one server-side Cloud Run secret/environment variable before enabling enrollment:

- `MFA_ENCRYPTION_KEY` — random value of at least 32 characters; keep it stable because it encrypts enrolled TOTP secrets.
- optional `MFA_ISSUER` — defaults to `TrackMyRMC` and is the label shown in Authenticator apps.

If `MFA_ENCRYPTION_KEY` is absent in production, the service still starts and existing email OTP continues to work. MFA endpoints fail closed until the key is configured.

## Login lifecycle

1. Unknown email -> existing TMRMC onboarding flow.
2. Approved staff without MFA -> email OTP bootstrap.
3. The bootstrap session can access only `/api/me`, logout, and MFA enrollment endpoints.
4. User scans the QR code (or uses the manual key), confirms the current six-digit TOTP, and receives ten one-time recovery codes.
5. The bootstrap session is promoted to a normal session only after TOTP confirmation; other pre-enrollment sessions are revoked.
6. Future login -> approved email + Authenticator code. Email OTP cannot bypass an enrolled TOTP.
7. Lost device -> one-time recovery code, or audited Owner/Authority/Central Admin reset.

## Reset authorization

- Plant Owner: may reset MFA only for non-owner staff in the Owner's own plant, and must confirm the Owner's own TOTP.
- Authority: may reset plant accounts but not Authority/Central Admin accounts, and must confirm Authority's own TOTP.
- Central Admin: may reset any staff MFA and must confirm Central Admin's own TOTP.

A reset revokes all active sessions for the target account and writes an audit event.

## Passkeys

Native Passkey / Android Credential Manager support is deliberately isolated to a follow-up PR. The MFA/session structure in this PR is the foundation for step-up authentication and passkey enrollment without coupling a new native module to the Authenticator rollout.
