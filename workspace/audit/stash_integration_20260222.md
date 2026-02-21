# Stash Integration Audit — 2026-02-22

Append-only evidence for integrating stashed local workspace changes into `codex/feat/wirings-integration-20260222` with minimal diffs and reversibility.

## Phase 0 Baseline (2026-02-21T23:23:34Z)
```bash
git status --porcelain -uall
?? workspace/audit/stash_integration_20260222.md

git branch --show-current
codex/feat/wirings-integration-20260222

git stash list
stash@{0}: On codex/sec/audit-secret-guard-20260221T090531Z: wip: local workspace state before wiring push
stash@{1}: WIP on main: b1a92bc Add message load balancer with ChatGPT fallback
stash@{2}: WIP on codex/feature/tacti-reservoir-physarum: 52fc85d docs: rewrite README to reflect current system state (TACTI(C)-R, HiveMind, Knowledge Base)
stash@{3}: On codex/system2-models-sorted: wip(off-scope): system2 inference changes
stash@{4}: On codex/system2-openai-paid-fallback: WIP: system2 paid fallback + dispatch hardening + groq alias
stash@{5}: WIP on redact/audit-evidence-20260212: c258381 fix(system2): fail-closed RCE posture + auth circuit breakers + snapshot wiring
stash@{6}: On codex/system2-brief-broad: system2-config-enable
stash@{7}: WIP on integration/j33bs-clawd-bridge: 04b0dca test(telegram): add secret-safe e2e verification harness
stash@{8}: On feat/system-evolution-2026-02: wip: system-evolution local changes (unblock acceptance gate fix)
stash@{9}: On feat/system-evolution-2026-02: defer-preexisting-dirty-reports
stash@{10}: On main: WIP before system1 tts_worker scaffolding

git show --stat origin/main...HEAD
commit fe75e368f79bdc92b5dc46293c6bfe22c2f0ef63
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:26:13 2026 +1000

    docs(audit): record push attempt evidence

 workspace/audit/wirings_integration_20260222.md | 1 +
 1 file changed, 1 insertion(+)

commit 061c92efb1f8db1f7ffa4c6f8b56dbf4bdc0fc66
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:25:43 2026 +1000

    docs(audit): finalize wirings integration evidence

 workspace/audit/wirings_integration_20260222.md | 411 ++++++++++++++++++++++++
 1 file changed, 411 insertions(+)

commit ed7843937631d115e78113d982bd9a21af631497
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:19:42 2026 +1000

    feat(router): integrate ActiveInferenceAgent decision path (EFE-based)

 env.d/system1-routing.env                          |  1 +
 .../test_policy_router_active_inference_hook.py    | 68 ++++++++++++++++
 tests_unittest/test_tacti_efe_calculator.py        | 42 ++++++++++
 workspace/audit/wirings_integration_20260222.md    | 51 ++++++++++++
 workspace/scripts/policy_router.py                 | 91 ++++++++++++++++++++--
 workspace/tacti/efe_calculator.py                  | 42 ++++++++--
 6 files changed, 281 insertions(+), 14 deletions(-)

commit e0942ff417bf50ae45e87eb0d9e975eee5035473
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:15:57 2026 +1000

    feat(hivemind): enable guarded counterfactual replay in dynamics pipeline

 env.d/system1-routing.env                         |  1 +
 tests_unittest/test_hivemind_dynamics_pipeline.py | 41 ++++++++++++
 workspace/audit/wirings_integration_20260222.md   | 26 ++++++++
 workspace/hivemind/hivemind/dynamics_pipeline.py  | 79 +++++++++++++++++++++++
 4 files changed, 147 insertions(+)

commit 7fada1686a0df9c944e6735e72d35dc926d393d4
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:14:38 2026 +1000

    feat(research): publish gap analysis into knowledge base

 .../test_research_gap_analyzer_bridge.py           |  67 +++++++++++
 workspace/audit/wirings_integration_20260222.md    |  20 ++++
 workspace/research/gap_analyzer.py                 | 123 +++++++++++++++++++++
 workspace/research/research_ingest.py              |  34 ++++++
 4 files changed, 244 insertions(+)

commit 8094e995674f65ea9c2ae51940d8c7aca9a41a62
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:12:59 2026 +1000

    feat(hivemind): enable valence-weighted trails under OPENCLAW_TRAIL_VALENCE

 env.d/system1-routing.env                         |  1 +
 tests_unittest/test_hivemind_dynamics_pipeline.py | 49 ++++++++++++++++++++++-
 tests_unittest/test_hivemind_physarum_router.py   | 17 +++++++-
 workspace/audit/wirings_integration_20260222.md   | 29 ++++++++++++++
 workspace/hivemind/hivemind/dynamics_pipeline.py  |  5 ++-
 workspace/hivemind/hivemind/physarum_router.py    |  7 +++-
 6 files changed, 104 insertions(+), 4 deletions(-)

commit aa564e7c215700e4a45d79cb8e408016c6acc33d
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:11:34 2026 +1000

    feat(cron): run narrative distillation before daily brief

 tests_unittest/test_ensure_cron_jobs.py         |  2 +
 workspace/audit/wirings_integration_20260222.md | 50 +++++++++++++++++++++++++
 workspace/automation/cron_jobs.json             |  2 +-
 3 files changed, 53 insertions(+), 1 deletion(-)

commit 1c694f00c94652c62dfcc81049e7a36508585be4
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:10:17 2026 +1000

    feat(router-js): include proprioception sample in response meta

 core/system2/inference/router.js                | 22 +++++++++++-
 tests/freecompute_cloud.test.js                 | 46 +++++++++++++++++++++++++
 workspace/audit/wirings_integration_20260222.md | 38 ++++++++++++++++++++
 3 files changed, 105 insertions(+), 1 deletion(-)

commit 58ecd12afc43e78c9a8d1887c3ac77b7b920ba67
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:09:07 2026 +1000

    feat(router): enable oscillatory gating under TACTI_CR_AROUSAL_OSC

 env.d/system1-routing.env                          |  1 +
 .../test_policy_router_oscillatory_gating.py       | 64 ++++++++++++++++++++++
 workspace/audit/wirings_integration_20260222.md    | 19 +++++++
 3 files changed, 84 insertions(+)

commit de3635446ee819508b4b97e1863bb915073ca1e2
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:07:59 2026 +1000

    feat(kb): enable PrefetchCache for context prefetch

 tests_unittest/test_kb_prefetch_cache.py        | 47 +++++++++++++++++++
 workspace/audit/wirings_integration_20260222.md | 41 ++++++++++++++++
 workspace/knowledge_base/kb.py                  | 62 ++++++++++++++++++++-----
 3 files changed, 139 insertions(+), 11 deletions(-)

commit 84b38a29a15c2417d3a75a3c63fd7fe00d87d365
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:06:45 2026 +1000

    feat(gov): chain governance log writes via witness ledger

 tests_unittest/test_audit_commit_hook_witness.py | 63 ++++++++++++++++++++++++
 workspace/audit/wirings_integration_20260222.md  | 45 +++++++++++++++++
 workspace/scripts/audit_commit_hook.py           | 46 +++++++++++++++++
 3 files changed, 154 insertions(+)

commit 4e1de3d9aaa86d863c23ccf1eed594d8ad04afa3
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 07:05:41 2026 +1000

    feat(itc): forward ingestion boundary to classifier

 tests_unittest/test_itc_ingestion_forwarding.py |   49 +
 workspace/audit/wirings_integration_20260222.md | 1093 +++++++++++++++++++++++
 workspace/itc_pipeline/ingestion_boundary.py    |   60 +-
 3 files changed, 1201 insertions(+), 1 deletion(-)

commit 9ed3446ce1bcfa10b1cecf1ee9adfad2c06e19e9
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sat Feb 21 23:45:02 2026 +1000

    chore(tacti_cr): guard exec-forward shims against double-exec

 tests_unittest/test_tacti_namespace_aliasing.py    |  24 ++++
 .../twenty_evolutions_impl_20260221T104827Z.md     | 129 +++++++++++++++++++++
 workspace/tacti_cr/__init__.py                     |   6 +-
 workspace/tacti_cr/active_inference_agent.py       |   6 +-
 workspace/tacti_cr/arousal.py                      |   6 +-
 workspace/tacti_cr/arousal_oscillator.py           |   6 +-
 workspace/tacti_cr/collapse.py                     |   6 +-
 workspace/tacti_cr/config.py                       |   6 +-
 workspace/tacti_cr/cross_timescale.py              |   6 +-
 workspace/tacti_cr/curiosity.py                    |   6 +-
 workspace/tacti_cr/dream_consolidation.py          |   6 +-
 workspace/tacti_cr/efe_calculator.py               |   6 +-
 workspace/tacti_cr/events.py                       |   6 +-
 workspace/tacti_cr/events_paths.py                 |   6 +-
 workspace/tacti_cr/expression.py                   |   6 +-
 workspace/tacti_cr/external_memory.py              |   6 +-
 workspace/tacti_cr/hivemind_bridge.py              |   6 +-
 workspace/tacti_cr/impasse.py                      |   6 +-
 workspace/tacti_cr/mirror.py                       |   6 +-
 workspace/tacti_cr/novel10_contract.py             |   6 +-
 workspace/tacti_cr/oscillatory_gating.py           |   6 +-
 workspace/tacti_cr/prefetch.py                     |   6 +-
 workspace/tacti_cr/repair.py                       |   6 +-
 workspace/tacti_cr/semantic_immune.py              |   6 +-
 workspace/tacti_cr/temporal.py                     |   6 +-
 workspace/tacti_cr/temporal_watchdog.py            |   6 +-
 workspace/tacti_cr/valence.py                      |   6 +-
 27 files changed, 253 insertions(+), 50 deletions(-)

commit 24b0781a771a988fca3eaf57eb4502af077bf466
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sat Feb 21 23:26:42 2026 +1000

    test(tacti): pin tacti/tacti_cr aliasing invariants; harden shim metadata

 tests_unittest/test_tacti_namespace_aliasing.py    |  57 +++++++
 .../twenty_evolutions_impl_20260221T104827Z.md     | 180 +++++++++++++++++++++
 workspace/tacti_cr/__init__.py                     |  11 +-
 workspace/tacti_cr/active_inference_agent.py       |  11 +-
 workspace/tacti_cr/arousal.py                      |  11 +-
 workspace/tacti_cr/arousal_oscillator.py           |  11 +-
 workspace/tacti_cr/collapse.py                     |  11 +-
 workspace/tacti_cr/config.py                       |  11 +-
 workspace/tacti_cr/cross_timescale.py              |  11 +-
 workspace/tacti_cr/curiosity.py                    |  11 +-
 workspace/tacti_cr/dream_consolidation.py          |  11 +-
 workspace/tacti_cr/efe_calculator.py               |  11 +-
 workspace/tacti_cr/events.py                       |  11 +-
 workspace/tacti_cr/events_paths.py                 |  11 +-
 workspace/tacti_cr/expression.py                   |  11 +-
 workspace/tacti_cr/external_memory.py              |  11 +-
 workspace/tacti_cr/hivemind_bridge.py              |  11 +-
 workspace/tacti_cr/impasse.py                      |  11 +-
 workspace/tacti_cr/mirror.py                       |  11 +-
 workspace/tacti_cr/novel10_contract.py             |  11 +-
 workspace/tacti_cr/oscillatory_gating.py           |  11 +-
 workspace/tacti_cr/prefetch.py                     |  11 +-
 workspace/tacti_cr/repair.py                       |  11 +-
 workspace/tacti_cr/semantic_immune.py              |  11 +-
 workspace/tacti_cr/temporal.py                     |  11 +-
 workspace/tacti_cr/temporal_watchdog.py            |  11 +-
 workspace/tacti_cr/valence.py                      |  11 +-
 27 files changed, 487 insertions(+), 25 deletions(-)

commit 45ca3ebe4e7aa1efa998331b47e5bd118e6466fe
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sat Feb 21 22:52:27 2026 +1000

    chore(tacti): rename tacti_cr namespace; restore twenty evolutions spec stub

 TWENTY_EVOLUTIONS.md                               |   63 ++
 tests_unittest/test_tacti_cr_impasse.py            |    7 +-
 .../twenty_evolutions_impl_20260221T104827Z.md     | 1119 ++++++++++++++++++++
 workspace/memory/session_handshake.py              |    2 +-
 workspace/scripts/team_chat.py                     |   10 +-
 workspace/{tacti_cr => tacti}/README.md            |    0
 workspace/tacti/__init__.py                        |   71 ++
 workspace/tacti/active_inference_agent.py          |   30 +
```

