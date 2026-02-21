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
