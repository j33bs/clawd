# Dali Audit: OpenAI Intent Binding + vLLM Tool Payload Gate

- Timestamp (UTC): 2026-02-21T02:42:01Z
- Baseline SHA: `c864665`
- Working branch: `fix/dali-openai-intent-no-vllm-20260221`
- Node: `v22.22.0`
- Python: `Python 3.12.3`

## Repo Constraint Acknowledgement

This repo snapshot enforces a no-OpenAI-lane posture for system2 routing/canonical model policy:
- governance contract states no `openai` / `openai-codex` lanes
- regression tests enforce no `openai/` or `openai-codex/` model-id prefixes in canonical/policy artifacts

Given that constraint, this change set implements strict provider-family intent and fail-closed diagnostics (instead of silently routing to local vLLM).

## Implemented Changes

1. Intent binding at routing boundary (`core/system2/inference/provider_registry.js`)
- Added requested provider family extraction from metadata:
  - `provider_family`, `providerFamily`, `provider`, `provider_id`
  - model prefix detection: `openai/` and `openai-codex/`
- Added candidate family resolution and strict filtering.
- If explicit OpenAI-family intent has no matching family candidate and `OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK != 1`:
  - throws structured error
  - `code: REQUESTED_PROVIDER_UNAVAILABLE`
  - message:
    - "Requested OpenAI family but no matching provider lane is enabled in this build."
    - "Either (a) enable/open the openai/openai-codex lane in catalog/policy, or (b) choose an available provider explicitly."
- Added override:
  - `OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK=1` permits cross-family fallback.
- Added guarded route debug log:
  - enabled only with `OPENCLAW_DEBUG_ROUTE=1`
  - logs only `requested_model`, `requested_provider_family`, `selected_provider_id`, `reason`
  - never logs secrets/tokens.

2. vLLM tool payload gate (`core/system2/inference/local_vllm_provider.js`)
- Added `OPENCLAW_VLLM_TOOLCALL` capability flag (default disabled).
- Before POST, when `OPENCLAW_VLLM_TOOLCALL != "1"`, strips:
  - `tools`, `tool_choice`, `parallel_tool_calls`, `tool_calls`, `function_call`
- Added explicit classification for known vLLM 400 tool-parser mismatch text:
  - `code: PROVIDER_TOOLCALL_UNSUPPORTED`
  - remediation message:
    - start vLLM with `--enable-auto-tool-choice --tool-call-parser ...`
    - or set `OPENCLAW_VLLM_TOOLCALL=0` (default)

## Regression Tests Added

1. `tests/freecompute_cloud.test.js`
- `registry: openai-family intent fails closed without cross-family fallback`
- `registry: openai-family intent can cross-family fallback only when override is enabled`

2. `tests/providers/local_vllm_provider.test.js`
- `generateChat strips tool payload fields by default`

## Evidence: Test Output (No Live Endpoints)

### A) OpenAI intent fails closed (and fallback override path)
Command:
- `node tests/freecompute_cloud.test.js`

Output:
```text
── Schema Validation ──
── Catalog Queries ──
── Config + Redaction ──
── Router ──
── Quota Ledger ──
── vLLM Utilities ──
── Provider Registry ──
── Provider Adapter ──
── Integration Tests ──

════════════════════════════════════════════
FreeComputeCloud Tests: 72 passed, 0 failed, 3 skipped
════════════════════════════════════════════
```

### B) vLLM strips tool payload fields by default
Command:
- `node tests/providers/local_vllm_provider.test.js`

Output:
```text
PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
PASS healthProbe returns fail-closed result when endpoint is unreachable
PASS generateChat returns expected output shape from vLLM response
PASS generateChat strips tool payload fields by default
PASS normalizeBaseUrl appends /v1 only when missing
```

## Full Suite Note

Command:
- `npm test`

Result:
- Fails in current workspace due pre-existing unrelated regressions (Python/unit policy and team-chat modules), including:
  - `test_evolution_scaffolds` import error (`cache_epitope`)
  - `test_team_chat_autocommit_contract` import error
  - `test_team_chat_no_side_effects` attribute error
  - `tests/model_routing_no_oauth.test.js` failure from pre-existing policy free_order drift
- Relevant system2/freecompute suites for this change passed as shown above.

## Dali Runtime Verification (2026-02-21)

### Gateway token drift remediation

Commands run:
- `openclaw gateway install --force`
- `sudo systemctl restart openclaw-gateway.service` (blocked in this shell: sudo password/TTY required)
- `sudo systemctl status openclaw-gateway.service --no-pager` (blocked in this shell: sudo password/TTY required)
- `systemctl --user restart openclaw-gateway.service && systemctl --user status openclaw-gateway.service --no-pager`

Observed:
- `openclaw gateway install --force` reinstalled gateway unit: `/home/jeebs/.config/systemd/user/openclaw-gateway.service`
- user service is active and running after restart (`Active: active (running)`)

### Phase 3 commands and observed behavior

#### Case A — OpenAI family request fail-closed; no vLLM dispatch

Command run:
- `node - <<'NODE'` (ProviderRegistry harness with `OPENCLAW_DEBUG_ROUTE=1`, `OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK=0`, and `metadata.model='openai/gpt-4o-mini'`)

Observed output:
- route debug: `[openclaw.route] {"requested_model":"openai/gpt-4o-mini","requested_provider_family":"openai","selected_provider_id":null,"reason":"requested_provider_family_unavailable"}`
- error code: `REQUESTED_PROVIDER_UNAVAILABLE`
- vLLM dispatch attempted: `false` (`caseA.localCalled=false`)

#### Case B — Cross-family fallback only when explicitly enabled

Command run:
- same ProviderRegistry harness, with `OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK=1` and `metadata.model='openai-codex/gpt-5-codex'`

Observed output:
- route debug: `[openclaw.route] {"requested_model":"openai-codex/gpt-5-codex","requested_provider_family":"openai-codex","selected_provider_id":"local_vllm","reason":"escape_hatch_local_vllm"}`
- selected provider: `local_vllm`
- fallback dispatch executed: `true` (`caseB.localCalled=true`)

#### Case C — vLLM tool payload gating default-off

Command run:
- `node - <<'NODE'` (LocalVllmProvider harness with `OPENCLAW_VLLM_ENABLE_AUTO_TOOL_CHOICE=1`, `OPENCLAW_VLLM_TOOLCALL=0`, and a stubbed `_httpRequest` capture)

Observed output:
- `caseC.has_tools=false`
- `caseC.has_tool_choice=false`

Result: outgoing vLLM payload had tool-related fields stripped while toolcalling gate was off.

#### Optional Case D — classify known vLLM tool-choice 400 with remediation

Command run:
- same LocalVllmProvider harness, with `OPENCLAW_VLLM_TOOLCALL=1`, forcing known tool-choice unsupported error text

Observed output:
- `caseD.code=PROVIDER_TOOLCALL_UNSUPPORTED`
- `caseD.status=400`
- message includes remediation: start vLLM with `--enable-auto-tool-choice --tool-call-parser ...` or disable gate via `OPENCLAW_VLLM_TOOLCALL=0`.