## Phase 1 Apply Stash (2026-02-21T23:23:45Z)
```bash
git stash apply stash@{0}
error: could not write index

git status --porcelain -uall
?? workspace/audit/stash_integration_20260222.md
```

### Retry with escalated git index permissions (2026-02-21T23:24:22Z)
```bash
git stash apply stash@{0}
Auto-merging MEMORY.md
CONFLICT (content): Merge conflict in MEMORY.md
Auto-merging memory/literature/state.json
CONFLICT (content): Merge conflict in memory/literature/state.json
Auto-merging workspace/knowledge_base/data/entities.jsonl
CONFLICT (content): Merge conflict in workspace/knowledge_base/data/entities.jsonl
CONFLICT (modify/delete): workspace/knowledge_base/data/last_sync.txt deleted in Updated upstream and modified in Stashed changes.  Version Stashed changes of workspace/knowledge_base/data/last_sync.txt left in tree.
CONFLICT (modify/delete): workspace/teamchat/sessions/tacti_architecture_review.jsonl deleted in Updated upstream and modified in Stashed changes.  Version Stashed changes of workspace/teamchat/sessions/tacti_architecture_review.jsonl left in tree.
On branch codex/feat/wirings-integration-20260222
Your branch is up to date with 'origin/codex/feat/wirings-integration-20260222'.

Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
	modified:   SOUL.md
	modified:   scripts/daily_technique.py
	modified:   scripts/get_daily_quote.js
	modified:   workspace/research/data/papers.jsonl

Unmerged paths:
  (use "git restore --staged <file>..." to unstage)
  (use "git add/rm <file>..." as appropriate to mark resolution)
	both modified:   MEMORY.md
	both modified:   memory/literature/state.json
	both modified:   workspace/knowledge_base/data/entities.jsonl
	deleted by us:   workspace/knowledge_base/data/last_sync.txt
	deleted by us:   workspace/teamchat/sessions/tacti_architecture_review.jsonl

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	workspace/MLX_INTEGRATION_AUDIT.md
	workspace/TEN_HIGH_LEVERAGE.md
	workspace/TWENTY_EVOLUTIONS.md
	workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
	workspace/audit/fix_canonical_soul_drift_20260221T080815Z.md
	workspace/audit/fix_groq_policy_alignment_20260221T081255Z.md
	workspace/audit/fix_regression_bootstrap_config_20260221T081128Z.md
	workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
	workspace/audit/sec_audit_secret_guard_normalize_20260221T092622Z.md
	workspace/audit/stash_integration_20260222.md
	workspace/briefs/codex_prompt_agents_update.md
	workspace/briefs/memory_integration.md
	workspace/knowledge_base/research/
	workspace/mlx_audit.zip


git status --porcelain -uall
UU MEMORY.md
M  SOUL.md
UU memory/literature/state.json
M  scripts/daily_technique.py
M  scripts/get_daily_quote.js
UU workspace/knowledge_base/data/entities.jsonl
DU workspace/knowledge_base/data/last_sync.txt
M  workspace/research/data/papers.jsonl
DU workspace/teamchat/sessions/tacti_architecture_review.jsonl
?? workspace/MLX_INTEGRATION_AUDIT.md
?? workspace/TEN_HIGH_LEVERAGE.md
?? workspace/TWENTY_EVOLUTIONS.md
?? workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
?? workspace/audit/fix_canonical_soul_drift_20260221T080815Z.md
?? workspace/audit/fix_groq_policy_alignment_20260221T081255Z.md
?? workspace/audit/fix_regression_bootstrap_config_20260221T081128Z.md
?? workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
?? workspace/audit/sec_audit_secret_guard_normalize_20260221T092622Z.md
?? workspace/audit/stash_integration_20260222.md
?? workspace/briefs/codex_prompt_agents_update.md
?? workspace/briefs/memory_integration.md
?? workspace/knowledge_base/research/papers/2601.06002_molecular_structure_thought.md
?? workspace/mlx_audit.zip
```

