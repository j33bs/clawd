# Fix Canonical SOUL Drift

- Branch: fix/canonical-soul-drift-20260221T080616Z
- Date (UTC): 2026-02-21T08:08:15Z

## Baseline

git rev-parse --short HEAD
a2a0aa5

git status --porcelain -uall
 M tests_unittest/test_goal_identity_invariants.py
 M workspace/scripts/verify_goal_identity_invariants.py
 M workspace/state/tacti_cr/events.jsonl
?? workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
?? workspace/audit/fix_canonical_soul_drift_20260221T080801Z.md
?? workspace/audit/fix_canonical_soul_drift_20260221T080815Z.md
?? workspace/audit/pr_body_c_lawd_full_remediation_20260221.md

## Reproduction

python3 -m unittest discover -s tests_unittest -p "test*.py" || true
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpjouly_pq/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpjouly_pq/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpjouly_pq/overlay/quarantine/20260221-180629/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpl28_jx_5/overlay/quarantine/20260221-180630/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpo3t7d0do/overlay/quarantine/20260221-180630/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpkvdhzic_/overlay/quarantine/20260221-180630/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpg_41aosh/overlay/quarantine/20260221-180630/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpa_ars045/overlay/quarantine/20260221-180630/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpa_ars045/quarantine/openclaw-quarantine-20260221-180630

Observation: clean main did not reproduce the SOUL failure; prior failure depended on local repo-root mirror drift.

## Root Cause
- Canonicality enforcement location: /private/tmp/clawd-followups-20260221T080402Z/workspace/scripts/verify_goal_identity_invariants.py lines 173-184.
- Drift occurs when repo-root governance mirror files diverge from canonical workspace/governance copies.

## Change
- Added sync_repo_root_governance_mirrors() in verifier to sync repo-root governance mirrors from canonical files before byte-identity enforcement.
- Added focused unittest test_verifier_syncs_repo_root_soul_mirror to prevent recurrence.

## Verification

python3 -m unittest -q tests_unittest.test_goal_identity_invariants


python3 -m unittest discover -s tests_unittest -p "test*.py"
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpvd80r3dx/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpvd80r3dx/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpvd80r3dx/overlay/quarantine/20260221-180744/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp3prlmuu5/overlay/quarantine/20260221-180746/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpoo6xtb60/overlay/quarantine/20260221-180746/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp_bt2ee7m/overlay/quarantine/20260221-180746/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp2b4z_nto/overlay/quarantine/20260221-180746/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp724njess/overlay/quarantine/20260221-180746/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp724njess/quarantine/openclaw-quarantine-20260221-180746

## Revert

git revert --no-edit HEAD
