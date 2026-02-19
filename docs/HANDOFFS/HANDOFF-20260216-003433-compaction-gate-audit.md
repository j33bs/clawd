# Handoff: System-2 Dispatch Compaction Gate + Request-Size Audit

Date: 2026-02-16

## Problem
We observed provider-side `400` failures that indicate the request payload/context is too large (example class: "reduce the length / context length exceeded"). This can happen on Groq (and could also happen on local OpenAI-compatible backends) and previously provided no structured signal about:

- Which provider/model rejected the request due to size
- How large the request was (without logging any content)
- Whether a compact+retry would succeed

## Change Summary (LOAR-aligned)
Updated the System-2 FreeComputeCloud dispatch loop to add:

1. **Secret-safe request shape audit events** before each provider call:
   - Counts only (no content): total chars, per-role chars, message count.
2. **Provider/model max-chars budget resolver** with env overrides.
3. **Compaction gate** that triggers only when necessary and retries once:
   - Preflight: only when `char_count_total > max_chars * 1.05`
   - Error-trigger: only on likely size errors (`statusCode` in `{400, 413}` with size/context keywords)
   - Bounded compaction to `target_chars = floor(max_chars * 0.90)`
   - Retry once per provider/model attempt; does not change routing order.
4. **Audit trail when all candidates fail** via an emitted summary event.

All of this is implemented without logging message content and without changing schemas/contracts.

## Where
- `/Users/heathyeager/clawd/core/system2/inference/provider_registry.js`
- `/Users/heathyeager/clawd/tests/freecompute_cloud.test.js` (new deterministic tests)

## New/Updated Events (no content)
Emitted via the existing registry event emitter:

- `freecompute_dispatch_request_shape`
  - `{ provider_id, model_id, messages_count, char_count_total, system_chars, user_chars, assistant_chars }`
- `freecompute_dispatch_error_shape`
  - `{ provider_id, model_id, statusCode, err_code, err_kind, messages_count, char_count_total }`
- `freecompute_dispatch_compaction_applied`
  - `{ provider_id, model_id, trigger, before_chars, after_chars, messages_before, messages_after }`
  - `trigger` is one of: `preflight`, `error_400`, `error_413`
- `freecompute_all_candidates_failed`
  - `{ taskClass, attempts: [{ provider_id, model_id, kind, statusCode, char_count_total, messages_count }, ...] }`

## Compaction Behavior (deterministic, bounded)
- Preserves early `system` content up to a capped budget.
- Preserves the newest tail of the conversation; ensures latest user message survives (truncates if required).
- Only drops from the front and truncates oversized content with a marker.
- Never reorders messages.
- Adds a short note to the last kept system message when possible.

## Env Knobs
All are optional; defaults are safe:

- `DEFAULT_MAX_CHARS` (default `24000`)
- `GROQ_MAX_CHARS` (provider default for `groq`; falls back to `DEFAULT_MAX_CHARS`)
- `LOCAL_MAX_CHARS` (provider default for `local_vllm` / `ollama`)
- `LOCAL_DEFAULT_MAX_CHARS` (default `32000` if `LOCAL_MAX_CHARS` unset)
- Per-provider+model override:
  - `OPENCLAW_MAX_CHARS__<PROVIDER>__<MODEL>`
  - `<PROVIDER>` is uppercased and non-alnum replaced with `_`
  - `<MODEL>` is the model id uppercased with non-alnum replaced with `_`
  - Example shape: `OPENCLAW_MAX_CHARS__GROQ__LLAMA_3_3_70B_VERSATILE`

## Verification
1. Unit tests:
   - `npm test`
2. Runtime (secret-safe):
   - Ensure events are being recorded by your System-2 event sink (if enabled).
   - Run a request that previously failed with size-related `400` and confirm:
     - The failing provider/model is visible via `freecompute_dispatch_error_shape`
     - A single compact+retry occurs (if applicable)

## Revert
Revert the commit that introduced this handoff (and the code change) with:

- `git revert <commit>`