## Conflict Resolution (2026-02-21T23:35:31Z)
Policy: keep stash-side content for docs/data conflicts; preserve branch code paths.
```bash
git checkout --theirs MEMORY.md
git checkout --theirs memory/literature/state.json
git checkout --theirs workspace/knowledge_base/data/entities.jsonl
git checkout --theirs workspace/knowledge_base/data/last_sync.txt
git checkout --theirs workspace/teamchat/sessions/tacti_architecture_review.jsonl

## Phase 2 Classification (2026-02-21T23:36:46Z)
A) Source/scripts: scripts/daily_technique.py, scripts/get_daily_quote.js
B) Data/KB/sessions: memory/literature/state.json, workspace/knowledge_base/data/entities.jsonl, workspace/knowledge_base/data/last_sync.txt, workspace/research/data/papers.jsonl, workspace/teamchat/sessions/tacti_architecture_review.jsonl, workspace/knowledge_base/research/papers/2601.06002_molecular_structure_thought.md
C) Docs/audits/briefs: MEMORY.md, SOUL.md, workspace/MLX_INTEGRATION_AUDIT.md, workspace/TEN_HIGH_LEVERAGE.md, workspace/TWENTY_EVOLUTIONS.md, workspace/audit/*.md, workspace/briefs/*.md
D) Artifacts: workspace/mlx_audit.zip (exclude from commits; remove from worktree before final clean status)

```bash
git status --porcelain -uall
 M MEMORY.md
 M SOUL.md
 M memory/literature/state.json
 M scripts/daily_technique.py
 M scripts/get_daily_quote.js
 M workspace/knowledge_base/data/entities.jsonl
 M workspace/research/data/papers.jsonl
