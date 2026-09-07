# Four-state RMC Places collector

Isolated Cloud Run Job for collecting Google Places RMC plant and supplier
records for Maharashtra, Goa, Karnataka, and Gujarat. It does not connect to
the TrackMyRMC database or serve HTTP traffic.

## Security

- Inject `GOOGLE_PLACES_API_KEY` from Secret Manager at runtime.
- Never pass the key as a literal command-line environment value.
- The job logs aggregate counts and Place IDs only; it never logs request
  headers or secret values.
- Output goes to a private Cloud Storage bucket with public access prevention.

## Coverage source

`data/coverage.csv` combines:

- the [Local Government Directory](https://lgdirectory.gov.in/downloadDirectory.do)
  subdistrict export [mirrored on 2026-06-21](https://gist.github.com/planemad/b2195c7feb506f8436659f36da1e58af);
- a [2026 Karnataka taluk supplement](https://en.wikipedia.org/wiki/List_of_taluks_of_Karnataka)
  because the LGD mirror omits newer taluks, with current district naming
  checked against the [Integrated Government Online Directory](https://igod.gov.in/sg/KA/E042/organizations);
- Mumbai City and Mumbai Suburban administrative supplements.

The collector resolves each taluka centre through Google Places before running
all ten RMC search terms with a geographic radius. High-density districts also
receive a five-point adaptive grid. A failed or fallback centre is explicitly
reported in `SEARCH_COVERAGE`.

## Required environment

| Variable | Purpose |
| --- | --- |
| `GOOGLE_PLACES_API_KEY` | Secret Manager injected Places key |
| `OUTPUT_BUCKET` | Private output bucket name |
| `STATES` | `Maharashtra|Goa|Karnataka|Gujarat` by default |
| `MAX_TEXT_REQUESTS` | Safety cap, default `34000` |
| `MAX_DETAIL_REQUESTS` | Safety cap, default `6500` |
| `RESUME` | Resume private checkpoint, default `true` |

The default request caps are intentionally below the published India monthly
free-usage caps for the relevant Places Pro and Enterprise categories. They are
still safety caps, not a guarantee of zero cost: previous monthly usage and the
billing account's eligibility determine actual charges.

## Output

Objects are written under `rmc-places/runs/<run-id>/` and
`rmc-places/latest/`:

- `MAHARASHTRA_RMC_PLACES_MASTER.xlsx`
- `GOA_RMC_PLACES_MASTER.xlsx`
- `KARNATAKA_RMC_PLACES_MASTER.xlsx`
- `GUJARAT_RMC_PLACES_MASTER.xlsx`
- `coverage-report.json`
- `raw-candidate-audit.json.gz`

The process exits `0` only when every planned search completed without a quota,
safety-cap, centre-resolution, or API error. It exits `2` for a valid but
incomplete collection so the output cannot be mislabelled complete.

## Deploy

From this directory in Cloud Shell:

```bash
export OUTPUT_BUCKET="trackmyrmc-rmc-places-224495133432"
chmod +x deploy-cloud-run-job.sh
./deploy-cloud-run-job.sh
```

Deployment creates or updates only the separate Cloud Run Job. It does not
execute the collection and does not deploy the TrackMyRMC web service.
