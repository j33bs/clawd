# Dali Dashboard Determinism Harness Fix

Timestamp (UTC): 2026-02-27

## Binary Provenance
- File: `/tmp/openclaw_bin.txt`
- Key points:
  - wrapper path: `/home/jeebs/.local/bin/openclaw`
  - real binary path via wrapper: `$HOME/.local/bin/openclaw.real`
  - version calls were stable across two runs

## Dist Grep Before
File: `/tmp/hardening_dist_grep.txt`

```text
51:function isAnthropicEnabled(env = process.env) {
52:  const allowlist = parseProviderList(env.OPENCLAW_PROVIDER_ALLOWLIST);
58:  const anthropicEnabled = isAnthropicEnabled(env);
```

## Dist Grep After
File: `/tmp/hardening_dist_grep_after.txt`

```text
52:  const allowlist = parseProviderList(env.OPENCLAW_PROVIDER_ALLOWLIST);
68:  const allowlistRaw = typeof env.OPENCLAW_PROVIDER_ALLOWLIST === 'string' ? env.OPENCLAW_PROVIDER_ALLOWLIST : '';
```

## Root Cause Resolution
Observed nondeterminism was environment-surface/bootstrap related, not provider logic alone.

Applied controls:
1. Hardening debug probe (`OPENCLAW_HARDENING_DEBUG=1`) added in source config path; emits:
   - raw allowlist
   - parsed providers
   - anthropicEnabled
   - anthropicKeyPresent (boolean only)
2. Dashboard startup env defaulting in runtime overlay:
   - if dashboard command and `OPENCLAW_PROVIDER_ALLOWLIST` unset/blank -> force `local_vllm`
   - if dashboard command and anthropic disabled -> remove `ANTHROPIC_API_KEY` from process env before downstream child work
3. Single config path retained with `getConfigOnce()` in overlay.

No dist files were edited directly.

## Files Changed
- `workspace/runtime_hardening/src/config.mjs`
- `workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs`
- `workspace/runtime_hardening/tests/config.test.mjs`
- `tools/repro_dashboard_determinism.sh`

## Verification
- `OPENCLAW_QUIESCE=1 node --test` -> PASS (60/60)
- `OPENCLAW_QUIESCE=1 python3 -m unittest -v` -> PASS (276 tests, skipped=1)
- `bash workspace/scripts/rebuild_runtime_openclaw.sh` -> PASS
- `bash tools/repro_dashboard_determinism.sh` -> PASS
  - Result: `PASS all_runs=25 modes=2 logs=/tmp/dash_repro`
  - No `ANTHROPIC_API_KEY required non-empty value is missing` failures across 25x2 runs.

## Before / After
Before:
- Intermittent dashboard startup failures reported with missing `ANTHROPIC_API_KEY`.

After:
- Dashboard startup deterministic under both:
  - allowlist unset (defaults local-first for dashboard path)
  - allowlist explicitly set to `local_vllm`
- No Anthropic key validation failures in harness.

## Rollback
1. `git revert <sha>`
2. `bash workspace/scripts/rebuild_runtime_openclaw.sh`