?? workspace/MLX_INTEGRATION_AUDIT.md
?? workspace/TEN_HIGH_LEVERAGE.md
?? workspace/TWENTY_EVOLUTIONS.md
?? workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
?? workspace/audit/fix_canonical_soul_drift_20260221T080815Z.md
?? workspace/audit/fix_groq_policy_alignment_20260221T081255Z.md
?? workspace/audit/fix_regression_bootstrap_config_20260221T081128Z.md
?? workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
?? workspace/audit/sec_audit_secret_guard_normalize_20260221T092622Z.md
?? workspace/audit/stash_integration_20260222.md
?? workspace/briefs/codex_prompt_agents_update.md
?? workspace/briefs/memory_integration.md
?? workspace/knowledge_base/data/last_sync.txt
?? workspace/knowledge_base/research/papers/2601.06002_molecular_structure_thought.md
?? workspace/mlx_audit.zip
```

## Phase 3 Commit 1 Docs/Audits/Briefs (2026-02-21T23:40:20Z)
Intent: integrate stashed documentation/audit artifacts only.
```bash
git diff --stat --cached
 MEMORY.md                                          |  58 ++--
 SOUL.md                                            |  10 +
 workspace/MLX_INTEGRATION_AUDIT.md                 | 192 +++++++++++
 workspace/TEN_HIGH_LEVERAGE.md                     | 116 +++++++
 workspace/TWENTY_EVOLUTIONS.md                     | 129 +++++++
 ...lawd_pr_merge_and_followups_20260221T080418Z.md |  90 +++++
 .../fix_canonical_soul_drift_20260221T080815Z.md   | 125 +++++++
 .../fix_groq_policy_alignment_20260221T081255Z.md  |  50 +++
 ...regression_bootstrap_config_20260221T081128Z.md |  81 +++++
 .../pr_body_c_lawd_full_remediation_20260221.md    |  57 ++++
 ...udit_secret_guard_normalize_20260221T092622Z.md |  33 ++
 workspace/audit/stash_integration_20260222.md      | 371 +++++++++++++++++++++
 workspace/briefs/codex_prompt_agents_update.md     |  48 +++
 workspace/briefs/memory_integration.md             | 155 +++++++++
 14 files changed, 1487 insertions(+), 28 deletions(-)
```
Rollback: git revert da84eba

## Phase 3 Commit 2 Data/KB/Sessions (2026-02-21T23:41:00Z)
Decision: exclude ignored session file workspace/teamchat/sessions/tacti_architecture_review.jsonl from commits due ambiguity (.gitignore-scoped session artifact).
```bash
git add memory/literature/state.json workspace/knowledge_base/data/entities.jsonl workspace/knowledge_base/data/last_sync.txt workspace/research/data/papers.jsonl workspace/knowledge_base/research/papers/2601.06002_molecular_structure_thought.md

git diff --stat --cached
 memory/literature/state.json                       |   7 +-
 workspace/knowledge_base/data/entities.jsonl       | 201 +++++++++++++++++++++
 workspace/knowledge_base/data/last_sync.txt        |   1 +
 .../2601.06002_molecular_structure_thought.md      |  78 ++++++++
 workspace/research/data/papers.jsonl               |  15 ++
 5 files changed, 300 insertions(+), 2 deletions(-)
```
Rollback: git revert 9ae463d

## Phase 3 Commit 3 Scripts/Source (2026-02-21T23:43:10Z)
Intent: integrate stashed script/source updates with no refactor.
```bash
git diff --stat --cached
 scripts/daily_technique.py | 35 +++++++++++++++++++++++++++++++++++
 scripts/get_daily_quote.js | 41 ++++++++++++++++++++++++++++++-----------
 2 files changed, 65 insertions(+), 11 deletions(-)
```
Rollback: git revert 5a78788

## Phase 3 Commit 4 Artifact Handling (2026-02-21T23:43:34Z)
Artifact workspace/mlx_audit.zip moved out of repo to /tmp/wt_wirings_integration_excluded/mlx_audit.zip (not committed).
Ambiguity isolated: workspace/teamchat/sessions/tacti_architecture_review.jsonl remains ignored by .gitignore and was excluded from commits.
```bash
git status --porcelain -uall
 M workspace/audit/stash_integration_20260222.md
