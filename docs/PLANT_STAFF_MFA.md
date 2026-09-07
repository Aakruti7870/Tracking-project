# Plant Staff Authenticator MFA

Approved Plant Staff accounts use email only for first-login/bootstrap. Normal authentication is Authenticator TOTP or an enrolled passkey. Central Admin remains on its dedicated Control Center authentication boundary.

## Production secret

Add one server-side Cloud Run secret/environment variable before enabling enrollment:

- `MFA_ENCRYPTION_KEY` — random value of at least 32 characters; keep it stable because it encrypts enrolled TOTP secrets.
- optional `MFA_ISSUER` — defaults to `TrackMyRMC` and is the label shown in Authenticator apps.

If `MFA_ENCRYPTION_KEY` is absent in production, the service still starts and existing email OTP continues to work for ordinary Plant Staff that have not yet enrolled MFA. MFA endpoints fail closed until the key is configured. Central Admin never falls back to an ordinary Plant Staff bearer when Control Center MFA is unavailable.

## Login lifecycle

1. Unknown email -> existing TMRMC onboarding flow.
2. Approved Plant Staff without MFA -> email OTP bootstrap.
3. The bootstrap session can access only `/api/me`, logout, and MFA enrollment endpoints.
4. User scans the QR code (or uses the manual key), confirms the current six-digit TOTP, and receives ten one-time recovery codes.
5. Ordinary Plant Staff bootstrap is promoted only after TOTP confirmation; other pre-enrollment sessions are revoked.
6. Future Plant Staff login -> approved email + passkey when available, otherwise Authenticator code. Email OTP cannot bypass enrolled MFA.
7. Lost Plant Staff device -> one-time recovery code, or audited Owner/Authority reset within the existing operational authorization boundary.

### Retired Google staff login

The historical `/api/auth/google/*` Plant Staff OAuth surface is retired and must not mint TrackMyRMC staff sessions. The server request boundary returns `410 Gone` for that path. Current Plant Staff authentication is the approved-email bootstrap followed by TOTP/passkey flow above. Google configuration, if still present for rollback archaeology, is not an active login authority.

## Central Admin lifecycle

- Central Admin is not part of the ordinary Plant Staff role set. An approved Central Admin may use email OTP only for a restricted first-time MFA enrollment bootstrap.
- Completing Central Admin enrollment revokes that bootstrap and requires a fresh sign-in through the dedicated web Control Center.
- Central Admin recovery uses a one-time recovery code through `/api/admin/auth/recover`. It revokes active administrator sessions, invalidates the old TOTP/recovery set, and issues only a short-lived re-enrollment bootstrap.
- The recovery/bootstrap token never receives `control_center_web` provenance and cannot become a privileged Control Center session.
- A full Control Center session is fail-closed to `/api/admin/*`, `/api/control-center/*`, `/api/me`, and logout. Legacy operational staff routes cannot be used as a permission bypass.

## Reset authorization

- Plant Owner: may reset MFA only for non-owner staff in the Owner's own plant, and must confirm the Owner's own TOTP.
- Authority: may reset plant accounts but not Authority/Central Admin accounts, and must confirm Authority's own TOTP.
- Central Admin: legacy Plant Staff reset is not exposed through the Control Center. A dedicated permission-gated Login / OTP administration contract must be implemented before such a capability is activated.

A permitted reset revokes all active sessions for the target account and writes an audit event.

## Passkeys

Passkey/WebAuthn support is implemented for ordinary Plant Staff on the canonical `https://trackmyrmc.com` relying-party origin.

- Authentication requires WebAuthn user verification.
- The mobile app uses a short-lived browser ceremony; JWT bearer tokens are never placed in the URL.
- Browser request IDs, challenges, and app handoff codes are random, short-lived, and single-use.
- The server stores the credential public key and metadata, never the user's private passkey.
- Registering or removing a passkey requires a fresh Authenticator TOTP, making TOTP the credential-management authority.
- Central Admin does not use the ordinary Plant Staff passkey router; its privileged login remains the dedicated Control Center MFA boundary.
