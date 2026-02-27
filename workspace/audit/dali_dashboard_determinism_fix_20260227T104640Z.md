# Dali Dashboard Determinism Fix

Timestamp (UTC): 2026-02-27

## Root Cause
Runtime hardening anthropic enablement was not strict-allowlist only. It could be inferred from default provider/model envs during dashboard/bootstrap paths, making `ANTHROPIC_API_KEY` validation nondeterministic across launch contexts.

## Fix Applied
1. Explicit anthropic enablement only:
- `anthropicEnabled = parseProviderList(OPENCLAW_PROVIDER_ALLOWLIST).includes("anthropic")`
- No inference from `OPENCLAW_DEFAULT_MODEL`, `OPENCLAW_DEFAULT_PROVIDER`, or key presence.

2. Validation gate:
- Require `ANTHROPIC_API_KEY` only when `anthropicEnabled === true`.
- Missing key is ignored when anthropic is disabled.

3. Log hygiene:
- Redacted config now omits `anthropicApiKey` entirely when anthropic is disabled.

4. Overlay singleton guard:
- Added module-level `getConfigOnce(env)` in runtime overlay and switched overlay init path to use it.

## Files Changed
- `workspace/runtime_hardening/src/config.mjs`
- `workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs`
- `workspace/runtime_hardening/tests/config.test.mjs`

## Rebuild
- `bash workspace/scripts/rebuild_runtime_openclaw.sh` -> success

## Verification Runs
1. Local-first version probe with anthropic key unset:
- `env -u ANTHROPIC_API_KEY OPENCLAW_PROVIDER_ALLOWLIST=local_vllm openclaw --version`
- Result: success

2. Dashboard launch determinism (twice):
- `OPENCLAW_PROVIDER_ALLOWLIST=local_vllm openclaw dashboard --no-open`
- `OPENCLAW_PROVIDER_ALLOWLIST=local_vllm openclaw dashboard --no-open`
- Result: both succeeded; identical dashboard URL token.
- Evidence logs:
  - `/tmp/dali_dash_det_1_20260227T104554Z.log`
  - `/tmp/dali_dash_det_2_20260227T104554Z.log`

3. Full tests:
- `OPENCLAW_QUIESCE=1 node --test` -> pass (60/60)
- `OPENCLAW_QUIESCE=1 python3 -m unittest -v` -> pass (276 tests, skipped=1)

## Before / After
Before:
- Intermittent dashboard/bootstrap failure with:
  - `Invalid runtime hardening configuration:`
  - `ANTHROPIC_API_KEY: required non-empty value is missing`

After:
- Dashboard launches are deterministic in local-first mode.
- Runtime hardening logs show `anthropicEnabled: false` under local allowlist and do not expose/emit `anthropicApiKey` when disabled.