```
Rollback: git revert 17eccdb

## Phase 4 Regression (2026-02-21T23:45:04Z)
```bash
npm test

> openclaw@0.0.0 test
> node scripts/run_tests.js

RUN python3  -m unittest discover -s tests_unittest -p test_*.py
..............................F..............................................................................................................................................................
======================================================================
FAIL: test_verifier_passes_in_repo (test_goal_identity_invariants.TestGoalIdentityInvariants.test_verifier_passes_in_repo)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/private/tmp/wt_wirings_integration/tests_unittest/test_goal_identity_invariants.py", line 21, in test_verifier_passes_in_repo
    self.assertEqual(p.returncode, 0, p.stdout + "\n" + p.stderr)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 2 != 0 : FAIL: repo-root governance file diverges from canonical: SOUL.md



----------------------------------------------------------------------
Ran 189 tests in 6.000s

FAILED (failures=1)
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
⚠️ witness ledger commit skipped: witness_error: boom
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
❌ witness ledger commit failed (strict): witness_error: boom
==================================================
❌ AUDIT FAILED - Commit blocked
==================================================
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp84sriljz/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp84sriljz/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp84sriljz/overlay/quarantine/20260222-094509/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpyre98cwq/overlay/quarantine/20260222-094510/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpwmd0u2_x/overlay/quarantine/20260222-094511/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpcwdmvx6d/overlay/quarantine/20260222-094511/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpeqevpseu/overlay/quarantine/20260222-094511/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp5ebjop6s/overlay/quarantine/20260222-094511/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp5ebjop6s/quarantine/openclaw-quarantine-20260222-094511
RUN node tests/analyze_session_patterns.test.js
PASS analyze_session_patterns aggregates recurring inefficiency patterns
RUN node tests/anticipate.test.js
PASS anticipate module emits suggestion-only low-risk automation hints
PASS anticipate feature flag disables suggestions
RUN node tests/ask_first_tool_governance.test.js
PASS ask_first enforces approval for exec
PASS ask_first allows ask-decision action with operator approval
PASS ask_first surfaces deny decisions as ToolDeniedError
RUN node tests/audit_sink_hash_chain.test.js
PASS audit sink hash chaining persists across rotation
RUN node tests/budget_circuit_breaker.test.js
PASS starts in closed state with zero usage
PASS records usage and decrements remaining
PASS trips on token cap exceeded
PASS trips on call cap exceeded
PASS rejects usage when open
PASS canProceed returns false when open
PASS canProceed returns false when estimate exceeds remaining
PASS reset restores closed state
PASS reset with new caps
budget_circuit_breaker tests complete
RUN node tests/context_sanitizer.test.js
PASS context sanitizer redacts tool-shaped JSON payload
PASS context sanitizer strips role/authority prefixes
PASS context sanitizer preserves normal human text
RUN node tests/freecompute_cloud.test.js

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

