# Post-merge Final Verification

- ts_utc: 20260227T015012Z
- branch: main
- head: 7bf1c6e768d64626317127177b3b528200e8412e

## Commands and Outputs

```bash
git checkout main
Your branch is ahead of 'origin/main' by 5 commits.
  (use "git push" to publish your local commits)

git pull --ff-only origin main
Already up to date.

node --test tests/no_html_on_machine_routes.test.js
✔ machine surface never serves html and unknown machine paths are JSON 404 (174.671625ms)
ℹ tests 1
ℹ suites 0
ℹ pass 1
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1208.130375

tools/assert_machine_surface.sh http://127.0.0.1:18789
PASS /health: status=200 content-type=application/json; charset=utf-8
PASS /ready: status=503 content-type=application/json; charset=utf-8
PASS /diag/runtime: status=200 content-type=application/json; charset=utf-8
PASS /api/does-not-exist: status=404 content-type=application/json; charset=utf-8
PASS /diag/does-not-exist: status=404 content-type=application/json; charset=utf-8
machine surface assertion passed for http://127.0.0.1:18789

tools/check_launchagent_points_to_repo.sh
PASS: launchagent points to repo wrapper (/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh)

OPENCLAW_QUIESCE=1 OPENCLAW_LOCAL_GATES=1 tools/run_checks.sh || true
[local-gates] enabled
[local-gates] checking launchagent alignment
PASS: launchagent points to repo wrapper (/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh)
[local-gates] PASS launchagent alignment
[local-gates] running machine-surface tripwire
PASS /health: status=200 content-type=application/json; charset=utf-8
PASS /ready: status=503 content-type=application/json; charset=utf-8
PASS /diag/runtime: status=200 content-type=application/json; charset=utf-8
PASS /api/does-not-exist: status=404 content-type=application/json; charset=utf-8
PASS /diag/does-not-exist: status=404 content-type=application/json; charset=utf-8
reliability tripwire passed for http://127.0.0.1:18789
[local-gates] PASS machine-surface tripwire
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
witness_paths_read=audit/commit_audit_log.jsonl
witness_paths_write=state_runtime/teamchat/witness_ledger.jsonl
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
witness_paths_read=audit/commit_audit_log.jsonl
witness_paths_write=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl
⚠️ witness ledger commit skipped: witness_commit_failed: ledger_path=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl audit_path=audit/commit_audit_log.jsonl error=RuntimeError: simulated_witness_commit_failure
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
witness_paths_read=audit/commit_audit_log.jsonl
witness_paths_write=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl
❌ witness ledger commit failed (strict): witness_commit_failed: ledger_path=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl audit_path=audit/commit_audit_log.jsonl error=RuntimeError: simulated_witness_commit_failure
==================================================
❌ AUDIT FAILED - Commit blocked
==================================================
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp3a_gpltt/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp3a_gpltt/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp3a_gpltt/overlay/quarantine/20260227-115042/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpcm95gthx/overlay/quarantine/20260227-115047/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpk8ohy_6u/overlay/quarantine/20260227-115048/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpuo3k0xef/overlay/quarantine/20260227-115048/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp5j2x47o3/overlay/quarantine/20260227-115049/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpdcrcliue/overlay/quarantine/20260227-115049/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_openai_sk
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpdcrcliue/quarantine/openclaw-quarantine-20260227-115049
PYTHON_EXE=/opt/homebrew/opt/python@3.14/bin/python3.14
PYTHON_VER=3.14.3 (main, Feb  3 2026, 15:32:20) [Clang 17.0.0 (clang-1700.6.3.2)]
PYTHON3_WHICH=/opt/homebrew/bin/python3
REPO_ROOT=/Users/heathyeager/clawd
BASE_CONFIG=/Users/heathyeager/clawd/pipelines/system1_trading.yaml
BASE_CONFIG_EXISTS=0
FEATURES_OVERLAY=/Users/heathyeager/clawd/pipelines/system1_trading.features.yaml
FEATURES_OVERLAY_EXISTS=1
```
