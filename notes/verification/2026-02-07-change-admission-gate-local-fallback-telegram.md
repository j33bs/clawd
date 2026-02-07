# Change Admission Gate - Local Fallback + Telegram Hardening (2026-02-07)

## Design Brief
- Add local continuity providers (Ollama + OpenAI-compatible) and gate them behind intent allowlist.
- Make local fallback last-resort only for rate-limit/cooldown/timeout/network failures.
- Add Telegram circuit breaker and backoff to reduce thrash and unhandled rejections.

## Evidence Pack
- New providers and routing policy wired in `core/` with strict caps.
- Telegram circuit breaker + retry behavior tested with unit tests.
- Local fallback routing verified via `scripts/verify_local_fallback.js`.

## Rollback Plan
- Disable local fallback by unsetting `OPENCLAW_LOCAL_FALLBACK`.
- Revert router/provider and Telegram changes via git if needed.

## Budget Envelope
- Local inference capped at 256 tokens (512 max) and 2048 context.
- Telegram retries capped (chat actions <=2 retries, messages <=4 retries).

## Expected ROI
- Maintains continuity during provider rate limits/timeouts.
- Reduces Telegram log spam and keeps pipeline responsive.

## Kill-Switch
- `OPENCLAW_LOCAL_FALLBACK=0` disables local continuity routing.
- Telegram breaker auto-disables chat actions on repeated failures.

## Post-Mortem
- Review fallback events in `logs/fallback_events.json` and Telegram failure trends.
- Adjust allowlist or thresholds if misuse is detected.