RUN node tests/freecompute_registry_error_classification.test.js
PASS classifyDispatchError: timeout
PASS classifyDispatchError: auth/config/http
RUN node tests/integrity_guard.test.js
PASS integrity baseline is deterministic
PASS integrity drift fails closed and explicit approval recovers
PASS runtime identity override metadata is denied
PASS integrity guard hook enforces baseline presence
RUN node tests/lint_legacy_node_names.test.js
PASS parseAddedLegacyMentions finds newly added System-1 references
PASS lintLegacyNames ignores files with legacy header notice
RUN node tests/memory_writer.test.js
PASS memory writer sanitizes and appends workspace memory entries
RUN node tests/model_routing_no_oauth.test.js
PASS model routing no oauth/codex regression gate
RUN node tests/module_resolution_gate.test.js
PASS returns zero findings when relative require resolves
PASS reports finding when relative require target is missing
module_resolution_gate tests complete
RUN node tests/moltbook_activity.test.js
PASS moltbook activity aggregates monthly impact from local stub events
RUN node tests/node_identity.test.js
PASS loads system map with expected defaults
PASS normalizes system1/system-1 aliases to dali
PASS normalizes system2/system-2 aliases to c_lawd
PASS resolves workspace and memory roots from alias
RUN node tests/provider_diag_format.test.js
PASS provider_diag includes grep-friendly providers_summary section
provider_diag_format tests complete
RUN node tests/providers/local_vllm_provider.test.js
PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
PASS healthProbe returns fail-closed result when endpoint is unreachable
PASS generateChat returns expected output shape from vLLM response
PASS normalizeBaseUrl appends /v1 only when missing
RUN node tests/redact_audit_evidence.test.js
PASS idempotent: applying rules twice yields same result
PASS JSON validity preserved after redaction
PASS no /Users/ or heathyeager remains after redaction
PASS repo root path replaced correctly
PASS openclaw config path replaced correctly
PASS generic home path replaced correctly
PASS ls -la line replaced correctly
PASS standalone username replaced
PASS timestamps, hashes, exit codes not redacted
PASS placeholders are not themselves redactable patterns
PASS CLI redacts synthetic fixtures and writes output bundle
PASS CLI dry-run emits summary and does not write output files
RUN node tests/secrets_bridge.test.js
PASS provider mapping exposes required env vars
PASS maskSecretFingerprint never returns raw secret value
PASS bridge serialization does not expose env secret values
PASS injectRuntimeEnv respects operator override and injects missing
PASS injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY
PASS config includes secrets bridge governance knobs
PASS redaction covers mapped secret env vars
PASS auto backend detection is platform deterministic
PASS file backend requires explicit opt-in
RUN node tests/secrets_cli_exec.test.js
PASS secrets cli exec injects alias env keys without printing values
RUN node tests/secrets_cli_plugin.test.js
PASS plugin registers CLI command: secrets
PASS secrets cli status prints enablement header (no secrets)
secrets_cli_plugin tests complete
RUN node tests/skill_composer.test.js
PASS skill composer is disabled by default
PASS skill composer respects tool governance decisions
RUN node tests/system1_ignores_system2_env.test.js
PASS createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false
PASS probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false
PASS probeVllmServer consults SYSTEM2_VLLM_* when system2 is true
PASS probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd
RUN node tests/system2_config_resolver.test.js
PASS resolves with explicit args (highest precedence)
PASS falls back to SYSTEM2_VLLM_* env vars
PASS falls back to OPENCLAW_VLLM_* env vars
PASS prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*
PASS uses node alias system-2 for c_lawd routing context
PASS uses defaults when envs not set
PASS emits diagnostic events (keys only)
PASS resolves numeric config deterministically
PASS invalid numeric env yields NaN (no throw)
RUN node tests/system2_evidence_bundle.test.js
PASS buildEvidenceBundle captures raw, writes redacted output, and emits manifest
PASS buildEvidenceBundle preserves fail-closed snapshot status
RUN node tests/system2_experiment.test.js
PASS no-change fixture yields INCONCLUSIVE
PASS improvement fixture yields KEEP
PASS regression fixture yields REVERT
PASS auth preset script maps to calibrated fail-on path
PASS calibrated auth fail-on yields REVERT on regression fixture
PASS failing subprocess writes UNAVAILABLE report and exits 3
RUN node tests/system2_federation_observability_contract.test.js
PASS FederatedEnvelopeV1 fixture validates (strict)
PASS FederatedEnvelopeV1 rejects invalid schema (fail-closed)
PASS System2EventV1 fixture validates
PASS JSONL sink contract is deterministic (exact line match)
PASS redaction-at-write is deterministic and idempotent
PASS gating: disabled emitter is a no-op
PASS gating: enabled emitter appends a redacted event
PASS emitter does not throw on sink error by default (strict=false)
PASS emitter fails closed on sink error when strict=true
RUN node tests/system2_http_edge.test.js
PASS edge rejects missing/invalid auth and does not log secrets
PASS edge rate limits per identity
PASS edge enforces body size limit (413)
PASS rpc routes require approval (fail-closed)
PASS malformed read tool payloads are denied at edge
PASS websocket upgrade requires approval (fail-closed)
PASS non-loopback bind requires explicit opt-in
PASS HMAC signing auth (replay resistant)
PASS HMAC mode can allow loopback Bearer (opt-in)
PASS audit sink writes JSONL and rotates (no secrets)
PASS tokens/hmac keys file mode is enforced (0600)
PASS inflight caps + timeouts are enforced/configured
system2_http_edge tests complete
RUN node tests/system2_repair_auth_profiles_acceptance.test.js
PASS system2 repair auth-profiles acceptance check
RUN node tests/system2_repair_models_acceptance.test.js
PASS system2 repair models acceptance check
RUN node tests/system2_repair_scripts_regression.test.js
PASS system2 repair scripts regression gate
RUN node tests/system2_snapshot_capture.test.js
PASS captureSnapshot writes stable files and summary shape
PASS captureSnapshot fail-closed with partial outputs when command fails
RUN node tests/system2_snapshot_diff.test.js
PASS JSON output is stable and ignores timestamp fields by default
PASS ignore list suppresses expected diff paths and exits 0
PASS fail-on marks regressions and exits 2
PASS human output includes summary counts and regression marker
PASS computeDiff supports deterministic dotpath flattening
RUN node tests/system2_snapshot_observability_seam.test.js
PASS OFF: system2.observability.enabled=false emits nothing and writes no JSONL
PASS ON: system2.observability.enabled=true writes exactly one deterministic JSONL line
RUN node tests/tacticr_feedback_writer.test.js
PASS tacticr feedback writer appends schema-valid sanitized JSONL entries
PASS tacticr feedback writer enforces required schema fields
RUN node tests/tool_governance.test.js
PASS tool governance allows explicit allowlist actions
PASS tool governance asks for exec/network/outside-workspace writes
PASS tool governance denies explicit denylist actions
RUN node tests/tool_governance_edge_hook.test.js
PASS http edge governance hook maps approval/deny errors deterministically
FAILURES: 1/38

## Regression Fix: SOUL canonical sync (2026-02-21T23:47:31Z)
Root cause: verify_goal_identity_invariants requires repo-root SOUL.md to byte-match workspace/governance/SOUL.md.
Action: cp workspace/governance/SOUL.md SOUL.md
```bash
python3 -m unittest tests_unittest.test_goal_identity_invariants -v
test_verifier_passes_in_repo (tests_unittest.test_goal_identity_invariants.TestGoalIdentityInvariants.test_verifier_passes_in_repo) ... ok
test_verifier_strict_fails_on_fixture_warning (tests_unittest.test_goal_identity_invariants.TestGoalIdentityInvariants.test_verifier_strict_fails_on_fixture_warning) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.376s

OK
```

