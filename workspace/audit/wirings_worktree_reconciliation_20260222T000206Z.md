# Wirings Worktree Reconciliation Audit

- Timestamp (UTC): 20260222T000206Z
- Target branch: codex/feat/wirings-integration-20260222
- Scope: Worktree collision resolution + branch sanity checks for PR prep

## Phase 0 Baseline
```bash
git status --porcelain -uall
 M workspace/knowledge_base/data/last_sync.txt
?? workspace/audit/stash_integration_20260222.md
?? workspace/audit/wirings_worktree_reconciliation_20260222T000053Z.md
?? workspace/audit/wirings_worktree_reconciliation_20260222T000206Z.md

git rev-parse HEAD
ebfa6b626d345948ef50af77d41f31b09f370fed

git worktree list
/Users/heathyeager/clawd                                               ebfa6b6 [codex/sec/audit-secret-guard-20260221T090531Z]
/private/tmp/clawd-audit-secret-guard-20260221T085921Z                 a2a0aa5 [codex/sec/audit-secret-guard-20260221T085921Z] prunable
/private/tmp/clawd-exec2-merge-SLe6cu                                  9f35bc1 [codex/exec2-merge-20260212] prunable
/private/tmp/clawd-fix-exp                                             8819f73 [fix/system2-experiment-exit3] prunable
/private/tmp/clawd-followups-20260221T080402Z                          f7cfb8b [fix/groq-policy-alignment-20260221T081156Z] prunable
/private/tmp/clawd-main-postmerge-UHssZc                               3db90e1 (detached HEAD) prunable
/private/tmp/clawd-main-pr19-stabilize                                 cef6fad [codex/docs-pr19-system2-vllm-resolver] prunable
/private/tmp/clawd-main-verify                                         de25cf3 [codex/verify/main-post-triage-20260212] prunable
/private/tmp/clawd-main-verify-auth-preset                             e567ff2 [codex/docs-system2-token-warning-20260212] prunable
/private/tmp/clawd-main-verify-redaction                               3492238 [codex/verify/main-post-redaction-20260212] prunable
/private/tmp/clawd-main-verify-system2-diff                            fee544f [codex/verify/main-post-system2-diff-20260212] prunable
/private/tmp/clawd-main-verify-system2-evidence                        67710b6 [codex/verify/main-post-system2-evidence-20260212] prunable
/private/tmp/clawd-main-verify-system2-experiment                      4b0a30e [codex/verify/main-post-system2-experiment-20260212] prunable
/private/tmp/clawd-main-verify-system2-experiment-fix                  27c2bd7 [verify/main-post-system2-experiment-fix-20260212] prunable
/private/tmp/clawd-openai-codex-align-20260221T081840Z                 5138d9b [fix/npm-policy-openai-codex-alignment-20260221T081840Z] prunable
/private/tmp/clawd-postmerge-validate-kDVoV5                           d2351b5 [docs/pr-template] prunable
/private/tmp/clawd-pr-body-lint                                        c0e6140 [codex/ci/pr-body-lint] prunable
/private/tmp/clawd-pr-hygiene-tEdubi                                   0f66680 [codex/pr-cleanup] prunable
/private/tmp/clawd-pr31-cifix-9oNdma                                   ebc2acf [codex/fix/pr31-secret-tool-ci] prunable
/private/tmp/clawd-pr31-fix-SblWGa                                     7067621 [codex/fix/pr31-mergeable-from-main] prunable
/private/tmp/clawd-pr31-resolve-4KmXO3                                 c598edb [pr31-merge-resolve] prunable
/private/tmp/clawd-redaction-workflow                                  feedd9a [codex/feature/redaction-workflow] prunable
/private/tmp/clawd-secrets-bridge                                      3886374 [feature/secrets-cli-integration] prunable
/private/tmp/clawd-system2-auth-preset                                 3a16022 [codex/chore-system2-auth-preset-20260212] prunable
/private/tmp/clawd-system2-config-resolver                             bdd84d5 (detached HEAD) prunable
/private/tmp/clawd-system2-diff                                        b5c5bb7 [codex/feature/system2-snapshot-diff] prunable
/private/tmp/clawd-system2-evidence                                    34b6779 [codex/feature/system2-evidence-workflow] prunable
/private/tmp/clawd-system2-experiment                                  15bc823 [codex/feature/system2-experiment-runner] prunable
/private/tmp/clawd-triage-closeout                                     4333ed2 [codex/docs/triage-closeout-20260212] prunable
/private/tmp/clawd-triage-docs-001                                     537092d [codex/triage/docs-001] prunable
/private/tmp/clawd-triage-docs-001-clean                               eaa7ad6 [codex/triage/docs-001-clean] prunable
/private/tmp/clawd-triage-mixed-001a-clean                             6153448 [codex/triage/mixed-001a-clean] prunable
/private/tmp/clawd-triage-tests-001                                    537092d [codex/triage/tests-001] prunable
/private/tmp/clawd-triage-tooling-001-clean                            1b18331 [codex/triage/tooling-001-clean] prunable
/private/tmp/twenty-evolutions-20260221                                a3cb70f [codex/feat/wirings-integration-20260222] prunable
/private/tmp/wt_autocommit_verify                                      81cec9a (detached HEAD) prunable
/private/tmp/wt_ci_baseline                                            ff8c813 [fix/ci-baseline-20260220] prunable
/private/tmp/wt_docs_main                                              d22c783 [main] prunable
/private/tmp/wt_evolution10                                            edd311e [codex/feature/evolution-ideas-1-10-20260220] prunable
/private/tmp/wt_evolution_pack                                         1342820 (detached HEAD) prunable
/private/tmp/wt_final                                                  1342820 (detached HEAD) prunable
/private/tmp/wt_main_parity                                            e8ad6d7 (detached HEAD) prunable
/private/tmp/wt_main_postmerge                                         197d056 (detached HEAD) prunable
/private/tmp/wt_main_verify                                            9c5a5bd (detached HEAD) prunable
/private/tmp/wt_oauth_fix                                              eed9ce7 [fix/oauth-openai-codex-teamchat-20260220] prunable
/private/tmp/wt_pr37_parity                                            1963b88 (detached HEAD) prunable
/private/tmp/wt_teamchat                                               84ecbc7 [codex/feature/team-chat-20260220] prunable
/private/tmp/wt_teamchat_witness                                       6cd2b0e [codex/feature/teamchat-witness-docs-and-verify-20260220] prunable
/private/tmp/wt_wirings_integration                                    a3cb70f [codex/feat/wirings-integration-20260222]
/Users/heathyeager/clawd/.claude/worktrees/adoring-bose                4a6c0ac [claude/adoring-bose]
/Users/heathyeager/clawd/.claude/worktrees/condescending-varahamihira  347f4c7 [claude/condescending-varahamihira]
/Users/heathyeager/clawd/.claude/worktrees/cranky-cartwright           831c219 [claude/cranky-cartwright]
/Users/heathyeager/clawd/.claude/worktrees/crazy-brahmagupta           4a6c0ac [claude/crazy-brahmagupta]
/Users/heathyeager/clawd/.claude/worktrees/elastic-swirles             4d226e6 [claude/elastic-swirles]
/Users/heathyeager/clawd/.claude/worktrees/strange-vaughan             831c219 [claude/strange-vaughan]
/Users/heathyeager/clawd/.claude/worktrees/trusting-lamarr             b1a92bc [claude/trusting-lamarr]
/Users/heathyeager/clawd/.worktrees/efficiency_baseline_main           e8ad6d7 (detached HEAD)
/Users/heathyeager/clawd/.worktrees/efficiency_hacks_20260221          fb0151d [codex/perf/efficiency-hacks-20260221]
/Users/heathyeager/clawd_system2_exec                                  9f35bc1 [integration/system2-unified]
```

