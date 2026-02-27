# Dali ULTRA Drift Gate Hygiene

- UTC: 2026-02-27T08:48:23Z
- Repo HEAD (start): eed0200ec83e260a744d948e8a1209d9554ac29f

## Phase 0 Baseline (before edits)
Commands run:
- git status --porcelain=v1 --untracked-files=all
- git ls-files -v | grep '^S' || true
- git rev-parse HEAD
- date -u

Captured status (relevant lines):

a. Untracked exhaust roots present:
- workspace/audit/.dali_ultra_*
- workspace/audit/evidence/**
- workspace/state_runtime/**
- workspace/state_runtime/vectorstores/**
- additional generated audit markdowns under workspace/audit/

b. Skip-worktree present:
S workspace/state/tacti_cr/events.jsonl

c. Tracked modifications at baseline:
(none)

## Phase 1 .gitignore Update
Backup:
/tmp/gitignore.backup.20260227T084537Z

Appended block:
# --- runtime exhaust (never version) ---
workspace/state_runtime/
workspace/state_runtime/**

# --- generated ULTRA evidence + markers (keep audit md trackable) ---
workspace/audit/evidence/
workspace/audit/evidence/**
workspace/audit/.dali_ultra_*

# --- python caches ---
**/__pycache__/
*.pyc

# --- runtime vectorstore/db exhaust ---
workspace/state_runtime/vectorstores/
workspace/state_runtime/vectorstores/**

Diff snippet:
diff --git a/.gitignore b/.gitignore
index ef44b0b..9fa8e7b 100644
--- a/.gitignore
+++ b/.gitignore
@@ -166,3 +166,20 @@ workspace/research/insights.json
 
 # Telegram private exports (must remain local-only)
 workspace/state_runtime/ingest/telegram_exports/
+
+# --- runtime exhaust (never version) ---
+workspace/state_runtime/
+workspace/state_runtime/**
+
+# --- generated ULTRA evidence + markers (keep audit md trackable) ---
+workspace/audit/evidence/
+workspace/audit/evidence/**
+workspace/audit/.dali_ultra_*
+
+# --- python caches ---
+**/__pycache__/
+*.pyc
+
+# --- runtime vectorstore/db exhaust ---
+workspace/state_runtime/vectorstores/
+workspace/state_runtime/vectorstores/**

## Phase 2 Drift Gate Recheck
Command:
- git status --porcelain=v1 --untracked-files=all

After ignore update (captured immediately after Phase 1):
 M .gitignore
?? workspace/audit/6h_run_6h_mem_orch_20260226T010847Z.md
?? workspace/audit/6h_run_env_6h_mem_orch_20260226T010847Z.md
?? workspace/audit/dali_fix_runtime_hardening_anthropic_key_20260227T083400Z.md
?? workspace/audit/dali_ultra_audit_20260227T081452Z.md
?? workspace/audit/dali_ultra_fix_plan_20260227T081452Z.md
?? workspace/audit/run_harness_env_run_harness_20260226T114708Z.md
?? workspace/audit/run_harness_run_harness_20260226T114708Z.md

Categorization of remaining untracked:
- B) Real trackable files (audit markdowns) that should be committed or intentionally retained for human review.
- No remaining A-category runtime exhaust from listed roots.
- No C-category suspicious items identified.

## Phase 3 Skip-Worktree Allowlist Guard
Added:
- tools/check_skip_worktree_allowlist.sh (POSIX sh, executable)

Allowlist (exact):
- workspace/state/tacti_cr/events.jsonl

Behavior:
- exits 0 if no skip-worktree entries or only allowlisted entry
- exits 2 if any non-allowlisted skip-worktree entry exists

Hook wiring:
- Added a single call in workspace/scripts/verify_preflight.sh:
  - ./tools/check_skip_worktree_allowlist.sh

Guard output (current repo state):
skip-worktree allowlist check: ok

## Phase 4 Tests
Direct guard run:
bash tools/check_skip_worktree_allowlist.sh
skip-worktree allowlist check: ok

Python tests:
python3 -m unittest -v
exit=0

Node tests:
node --test
exit=1

Node failure summary (from run tail):
- not ok 54 - workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js
- not ok 56 - workspace/skills/mlx-infer/tests/mlx_infer_preflight_isolation.test.js
- not ok 57 - workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js
- final summary: pass 52, fail 8

## Rollback
1. Restore ignore file from backup:
cp -a /tmp/gitignore.backup.20260227T084537Z .gitignore

2. Revert commit:
git revert <sha>