### npm test (2026-02-21T23:48:36Z)
```bash
npm test

> openclaw@0.0.0 test
> node scripts/run_tests.js

RUN python3  -m unittest discover -s tests_unittest -p test_*.py
.............................................................................................................................................................................................
----------------------------------------------------------------------
Ran 189 tests in 4.803s

OK
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
⚠️ witness ledger commit skipped: witness_error: boom
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
❌ witness ledger commit failed (strict): witness_error: boom
==================================================
❌ AUDIT FAILED - Commit blocked
==================================================
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp2_unpjpj/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp2_unpjpj/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp2_unpjpj/overlay/quarantine/20260222-094839/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpiluyfnox/overlay/quarantine/20260222-094841/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpqidc0ksn/overlay/quarantine/20260222-094841/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpz8aq8rzg/overlay/quarantine/20260222-094841/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp8rq8qoqj/overlay/quarantine/20260222-094841/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmplws3y6s6/overlay/quarantine/20260222-094841/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmplws3y6s6/quarantine/openclaw-quarantine-20260222-094841
RUN node tests/analyze_session_patterns.test.js
PASS analyze_session_patterns aggregates recurring inefficiency patterns
RUN node tests/anticipate.test.js
PASS anticipate module emits suggestion-only low-risk automation hints
PASS anticipate feature flag disables suggestions
RUN node tests/ask_first_tool_governance.test.js
PASS ask_first enforces approval for exec
PASS ask_first allows ask-decision action with operator approval
PASS ask_first surfaces deny decisions as ToolDeniedError
RUN node tests/audit_sink_hash_chain.test.js
PASS audit sink hash chaining persists across rotation
RUN node tests/budget_circuit_breaker.test.js
PASS starts in closed state with zero usage
PASS records usage and decrements remaining
PASS trips on token cap exceeded
PASS trips on call cap exceeded
PASS rejects usage when open
PASS canProceed returns false when open
PASS canProceed returns false when estimate exceeds remaining
PASS reset restores closed state
PASS reset with new caps
budget_circuit_breaker tests complete
RUN node tests/context_sanitizer.test.js
PASS context sanitizer redacts tool-shaped JSON payload
PASS context sanitizer strips role/authority prefixes
PASS context sanitizer preserves normal human text
RUN node tests/freecompute_cloud.test.js

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

RUN node tests/freecompute_registry_error_classification.test.js
PASS classifyDispatchError: timeout
PASS classifyDispatchError: auth/config/http
RUN node tests/integrity_guard.test.js
PASS integrity baseline is deterministic
PASS integrity drift fails closed and explicit approval recovers
PASS runtime identity override metadata is denied
PASS integrity guard hook enforces baseline presence
RUN node tests/lint_legacy_node_names.test.js
PASS parseAddedLegacyMentions finds newly added System-1 references
PASS lintLegacyNames ignores files with legacy header notice
RUN node tests/memory_writer.test.js
PASS memory writer sanitizes and appends workspace memory entries
RUN node tests/model_routing_no_oauth.test.js
PASS model routing no oauth/codex regression gate
RUN node tests/module_resolution_gate.test.js
PASS returns zero findings when relative require resolves
PASS reports finding when relative require target is missing
module_resolution_gate tests complete
RUN node tests/moltbook_activity.test.js
PASS moltbook activity aggregates monthly impact from local stub events
RUN node tests/node_identity.test.js
PASS loads system map with expected defaults
PASS normalizes system1/system-1 aliases to dali
PASS normalizes system2/system-2 aliases to c_lawd
PASS resolves workspace and memory roots from alias
RUN node tests/provider_diag_format.test.js
PASS provider_diag includes grep-friendly providers_summary section
provider_diag_format tests complete
RUN node tests/providers/local_vllm_provider.test.js
PASS healthProbe succeeds against mocked vLLM endpoint and normalizes /v1
PASS healthProbe returns fail-closed result when endpoint is unreachable
PASS generateChat returns expected output shape from vLLM response
PASS normalizeBaseUrl appends /v1 only when missing
RUN node tests/redact_audit_evidence.test.js
PASS idempotent: applying rules twice yields same result
PASS JSON validity preserved after redaction
PASS no /Users/ or heathyeager remains after redaction
PASS repo root path replaced correctly
PASS openclaw config path replaced correctly
PASS generic home path replaced correctly
PASS ls -la line replaced correctly
PASS standalone username replaced
PASS timestamps, hashes, exit codes not redacted
PASS placeholders are not themselves redactable patterns
PASS CLI redacts synthetic fixtures and writes output bundle
PASS CLI dry-run emits summary and does not write output files
RUN node tests/secrets_bridge.test.js
PASS provider mapping exposes required env vars
PASS maskSecretFingerprint never returns raw secret value
PASS bridge serialization does not expose env secret values
PASS injectRuntimeEnv respects operator override and injects missing
PASS injectRuntimeEnv propagates GROQ_API_KEY operator override to OPENCLAW_GROQ_API_KEY
PASS config includes secrets bridge governance knobs
PASS redaction covers mapped secret env vars
PASS auto backend detection is platform deterministic
PASS file backend requires explicit opt-in
RUN node tests/secrets_cli_exec.test.js
PASS secrets cli exec injects alias env keys without printing values
RUN node tests/secrets_cli_plugin.test.js
PASS plugin registers CLI command: secrets
PASS secrets cli status prints enablement header (no secrets)
secrets_cli_plugin tests complete
RUN node tests/skill_composer.test.js
PASS skill composer is disabled by default
PASS skill composer respects tool governance decisions
RUN node tests/system1_ignores_system2_env.test.js
PASS createVllmProvider ignores SYSTEM2_VLLM_* when system2 is false
PASS probeVllmServer ignores SYSTEM2_VLLM_* when system2 is false
PASS probeVllmServer consults SYSTEM2_VLLM_* when system2 is true
PASS probeVllmServer consults SYSTEM2_VLLM_* when nodeId alias resolves to c_lawd
RUN node tests/system2_config_resolver.test.js
PASS resolves with explicit args (highest precedence)
PASS falls back to SYSTEM2_VLLM_* env vars
PASS falls back to OPENCLAW_VLLM_* env vars
PASS prefers SYSTEM2_VLLM_* over OPENCLAW_VLLM_*
PASS uses node alias system-2 for c_lawd routing context
PASS uses defaults when envs not set
PASS emits diagnostic events (keys only)
PASS resolves numeric config deterministically
PASS invalid numeric env yields NaN (no throw)
RUN node tests/system2_evidence_bundle.test.js
PASS buildEvidenceBundle captures raw, writes redacted output, and emits manifest
PASS buildEvidenceBundle preserves fail-closed snapshot status
RUN node tests/system2_experiment.test.js
PASS no-change fixture yields INCONCLUSIVE
PASS improvement fixture yields KEEP
PASS regression fixture yields REVERT
PASS auth preset script maps to calibrated fail-on path
PASS calibrated auth fail-on yields REVERT on regression fixture
PASS failing subprocess writes UNAVAILABLE report and exits 3
RUN node tests/system2_federation_observability_contract.test.js
PASS FederatedEnvelopeV1 fixture validates (strict)
PASS FederatedEnvelopeV1 rejects invalid schema (fail-closed)
PASS System2EventV1 fixture validates
PASS JSONL sink contract is deterministic (exact line match)
PASS redaction-at-write is deterministic and idempotent
PASS gating: disabled emitter is a no-op
PASS gating: enabled emitter appends a redacted event
PASS emitter does not throw on sink error by default (strict=false)
PASS emitter fails closed on sink error when strict=true
RUN node tests/system2_http_edge.test.js
PASS edge rejects missing/invalid auth and does not log secrets
PASS edge rate limits per identity
PASS edge enforces body size limit (413)
PASS rpc routes require approval (fail-closed)
PASS malformed read tool payloads are denied at edge
PASS websocket upgrade requires approval (fail-closed)
PASS non-loopback bind requires explicit opt-in
PASS HMAC signing auth (replay resistant)
PASS HMAC mode can allow loopback Bearer (opt-in)
PASS audit sink writes JSONL and rotates (no secrets)
PASS tokens/hmac keys file mode is enforced (0600)
PASS inflight caps + timeouts are enforced/configured
system2_http_edge tests complete
RUN node tests/system2_repair_auth_profiles_acceptance.test.js
PASS system2 repair auth-profiles acceptance check
RUN node tests/system2_repair_models_acceptance.test.js
PASS system2 repair models acceptance check
RUN node tests/system2_repair_scripts_regression.test.js
PASS system2 repair scripts regression gate
RUN node tests/system2_snapshot_capture.test.js
PASS captureSnapshot writes stable files and summary shape
PASS captureSnapshot fail-closed with partial outputs when command fails
RUN node tests/system2_snapshot_diff.test.js
PASS JSON output is stable and ignores timestamp fields by default
PASS ignore list suppresses expected diff paths and exits 0
PASS fail-on marks regressions and exits 2
PASS human output includes summary counts and regression marker
PASS computeDiff supports deterministic dotpath flattening
RUN node tests/system2_snapshot_observability_seam.test.js
PASS OFF: system2.observability.enabled=false emits nothing and writes no JSONL
PASS ON: system2.observability.enabled=true writes exactly one deterministic JSONL line
RUN node tests/tacticr_feedback_writer.test.js
PASS tacticr feedback writer appends schema-valid sanitized JSONL entries
PASS tacticr feedback writer enforces required schema fields
RUN node tests/tool_governance.test.js
PASS tool governance allows explicit allowlist actions
PASS tool governance asks for exec/network/outside-workspace writes
PASS tool governance denies explicit denylist actions
RUN node tests/tool_governance_edge_hook.test.js
PASS http edge governance hook maps approval/deny errors deterministically
OK 38 test group(s)
```

