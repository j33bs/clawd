# Change Admission Gate Record — Prompt audit instrumentation

## Design brief
- Expand append-only prompt-size audit logging at the model invocation boundary (`core/model_call.js`) to emit phase-based records (`embedded_prompt_before`, `before_call`, `embedded_attempt`) with size-only metadata and stable hash.
- Keep logging content-free (sizes, booleans, hashes only), with non-fatal logging failure handling.
- Add synthetic model-call audit coverage in `tests/model_call_prompt_audit.test.js`.
- Scope is instrumentation only; no routing/provider behavior change.

## Evidence pack
- `node tests/model_call_prompt_audit.test.js` passes.
- `node tests/prompt_audit.test.js` passes.
- `node tests/chain_budget.test.js` passes.
- `node tests/chain_runner_smoke.test.js` passes.
- Commit scope limited to model-call audit instrumentation and test coverage.

## Rollback plan
- Revert this commit to remove prompt-audit instrumentation and test additions.
- Confirm baseline by re-running `node tests/chain_budget.test.js` and `node tests/chain_runner_smoke.test.js`.

## Budget envelope
- Runtime overhead limited to per-call character counting, hashing, and one JSONL append write.
- No model token budget increase; no new provider calls.

## Expected ROI
- Provides concrete observability into prompt growth/overflow vectors and model/backend context pressure with low overhead.
- Enables governed diagnosis before behavioral changes.

## Kill-switch
- Remove or bypass prompt-audit writes by reverting this change if performance or stability issues occur.
- Logging failures are non-fatal and do not block model execution.

## Post-mortem
- If overflow persists after instrumentation, document observed size vectors and follow-on budget/routing fixes in a subsequent admitted change.
