# Fresh production verification checklist

Before merging this release candidate:

- [ ] Pre-AAB End-to-End Gate passes on the exact PR SHA.
- [ ] Production Readiness passes on the exact PR SHA.
- [ ] Frontend typecheck, lint, Expo Doctor, and web build are green.
- [ ] Android standalone release compilation/signature validation is green.
- [ ] Passkey ceremony callback stability regression is resolved.
- [ ] `support@trackmyrmc.com` resolves to `central_admin` and still requires dedicated portal TOTP authentication.

After merge to `main`:

- [ ] Backend deployment is healthy.
- [ ] Web deployment is healthy.
- [ ] `trackmyrmc.com/` and `/login` serve the new Expo UI, not legacy landing copy.
- [ ] `www.trackmyrmc.com/` opens the fresh TrackMyRMC experience without 502.
- [ ] Legal routes are current and public.
- [ ] `/.well-known/assetlinks.json` contains `com.trackmyrmc.concreteking`.
- [ ] Plant Staff first-login email OTP delivery is verified with the production SendGrid configuration.
- [ ] Create a release branch from the final green `main` SHA to trigger the signed AAB workflow.
- [ ] Signed AAB is `2.0.28` / versionCode `86`, bundletool-valid, upload-signed, and pinned to `https://trackmyrmc.com`.
- [ ] Only that final AAB is used for the next Google Play Console upload.
