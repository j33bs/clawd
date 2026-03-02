# Branch Lock Fix Report

- run_id: c_lawd_branch_lock_fix_20260302T053001Z
- finished_utc: 2026-03-02T06:22:14Z
- branch: codex/feat/unified-memory-query-20260302
- head: 720882672e53284b43579c5a8a698f82ce6f3079

## Root Cause Classification

Primary error reproduced:
- `cannot lock ref ... Operation not permitted` during `git checkout -b codex/feat/unified-memory-query-20260302`.

Repo filesystem context:
- backing mount: APFS (`/System/Volumes/Data`)
- evidence: `workspace/audit/_evidence/c_lawd_branch_lock_fix_20260302T053001Z/filesystem_type.txt`

Evidence indicates this was **not** a stale lock-file issue and not a unix mode/owner mismatch:
- no `*.lock` files found in `.git` scan.
- owner/group/mode of `.git`, refs, and logs paths were normal for current user.
- immutable flags (`uchg`/`schg`) were not present on relevant paths.

Deterministic write probes to `.git` paths failed with `Operation not permitted` even for temporary files.
This points to a **runtime/sandbox write restriction on `.git` internals**, not repo data corruption.

## Remediation Applied

- No destructive cleanup was needed.
- No lock files removed.
- Used an explicit escalated execution path (still no sudo) to run git ref mutations outside sandbox restrictions.
- Branch creation then succeeded immediately.

## Branch + Commits

- branch: `codex/feat/unified-memory-query-20260302`
- commit 1: `9712e4dbb929`
  - `test(integrity): add guard-aware dispatch sim mode (test-only)`
- commit 2: `720882672e53`
  - `feat(memory): add UnifiedMemoryQuery read-only aggregator + tests`

## Files Included in Tranche

- `core/system2/security/integrity_guard.js`
- `tests/freecompute_cloud.test.js`
- `workspace/memory/unified_query.js`
- `tests/unified_memory_query.test.js`

## Test Outcomes

- `node tests/unified_memory_query.test.js` -> `0`
- `node tests/freecompute_cloud.test.js` -> `0`

## Safe Rollback

1. `git checkout codex/feat/unified-memory-query-20260302`
2. `git revert 720882672e53`
3. `git revert 9712e4dbb929`

Alternative (drop branch):
1. checkout previous branch
2. `git branch -D codex/feat/unified-memory-query-20260302`

## PR-Ready Description Snippet

### Intent
Package the unified memory query tranche and unblock dispatch-path tests blocked by integrity guard drift in sandboxed environments.

### Changes
- Added test-only guard-aware dispatch simulation controls (`OPENCLAW_DISPATCH_SIM_MODE` + test runtime gate + simulated repo root fixture path).
- Added deterministic fixture setup in freecompute tests so dispatch integrity checks stay enabled while test runs remain local/offline.
- Added `UnifiedMemoryQuery` thin read-only aggregation layer with pluggable adapters and normalized output shape.
- Added deterministic unit tests for merge/sort/filter/limit/output-shape behavior.

### Why Safe
- Guard verification remains ON; no global disable.
- Simulation mode is test-only and rejected outside test runtime.
- No network dependency introduced.
- Scoped file set only; reversible via two commits.

### Evidence
- Branch creation repro + diagnostics: `workspace/audit/_evidence/c_lawd_branch_lock_fix_20260302T053001Z/branch_create_attempt.txt`, `workspace/audit/_evidence/c_lawd_branch_lock_fix_20260302T053001Z/phase3_classification_inputs.txt`
- Commits: `9712e4dbb929`, `720882672e53`
- Tests: `workspace/audit/_evidence/c_lawd_branch_lock_fix_20260302T053001Z/test_unified_memory_query_after_commit.txt`, `workspace/audit/_evidence/c_lawd_branch_lock_fix_20260302T053001Z/test_freecompute_after_commit.txt`
- Final patch: `workspace/audit/_evidence/c_lawd_branch_lock_fix_20260302T053001Z/final_patch.diff`
