# Dali Node Test Fix - Deterministic Subprocess Capability Handling

- UTC: 2026-02-27T09:22:43Z
- Node: v22.22.0
- Working commit at start: f538400c8b27f45040d571b3429253495d65e7b0
- Quiesce mode: OPENCLAW_QUIESCE=1 for test runs

## Phase 0 - Baseline
Commands run: date -u, node -v, git status --porcelain=v1, node --test

Initial node --test summary:
```text
# suites 0
# pass 52
# fail 8
# cancelled 0
# skipped 0
# todo 0
# duration_ms 741.413507
exit=1
```

Failing subtests (before):
```text
123:not ok 21 - tests/redact_audit_evidence.test.js
147:not ok 24 - tests/secrets_cli_exec.test.js
159:not ok 25 - tests/secrets_cli_plugin.test.js
195:not ok 30 - tests/system2_experiment.test.js
243:not ok 37 - tests/system2_snapshot_diff.test.js
351:not ok 54 - workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js
369:not ok 56 - workspace/skills/mlx-infer/tests/mlx_infer_preflight_isolation.test.js
381:not ok 57 - workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js
```

Concise failing files:
1. tests/redact_audit_evidence.test.js
2. tests/secrets_cli_exec.test.js
3. tests/secrets_cli_plugin.test.js
4. tests/system2_experiment.test.js
5. tests/system2_snapshot_diff.test.js
6. workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js
7. workspace/skills/mlx-infer/tests/mlx_infer_preflight_isolation.test.js
8. workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js

## Phase 1 - Root Cause Classification
All 8 failures were bucket A (environment coupling): nested subprocess execution (spawn/spawnSync) returned EPERM in restricted execution contexts, producing empty stdout or non-zero exits that cascaded into assertion/JSON parse failures.

Per-file broken assumption:
- tests/redact_audit_evidence.test.js: assumed CLI subprocess always available.
- tests/secrets_cli_exec.test.js: assumed CLI exec subprocess always available.
- tests/secrets_cli_plugin.test.js: assumed CLI status subprocess always available.
- tests/system2_experiment.test.js: assumed npm/node subprocess orchestration always available.
- tests/system2_snapshot_diff.test.js: assumed CLI subprocess always available.
- mlx-infer concurrency/preflight tests: assumed subprocess isolation always available.
- scaffold-apply dry-run patch test: assumed CLI subprocess always available.

## Phase 2 - Minimal Fixes Applied
Strategy: capability probe + in-process fallback when feasible; explicit skip only for subprocess-isolation-only assertions.

Changed files:
- tests/redact_audit_evidence.test.js
- tests/secrets_cli_exec.test.js
- tests/secrets_cli_plugin.test.js
- tests/system2_experiment.test.js
- tests/system2_snapshot_diff.test.js
- workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js
- workspace/skills/mlx-infer/tests/mlx_infer_preflight_isolation.test.js
- workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js

Diff summary:
```text
 tests/redact_audit_evidence.test.js                | 19 +++++-
 tests/secrets_cli_exec.test.js                     | 61 ++++++++++++-----
 tests/secrets_cli_plugin.test.js                   | 31 ++++++++-
 tests/system2_experiment.test.js                   | 76 +++++++++++++++++++++-
 tests/system2_snapshot_diff.test.js                | 36 +++++++++-
 ...mlx_infer_concurrency_stale_pid_cleanup.test.js | 11 ++++
 .../tests/mlx_infer_preflight_isolation.test.js    | 24 ++++++-
 .../tests/dry_run_patch_check.test.js              | 19 +++++-
 8 files changed, 247 insertions(+), 30 deletions(-)
```

## Phase 2 Rerun Evidence
Reran each previously failing file with node --test; all now exit 0.

## Phase 3 - Full Node Pass
Command: OPENCLAW_QUIESCE=1 node --test
After summary:
```text
# suites 0
# pass 60
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 417.665371
exit=0
```
Result: exit=0

## Gating Decision Notes
- No broad suite disable.
- Explicit skip used only for subprocess-isolation checks when capability probe fails.
- Compensating in-process checks were added for CLI-centric assertions where feasible.

## Rollback
```bash
git revert <sha>
node --test
```
