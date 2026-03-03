# Event Envelope Schema (Golden)

Schema id: `openclaw.event_envelope.v1`

## Required Keys

- `schema` (string)
  - Must equal `openclaw.event_envelope.v1`
- `ts` (string)
  - UTC ISO8601 timestamp (`YYYY-MM-DDTHH:MM:SSZ`)
- `event` (string)
  - Stable event name, lowercase snake/camel allowed
- `severity` (string)
  - One of `INFO`, `WARN`, `ERROR`
- `component` (string)
  - Emitter component id, e.g. `provider_diag`, `dali_canary_runner`, `vram_guard`
- `corr_id` (string)
  - Correlation id (may be empty string for local/manual checks)
- `details` (object)
  - Structured metadata for the event

## Forbidden Keys (Any Depth)

The following keys MUST NOT appear anywhere in `details` payloads:

- `prompt`
- `text`
- `body`
- `document_body`
- `messages`
- `content`
- `raw_content`
- `raw`

## Notes

- The envelope is designed for gate/health observability and replay-safe auditing.
- Payloads must be metadata-only; never include raw user documents or prompt text.
- Producers in Python and Node MUST emit the same top-level keys and types.
