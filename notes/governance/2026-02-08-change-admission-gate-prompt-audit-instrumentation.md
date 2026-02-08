# Change Admission Gate Record — Prompt audit instrumentation

## Design brief
- Expand append-only prompt-size audit logging at the model invocation boundary (`core/model_call.js`) to emit phase-based records (`embedded_prompt_before`, `before_call`, `embedded_attempt`) with size-only metadata and stable hash.
- Keep logging content-free (sizes, booleans, hashes only), with non-fatal logging failure handling.
- Add synthetic model-call audit coverage in `tests/model_call_prompt_audit.test.js`.
- Enforce deterministic prompt budget caps and model-window preflight before provider calls, with a controlled no-provider block response when caps cannot be met.

## Evidence pack
- `node tests/model_call_prompt_audit.test.js` passes.
- `node tests/prompt_audit.test.js` passes.
- `node tests/chain_budget.test.js` passes.
- `node tests/chain_runner_smoke.test.js` passes.
- `node scripts/verify_model_routing.js` passes (5/5).
- Commit scope limited to model-call audit instrumentation plus budget/preflight guardrails.

## Rollback plan
- Revert the latest prompt-budget/preflight commit if guarded truncation causes regressions.
- Confirm baseline by re-running `node scripts/verify_model_routing.js`, `node tests/chain_budget.test.js`, and `node tests/chain_runner_smoke.test.js`.

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

## Runtime hotfix deprecation
- Previously applied runtime bundle hotfixes in global installs were temporary forensic mitigation only.
- Repository source is now canonical for prompt budget, preflight, and audit behavior.
- Any remaining global `.bak.*` runtime artifacts are non-authoritative and must not be relied upon.