### python3 -m unittest (2026-02-21T23:48:56Z)
```bash
python3 -m unittest
.............................................................................................................................................................................................
----------------------------------------------------------------------
Ran 189 tests in 4.001s

OK
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
⚠️ witness ledger commit skipped: witness_error: boom
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
❌ witness ledger commit failed (strict): witness_error: boom
==================================================
❌ AUDIT FAILED - Commit blocked
==================================================
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpycy_gg12/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpycy_gg12/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpycy_gg12/overlay/quarantine/20260222-094858/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpqmypssb_/overlay/quarantine/20260222-094859/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpkc887s8x/overlay/quarantine/20260222-094859/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpqtv5sgvc/overlay/quarantine/20260222-094900/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmppaz1pg9z/overlay/quarantine/20260222-094900/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpmr4oz5d9/overlay/quarantine/20260222-094900/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpmr4oz5d9/quarantine/openclaw-quarantine-20260222-094900
```

## Pre-final Diff (2026-02-21T23:52:36Z)
```bash
git diff --name-status
M	SOUL.md
M	workspace/audit/stash_integration_20260222.md
```

## Residual Risks / Uncertainty
- Ignored session file workspace/teamchat/sessions/tacti_architecture_review.jsonl was restored by stash but intentionally excluded from commits due .gitignore and ambiguity about whether it should be versioned.
- Artifact workspace/mlx_audit.zip excluded from repo commits and moved to /tmp/wt_wirings_integration_excluded/mlx_audit.zip.

## Revert Sequence (reverse order)
1. git revert HEAD
2. git revert 5a78788
3. git revert 9ae463d
4. git revert da84eba

(Current HEAD commit hashes before final fix commit listed above; final exact list captured after commit/push.)
