# Order automation operations

`order_status_history` remains the authoritative event ledger. The API materializes
each history row into a deduplicated queue record; integrations can only claim,
acknowledge, or fail these records and have no status-mutation capability.

## Configuration

Set `AUTOMATION_WORKER_TOKEN` and `AUTOMATION_CALLBACK_TOKEN` (at least 32 characters)
in the secret store. Provider
workers may separately use provider-specific environment variables such as
`VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `N8N_WEBHOOK_URL`, and
`N8N_WEBHOOK_SIGNING_SECRET`; values must never be stored in the repository or
forwarded in event payloads. Providers are optional and disabled when unconfigured.

The n8n adapter signs the canonical JSON body with HMAC-SHA256 and sends a timestamp
and history-derived idempotency key. Vapi uses bearer authentication and the same
idempotency key. SMS and WhatsApp use Twilio HTTP Basic authentication, while push
uses the existing Firebase OAuth adapter. Provider callbacks use the distinct
`AUTOMATION_CALLBACK_TOKEN` and accept only normalized IDs/status/failure metadata.

Deployments also set `AUTOMATION_ENABLED` and independently control
`AUTOMATION_N8N_ENABLED`, `AUTOMATION_VOICE_ENABLED`, `AUTOMATION_WHATSAPP_ENABLED`,
`AUTOMATION_SMS_ENABLED`, `AUTOMATION_EMAIL_ENABLED`, and `AUTOMATION_PUSH_ENABLED`.
All flags default off. A durable action row is unique per history event and channel,
so a retry skips channels already completed. Configuration errors become permanent
action failures; transient delivery errors use the bounded event retry schedule.

Workers claim events with a bounded lease. Every acknowledgement/failure must carry
the opaque lease token, preventing a stale worker from completing a reclaimed event.
Failures retry with bounded delay and move to `DEAD_LETTER` after five attempts.
Provider persistence is restricted to identifiers, status, timestamps, and a bounded
failure reason. Customer channel workers must enforce the event's opt-out and quiet-
hours policy before delivery.

Conversational ordering is authenticated and two phase: preparation verifies KYC and
returns a safe summary, while a distinct explicit-confirmation request delegates to
the existing order endpoint. Customer-scoped idempotency prevents duplicate orders.
Voice users must approve the authenticated in-app action; they must never speak an
OTP, password, passkey, or recovery code to an assistant.

## Rollout and rollback

Roll out with provider workers disabled, inspect backfill/queue counts, then enable
channels incrementally. To roll back, stop workers and deploy the prior API; the
history ledger and queued records remain intact for replay. Rotate the worker token
immediately on suspected disclosure. Dead letters require an operator review before
replay; never edit order status as part of replay.