## Phase 0 Branch Inspection
```bash
git fetch origin

git log --oneline --decorate --max-count=20 origin/codex/feat/wirings-integration-20260222
a3cb70f (origin/codex/feat/wirings-integration-20260222, codex/feat/wirings-integration-20260222) docs(audit): finalize stash integration report
7bc4d07 fix(gov): restore canonical SOUL after stash integration
e9230af chore(repo): handle stashed artifacts/ignore rules
5a78788 feat(chore): integrate stashed script/source updates
9ae463d data(kb): integrate stashed knowledge base/session updates
da84eba docs: integrate stashed documentation and audit artifacts
fe75e36 docs(audit): record push attempt evidence
061c92e docs(audit): finalize wirings integration evidence
ed78439 feat(router): integrate ActiveInferenceAgent decision path (EFE-based)
e0942ff feat(hivemind): enable guarded counterfactual replay in dynamics pipeline
7fada16 feat(research): publish gap analysis into knowledge base
8094e99 feat(hivemind): enable valence-weighted trails under OPENCLAW_TRAIL_VALENCE
aa564e7 feat(cron): run narrative distillation before daily brief
1c694f0 feat(router-js): include proprioception sample in response meta
58ecd12 feat(router): enable oscillatory gating under TACTI_CR_AROUSAL_OSC
de36354 feat(kb): enable PrefetchCache for context prefetch
84b38a2 feat(gov): chain governance log writes via witness ledger
4e1de3d feat(itc): forward ingestion boundary to classifier
9ed3446 (codex/feature/twenty-evolutions-20260221) chore(tacti_cr): guard exec-forward shims against double-exec
24b0781 test(tacti): pin tacti/tacti_cr aliasing invariants; harden shim metadata

git diff --name-status origin/main...origin/codex/feat/wirings-integration-20260222
M	MEMORY.md
A	TWENTY_EVOLUTIONS.md
M	core/system2/inference/router.js
M	env.d/system1-routing.env
M	memory/literature/state.json
M	scripts/daily_technique.py
M	scripts/get_daily_quote.js
M	tests/freecompute_cloud.test.js
M	tests/system2_http_edge.test.js
A	tests_unittest/test_audit_commit_hook_witness.py
M	tests_unittest/test_ensure_cron_jobs.py
M	tests_unittest/test_hivemind_dynamics_pipeline.py
M	tests_unittest/test_hivemind_physarum_router.py
A	tests_unittest/test_itc_ingestion_forwarding.py
A	tests_unittest/test_kb_prefetch_cache.py
A	tests_unittest/test_memory_message_hooks.py
M	tests_unittest/test_policy_router_active_inference_hook.py
A	tests_unittest/test_policy_router_oscillatory_gating.py
A	tests_unittest/test_research_gap_analyzer_bridge.py
A	tests_unittest/test_session_handshake.py
A	tests_unittest/test_tacti_cr_impasse.py
A	tests_unittest/test_tacti_efe_calculator.py
A	tests_unittest/test_tacti_namespace_aliasing.py
A	tests_unittest/test_verify_llm_policy_alias.py
A	workspace/MLX_INTEGRATION_AUDIT.md
A	workspace/TEN_HIGH_LEVERAGE.md
A	workspace/TWENTY_EVOLUTIONS.md
A	workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
A	workspace/audit/fix_canonical_soul_drift_20260221T080815Z.md
A	workspace/audit/fix_groq_policy_alignment_20260221T081255Z.md
A	workspace/audit/fix_regression_bootstrap_config_20260221T081128Z.md
A	workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
A	workspace/audit/sec_audit_secret_guard_normalize_20260221T092622Z.md
A	workspace/audit/stash_integration_20260222.md
A	workspace/audit/twenty_evolutions_impl_20260221T104827Z.md
A	workspace/audit/wirings_integration_20260222.md
M	workspace/automation/cron_jobs.json
A	workspace/briefs/codex_prompt_agents_update.md
A	workspace/briefs/memory_integration.md
M	workspace/hivemind/hivemind/dynamics_pipeline.py
M	workspace/hivemind/hivemind/physarum_router.py
M	workspace/itc_pipeline/ingestion_boundary.py
M	workspace/knowledge_base/data/entities.jsonl
A	workspace/knowledge_base/data/last_sync.txt
M	workspace/knowledge_base/kb.py
A	workspace/knowledge_base/research/papers/2601.06002_molecular_structure_thought.md
A	workspace/memory/arousal_tracker.py
A	workspace/memory/message_hooks.py
A	workspace/memory/relationship_tracker.py
A	workspace/memory/session_handshake.py
M	workspace/research/data/papers.jsonl
A	workspace/research/gap_analyzer.py
M	workspace/research/research_ingest.py
M	workspace/scripts/audit_commit_hook.py
M	workspace/scripts/policy_router.py
M	workspace/scripts/team_chat.py
M	workspace/scripts/verify_llm_policy.sh
R100	workspace/tacti_cr/README.md	workspace/tacti/README.md
A	workspace/tacti/__init__.py
A	workspace/tacti/active_inference_agent.py
A	workspace/tacti/arousal.py
A	workspace/tacti/arousal_oscillator.py
A	workspace/tacti/collapse.py
A	workspace/tacti/config.py
A	workspace/tacti/cross_timescale.py
A	workspace/tacti/curiosity.py
A	workspace/tacti/dream_consolidation.py
A	workspace/tacti/efe_calculator.py
A	workspace/tacti/events.py
A	workspace/tacti/events_paths.py
A	workspace/tacti/expression.py
A	workspace/tacti/external_memory.py
A	workspace/tacti/hivemind_bridge.py
A	workspace/tacti/impasse.py
A	workspace/tacti/mirror.py
A	workspace/tacti/novel10_contract.py
A	workspace/tacti/oscillatory_gating.py
A	workspace/tacti/prefetch.py
A	workspace/tacti/repair.py
A	workspace/tacti/semantic_immune.py
A	workspace/tacti/temporal.py
A	workspace/tacti/temporal_watchdog.py
A	workspace/tacti/valence.py
M	workspace/tacti_cr/__init__.py
M	workspace/tacti_cr/active_inference_agent.py
M	workspace/tacti_cr/arousal.py
M	workspace/tacti_cr/arousal_oscillator.py
M	workspace/tacti_cr/collapse.py
M	workspace/tacti_cr/config.py
M	workspace/tacti_cr/cross_timescale.py
M	workspace/tacti_cr/curiosity.py
M	workspace/tacti_cr/dream_consolidation.py
M	workspace/tacti_cr/efe_calculator.py
M	workspace/tacti_cr/events.py
M	workspace/tacti_cr/events_paths.py
M	workspace/tacti_cr/expression.py
M	workspace/tacti_cr/external_memory.py
M	workspace/tacti_cr/hivemind_bridge.py
A	workspace/tacti_cr/impasse.py
M	workspace/tacti_cr/mirror.py
M	workspace/tacti_cr/novel10_contract.py
M	workspace/tacti_cr/oscillatory_gating.py
M	workspace/tacti_cr/prefetch.py
M	workspace/tacti_cr/repair.py
M	workspace/tacti_cr/semantic_immune.py
M	workspace/tacti_cr/temporal.py
M	workspace/tacti_cr/temporal_watchdog.py
M	workspace/tacti_cr/valence.py
M	workspace/teamchat/session.py

git diff --stat origin/main...origin/codex/feat/wirings-integration-20260222
 MEMORY.md                                          |   58 +-
 TWENTY_EVOLUTIONS.md                               |   63 +
 core/system2/inference/router.js                   |   22 +-
 env.d/system1-routing.env                          |    4 +
 memory/literature/state.json                       |    7 +-
 scripts/daily_technique.py                         |   35 +
 scripts/get_daily_quote.js                         |   41 +-
 tests/freecompute_cloud.test.js                    |   46 +
 tests/system2_http_edge.test.js                    |   39 +-
 tests_unittest/test_audit_commit_hook_witness.py   |   63 +
 tests_unittest/test_ensure_cron_jobs.py            |    2 +
 tests_unittest/test_hivemind_dynamics_pipeline.py  |   90 +-
 tests_unittest/test_hivemind_physarum_router.py    |   17 +-
 tests_unittest/test_itc_ingestion_forwarding.py    |   49 +
 tests_unittest/test_kb_prefetch_cache.py           |   47 +
 tests_unittest/test_memory_message_hooks.py        |   72 +
 .../test_policy_router_active_inference_hook.py    |   68 +
 .../test_policy_router_oscillatory_gating.py       |   64 +
 .../test_research_gap_analyzer_bridge.py           |   67 +
 tests_unittest/test_session_handshake.py           |   57 +
 tests_unittest/test_tacti_cr_impasse.py            |   48 +
 tests_unittest/test_tacti_efe_calculator.py        |   42 +
 tests_unittest/test_tacti_namespace_aliasing.py    |   81 +
 tests_unittest/test_verify_llm_policy_alias.py     |   62 +
 workspace/MLX_INTEGRATION_AUDIT.md                 |  192 +
 workspace/TEN_HIGH_LEVERAGE.md                     |  116 +
 workspace/TWENTY_EVOLUTIONS.md                     |  129 +
 ...lawd_pr_merge_and_followups_20260221T080418Z.md |   90 +
 .../fix_canonical_soul_drift_20260221T080815Z.md   |  125 +
 .../fix_groq_policy_alignment_20260221T081255Z.md  |   50 +
 ...regression_bootstrap_config_20260221T081128Z.md |   81 +
 .../pr_body_c_lawd_full_remediation_20260221.md    |   57 +
 ...udit_secret_guard_normalize_20260221T092622Z.md |   33 +
 workspace/audit/stash_integration_20260222.md      | 1095 +++
 .../twenty_evolutions_impl_20260221T104827Z.md     | 9524 ++++++++++++++++++++
 workspace/audit/wirings_integration_20260222.md    | 1824 ++++
 workspace/automation/cron_jobs.json                |    2 +-
 workspace/briefs/codex_prompt_agents_update.md     |   48 +
 workspace/briefs/memory_integration.md             |  155 +
 workspace/hivemind/hivemind/dynamics_pipeline.py   |   84 +-
 workspace/hivemind/hivemind/physarum_router.py     |    7 +-
 workspace/itc_pipeline/ingestion_boundary.py       |   78 +-
 workspace/knowledge_base/data/entities.jsonl       |  201 +
 workspace/knowledge_base/data/last_sync.txt        |    1 +
 workspace/knowledge_base/kb.py                     |   62 +-
 .../2601.06002_molecular_structure_thought.md      |   78 +
 workspace/memory/arousal_tracker.py                |  100 +
 workspace/memory/message_hooks.py                  |   52 +
 workspace/memory/relationship_tracker.py           |  180 +
 workspace/memory/session_handshake.py              |  144 +
 workspace/research/data/papers.jsonl               |   15 +
 workspace/research/gap_analyzer.py                 |  123 +
 workspace/research/research_ingest.py              |   34 +
 workspace/scripts/audit_commit_hook.py             |   46 +
 workspace/scripts/policy_router.py                 |   91 +-
 workspace/scripts/team_chat.py                     |  138 +-
 workspace/scripts/verify_llm_policy.sh             |   51 +-
 workspace/{tacti_cr => tacti}/README.md            |    0
 workspace/tacti/__init__.py                        |   71 +
 workspace/tacti/active_inference_agent.py          |   30 +
 workspace/tacti/arousal.py                         |  117 +
 workspace/tacti/arousal_oscillator.py              |  152 +
 workspace/tacti/collapse.py                        |   99 +
 workspace/tacti/config.py                          |  190 +
 workspace/tacti/cross_timescale.py                 |   83 +
 workspace/tacti/curiosity.py                       |   18 +
 workspace/tacti/dream_consolidation.py             |  374 +
 workspace/tacti/efe_calculator.py                  |   62 +
 workspace/tacti/events.py                          |   93 +
 workspace/tacti/events_paths.py                    |   22 +
 workspace/tacti/expression.py                      |  112 +
 workspace/tacti/external_memory.py                 |  142 +
 workspace/tacti/hivemind_bridge.py                 |  125 +
 workspace/tacti/impasse.py                         |   96 +
 workspace/tacti/mirror.py                          |  116 +
 workspace/tacti/novel10_contract.py                |   44 +
 workspace/tacti/oscillatory_gating.py              |   86 +
 workspace/tacti/prefetch.py                        |   96 +
 workspace/tacti/repair.py                          |   34 +
 workspace/tacti/semantic_immune.py                 |  265 +
 workspace/tacti/temporal.py                        |  217 +
 workspace/tacti/temporal_watchdog.py               |  145 +
 workspace/tacti/valence.py                         |   89 +
 workspace/tacti_cr/__init__.py                     |   88 +-
 workspace/tacti_cr/active_inference_agent.py       |   51 +-
 workspace/tacti_cr/arousal.py                      |  138 +-
 workspace/tacti_cr/arousal_oscillator.py           |  167 +-
 workspace/tacti_cr/collapse.py                     |  114 +-
 workspace/tacti_cr/config.py                       |  205 +-
 workspace/tacti_cr/cross_timescale.py              |  104 +-
 workspace/tacti_cr/curiosity.py                    |   35 +-
 workspace/tacti_cr/dream_consolidation.py          |  389 +-
 workspace/tacti_cr/efe_calculator.py               |   53 +-
 workspace/tacti_cr/events.py                       |  108 +-
 workspace/tacti_cr/events_paths.py                 |   37 +-
 workspace/tacti_cr/expression.py                   |  127 +-
 workspace/tacti_cr/external_memory.py              |  157 +-
 workspace/tacti_cr/hivemind_bridge.py              |  140 +-
 workspace/tacti_cr/impasse.py                      |   21 +
 workspace/tacti_cr/mirror.py                       |  131 +-
 workspace/tacti_cr/novel10_contract.py             |   59 +-
 workspace/tacti_cr/oscillatory_gating.py           |  107 +-
 workspace/tacti_cr/prefetch.py                     |  111 +-
 workspace/tacti_cr/repair.py                       |   55 +-
 workspace/tacti_cr/semantic_immune.py              |  280 +-
 workspace/tacti_cr/temporal.py                     |  232 +-
 workspace/tacti_cr/temporal_watchdog.py            |  160 +-
 workspace/tacti_cr/valence.py                      |  104 +-
 workspace/teamchat/session.py                      |   23 +
 109 files changed, 19442 insertions(+), 2782 deletions(-)
```

