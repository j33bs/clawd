# Audit: Tool Choice Auto Sanitization

- Date (UTC): 2026-02-21T04:11:44Z
- Branch: fix/toolchoice-auto-sanitize-20260221T041144Z
- Baseline SHA before fix: ba26d91

## Objective
Prevent invalid outbound payloads that include `tool_choice` without `tools`, and enforce provider tool-call capability caps.

## Before Reproduction
Command:
- `node - <<'NODE'` (pre-fix logic replay of LocalVllmProvider tool payload builder)

Observed:
- `before.has_tool_choice=true`
- `before.payload={"tool_choice":"auto"}`

Interpretation:
- The previous shaping could emit `tool_choice="auto"` while `tools` were absent.

## After Reproduction
Command:
- `node - <<'NODE'` (current `LocalVllmProvider.generateChat` with `OPENCLAW_VLLM_TOOLCALL=1`, no `tools`, `tool_choice='auto'`, capturing outbound body)

Observed key line:
- `after.has_tool_choice=false`

Additional observed fields:
- `after.has_tools=false`
- `after.payload={"model":"qwen2.5","messages":[{"role":"user","content":"hi"}],"max_tokens":4096,"temperature":0.7,"stream":false}`

Interpretation:
- Sanitizer removed invalid `tool_choice` and ensured no empty/absent tool payload leakage.

## Regression Tests Added
- `tests/providers/tool_payload_sanitizer.test.js`
  - missing tools => strip `tool_choice`
  - empty tools => strip both
  - provider tool calls unsupported => strip both
- `tests/providers/provider_adapter_tool_payload.test.js`
  - adapter dispatch path strips invalid `tool_choice`
  - adapter dispatch path strips tools/tool_choice when model tool support is `none`
- `tests/providers/local_vllm_provider.test.js`
  - added: `generateChat removes tool_choice when tools are absent`

## Verification Commands
- `node tests/providers/local_vllm_provider.test.js`
- `node tests/providers/tool_payload_sanitizer.test.js`
- `node tests/providers/provider_adapter_tool_payload.test.js`
- `node --test tests/freecompute_registry_error_classification.test.js`

All commands passed.
