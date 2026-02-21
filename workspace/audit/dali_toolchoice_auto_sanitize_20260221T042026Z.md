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

## Bypass Detector Hardening (2026-02-21)

### Branch
- `fix/dali-toolchoice-auto-bypass-detector-20260221T043027Z`

### Phase 1 — Dispatch Census (exhaustive)

Commands run:
- `rg -n --hidden --glob '!**/.git/**' -S "tool_choice|\btools\b|tool_calls|function_call" .`
- `rg -n --hidden --glob '!**/.git/**' -S "requests\.|httpx\.|aiohttp\.|urllib3\." .`
- `rg -n --hidden --glob '!**/.git/**' -S "fetch\(|axios\(|http\.request\(|https\.request\(" .`

Relevant outbound paths and sanitizer status:
- `workspace/scripts/policy_router.py:_call_openai_compatible`
  - Outbound: `requests.post(.../chat/completions)`
  - Reaches: Dali policy providers of type `openai_compatible` (e.g., groq/qwen/minimax aliases per policy)
  - Sanitizer: **YES** (final-boundary guard + sanitizer)
- `workspace/scripts/policy_router.py:_call_anthropic`
  - Outbound: `requests.post(.../messages)`
  - Reaches: Dali anthropic providers
  - Sanitizer: **YES** (final-boundary guard + sanitizer, unsupported caps)
- `workspace/scripts/policy_router.py:_call_ollama`
  - Outbound: `requests.post(.../api/generate)`
  - Reaches: Dali ollama providers
  - Sanitizer: **YES** (final-boundary guard + sanitizer, unsupported caps)
- `core/system2/inference/provider_adapter.js:_httpPost`
  - Outbound: Node provider adapter final POST
  - Reaches: gateway/system2 openai-compatible + vendor providers using adapter
  - Sanitizer: **YES** (final-boundary guard + sanitizer)
- `core/system2/inference/local_vllm_provider.js:_sanitizePayloadForToolCalls` before `_httpRequest/_streamRequest`
  - Outbound: local vLLM `/chat/completions`
  - Reaches: local_vllm provider
  - Sanitizer: **YES** (final-boundary guard + sanitizer)
- `scripts/system2_http_edge.js:proxyUpstream` (`http.request`)
  - Outbound: raw proxy to upstream gateway (`/rpc/*`)
  - Reaches: gateway RPC surface (opaque pass-through)
  - Sanitizer: N/A at proxy body level; relies on downstream final-boundary sanitizers above

Non-LLM outbound paths observed:
- `workspace/scripts/message_handler.py` uses `aiohttp` for gateway messaging/spawn APIs, not direct provider chat payload dispatch.

### Phase 2/3 — Unavoidable Final-Boundary Guard + Sanitizer

Canonical Python module (`workspace/scripts/tool_payload_sanitizer.py`) now provides:
- `sanitize_tool_payload(payload, provider_caps)`
- `resolve_tool_call_capability(provider, model_id)` (fail-closed unknown => false)
- `enforce_tool_payload_invariant(payload, provider_caps, provider_id, model_id, callsite_tag)`

Strict mode behavior:
- `OPENCLAW_STRICT_TOOL_PAYLOAD=1` + invalid shape (`tool_choice` present without non-empty `tools`) => raises structured `ToolPayloadBypassError` including:
  - `provider_id`, `model_id`, `callsite_tag`, remediation
- strict mode off => structured warning to stderr, then sanitize and continue

Callsite tags:
- `policy_router.final_dispatch` (Dali Python boundary)
- `gateway.adapter.final_dispatch` (Node adapter boundary)

### Phase 4 — Runtime Identity Helper (stale-code trap)

Added:
- `workspace/scripts/diagnose_tool_payload_runtime.py`

What it prints:
- absolute module path for `policy_router`
- absolute module path for `tool_payload_sanitizer`
- git SHA (best-effort from `.git/HEAD`)
- `OPENCLAW_STRICT_TOOL_PAYLOAD` state

Interactive command:
- `python3 workspace/scripts/diagnose_tool_payload_runtime.py`

Service-context inspection commands:
- `systemctl --user show openclaw-gateway.service --property=ExecStart --no-pager`
- `systemctl --user show openclaw-gateway.service --property=Environment --no-pager`
- Compare service `ExecStart`/workspace with helper output from the same host.

Observed helper output:
- `policy_router_module_path=/home/jeebs/src/clawd/workspace/scripts/policy_router.py`
- `tool_payload_sanitizer_module_path=/home/jeebs/src/clawd/workspace/scripts/tool_payload_sanitizer.py`
- `git_sha=025483c5464a`
- strict disabled by default

### Phase 5 — Tests

Added/updated:
- `tests_unittest/test_policy_router_tool_payload_sanitizer.py`
  - Added strict-mode structured raise assertion
- `tests/providers/tool_payload_sanitizer.test.js`
  - Added strict-mode structured bypass error assertion

### Phase 6 — Verification Evidence

Commands run:
- `python3 -m py_compile workspace/scripts/tool_payload_sanitizer.py workspace/scripts/policy_router.py workspace/scripts/diagnose_tool_payload_runtime.py`
- `python3 -m unittest tests_unittest.test_policy_router_tool_payload_sanitizer`
- `node tests/providers/tool_payload_sanitizer.test.js && node tests/providers/provider_adapter_tool_payload.test.js && node tests/providers/local_vllm_provider.test.js`

All passed.

Strict repro (Dali boundary):
- `OPENCLAW_STRICT_TOOL_PAYLOAD=1 python3 - <<'PY' ... mod._call_openai_compatible(..., {'tool_choice':'auto'}, provider_caps={'tool_calls_supported': True}) ... PY`

Observed:
- `strict.error_type=ToolPayloadBypassError`
- `strict.code=TOOL_PAYLOAD_SANITIZER_BYPASSED`
- `strict.callsite_tag=policy_router.final_dispatch`
- `strict.provider_id=openai_compatible`
- `strict.model_id=model-a`

Strict repro (Node adapter boundary):
- `OPENCLAW_STRICT_TOOL_PAYLOAD=1 node - <<'NODE' ... adapter._httpPost(... tool_choice:'auto' without tools) ... NODE`

Observed:
- `node.strict.code=TOOL_PAYLOAD_SANITIZER_BYPASSED`
- `node.strict.callsite_tag=gateway.adapter.final_dispatch`
- `node.strict.provider_id=provider_x`
- `node.strict.model_id=model-a`

Diagnosis guidance from evidence:
- If real run still returns original vLLM `auto tool choice` error and strict guard does **not** trigger, runtime is likely executing stale codepath/module instance. Use runtime helper + service `ExecStart` inspection to confirm.
