# Application security audit (2026-09-01)

## Uploads

The only upload route accepts authenticated Driver POD images tied to an active trip. It enforces a configurable byte limit while streaming, verifies decoded image content and pixel count with Pillow, accepts only JPEG/PNG/WebP, and compares the declared media type. Images are re-encoded before storage to remove metadata and trailing/polyglot payloads. Object names are random, downloads require object-level authorization, and responses force attachment download with `nosniff` and a sandbox CSP. Production storage is private GCS or the isolated object-store service; local storage under `/tmp` is rejected outside development/test.

## Error handling and validation

Unhandled exceptions are logged server-side with request context and full traceback, but return only a generic message. Schema errors similarly return a generic response while detailed validation diagnostics are logged. All request models reject undeclared fields and trim strings; individual schemas additionally constrain types, lengths, ranges, patterns, and enumerations.

## Rate limits

Every API request is limited. Authentication/deletion routes use independent per-IP and SHA-256-hashed per-account counters with bounded exponential `Retry-After` backoff and no hard lockout. Public requests have moderate limits and bearer-authenticated requests have looser limits. Every threshold/window/backoff value is configured by environment variables. Deployments with multiple workers should replace the in-process counter store with a shared atomic store to enforce a fleet-wide aggregate.

## Dependencies

`pip-audit` initially reported nine Starlette advisories (severity was not supplied by that data source). FastAPI and Starlette were upgraded to 0.141.1 and 1.6.0 respectively, clearing the Python runtime audit. npm overrides safely update vulnerable transitive `@eslint/plugin-kit`, PostCSS, UUID, and `decode-uri-component` versions.

Eight **high** npm findings remain, all from two denial-of-service advisories against `image-size` through Expo 54/Metro. npm reports that remediation requires the breaking Expo 57 upgrade, so it was intentionally not forced into this security patch. Overriding `image-size` alone is unsafe because Expo 54's Metro version requires the 1.x CommonJS API. The package is build tooling rather than backend request-processing code; schedule and test the coordinated Expo SDK migration separately.

## Secrets

Repository scanning found no private keys, AWS keys, bearer tokens, passwords, or server API secrets. Runtime secrets are read from environment variables, production rejects missing/weak authentication secrets, and environment/credential files are ignored. `frontend/google-services.json` contains the Firebase Android API identifier required in a compiled client; Google documents these identifiers as non-secret. It must nevertheless be restricted in Google Cloud to the Android package/signing certificate and only non-sensitive Firebase APIs.
