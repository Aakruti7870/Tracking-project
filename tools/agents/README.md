# NVIDIA analysis agents

These dependency-free Node/TypeScript tools delegate **read-only analysis** while Codex remains the only editor and final verifier. They require Node 22.6+ (native TypeScript type stripping).

## Configuration

Set `NVIDIA_API_KEY` locally and set one or more model variables: `KIMI_MODEL`, `DEEPSEEK_MODEL`, `LAGUNA_MODEL`, and `GEMMA_MODEL`. Values are not assumed: every configured ID is checked against `GET /v1/models` before use. Never put values in source, command arguments, task text, or committed `.env` files.

```sh
npm run agents:validate
npm run agents:route -- --task "Map the modules relevant to trip tracking"
npm run agents:deepseek -- --task "Analyze this sanitized backend error"
npm run agents:laguna -- --task "Diagnose the failing build" --file test-output.txt
printf '%s' 'Review this UI concern' | npm run agents:gemma
```

Automatic routing selects Laguna for CI/build/test/log work, Gemma for frontend/UI, DeepSeek for backend/security/debugging, and Kimi otherwise. If the selected service/model fails, configured roles are tried as fallbacks and the selected role is reported. A total failure exits nonzero so Codex can perform the smallest safe local fallback.

`--file` attaches at most 60,000 characters from one explicitly named, non-sensitive file. Prefer sanitized excerpts. Paths resembling credentials, `.env`, `.git`, or `.agent-cache` are rejected.

## Operational safeguards

- Requests time out after 45 seconds by default (`AGENT_TIMEOUT_MS` may tune this), retry transient HTTP/rate-limit failures twice with backoff, and are locally spaced to reduce bursts.
- Results are capped at 1,200 tokens and normalized into summary/findings/recommendations/verification/limitations.
- Sanitized results are cached by a SHA-256 digest in ignored `.agent-cache/` files with owner-only permissions. Delete the directory to invalidate it; never treat it as a secret store.
- The API key is read only from the process environment and is never printed or cached. API errors report status codes, not response bodies.
- External agents cannot edit or run commands through this client. Codex must validate every recommendation and exclusively owns edits, commits, tests, pushes, and merges.
