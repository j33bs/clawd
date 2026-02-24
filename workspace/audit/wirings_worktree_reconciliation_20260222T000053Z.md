# Wirings Worktree Reconciliation Audit

- Timestamp (UTC): 20260222T000053Z
- Target branch: codex/feat/wirings-integration-20260222
- Scope: Worktree collision resolution + branch sanity checks for PR prep

## Phase 0 Baseline
```bash
git status --porcelain -uall
 M workspace/knowledge_base/data/last_sync.txt
?? workspace/audit/stash_integration_20260222.md
?? workspace/audit/wirings_worktree_reconciliation_20260222T000053Z.md

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
