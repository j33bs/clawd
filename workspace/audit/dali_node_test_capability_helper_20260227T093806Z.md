# Dali Node Test Capability Helper Dedupe — 2026-02-27T09:38:06Z

## Scope
Deduplicated subprocess capability detection across the 8 previously patched Node test files.

Constraint observed: no behavior change (same skip/pass behavior and same skip reason text where skip is used).

## Root Cause / Motivation
Commit `1e538673c2a6958f411b6af9aebfc1344638ad48` made tests deterministic on restricted environments, but repeated the same spawn-capability probe logic in multiple test files.

## Changes
Added shared helper:
- `tests/helpers/capabilities.js`

Exported API:
- `canSpawnSubprocess()` -> `{ ok, reason }`
- `hasCommand(cmd)` -> boolean
- `isRestrictedContext()` -> boolean heuristic
- `requireSubprocessOrSkip(t, label)` -> applies `t.skip(...)` when subprocess spawn is unavailable

Updated tests to consume helper (dedupe only):
- `tests/redact_audit_evidence.test.js`
- `tests/secrets_cli_exec.test.js`
- `tests/secrets_cli_plugin.test.js`
- `tests/system2_experiment.test.js`
- `tests/system2_snapshot_diff.test.js`
- `workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js`
- `workspace/skills/mlx-infer/tests/mlx_infer_preflight_isolation.test.js`
- `workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js`

## Behavior Preservation Notes
- Fallback branches for restricted environments are unchanged; only probe source was centralized.
- Skip reason string remains: `subprocess spawn unavailable in this environment`.

## Validation
### Targeted affected files
Command:
```bash
OPENCLAW_QUIESCE=1 node --test \
  tests/redact_audit_evidence.test.js \
  tests/secrets_cli_exec.test.js \
  tests/secrets_cli_plugin.test.js \
  tests/system2_experiment.test.js \
  tests/system2_snapshot_diff.test.js \
  workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js \
  workspace/skills/mlx-infer/tests/mlx_infer_preflight_isolation.test.js \
  workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js
```
Result:
- `# pass 8`
- `# fail 0`
- exit `0`

### Full Node suite
Command:
```bash
OPENCLAW_QUIESCE=1 node --test
```
Result:
- `# tests 60`
- `# pass 60`
- `# fail 0`
- exit `0`

## Diff Summary
- 1 new helper module
- 8 tests updated to import helper
- net effect: duplicated probe functions removed; no assertion logic changes

## Rollback
```bash
git revert <commit_sha>
```
