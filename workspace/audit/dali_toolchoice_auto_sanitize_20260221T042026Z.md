# Dali Audit: Tool Choice Auto Sanitization

- Timestamp (UTC): 2026-02-21T04:20:26Z
- Branch: fix/dali-toolchoice-auto-sanitize-20260221T042026Z
- Baseline SHA: 23c831e
- Node: v22.22.0
- Python: Python 3.12.3

## Baseline Worktree

```text
 M workspace/hivemind/hivemind/reservoir.py
 M workspace/policy/llm_policy.json
 M workspace/scripts/policy_router.py
 M workspace/state/tacti_cr/events.jsonl
?? core/system2/inference/concurrency_tuner.js
?? core/system2/inference/gpu_guard.js
?? docs/GPU_SETUP.md
?? scripts/vllm_launch_optimal.sh
?? scripts/vllm_prefix_warmup.js
?? workspace/NOVELTY_LOVE_ALIGNMENT_RECS.md
?? workspace/NOVELTY_LOVE_ALIGNMENT_TODO.md
?? workspace/artifacts/itc/events/itc_events.jsonl
?? workspace/scripts/vllm_metrics_sink.py
```

## Known Failure Signature (Pre-fix)

Expected error signature from Dali/openai-compatible tool payload mismatch:
- `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

## Planned Repro Command(s)

- Minimal deterministic payload repro via Dali path (`workspace/scripts/policy_router.py` openai-compatible dispatch), asserting outbound payload must not contain `tool_choice` when `tools` is absent/empty.

## Phase 1 Discovery (Dali Outbound Paths)

Commands run:
- `rg -n --hidden --glob '!**/.git/**' -S "tool_choice|tools\\s*[:=]|tool_calls|function_call" .`
- `rg -n --hidden --glob '!**/.git/**' -S "fetch\\(|axios\\(|http\\.request\\(|https\\.request\\(" .`
- `rg -n --hidden --glob '!**/.git/**' -S "requests\\.|httpx\\.|aiohttp\\.|urllib3\\." .`

Key Dali findings:
- `workspace/scripts/policy_router.py:612` `_call_openai_compatible(...)` -> `requests.post(...)`
- `workspace/scripts/policy_router.py:645` `_call_anthropic(...)` -> `requests.post(...)`
- `workspace/scripts/policy_router.py:694` `_call_ollama(...)` -> `requests.post(...)`

Last responsible moments before network dispatch:
- OpenAI-compatible: payload passed to `requests.post` in `_call_openai_compatible`
- Anthropic: payload mapped to request body in `_call_anthropic`
- Ollama: payload mapped to request body in `_call_ollama`

## Phase 2-4 Implementation Summary

Canonical sanitizer module added:
- `workspace/scripts/tool_payload_sanitizer.py`

Implemented:
- `sanitize_tool_payload(payload, provider_caps)`
- `resolve_tool_call_capability(provider, model_id)` (fail-closed)

Rules enforced:
- tools missing/not-list/empty => remove `tools` and `tool_choice`
- `tool_calls_supported` not explicitly true => remove both
- unknown capability defaults to `tool_calls_supported=false`
- never inject `tool_choice:"none"`

Wiring:
- `workspace/scripts/policy_router.py`
  - `_call_openai_compatible(..., provider_caps=...)` sanitizes immediately pre-dispatch
  - `_call_anthropic(...)` sanitizes with explicit unsupported caps
  - `_call_ollama(...)` sanitizes with explicit unsupported caps
  - openai-compatible dispatch now derives caps via `resolve_tool_call_capability(provider, model_id)`

Invariant comments added at final dispatch points.

## Phase 5 Regression Tests

Added:
- `tests_unittest/test_policy_router_tool_payload_sanitizer.py`

Covered cases:
- A) `tool_choice:auto` + missing tools => `tool_choice` removed
- B) `tool_choice:auto` + `tools:[]` => both removed
- C) `tool_calls_supported=false` => both removed even when tools present
- fail-closed unknown capability => strips both
- D) integration-style `_call_openai_compatible` captures sanitized body before network dispatch

## Phase 6 Repro Verification

Deterministic repro command:
- `python3 - <<'PY'` script simulating endpoint behavior:
  - before: returns 400 with signature when `tool_choice=auto` and no tools
  - after: invokes Dali `_call_openai_compatible` with sanitizer + captured outbound payload

Observed output:
- `before.status=400`
- `before.signature="auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`
- `after.ok=True`
- `after.has_tool_choice=False`
- `after.payload={'model': 'model-a', 'messages': [{'role': 'user', 'content': 'hi'}]}`

Conclusion:
- Dali no longer emits `tool_choice` when `tools` is absent/empty.
- Dali strips tool payloads for unsupported/unknown capability (fail closed).

## Verification Commands and Results

Passed:
- `python3 -m py_compile workspace/scripts/tool_payload_sanitizer.py workspace/scripts/policy_router.py`
- `python3 -m unittest tests_unittest.test_policy_router_tool_payload_sanitizer`

Not included due known unrelated drift in current workspace:
- `python3 -m unittest tests_unittest.test_policy_router_teamchat_intent` (fails before dispatch with `no_provider_available` from unrelated routing drift)

## Files Changed

- `workspace/scripts/tool_payload_sanitizer.py`
- `workspace/scripts/policy_router.py`
- `tests_unittest/test_policy_router_tool_payload_sanitizer.py`
- `workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md`
