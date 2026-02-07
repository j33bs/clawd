# Telegram / Local-Fallback Workstream — Design Brief

## Objective
- Establish a governed, auditable reliability layer for Telegram interactions and local model fallback so the system remains responsive under network errors, provider outages, and rate limits.
- Ensure continuity behavior is explicit, bounded, and observable without changing main routing semantics or introducing new external dependencies.

## In Scope
- Telegram client
- Circuit breaker / backoff
- Local fallback providers (ollama / openai-compat / etc.)
- Continuity prompt handling (if applicable)

## Out of Scope
- Anything not strictly required for reliable ingestion + fallback routing.

## Invariants
- No secrets committed
- Deterministic routing decisions where possible
- Fallbacks are auditable (trace/log)
- Main branch stability is preserved
- Tests gate behavior changes

## Failure Modes to Handle
- Network outage
- API auth failure
- Rate limiting
- Provider timeouts
- Telegram API errors

## Test Plan
- Unit tests:
  - circuit breaker
  - backoff
  - routing under failure modes
- Integration smoke:
  - simulate provider failure → fallback engaged
- Regression:
  - ensure no change to chain routing semantics

## Rollback Plan
- Revert this feature branch or back out the specific commits (tests, implementation, integration, tooling) in reverse order.
- Disable feature flags or fallback pathways introduced in this stream to restore baseline behavior.

## Admission Criteria (for merge to main)
- All tests pass
- No secrets detected
- Logs/traces show correct fallback behavior
- Review of diff scope vs this brief
