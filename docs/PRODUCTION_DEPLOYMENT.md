# TrackMyRMC production deployment

This repository separates validation from production deployment.

## CI validation

`Cloud Run Container Gate` builds and boots the backend container in GitHub Actions. It proves the container can start and answer `/api/health`, but it does **not** deploy a new Google Cloud Run revision.

## Production deployment

`Deploy Production Cloud Run` is the guarded production deployment workflow. It is intentionally manual (`workflow_dispatch`) and:

1. checks out the requested candidate (default `main`),
2. authenticates to Google Cloud with GitHub OIDC / Workload Identity Federation,
3. deploys the repository Dockerfile to the configured Cloud Run service,
4. verifies `/health`, `/api/health`, `/privacy_policy`, `/terms`, and `/account-deletion`,
5. confirms the Cloud Run service is Ready,
6. probes the canonical `trackmyrmc.com` URLs separately so a domain-routing problem is visible.

### Required repository configuration

Repository variable:

- `GCP_PROJECT_ID` — Google Cloud project containing the production Cloud Run service.

GitHub Actions secrets:

- `GCP_WORKLOAD_IDENTITY_PROVIDER` — full Workload Identity Provider resource name.
- `GCP_SERVICE_ACCOUNT` — deployment service-account email.

The deployment service account needs the permissions required for Cloud Run source deployment / Cloud Build and to act as the runtime service account where applicable.

### Default deployment target

- Region: `asia-south1`
- Service: `tracking-preview-api`

Both can be overridden in the manual workflow form if the production service uses different names.

## Domain routing

A successful Cloud Run deployment does not by itself prove that `https://trackmyrmc.com` is routed to that service. Domain mapping, external HTTP(S) load balancer, Cloudflare, or another website origin can continue to serve older content.

The workflow therefore treats the canonical-domain probes as diagnostic and keeps them separate from Cloud Run deployment success. If Cloud Run serves the new routes while `trackmyrmc.com` does not, fix the domain/load-balancer/CDN origin routing rather than changing application code.