## Phase 1 Sanity Checks
```bash
# prompt command adapted: ls-files does not accept tree-ish; using ls-tree for branch content scan
git ls-tree -r --name-only origin/codex/feat/wirings-integration-20260222 | rg '^/tmp/' || true

tip_sha=a3cb70f
git show --name-only --stat a3cb70f
commit a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 09:53:38 2026 +1000

    docs(audit): finalize stash integration report

workspace/audit/stash_integration_20260222.md

rg -n 'mlx_audit\.zip' -S . || true

git ls-tree -r --name-only origin/codex/feat/wirings-integration-20260222 | rg 'mlx_audit\.zip' || true
```

## Phase 2 Worktree Resolution
```bash
# active worktree for branch
cd /tmp/wt_wirings_integration
git status --porcelain -uall

git rev-parse --abbrev-ref HEAD
codex/feat/wirings-integration-20260222

git rev-parse --short HEAD
a3cb70f

git show --name-only --stat a3cb70f
commit a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f
Author: Heath Yeager <heathyeager@gmail.com>
Date:   Sun Feb 22 09:53:38 2026 +1000

    docs(audit): finalize stash integration report

workspace/audit/stash_integration_20260222.md
```

## Findings
- No tracked absolute /tmp paths found in target branch tree.
- Tip commit a3cb70f is docs-only: workspace/audit/stash_integration_20260222.md.
- workspace/mlx_audit.zip is not tracked in target branch and no references were found by repository grep.
- Active worktree /tmp/wt_wirings_integration is clean and on codex/feat/wirings-integration-20260222 at a3cb70f.

## Risks / Open Questions
- Multiple stale prunable worktree entries exist under /private/tmp/* for this repo; no deletion performed in this pass.
- Current root worktree (/Users/heathyeager/clawd) has unrelated local drift on branch codex/sec/audit-secret-guard-20260221T090531Z.
