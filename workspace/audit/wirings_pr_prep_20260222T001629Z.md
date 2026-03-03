# Wirings PR Prep Audit

- Timestamp (UTC): 20260222T001629Z
- Worktree: /tmp/wt_wirings_integration
- Target branch: codex/feat/wirings-integration-20260222

## Phase 0 Baseline
```bash
git status --porcelain -uall
?? workspace/audit/wirings_pr_prep_20260222T001629Z.md

git rev-parse --abbrev-ref HEAD
codex/feat/wirings-integration-20260222

git rev-parse HEAD
a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f

git remote -v
origin	git@github.com:j33bs/clawd.git (fetch)
origin	git@github.com:j33bs/clawd.git (push)

git log --oneline --decorate --max-count=20
a3cb70f (HEAD -> codex/feat/wirings-integration-20260222, origin/codex/feat/wirings-integration-20260222) docs(audit): finalize stash integration report
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
```

## Phase 0 Remote Parity
```bash
git fetch origin

## Phase 0 Remote Parity
```bash
git fetch origin

git rev-parse origin/codex/feat/wirings-integration-20260222
a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f

git rev-parse HEAD
a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f
```

- parity_check: PASS

## Phase 1 Secret / Leak Scan
```bash
scanner_missing: workspace/scripts/scan_audit_secrets.sh
precommit_scan_mode_unclear: workspace/scripts/hooks/pre-commit (skipped per read-only constraint)

rg -n "(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH) PRIVATE KEY|xox[baprs]-|ghp_[A-Za-z0-9]{20,}|eyJhbGciOi)" -S . || true
./fixtures/redaction/in/metadata.json:5:  "token": "sk-TESTABCDEFGHIJKLMN123456"
./fixtures/redaction/in/credentials.txt:2:github_token=ghp_FAKE123456789012345678901234567890
./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:655:fixtures/redaction/in/metadata.json:5:  "token": "sk-TESTABCDEFGHIJKLMN123456"
./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:661:fixtures/redaction/in/credentials.txt:2:github_token=ghp_FAKE123456789012345678901234567890
./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:698:tests/redact_audit_evidence.test.js:149:  assert.ok(!credentialsOut.includes('ghp_FAKE123456789012345678901234567890'), 'GitHub-like key should be redacted');
./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:699:tests/redact_audit_evidence.test.js:158:  assert.ok(!metadataOut.includes('sk-TESTABCDEFGHIJKLMN123456'), 'JSON token should be redacted');
./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:707:tests/freecompute_cloud.test.js:281:  assert.equal(redactIfSensitive('some_field', 'Bearer eyJhbGciOiJ'), '[REDACTED]');
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:67:rg -n "(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH) PRIVATE KEY|xox[baprs]-|ghp_[A-Za-z0-9]{20,}|eyJhbGciOi)" -S . || true
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:68:./fixtures/redaction/in/metadata.json:5:  "token": "sk-TESTABCDEFGHIJKLMN123456"
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:69:./fixtures/redaction/in/credentials.txt:2:github_token=ghp_FAKE123456789012345678901234567890
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:70:./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:655:fixtures/redaction/in/metadata.json:5:  "token": "sk-TESTABCDEFGHIJKLMN123456"
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:71:./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:661:fixtures/redaction/in/credentials.txt:2:github_token=ghp_FAKE123456789012345678901234567890
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:72:./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:698:tests/redact_audit_evidence.test.js:149:  assert.ok(!credentialsOut.includes('ghp_FAKE123456789012345678901234567890'), 'GitHub-like key should be redacted');
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:73:./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:699:tests/redact_audit_evidence.test.js:158:  assert.ok(!metadataOut.includes('sk-TESTABCDEFGHIJKLMN123456'), 'JSON token should be redacted');
./workspace/audit/wirings_pr_prep_20260222T001629Z.md:74:./workspace/audit/repo_audit_remediation_dali_20260220T025348Z.md:707:tests/freecompute_cloud.test.js:281:  assert.equal(redactIfSensitive('some_field', 'Bearer eyJhbGciOiJ'), '[REDACTED]');
./tests/freecompute_cloud.test.js:281:  assert.equal(redactIfSensitive('some_field', 'Bearer eyJhbGciOiJ'), '[REDACTED]');
./tests/redact_audit_evidence.test.js:149:  assert.ok(!credentialsOut.includes('ghp_FAKE123456789012345678901234567890'), 'GitHub-like key should be redacted');
./tests/redact_audit_evidence.test.js:158:  assert.ok(!metadataOut.includes('sk-TESTABCDEFGHIJKLMN123456'), 'JSON token should be redacted');
```

## Phase 2 Reviewability Packet
```bash
git diff --name-status origin/main...HEAD
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

git diff --stat origin/main...HEAD | sed -n '1,200p'
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

# top 10 most-touched path groups (first two path segments)
  26 workspace/tacti
  25 workspace/tacti_cr
   9 workspace/audit
   4 workspace/scripts
   4 workspace/memory
   4 workspace/knowledge_base
   3 workspace/research
   2 workspace/hivemind
   2 workspace/briefs
   1 workspace/teamchat

rg -n "(FLAG|flags\.|feature\.|enable_|disabled_|router_gating|telemetry|witness|ledger|prefetch|distill|counterfactual)" workspace scripts memory tests -S || true
workspace/briefs/memory_integration.md:52:3. **Telling** — The story finds language, sequence, and witness
workspace/briefs/memory_integration.md:59:A story requires a listener. This is why therapy works — the therapist is a witness. But you can also be your own witness. The act of writing *is* creating a witness (your future self reading it).
memory/literature/The-Gay-Science.txt:1922:unrobust feature. Consciousness gives rise to countless mistakes that 
memory/literature/The-Gay-Science.txt:8114:German species, bears emphatic witness to the opposite. No, the 
memory/literature/The-Gay-Science.txt:8519:either to monologue art or to art before witnesses. The second category 
memory/literature/The-Gay-Science.txt:8528:budding artwork ('himself') from the eye of the witness, or whether he 
memory/literature/The-Gay-Science.txt:8935:condemned as eyewitnesses of politics that are destroying the German 
workspace/AUDIT_AIF_PHASE1_20260219.md:44:  - `npm test` currently fails on pre-existing governance invariant check unrelated to this feature.
scripts/system2/provider_diag.js:66:    reason = reason || 'disabled_by_policy';
scripts/system2/provider_diag.js:70:    reason = reason || 'disabled_by_policy';
scripts/system2/provider_diag.js:74:    reason = reason || 'disabled_by_policy';
scripts/system2/provider_diag.js:79:      reason = reason || 'disabled_by_policy';
scripts/system2/provider_diag.js:89:  if (!routingEnabledForProvider && !reason) reason = 'disabled_by_policy';
workspace/tacti/prefetch.py:1:"""Predictive context prefetcher with deterministic topic prediction and adaptive depth."""
workspace/tacti/prefetch.py:19:        self.cache_path = root / "workspace" / "state" / "prefetch" / "cache.jsonl"
workspace/tacti/prefetch.py:20:        self.index_path = root / "workspace" / "state" / "prefetch" / "index.json"
workspace/tacti/prefetch.py:46:    def record_prefetch(self, topic: str, docs: list[str]) -> None:
workspace/tacti/prefetch.py:54:        emit("tacti_cr.prefetch.recorded", {"topic": topic, "docs_count": len(docs), "depth": int(idx.get("depth", 3))})
workspace/tacti/prefetch.py:67:        emit("tacti_cr.prefetch.hit_rate", {"hit": bool(hit), "hit_rate": hit_rate, "depth": int(idx["depth"]), "total": total})
workspace/tacti/prefetch.py:82:def prefetch_context(token_stream: str, query_fn, *, repo_root: Path | None = None) -> dict[str, Any]:
workspace/tacti/prefetch.py:83:    if not is_enabled("prefetch"):
workspace/tacti/prefetch.py:84:        return {"ok": False, "reason": "prefetch_disabled", "topics": []}
workspace/tacti/prefetch.py:87:    emit("tacti_cr.prefetch.predicted_topics", {"topics": topics, "depth": cache.depth()})
workspace/tacti/prefetch.py:91:    cache.record_prefetch("|".join(topics), docs)
workspace/tacti/prefetch.py:92:    emit("tacti_cr.prefetch.cache_put", {"topics": topics, "docs_count": len(docs)})
workspace/tacti/prefetch.py:96:__all__ = ["PrefetchCache", "predict_topics", "prefetch_context"]
tests/freecompute_cloud.test.js:521:test('ledger: starts with zero counters', () => {
tests/freecompute_cloud.test.js:522:  const ledger = new QuotaLedger({ disabled: true });
tests/freecompute_cloud.test.js:523:  const check = ledger.check('test', { rpm: 10, rpd: 100 });
tests/freecompute_cloud.test.js:529:test('ledger: tracks requests', () => {
tests/freecompute_cloud.test.js:530:  const ledger = new QuotaLedger({ disabled: true });
tests/freecompute_cloud.test.js:531:  ledger.record('groq', { tokensIn: 100, tokensOut: 50 });
tests/freecompute_cloud.test.js:532:  ledger.record('groq', { tokensIn: 200, tokensOut: 100 });
tests/freecompute_cloud.test.js:533:  const check = ledger.check('groq', { rpm: 10 });
tests/freecompute_cloud.test.js:538:test('ledger: blocks when RPM exceeded', () => {
tests/freecompute_cloud.test.js:539:  const ledger = new QuotaLedger({ disabled: true });
tests/freecompute_cloud.test.js:541:    ledger.record('test', { tokensIn: 10 });
tests/freecompute_cloud.test.js:543:  const check = ledger.check('test', { rpm: 5 });
tests/freecompute_cloud.test.js:548:test('ledger: blocks when RPD exceeded', () => {
tests/freecompute_cloud.test.js:549:  const ledger = new QuotaLedger({ disabled: true });
tests/freecompute_cloud.test.js:551:    ledger.record('test', { tokensIn: 10 });
tests/freecompute_cloud.test.js:553:  const check = ledger.check('test', { rpd: 3 });
tests/freecompute_cloud.test.js:558:test('ledger: blocks when TPM exceeded', () => {
tests/freecompute_cloud.test.js:559:  const ledger = new QuotaLedger({ disabled: true });
tests/freecompute_cloud.test.js:560:  ledger.record('test', { tokensIn: 50000, tokensOut: 50001 });
tests/freecompute_cloud.test.js:561:  const check = ledger.check('test', { tpm: 100000 });
tests/freecompute_cloud.test.js:566:test('ledger: snapshot returns all providers', () => {
tests/freecompute_cloud.test.js:567:  const ledger = new QuotaLedger({ disabled: true });
tests/freecompute_cloud.test.js:568:  ledger.record('a', { tokensIn: 1 });
tests/freecompute_cloud.test.js:569:  ledger.record('b', { tokensIn: 2 });
tests/freecompute_cloud.test.js:570:  const snap = ledger.snapshot();
tests/freecompute_cloud.test.js:577:test('ledger: reset clears provider counters', () => {
tests/freecompute_cloud.test.js:578:  const ledger = new QuotaLedger({ disabled: true });
tests/freecompute_cloud.test.js:579:  ledger.record('test', { tokensIn: 100 });
tests/freecompute_cloud.test.js:580:  ledger.resetProvider('test');
tests/freecompute_cloud.test.js:581:  const check = ledger.check('test', { rpm: 1 });
tests/freecompute_cloud.test.js:586:test('ledger: disk persistence (write)', () => {
tests/freecompute_cloud.test.js:587:  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fc-ledger-'));
tests/freecompute_cloud.test.js:589:    const ledger = new QuotaLedger({ ledgerPath: tmpDir });
tests/freecompute_cloud.test.js:590:    ledger.record('test', { tokensIn: 100, tokensOut: 50 });
workspace/scripts/nightly_build.sh:177:        log "Running narrative distillation (OPENCLAW_NARRATIVE_DISTILL=1)"
workspace/scripts/nightly_build.sh:178:        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
workspace/scripts/nightly_build.sh:179:            log "Narrative distillation complete"
workspace/scripts/nightly_build.sh:181:            log "⚠️ Narrative distillation failed"
workspace/scripts/narrative_distill.py:118:def _narrative_distill_enabled() -> bool:
workspace/scripts/narrative_distill.py:123:def distill_episodes(episodes, max_items=50):
workspace/scripts/narrative_distill.py:144:    distilled: List[Dict[str, Any]] = []
workspace/scripts/narrative_distill.py:154:        distilled.append(
workspace/scripts/narrative_distill.py:165:    distilled.sort(
workspace/scripts/narrative_distill.py:172:    return distilled[: max(1, int(max_items))]
workspace/scripts/narrative_distill.py:195:    if not _narrative_distill_enabled():
workspace/scripts/narrative_distill.py:294:__all__ = ["distill_episodes", "read_episodic_events", "write_semantic_entries"]
workspace/CONSTITUTION.md:197:3. Update MEMORY.md with distilled learnings
workspace/tacti/README.md:94:All integrations check master + sub-feature flags.
workspace/scripts/team_chat.py:945:        witness_enabled=_truthy(os.environ.get("OPENCLAW_TEAMCHAT_WITNESS")),
workspace/scripts/verify_tacti_cr_novel_10.sh:42:  workspace/tacti_cr/prefetch.py \
workspace/scripts/verify_teamchat_witness.sh:6:python3 "$REPO_ROOT/workspace/teamchat/witness_verify.py" --repo-root "$REPO_ROOT" "$@"
workspace/tacti_cr/prefetch.py:3:Canonical source is workspace/tacti/prefetch.py.
workspace/tacti_cr/prefetch.py:10:_src = _shim_file.parents[1] / "tacti" / "prefetch.py"
workspace/TWENTY_EVOLUTIONS.md:86:**Why:** The roadmap lists this as a "dream feature." It's actually the missing input signal. Without tone data, relationship health is a guess. With it, attunement scoring becomes real.
workspace/tacti/__init__.py:25:from .prefetch import PrefetchCache, predict_topics, prefetch_context
workspace/tacti/__init__.py:67:    "prefetch_context",
workspace/scripts/audit_commit_hook.py:14:DEFAULT_WITNESS_LEDGER_PATH = WORKSPACE_ROOT / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/scripts/audit_commit_hook.py:17:    from witness_ledger import commit as witness_commit
workspace/scripts/audit_commit_hook.py:19:    witness_commit = None
workspace/scripts/audit_commit_hook.py:36:def _commit_witness_entry(audit_entry: dict, audit_log: Path) -> tuple[bool, str]:
workspace/scripts/audit_commit_hook.py:38:        return True, "witness_disabled"
workspace/scripts/audit_commit_hook.py:39:    if not callable(witness_commit):
workspace/scripts/audit_commit_hook.py:40:        return False, "witness_unavailable"
workspace/scripts/audit_commit_hook.py:41:    ledger_path = Path(
workspace/scripts/audit_commit_hook.py:54:    witness_commit(record=record, ledger_path=str(ledger_path))
workspace/scripts/audit_commit_hook.py:136:        witness_ok, witness_reason = _commit_witness_entry(audit_entry, audit_log)
workspace/scripts/audit_commit_hook.py:138:        witness_ok, witness_reason = False, f"witness_error: {e}"
workspace/scripts/audit_commit_hook.py:139:    if not witness_ok:
workspace/scripts/audit_commit_hook.py:143:            print(f"❌ witness ledger commit failed (strict): {witness_reason}")
workspace/scripts/audit_commit_hook.py:145:            print(f"⚠️ witness ledger commit skipped: {witness_reason}")
workspace/research/WIM_HOF_AI_ENHANCEMENTS_BRIEF_2026-02-18.md:31:- Baseline current app telemetry and interaction points.
workspace/research/WIM_HOF_AI_ENHANCEMENTS_BRIEF_2026-02-18.md:57:- Convert this brief into a technical implementation spec with data schema and feature flags.
workspace/audit/tacti_cr_event_contract_20260219T130107Z.md:34:- `workspace/tacti_cr/prefetch.py`: emits prefetch/hit-rate events.
workspace/audit/tacti_cr_event_contract_20260219T130107Z.md:58: M workspace/tacti_cr/prefetch.py
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:75:  - `workspace/scripts/narrative_distill.py`
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:76:  - `workspace/scripts/run_narrative_distill.py`
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:80:  - `workspace/scripts/witness_ledger.py`
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:82:  - `tests_unittest/test_narrative_distill.py`
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:83:  - `tests_unittest/test_active_inference_counterfactual.py`
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:86:  - `tests_unittest/test_witness_ledger.py`
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:95:  - Added `replay_counterfactuals(event, k=3, rng_seed=None)` with deterministic phantom updates and no external calls.
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:98:  - Added witness chain verification utility (`verify_chain`) and tamper detection coverage.
workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:103:python3 -m unittest -q tests_unittest/test_narrative_distill.py tests_unittest/test_active_inference_counterfactual.py tests_unittest/test_semantic_immune_epitopes.py tests_unittest/test_oscillatory_attention.py tests_unittest/test_witness_ledger.py tests_unittest/test_evolution_scaffolds.py
workspace/tacti/novel10_contract.py:14:    "prefetch": ["tacti_cr.prefetch.predicted_topics", "tacti_cr.prefetch.cache_put"],
workspace/tacti/novel10_contract.py:20:FEATURE_FLAGS = {
workspace/tacti/novel10_contract.py:44:__all__ = ["EXPECTED_EVENTS", "FEATURE_FLAGS", "required_for_fixture"]
workspace/scripts/run_novel10_fixture.py:27:from tacti_cr.novel10_contract import FEATURE_FLAGS
workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/scripts/run_novel10_fixture.py:63:def _enable_all_flags() -> None:
workspace/scripts/run_novel10_fixture.py:64:    for key in FEATURE_FLAGS:
workspace/scripts/run_novel10_fixture.py:138:        prefetch_context(token_stream, query_fn, repo_root=temp_root)
workspace/scripts/run_novel10_fixture.py:196:    if args.enable_all:
workspace/scripts/run_novel10_fixture.py:197:        _enable_all_flags()
workspace/audit/PR_BODY_teamchat_witness_verify_20260220.md:3:- Summary: Team Chat witness verifier + docs + canonical hash versioning.
workspace/audit/PR_BODY_teamchat_witness_verify_20260220.md:4:- Evidence: `workspace/audit/teamchat_witness_verify_20260220T113745Z.md`
workspace/audit/PR_BODY_teamchat_witness_verify_20260220.md:9:- `bash workspace/scripts/verify_teamchat_witness.sh --session verify_teamchat_witness_fixture`
workspace/tacti/config.py:80:FEATURE_FLAGS = {
workspace/tacti/config.py:87:    "prefetch": "TACTI_CR_PREFETCH",
workspace/tacti/config.py:146:    master_env = FEATURE_FLAGS["master"]
workspace/tacti/config.py:153:    flag_name = FEATURE_FLAGS.get(feature_name, feature_name)
workspace/tacti/config.py:154:    if flag_name in FEATURE_FLAGS.values():
workspace/tacti/config.py:159:        return _parse_bool(policy_flags.get(feature_name, False))
workspace/scripts/policy_router.py:45:WITNESS_LEDGER_PATH = BASE_DIR / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/scripts/run_narrative_distill.py:10:from narrative_distill import distill_episodes, read_episodic_events, write_semantic_entries
workspace/scripts/run_narrative_distill.py:52:    entries = distill_episodes(episodes, max_items=args.max_items)
workspace/scripts/run_narrative_distill.py:57:    audit_path = audit_dir / f"narrative_distill_{_utc_stamp()}.md"
workspace/audit/stash_integration_20260222.md:63:    feat(hivemind): enable guarded counterfactual replay in dynamics pipeline
workspace/audit/stash_integration_20260222.md:101:    feat(cron): run narrative distillation before daily brief
workspace/audit/stash_integration_20260222.md:134:    feat(kb): enable PrefetchCache for context prefetch
workspace/audit/stash_integration_20260222.md:136: tests_unittest/test_kb_prefetch_cache.py        | 47 +++++++++++++++++++
workspace/audit/stash_integration_20260222.md:145:    feat(gov): chain governance log writes via witness ledger
workspace/audit/stash_integration_20260222.md:147: tests_unittest/test_audit_commit_hook_witness.py | 63 ++++++++++++++++++++++++
workspace/audit/stash_integration_20260222.md:190: workspace/tacti_cr/prefetch.py                     |   6 +-
workspace/audit/stash_integration_20260222.md:225: workspace/tacti_cr/prefetch.py                     |  11 +-
workspace/audit/stash_integration_20260222.md:464:⚠️ witness ledger commit skipped: witness_error: boom
workspace/audit/stash_integration_20260222.md:472:❌ witness ledger commit failed (strict): witness_error: boom
workspace/audit/stash_integration_20260222.md:741:⚠️ witness ledger commit skipped: witness_error: boom
workspace/audit/stash_integration_20260222.md:749:❌ witness ledger commit failed (strict): witness_error: boom
workspace/audit/stash_integration_20260222.md:1000:⚠️ witness ledger commit skipped: witness_error: boom
workspace/audit/stash_integration_20260222.md:1008:❌ witness ledger commit failed (strict): witness_error: boom
workspace/scripts/witness_ledger.py:45:def commit(record: dict, ledger_path: str, timestamp_utc: str | None = None) -> dict:
workspace/scripts/witness_ledger.py:46:    path = Path(ledger_path)
workspace/scripts/witness_ledger.py:75:def verify_chain(ledger_path: str) -> dict:
workspace/scripts/witness_ledger.py:76:    path = Path(ledger_path)
workspace/AGENTS.md:36:- This is your curated memory — the distilled essence, not raw logs
workspace/AGENTS.md:203:3. Update `MEMORY.md` with distilled learnings
workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import PrefetchCache, predict_topics
workspace/knowledge_base/kb.py:34:def _get_prefetch_cache(repo_root: Path):
workspace/knowledge_base/kb.py:47:def _prefetch_with_cache(query: str, query_fn, *, repo_root: Path):
workspace/knowledge_base/kb.py:48:    cache = _get_prefetch_cache(repo_root)
workspace/knowledge_base/kb.py:67:        cache.record_prefetch("|".join(topics), docs)
workspace/knowledge_base/kb.py:81:    _prefetch_with_cache(
workspace/policy/expression_manifest.json:23:      "feature_name": "prefetch",
workspace/fixtures/novel10/memory/2026-02-18.md:6:- 16:45 prefetch topic rehearsal with whales and routing context.
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:4:- Branch: codex/feature/teamchat-witness-docs-and-verify-20260220
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:8:- Added deterministic Team Chat witness verification with no default side effects.
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:9:- Reused existing witness chain verification from `workspace/scripts/witness_ledger.py` (`verify_chain`) and layered Team Chat consistency checks on top.
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:11:  - New witness entries use `message_hash_version=teamchat-msg-sha256-v2` and:
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:16:- Team Chat witness ledger path for Team Chat is runtime-only and ignored:
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:17:  - `workspace/state_runtime/teamchat/witness_ledger.jsonl`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:23:- `workspace/teamchat/witness_verify.py`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:25:- `workspace/scripts/verify_teamchat_witness.sh`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:26:- `tests_unittest/test_teamchat_witness_verify.py`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:32:- `python3 -m unittest -q tests_unittest.test_teamchat_witness_verify tests_unittest.test_team_chat_witness tests_unittest.test_team_chat_basic`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:40:- `bash workspace/scripts/verify_teamchat_witness.sh --session verify_teamchat_witness_fixture`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:41:  - `PASS session=verify_teamchat_witness_fixture witnessed_events=2 head_hash=86c931c0fb2320cdfdb59e0756511f562a218cb93a2f763e01408ce45cdbd0bd`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:45:1. Run Team Chat with witness enabled:
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:47:2. Verify witness provenance:
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:48:   - `bash workspace/scripts/verify_teamchat_witness.sh --session demo`
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:49:3. Optional explicit ledger override:
workspace/audit/teamchat_witness_verify_20260220T113745Z.md:50:   - `bash workspace/scripts/verify_teamchat_witness.sh --session demo --ledger workspace/state_runtime/teamchat/witness_ledger.jsonl`
workspace/audit/PR_BODY_evolution_ideas_1_10_20260220.md:8:- Adds/extends deterministic tests for each subsystem contract (dream pruning, router proprioception arousal input, trails valence, temporal surprise gate, peer annealing, narrative distill idempotency, active inference counterfactual replay, semantic immune epitopes, oscillatory attention gating, witness tamper detection).
workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:41:tacti_cr.prefetch.cache_put,1
workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:42:tacti_cr.prefetch.hit_rate,1
workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:43:tacti_cr.prefetch.predicted_topics,1
workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:44:tacti_cr.prefetch.recorded,1
workspace/audit/tacti_mainflow_wiring_20260219T051649Z.md:18:- `workspace/hivemind/hivemind/flags.py`
workspace/docs/briefs/BRIEF-2026-02-13-system2-federation-observability.md:48:- Implement envelope encode/decode, signature interface, and a transport adapter behind flags.
workspace/docs/briefs/BRIEF-2026-02-13-system2-federation-observability.md:50:- Implement append-only event log sink interface behind flags.
workspace/docs/briefs/BRIEF-2026-02-13-system2-federation-observability.md:228:- Strict default-off gating with explicit flags.
workspace/audit/repo_audit_regression_gate_dali_20260220T032340Z.md:104:core/system2/inference/quota_ledger.js
workspace/handoffs/audit_2026-02-08.md:9:- **Data stores**: `itc/` JSONL, `market/` candles, `sim/` state + trades, `economics/` ledger.
workspace/docs/briefs/BRIEF-2026-02-18-001_TACTI_CR_Implementation.md:112:- Deliberative planner: search, synthesis, counterfactual (slow)
workspace/docs/briefs/BRIEF-2026-02-18-001_TACTI_CR_Implementation.md:175:This transforms collapse from accident to design feature.
workspace/docs/briefs/BRIEF-2026-02-18-001_TACTI_CR_Implementation.md:223:    """Slow: search, synthesis, counterfactual"""
workspace/automation/cron_jobs.json:29:      "command": "⏰ **Daily Briefing Time**\nIt is 7 AM. Before briefing content generation, run this best-effort pre-step and continue even on failure:\nOPENCLAW_NARRATIVE_DISTILL=1 python3 workspace/scripts/run_narrative_distill.py >> reports/automation/narrative_distill.log 2>&1 || echo \"[WARN] narrative distill failed\" >> reports/automation/narrative_distill.log\n\nThen generate the daily briefing for Heath with:\n1. Literature Quote (run node scripts/get_daily_quote.js)\n2. Therapeutic Technique (run python3 scripts/daily_technique.py --format briefing)\n3. Behavioral Prime paragraph (derived from the selected technique)\n4. Apple Reminders (run remindctl today)\n5. Calendar Events (run workspace/scripts/calendar.sh today)\n6. News Article (web_search)\n7. Agent Goal\n8. Time Management Tip (run python3 workspace/time_management/time_management.py tip)\n9. Self-Care Suggestion (run python3 workspace/time_management/time_management.py self_care)\n\nFormat as a clean, inspiring briefing. Include a section to track which suggestions Heath does/dismissed so we can learn."
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:54:./tests_unittest/test_tacti_cr_novel_10.py:67:                json.dumps({"features": [{"feature_name": "prefetch", "activation_conditions": {"valence_min": -0.1}, "suppression_conditions": {}, "priority": 1}]}, indent=2),
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:91:./workspace/state/tacti_cr/events.jsonl:1:{"ts": 1771506277399, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:93:./workspace/state/tacti_cr/events.jsonl:4:{"ts": 1771535085092, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:95:./workspace/state/tacti_cr/events.jsonl:7:{"ts": 1771535094165, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:97:./workspace/state/tacti_cr/events.jsonl:10:{"ts": 1771535104622, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:99:./workspace/state/tacti_cr/events.jsonl:13:{"ts": 1771535114296, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:101:./workspace/state/tacti_cr/events.jsonl:16:{"ts": 1771535122066, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:103:./workspace/state/tacti_cr/events.jsonl:19:{"ts": 1771535125674, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:105:./workspace/state/tacti_cr/events.jsonl:22:{"ts": 1771535797828, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:107:./workspace/state/tacti_cr/events.jsonl:25:{"ts": 1771543883143, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:109:./workspace/state/tacti_cr/events.jsonl:28:{"ts": 1771543886658, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:111:./workspace/state/tacti_cr/events.jsonl:31:{"ts": 1771543900227, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:113:./workspace/state/tacti_cr/events.jsonl:34:{"ts": 1771543903469, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:203:$ rg -n "audit|workspace/audit|hash|sha256|witness" -S .
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:332:./tests_unittest/test_tacti_cr_novel_10.py:67:                json.dumps({"features": [{"feature_name": "prefetch", "activation_conditions": {"valence_min": -0.1}, "suppression_conditions": {}, "priority": 1}]}, indent=2),
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:480:$ rg -n "audit|workspace/audit|hash|sha256|witness" -S .
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:612:- `workspace/scripts/narrative_distill.py`
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:613:- `workspace/scripts/run_narrative_distill.py`
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:615:- `tests_unittest/test_narrative_distill.py`
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:618:- Added deterministic distiller: `distill_episodes(episodes, max_items=50)`.
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:626:$ python3 -m unittest -q tests_unittest/test_narrative_distill.py tests_unittest/test_tacti_cr_novel_10.py
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:636:- `workspace/scripts/witness_ledger.py`
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:638:- `tests_unittest/test_witness_ledger.py`
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:641:- Added append-only witness ledger with stable canonical JSON bytes and SHA-256 commitments.
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:644:- Router adds `witness_hash` in event detail and `result.meta` when enabled.
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:648:$ python3 -m unittest -q tests_unittest/test_witness_ledger.py tests_unittest/test_router_proprioception.py
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:704:2b36b3e feat(memory): add narrative distillation module and runner
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:705:4bd3530 feat(audit): add witness ledger hash-chain module and tests
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:713:| OPENCLAW_ROUTER_PROPRIOCEPTION | 0 | Attach rolling router telemetry in `result.meta.proprioception` |
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:714:| OPENCLAW_NARRATIVE_DISTILL | 0 | Enable nightly episodic→semantic distillation run |
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:715:| OPENCLAW_WITNESS_LEDGER | 0 | Enable append-only witness hash-chain commits for router decisions |
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:720:| OPENCLAW_COUNTERFACTUAL_REPLAY | 0 | Generate deterministic counterfactual routing alternatives |
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:726:- Witness ledger commit currently stores minimal routing summary record only; no cross-process lock is used.
workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:727:- Narrative distillation currently uses token Jaccard fallback and does not require embedding infrastructure.
workspace/MEMORY.md:3:This is the curated, long-term memory that persists across sessions. This file contains distilled insights, important decisions, and key information worth remembering long-term.
workspace/teamchat/witness_verify.py:29:        from witness_ledger import verify_chain  # type: ignore
workspace/teamchat/witness_verify.py:34:        from witness_ledger import verify_chain  # type: ignore
workspace/teamchat/witness_verify.py:42:    witnessed_events: int
workspace/teamchat/witness_verify.py:68:def default_ledger_path(repo_root: Path) -> Path:
workspace/teamchat/witness_verify.py:69:    return Path(repo_root) / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/teamchat/witness_verify.py:110:def verify_session_witness(session_path: Path, ledger_path: Path) -> VerificationResult:
workspace/teamchat/witness_verify.py:112:    ledger_path = Path(ledger_path)
workspace/teamchat/witness_verify.py:116:    if not ledger_path.exists():
workspace/teamchat/witness_verify.py:117:        return VerificationResult(False, session_id, 0, "", "ledger_missing", str(ledger_path))
workspace/teamchat/witness_verify.py:120:    chain = verify_chain(str(ledger_path))
workspace/teamchat/witness_verify.py:127:            "ledger_chain_invalid",
workspace/teamchat/witness_verify.py:133:        ledger_rows = _load_jsonl(ledger_path)
workspace/teamchat/witness_verify.py:140:    for row in ledger_rows:
workspace/teamchat/witness_verify.py:221:    parser = argparse.ArgumentParser(description="Verify Team Chat witness ledger integrity for a session")
workspace/teamchat/witness_verify.py:223:    parser.add_argument("--ledger", default="", help="Path to witness ledger JSONL")
workspace/teamchat/witness_verify.py:233:    ledger_path = Path(args.ledger).resolve() if str(args.ledger).strip() else default_ledger_path(repo_root)
workspace/teamchat/witness_verify.py:235:    result = verify_session_witness(session_path, ledger_path)
workspace/teamchat/witness_verify.py:238:            f"FAIL session={result.session_id} witnessed_events={result.witnessed_events} "
workspace/teamchat/witness_verify.py:243:        f"PASS session={result.session_id} witnessed_events={result.witnessed_events} "
workspace/teamchat/orchestrator.py:10:    from witness_ledger import commit as witness_commit
workspace/teamchat/orchestrator.py:12:    witness_commit = None
workspace/teamchat/orchestrator.py:23:        witness_enabled: bool = False,
workspace/teamchat/orchestrator.py:24:        witness_ledger_path: Path | None = None,
workspace/teamchat/orchestrator.py:29:        self.witness_enabled = bool(witness_enabled)
workspace/teamchat/orchestrator.py:30:        self.witness_ledger_path = Path(witness_ledger_path) if witness_ledger_path else (
workspace/teamchat/orchestrator.py:31:            self.session.repo_root / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/teamchat/orchestrator.py:59:    def _emit_witness(self, *, turn: int, agent: str, route: dict[str, Any], message_row: dict[str, Any]) -> None:
workspace/teamchat/orchestrator.py:60:        if not self.witness_enabled or not callable(witness_commit):
workspace/teamchat/orchestrator.py:76:        witness_commit(record=record, ledger_path=str(self.witness_ledger_path))
workspace/teamchat/orchestrator.py:102:            self._emit_witness(turn=self.session.turn, agent=agent, route=route, message_row=row)
workspace/audit/wirings_integration_20260222.md:11:command: rg -n "TODO: Forward to classification|ingestion_boundary|itc_classify|witness_ledger|PrefetchCache|prefetch_context|TACTI_CR_AROUSAL_OSC|OPENCLAW_COUNTERFACTUAL_REPLAY|OPENCLAW_ROUTER_PROPRIOCEPTION|run_narrative_distill|OPENCLAW_TRAIL_VALENCE|gap_analyzer" -S workspace scripts core
workspace/audit/wirings_integration_20260222.md:12:workspace/tacti/__init__.py:25:from .prefetch import PrefetchCache, predict_topics, prefetch_context
workspace/audit/wirings_integration_20260222.md:14:workspace/tacti/__init__.py:67:    "prefetch_context",
workspace/audit/wirings_integration_20260222.md:25:workspace/tacti/prefetch.py:16:class PrefetchCache:
workspace/audit/wirings_integration_20260222.md:26:workspace/tacti/prefetch.py:82:def prefetch_context(token_stream: str, query_fn, *, repo_root: Path | None = None) -> dict[str, Any]:
workspace/audit/wirings_integration_20260222.md:27:workspace/tacti/prefetch.py:85:    cache = PrefetchCache(repo_root=repo_root)
workspace/audit/wirings_integration_20260222.md:28:workspace/tacti/prefetch.py:96:__all__ = ["PrefetchCache", "predict_topics", "prefetch_context"]
workspace/audit/wirings_integration_20260222.md:35:workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/wirings_integration_20260222.md:36:workspace/knowledge_base/kb.py:27:    prefetch_context = None
workspace/audit/wirings_integration_20260222.md:37:workspace/knowledge_base/kb.py:37:    if callable(prefetch_context):
workspace/audit/wirings_integration_20260222.md:38:workspace/knowledge_base/kb.py:39:            prefetch_context(
workspace/audit/wirings_integration_20260222.md:51:workspace/teamchat/orchestrator.py:10:    from witness_ledger import commit as witness_commit
workspace/audit/wirings_integration_20260222.md:52:workspace/teamchat/orchestrator.py:24:        witness_ledger_path: Path | None = None,
workspace/audit/wirings_integration_20260222.md:53:workspace/teamchat/orchestrator.py:30:        self.witness_ledger_path = Path(witness_ledger_path) if witness_ledger_path else (
workspace/audit/wirings_integration_20260222.md:54:workspace/teamchat/orchestrator.py:31:            self.session.repo_root / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/audit/wirings_integration_20260222.md:55:workspace/teamchat/orchestrator.py:76:        witness_commit(record=record, ledger_path=str(self.witness_ledger_path))
workspace/audit/wirings_integration_20260222.md:56:workspace/scripts/policy_router.py:45:WITNESS_LEDGER_PATH = BASE_DIR / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/audit/wirings_integration_20260222.md:61:workspace/teamchat/witness_verify.py:29:        from witness_ledger import verify_chain  # type: ignore
workspace/audit/wirings_integration_20260222.md:62:workspace/teamchat/witness_verify.py:34:        from witness_ledger import verify_chain  # type: ignore
workspace/audit/wirings_integration_20260222.md:63:workspace/teamchat/witness_verify.py:69:    return Path(repo_root) / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/audit/wirings_integration_20260222.md:93:workspace/scripts/nightly_build.sh:178:        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
workspace/audit/wirings_integration_20260222.md:94:workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/audit/wirings_integration_20260222.md:95:workspace/scripts/run_novel10_fixture.py:138:        prefetch_context(token_stream, query_fn, repo_root=temp_root)
workspace/audit/wirings_integration_20260222.md:99:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:76:  - `workspace/scripts/run_narrative_distill.py`
workspace/audit/wirings_integration_20260222.md:100:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:80:  - `workspace/scripts/witness_ledger.py`
workspace/audit/wirings_integration_20260222.md:101:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:86:  - `tests_unittest/test_witness_ledger.py`
workspace/audit/wirings_integration_20260222.md:103:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:103:python3 -m unittest -q tests_unittest/test_narrative_distill.py tests_unittest/test_active_inference_counterfactual.py tests_unittest/test_semantic_immune_epitopes.py tests_unittest/test_oscillatory_attention.py tests_unittest/test_witness_ledger.py tests_unittest/test_evolution_scaffolds.py
workspace/audit/wirings_integration_20260222.md:105:workspace/audit/teamchat_witness_verify_20260220T113745Z.md:9:- Reused existing witness chain verification from `workspace/scripts/witness_ledger.py` (`verify_chain`) and layered Team Chat consistency checks on top.
workspace/audit/wirings_integration_20260222.md:106:workspace/audit/teamchat_witness_verify_20260220T113745Z.md:17:  - `workspace/state_runtime/teamchat/witness_ledger.jsonl`
workspace/audit/wirings_integration_20260222.md:107:workspace/audit/teamchat_witness_verify_20260220T113745Z.md:50:   - `bash workspace/scripts/verify_teamchat_witness.sh --session demo --ledger workspace/state_runtime/teamchat/witness_ledger.jsonl`
workspace/audit/wirings_integration_20260222.md:147:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:613:- `workspace/scripts/run_narrative_distill.py`
workspace/audit/wirings_integration_20260222.md:148:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:636:- `workspace/scripts/witness_ledger.py`
workspace/audit/wirings_integration_20260222.md:149:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:638:- `tests_unittest/test_witness_ledger.py`
workspace/audit/wirings_integration_20260222.md:150:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:648:$ python3 -m unittest -q tests_unittest/test_witness_ledger.py tests_unittest/test_router_proprioception.py
workspace/audit/wirings_integration_20260222.md:153:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:713:| OPENCLAW_ROUTER_PROPRIOCEPTION | 0 | Attach rolling router telemetry in `result.meta.proprioception` |
workspace/audit/wirings_integration_20260222.md:155:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:720:| OPENCLAW_COUNTERFACTUAL_REPLAY | 0 | Generate deterministic counterfactual routing alternatives |
workspace/audit/wirings_integration_20260222.md:160:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:930:./tests_unittest/test_witness_ledger.py:26:            "providers": {"mock_provider": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "mock-model", "maxInputChars": 8000}]}},
workspace/audit/wirings_integration_20260222.md:161:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:931:./tests_unittest/test_witness_ledger.py:27:            "routing": {"free_order": ["mock_provider"], "intents": {"coding": {"order": ["free"], "allowPaid": False}}},
workspace/audit/wirings_integration_20260222.md:162:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:932:./tests_unittest/test_witness_ledger.py:38:            rec1 = {"intent": "coding", "provider": "local", "ok": True}
workspace/audit/wirings_integration_20260222.md:163:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:933:./tests_unittest/test_witness_ledger.py:39:            rec2 = {"intent": "coding", "provider": "remote", "ok": False}
workspace/audit/wirings_integration_20260222.md:164:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:934:./tests_unittest/test_witness_ledger.py:62:            commit({"intent": "coding", "provider": "local", "ok": True}, str(ledger), timestamp_utc="2026-02-20T00:00:00Z")
workspace/audit/wirings_integration_20260222.md:165:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:935:./tests_unittest/test_witness_ledger.py:63:            commit({"intent": "coding", "provider": "remote", "ok": False}, str(ledger), timestamp_utc="2026-02-20T00:00:01Z")
workspace/audit/wirings_integration_20260222.md:166:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:936:./tests_unittest/test_witness_ledger.py:65:            rows[0]["record"]["provider"] = "tampered-provider"
workspace/audit/wirings_integration_20260222.md:167:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:937:./tests_unittest/test_witness_ledger.py:87:                        handlers={"mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
workspace/audit/wirings_integration_20260222.md:169:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3569:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:930:./tests_unittest/test_witness_ledger.py:26:            "providers": {"mock_provider": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "mock-model", "maxInputChars": 8000}]}},
workspace/audit/wirings_integration_20260222.md:170:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3570:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:931:./tests_unittest/test_witness_ledger.py:27:            "routing": {"free_order": ["mock_provider"], "intents": {"coding": {"order": ["free"], "allowPaid": False}}},
workspace/audit/wirings_integration_20260222.md:171:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3571:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:932:./tests_unittest/test_witness_ledger.py:38:            rec1 = {"intent": "coding", "provider": "local", "ok": True}
workspace/audit/wirings_integration_20260222.md:172:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3572:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:933:./tests_unittest/test_witness_ledger.py:39:            rec2 = {"intent": "coding", "provider": "remote", "ok": False}
workspace/audit/wirings_integration_20260222.md:173:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3573:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:934:./tests_unittest/test_witness_ledger.py:62:            commit({"intent": "coding", "provider": "local", "ok": True}, str(ledger), timestamp_utc="2026-02-20T00:00:00Z")
workspace/audit/wirings_integration_20260222.md:174:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3574:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:935:./tests_unittest/test_witness_ledger.py:63:            commit({"intent": "coding", "provider": "remote", "ok": False}, str(ledger), timestamp_utc="2026-02-20T00:00:01Z")
workspace/audit/wirings_integration_20260222.md:175:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3575:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:936:./tests_unittest/test_witness_ledger.py:65:            rows[0]["record"]["provider"] = "tampered-provider"
workspace/audit/wirings_integration_20260222.md:176:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3576:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:937:./tests_unittest/test_witness_ledger.py:87:                        handlers={"mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
workspace/audit/wirings_integration_20260222.md:183:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6044:workspace/scripts/witness_ledger.py:10:def canonicalize(obj) -> bytes:
workspace/audit/wirings_integration_20260222.md:184:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6045:workspace/scripts/witness_ledger.py:42:    return hashlib.sha256(canonicalize(base)).hexdigest()
workspace/audit/wirings_integration_20260222.md:185:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6046:workspace/scripts/witness_ledger.py:110:__all__ = ["canonicalize", "commit", "verify_chain"]
workspace/audit/wirings_integration_20260222.md:192:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6567:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6044:workspace/scripts/witness_ledger.py:10:def canonicalize(obj) -> bytes:
workspace/audit/wirings_integration_20260222.md:193:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6568:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6045:workspace/scripts/witness_ledger.py:42:    return hashlib.sha256(canonicalize(base)).hexdigest()
workspace/audit/wirings_integration_20260222.md:194:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6569:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6046:workspace/scripts/witness_ledger.py:110:__all__ = ["canonicalize", "commit", "verify_chain"]
workspace/audit/wirings_integration_20260222.md:199:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7366:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/wirings_integration_20260222.md:227:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7598:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/wirings_integration_20260222.md:228:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7599:workspace/scripts/run_narrative_distill.py:75:    summary = {
workspace/audit/wirings_integration_20260222.md:229:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7600:workspace/scripts/run_narrative_distill.py:84:    print(json.dumps(summary, ensure_ascii=True))
workspace/audit/wirings_integration_20260222.md:233:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8151:./tests_unittest/test_tacti_cr_novel_10.py:24:from tacti_cr.prefetch import PrefetchCache, predict_topics
workspace/audit/wirings_integration_20260222.md:234:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8172:./workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/wirings_integration_20260222.md:235:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8215:./workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/audit/wirings_integration_20260222.md:236:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:237:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8640:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8151:./tests_unittest/test_tacti_cr_novel_10.py:24:from tacti_cr.prefetch import PrefetchCache, predict_topics
workspace/audit/wirings_integration_20260222.md:238:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8661:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8172:./workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/wirings_integration_20260222.md:239:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8704:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8215:./workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/audit/wirings_integration_20260222.md:240:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8721:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:241:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9047:tests_unittest/test_tacti_cr_novel_10.py:24:from tacti_cr.prefetch import PrefetchCache, predict_topics
workspace/audit/wirings_integration_20260222.md:242:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9057:workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/wirings_integration_20260222.md:243:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9075:workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/audit/wirings_integration_20260222.md:244:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9078:workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:258:$ rg -n "def commit\(|witness_ledger|governance_log|audit" -S workspace/scripts workspace/governance
workspace/audit/wirings_integration_20260222.md:294:workspace/scripts/witness_ledger.py:45:def commit(record: dict, ledger_path: str, timestamp_utc: str | None = None) -> dict:
workspace/audit/wirings_integration_20260222.md:305:workspace/scripts/run_narrative_distill.py:55:    audit_dir = root / "workspace" / "audit"
workspace/audit/wirings_integration_20260222.md:306:workspace/scripts/run_narrative_distill.py:56:    audit_dir.mkdir(parents=True, exist_ok=True)
workspace/audit/wirings_integration_20260222.md:307:workspace/scripts/run_narrative_distill.py:57:    audit_path = audit_dir / f"narrative_distill_{_utc_stamp()}.md"
workspace/audit/wirings_integration_20260222.md:308:workspace/scripts/run_narrative_distill.py:58:    audit_path.write_text(
workspace/audit/wirings_integration_20260222.md:309:workspace/scripts/run_narrative_distill.py:82:        "audit_path": str(audit_path),
workspace/audit/wirings_integration_20260222.md:310:workspace/scripts/policy_router.py:45:WITNESS_LEDGER_PATH = BASE_DIR / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
workspace/audit/wirings_integration_20260222.md:312:$ rg -n "PrefetchCache|prefetch_context|cmd_query|query" -S workspace/knowledge_base/kb.py workspace/tacti workspace/tacti_cr
workspace/audit/wirings_integration_20260222.md:313:workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/wirings_integration_20260222.md:314:workspace/knowledge_base/kb.py:27:    prefetch_context = None
workspace/audit/wirings_integration_20260222.md:318:workspace/knowledge_base/kb.py:37:    if callable(prefetch_context):
workspace/audit/wirings_integration_20260222.md:319:workspace/knowledge_base/kb.py:39:            prefetch_context(
workspace/audit/wirings_integration_20260222.md:333:workspace/tacti/__init__.py:25:from .prefetch import PrefetchCache, predict_topics, prefetch_context
workspace/audit/wirings_integration_20260222.md:336:workspace/tacti/__init__.py:67:    "prefetch_context",
workspace/audit/wirings_integration_20260222.md:344:workspace/tacti/prefetch.py:16:class PrefetchCache:
workspace/audit/wirings_integration_20260222.md:345:workspace/tacti/prefetch.py:82:def prefetch_context(token_stream: str, query_fn, *, repo_root: Path | None = None) -> dict[str, Any]:
workspace/audit/wirings_integration_20260222.md:346:workspace/tacti/prefetch.py:85:    cache = PrefetchCache(repo_root=repo_root)
workspace/audit/wirings_integration_20260222.md:347:workspace/tacti/prefetch.py:90:        docs.extend(query_fn(topic))
workspace/audit/wirings_integration_20260222.md:348:workspace/tacti/prefetch.py:96:__all__ = ["PrefetchCache", "predict_topics", "prefetch_context"]
workspace/audit/wirings_integration_20260222.md:416:$ rg -n "daily brief|daily_brief|run_narrative_distill|cron|7 AM|7AM" -S workspace/scripts workspace
workspace/audit/wirings_integration_20260222.md:441:workspace/scripts/nightly_build.sh:178:        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
workspace/audit/wirings_integration_20260222.md:469:workspace/scripts/nightly_build.sh:178:        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
workspace/audit/wirings_integration_20260222.md:472:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:76:  - `workspace/scripts/run_narrative_distill.py`
workspace/audit/wirings_integration_20260222.md:494:workspace/audit/wirings_integration_20260222.md:11:command: rg -n "TODO: Forward to classification|ingestion_boundary|itc_classify|witness_ledger|PrefetchCache|prefetch_context|TACTI_CR_AROUSAL_OSC|OPENCLAW_COUNTERFACTUAL_REPLAY|OPENCLAW_ROUTER_PROPRIOCEPTION|run_narrative_distill|OPENCLAW_TRAIL_VALENCE|gap_analyzer" -S workspace scripts core
workspace/audit/wirings_integration_20260222.md:495:workspace/audit/wirings_integration_20260222.md:93:workspace/scripts/nightly_build.sh:178:        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
workspace/audit/wirings_integration_20260222.md:496:workspace/audit/wirings_integration_20260222.md:99:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:76:  - `workspace/scripts/run_narrative_distill.py`
workspace/audit/wirings_integration_20260222.md:497:workspace/audit/wirings_integration_20260222.md:147:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:613:- `workspace/scripts/run_narrative_distill.py`
workspace/audit/wirings_integration_20260222.md:498:workspace/audit/wirings_integration_20260222.md:199:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7366:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/wirings_integration_20260222.md:499:workspace/audit/wirings_integration_20260222.md:227:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7598:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/wirings_integration_20260222.md:500:workspace/audit/wirings_integration_20260222.md:228:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7599:workspace/scripts/run_narrative_distill.py:75:    summary = {
workspace/audit/wirings_integration_20260222.md:501:workspace/audit/wirings_integration_20260222.md:229:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7600:workspace/scripts/run_narrative_distill.py:84:    print(json.dumps(summary, ensure_ascii=True))
workspace/audit/wirings_integration_20260222.md:502:workspace/audit/wirings_integration_20260222.md:236:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:503:workspace/audit/wirings_integration_20260222.md:240:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8721:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:504:workspace/audit/wirings_integration_20260222.md:244:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9078:workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:505:workspace/audit/wirings_integration_20260222.md:305:workspace/scripts/run_narrative_distill.py:55:    audit_dir = root / "workspace" / "audit"
workspace/audit/wirings_integration_20260222.md:506:workspace/audit/wirings_integration_20260222.md:306:workspace/scripts/run_narrative_distill.py:56:    audit_dir.mkdir(parents=True, exist_ok=True)
workspace/audit/wirings_integration_20260222.md:507:workspace/audit/wirings_integration_20260222.md:307:workspace/scripts/run_narrative_distill.py:57:    audit_path = audit_dir / f"narrative_distill_{_utc_stamp()}.md"
workspace/audit/wirings_integration_20260222.md:508:workspace/audit/wirings_integration_20260222.md:308:workspace/scripts/run_narrative_distill.py:58:    audit_path.write_text(
workspace/audit/wirings_integration_20260222.md:509:workspace/audit/wirings_integration_20260222.md:309:workspace/scripts/run_narrative_distill.py:82:        "audit_path": str(audit_path),
workspace/audit/wirings_integration_20260222.md:510:workspace/audit/wirings_integration_20260222.md:416:$ rg -n "daily brief|daily_brief|run_narrative_distill|cron|7 AM|7AM" -S workspace/scripts workspace
workspace/audit/wirings_integration_20260222.md:535:workspace/audit/wirings_integration_20260222.md:441:workspace/scripts/nightly_build.sh:178:        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
workspace/audit/wirings_integration_20260222.md:563:workspace/audit/wirings_integration_20260222.md:469:workspace/scripts/nightly_build.sh:178:        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
workspace/audit/wirings_integration_20260222.md:566:workspace/audit/wirings_integration_20260222.md:472:workspace/audit/evolution_ideas_1_10_20260220T063914Z.md:76:  - `workspace/scripts/run_narrative_distill.py`
workspace/audit/wirings_integration_20260222.md:592:workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:613:- `workspace/scripts/run_narrative_distill.py`
workspace/audit/wirings_integration_20260222.md:800:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7366:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/wirings_integration_20260222.md:802:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7598:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/wirings_integration_20260222.md:803:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7599:workspace/scripts/run_narrative_distill.py:75:    summary = {
workspace/audit/wirings_integration_20260222.md:804:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7600:workspace/scripts/run_narrative_distill.py:84:    print(json.dumps(summary, ensure_ascii=True))
workspace/audit/wirings_integration_20260222.md:809:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:810:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8721:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:811:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9078:workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/wirings_integration_20260222.md:856:workspace/hivemind/hivemind/dynamics_pipeline.py:43:        self.enable_physarum = _env_enabled("ENABLE_PHYSARUM_ROUTER")
workspace/audit/wirings_integration_20260222.md:857:workspace/hivemind/hivemind/dynamics_pipeline.py:44:        self.enable_trails = _env_enabled("ENABLE_TRAIL_MEMORY")
workspace/audit/wirings_integration_20260222.md:861:workspace/hivemind/hivemind/dynamics_pipeline.py:51:        if not self.enable_trails:
workspace/audit/wirings_integration_20260222.md:864:workspace/hivemind/hivemind/dynamics_pipeline.py:86:            if self.enable_physarum
workspace/audit/wirings_integration_20260222.md:868:workspace/hivemind/hivemind/dynamics_pipeline.py:155:            if self.enable_physarum:
workspace/audit/wirings_integration_20260222.md:871:workspace/hivemind/hivemind/dynamics_pipeline.py:159:        if self.enable_trails:
workspace/audit/wirings_integration_20260222.md:874:workspace/hivemind/hivemind/dynamics_pipeline.py:184:                "ENABLE_PHYSARUM_ROUTER": self.enable_physarum,
workspace/audit/wirings_integration_20260222.md:875:workspace/hivemind/hivemind/dynamics_pipeline.py:185:                "ENABLE_TRAIL_MEMORY": self.enable_trails,
workspace/audit/wirings_integration_20260222.md:958:$ rg -n "OPENCLAW_COUNTERFACTUAL_REPLAY|counterfactual|replay|active inference|ActiveInferenceAgent|EFE|efe" -S workspace/hivemind workspace/tacti workspace/tacti_cr workspace/scripts/policy_router.py
workspace/audit/wirings_integration_20260222.md:984:workspace/tacti_cr/prefetch.py:3:Canonical source is workspace/tacti/prefetch.py.
workspace/audit/wirings_integration_20260222.md:985:workspace/tacti_cr/prefetch.py:10:_src = _shim_file.parents[1] / "tacti" / "prefetch.py"
workspace/audit/wirings_integration_20260222.md:987:workspace/tacti/novel10_contract.py:14:    "prefetch": ["tacti_cr.prefetch.predicted_topics", "tacti_cr.prefetch.cache_put"],
workspace/audit/wirings_integration_20260222.md:994:workspace/tacti/config.py:87:    "prefetch": "TACTI_CR_PREFETCH",
workspace/audit/wirings_integration_20260222.md:998:workspace/tacti/__init__.py:25:from .prefetch import PrefetchCache, predict_topics, prefetch_context
workspace/audit/wirings_integration_20260222.md:1001:workspace/tacti/__init__.py:67:    "prefetch_context",
workspace/audit/wirings_integration_20260222.md:1003:workspace/tacti/prefetch.py:1:"""Predictive context prefetcher with deterministic topic prediction and adaptive depth."""
workspace/audit/wirings_integration_20260222.md:1004:workspace/tacti/prefetch.py:16:class PrefetchCache:
workspace/audit/wirings_integration_20260222.md:1005:workspace/tacti/prefetch.py:19:        self.cache_path = root / "workspace" / "state" / "prefetch" / "cache.jsonl"
workspace/audit/wirings_integration_20260222.md:1006:workspace/tacti/prefetch.py:20:        self.index_path = root / "workspace" / "state" / "prefetch" / "index.json"
workspace/audit/wirings_integration_20260222.md:1007:workspace/tacti/prefetch.py:46:    def record_prefetch(self, topic: str, docs: list[str]) -> None:
workspace/audit/wirings_integration_20260222.md:1008:workspace/tacti/prefetch.py:54:        emit("tacti_cr.prefetch.recorded", {"topic": topic, "docs_count": len(docs), "depth": int(idx.get("depth", 3))})
workspace/audit/wirings_integration_20260222.md:1009:workspace/tacti/prefetch.py:67:        emit("tacti_cr.prefetch.hit_rate", {"hit": bool(hit), "hit_rate": hit_rate, "depth": int(idx["depth"]), "total": total})
workspace/audit/wirings_integration_20260222.md:1010:workspace/tacti/prefetch.py:82:def prefetch_context(token_stream: str, query_fn, *, repo_root: Path | None = None) -> dict[str, Any]:
workspace/audit/wirings_integration_20260222.md:1011:workspace/tacti/prefetch.py:83:    if not is_enabled("prefetch"):
workspace/audit/wirings_integration_20260222.md:1012:workspace/tacti/prefetch.py:84:        return {"ok": False, "reason": "prefetch_disabled", "topics": []}
workspace/audit/wirings_integration_20260222.md:1013:workspace/tacti/prefetch.py:85:    cache = PrefetchCache(repo_root=repo_root)
workspace/audit/wirings_integration_20260222.md:1014:workspace/tacti/prefetch.py:87:    emit("tacti_cr.prefetch.predicted_topics", {"topics": topics, "depth": cache.depth()})
workspace/audit/wirings_integration_20260222.md:1015:workspace/tacti/prefetch.py:91:    cache.record_prefetch("|".join(topics), docs)
workspace/audit/wirings_integration_20260222.md:1016:workspace/tacti/prefetch.py:92:    emit("tacti_cr.prefetch.cache_put", {"topics": topics, "docs_count": len(docs)})
workspace/audit/wirings_integration_20260222.md:1017:workspace/tacti/prefetch.py:96:__all__ = ["PrefetchCache", "predict_topics", "prefetch_context"]
workspace/audit/wirings_integration_20260222.md:1029:workspace/hivemind/hivemind/active_inference.py:137:def counterfactual_replay_enabled() -> bool:
workspace/audit/wirings_integration_20260222.md:1031:workspace/hivemind/hivemind/active_inference.py:147:def generate_counterfactual_routings(event: Dict[str, Any], candidates: list[str] | None = None, max_items: int = 3) -> list[Dict[str, Any]]:
workspace/audit/wirings_integration_20260222.md:1032:workspace/hivemind/hivemind/active_inference.py:151:    if not counterfactual_replay_enabled():
workspace/audit/wirings_integration_20260222.md:1033:workspace/hivemind/hivemind/active_inference.py:173:                "reason": f"counterfactual_from_{base_reason}",
workspace/audit/wirings_integration_20260222.md:1034:workspace/hivemind/hivemind/active_inference.py:179:def replay_counterfactuals(event: Dict[str, Any], k: int = 3, rng_seed: int | None = None) -> Dict[str, Any]:
workspace/audit/wirings_integration_20260222.md:1035:workspace/hivemind/hivemind/active_inference.py:181:    Generate deterministic counterfactual routing alternatives and apply
workspace/audit/wirings_integration_20260222.md:1036:workspace/hivemind/hivemind/active_inference.py:184:    if not counterfactual_replay_enabled():
workspace/audit/wirings_integration_20260222.md:1037:workspace/hivemind/hivemind/active_inference.py:185:        return {"ok": True, "enabled": False, "counterfactuals": [], "updates": [], "free_energy": {}}
workspace/audit/wirings_integration_20260222.md:1038:workspace/hivemind/hivemind/active_inference.py:210:    counterfactuals = []
workspace/audit/wirings_integration_20260222.md:1039:workspace/hivemind/hivemind/active_inference.py:215:        counterfactuals.append(
workspace/audit/wirings_integration_20260222.md:1040:workspace/hivemind/hivemind/active_inference.py:219:                "reason": "counterfactual_replay",
workspace/audit/wirings_integration_20260222.md:1041:workspace/hivemind/hivemind/active_inference.py:230:        "counterfactuals": counterfactuals,
workspace/audit/wirings_integration_20260222.md:1096:$ python3 -m unittest tests_unittest.test_audit_commit_hook_witness tests_unittest.test_witness_ledger -v
workspace/audit/wirings_integration_20260222.md:1097:test_witness_commit_invoked_on_audit_write (tests_unittest.test_audit_commit_hook_witness.TestAuditCommitHookWitness.test_witness_commit_invoked_on_audit_write) ... ok
workspace/audit/wirings_integration_20260222.md:1098:test_witness_failure_degrades_when_not_strict (tests_unittest.test_audit_commit_hook_witness.TestAuditCommitHookWitness.test_witness_failure_degrades_when_not_strict) ... ok
workspace/audit/wirings_integration_20260222.md:1099:test_witness_failure_fails_closed_when_strict (tests_unittest.test_audit_commit_hook_witness.TestAuditCommitHookWitness.test_witness_failure_fails_closed_when_strict) ... ok
workspace/audit/wirings_integration_20260222.md:1100:test_commit_chain_is_deterministic (tests_unittest.test_witness_ledger.TestWitnessLedger.test_commit_chain_is_deterministic) ... ok
workspace/audit/wirings_integration_20260222.md:1101:test_flag_off_produces_no_witness_ledger_writes (tests_unittest.test_witness_ledger.TestWitnessLedger.test_flag_off_produces_no_witness_ledger_writes) ... ok
workspace/audit/wirings_integration_20260222.md:1102:test_tamper_detection_fails_chain_verification (tests_unittest.test_witness_ledger.TestWitnessLedger.test_tamper_detection_fails_chain_verification) ... ok
workspace/audit/wirings_integration_20260222.md:1119:⚠️ witness ledger commit skipped: witness_error: boom
workspace/audit/wirings_integration_20260222.md:1127:❌ witness ledger commit failed (strict): witness_error: boom
workspace/audit/wirings_integration_20260222.md:1136:- Intent: chain governance/audit JSONL writes through witness ledger with strict fail-closed mode optional.
workspace/audit/wirings_integration_20260222.md:1141:$ python3 -m unittest tests_unittest.test_kb_prefetch_cache -v
workspace/audit/wirings_integration_20260222.md:1142:test_prefetch_miss_then_hit_reuses_cached_context (tests_unittest.test_kb_prefetch_cache.TestKbPrefetchCache.test_prefetch_miss_then_hit_reuses_cached_context) ... FAIL
workspace/audit/wirings_integration_20260222.md:1145:FAIL: test_prefetch_miss_then_hit_reuses_cached_context (tests_unittest.test_kb_prefetch_cache.TestKbPrefetchCache.test_prefetch_miss_then_hit_reuses_cached_context)
workspace/audit/wirings_integration_20260222.md:1148:  File "/private/tmp/twenty-evolutions-20260221/tests_unittest/test_kb_prefetch_cache.py", line 38, in test_prefetch_miss_then_hit_reuses_cached_context
workspace/audit/wirings_integration_20260222.md:1157:$ python3 -m unittest tests_unittest.test_kb_prefetch_cache -v
workspace/audit/wirings_integration_20260222.md:1158:test_prefetch_miss_then_hit_reuses_cached_context (tests_unittest.test_kb_prefetch_cache.TestKbPrefetchCache.test_prefetch_miss_then_hit_reuses_cached_context) ... ok
workspace/audit/wirings_integration_20260222.md:1197:- Router callsite already existed in policy_router._tacti_runtime_controls; test pins invocation under enabled flags.
workspace/audit/wirings_integration_20260222.md:1239:$ python3 -m unittest tests_unittest.test_ensure_cron_jobs tests_unittest.test_narrative_distill -v
workspace/audit/wirings_integration_20260222.md:1243:test_distillation_is_stable_for_fixed_fixture (tests_unittest.test_narrative_distill.TestNarrativeDistill.test_distillation_is_stable_for_fixed_fixture) ... ok
workspace/audit/wirings_integration_20260222.md:1244:test_flag_off_produces_no_write (tests_unittest.test_narrative_distill.TestNarrativeDistill.test_flag_off_produces_no_write) ... ok
workspace/audit/wirings_integration_20260222.md:1245:test_max_items_is_respected (tests_unittest.test_narrative_distill.TestNarrativeDistill.test_max_items_is_respected) ... ok
workspace/audit/wirings_integration_20260222.md:1246:test_semantic_store_write_is_idempotent_when_flag_on (tests_unittest.test_narrative_distill.TestNarrativeDistill.test_semantic_store_write_is_idempotent_when_flag_on) ... ERROR
workspace/audit/wirings_integration_20260222.md:1249:ERROR: test_semantic_store_write_is_idempotent_when_flag_on (tests_unittest.test_narrative_distill.TestNarrativeDistill.test_semantic_store_write_is_idempotent_when_flag_on)
workspace/audit/wirings_integration_20260222.md:1252:  File "/private/tmp/twenty-evolutions-20260221/workspace/scripts/narrative_distill.py", line 199, in write_semantic_entries
workspace/audit/wirings_integration_20260222.md:1259:  File "/private/tmp/twenty-evolutions-20260221/tests_unittest/test_narrative_distill.py", line 58, in test_semantic_store_write_is_idempotent_when_flag_on
workspace/audit/wirings_integration_20260222.md:1261:  File "/private/tmp/twenty-evolutions-20260221/workspace/scripts/narrative_distill.py", line 206, in write_semantic_entries
workspace/audit/wirings_integration_20260222.md:1269:$ PYTHONPATH=workspace/hivemind python3 -m unittest tests_unittest.test_narrative_distill.TestNarrativeDistill.test_semantic_store_write_is_idempotent_when_flag_on -v
workspace/audit/wirings_integration_20260222.md:1270:test_semantic_store_write_is_idempotent_when_flag_on (tests_unittest.test_narrative_distill.TestNarrativeDistill.test_semantic_store_write_is_idempotent_when_flag_on) ... ok
workspace/audit/wirings_integration_20260222.md:1283:- Intent: invoke narrative distillation before the Daily Morning Briefing cron payload.
workspace/audit/wirings_integration_20260222.md:1284:- Failure handling: command is best-effort and appends warnings to reports/automation/narrative_distill.log without blocking briefing generation.
workspace/audit/wirings_integration_20260222.md:1285:- Note: full narrative_distill unittest module requires PYTHONPATH=workspace/hivemind in this environment.
workspace/audit/wirings_integration_20260222.md:1339:test_counterfactual_replay_guarded_and_non_crashing (tests_unittest.test_hivemind_dynamics_pipeline.TestTactiDynamicsPipeline.test_counterfactual_replay_guarded_and_non_crashing) ... ok
workspace/audit/wirings_integration_20260222.md:1359:- Intent: enable counterfactual replay in dynamics routing loop with runtime circuit breakers.
workspace/audit/wirings_integration_20260222.md:1437:⚠️ witness ledger commit skipped: witness_error: boom
workspace/audit/wirings_integration_20260222.md:1445:❌ witness ledger commit failed (strict): witness_error: boom
workspace/audit/wirings_integration_20260222.md:1663:$ PYTHONPATH=workspace/hivemind python3 -m unittest tests_unittest.test_policy_router_oscillatory_gating tests_unittest.test_hivemind_active_inference tests_unittest.test_hivemind_dynamics_pipeline tests_unittest.test_hivemind_physarum_router tests_unittest.test_hivemind_trails tests_unittest.test_witness_ledger tests_unittest.test_audit_commit_hook_witness tests_unittest.test_kb_prefetch_cache tests_unittest.test_research_gap_analyzer_bridge tests_unittest.test_policy_router_active_inference_hook tests_unittest.test_router_proprioception tests_unittest.test_itc_ingestion_forwarding tests_unittest.test_tacti_efe_calculator -v
workspace/audit/wirings_integration_20260222.md:1668:test_counterfactual_replay_guarded_and_non_crashing (tests_unittest.test_hivemind_dynamics_pipeline.TestTactiDynamicsPipeline.test_counterfactual_replay_guarded_and_non_crashing) ... ok
workspace/audit/wirings_integration_20260222.md:1677:test_commit_chain_is_deterministic (tests_unittest.test_witness_ledger.TestWitnessLedger.test_commit_chain_is_deterministic) ... ok
workspace/audit/wirings_integration_20260222.md:1678:test_flag_off_produces_no_witness_ledger_writes (tests_unittest.test_witness_ledger.TestWitnessLedger.test_flag_off_produces_no_witness_ledger_writes) ... ok
workspace/audit/wirings_integration_20260222.md:1679:test_tamper_detection_fails_chain_verification (tests_unittest.test_witness_ledger.TestWitnessLedger.test_tamper_detection_fails_chain_verification) ... ok
workspace/audit/wirings_integration_20260222.md:1680:test_witness_commit_invoked_on_audit_write (tests_unittest.test_audit_commit_hook_witness.TestAuditCommitHookWitness.test_witness_commit_invoked_on_audit_write) ... ok
workspace/audit/wirings_integration_20260222.md:1681:test_witness_failure_degrades_when_not_strict (tests_unittest.test_audit_commit_hook_witness.TestAuditCommitHookWitness.test_witness_failure_degrades_when_not_strict) ... ok
workspace/audit/wirings_integration_20260222.md:1682:test_witness_failure_fails_closed_when_strict (tests_unittest.test_audit_commit_hook_witness.TestAuditCommitHookWitness.test_witness_failure_fails_closed_when_strict) ... ok
workspace/audit/wirings_integration_20260222.md:1683:test_prefetch_miss_then_hit_reuses_cached_context (tests_unittest.test_kb_prefetch_cache.TestKbPrefetchCache.test_prefetch_miss_then_hit_reuses_cached_context) ... ok
workspace/audit/wirings_integration_20260222.md:1712:⚠️ witness ledger commit skipped: witness_error: boom
workspace/audit/wirings_integration_20260222.md:1720:❌ witness ledger commit failed (strict): witness_error: boom
workspace/audit/wirings_integration_20260222.md:1732:- [x] #4 Witness ledger chained on audit/governance JSONL writes (`84b38a2`)
workspace/audit/wirings_integration_20260222.md:1736:- [x] #7 Narrative distill invoked before daily briefing cron payload (`aa564e7`)
workspace/audit/wirings_integration_20260222.md:1768:- Narrative-distill full module tests in this worktree require `PYTHONPATH=workspace/hivemind`; targeted invocation was validated under that environment.
workspace/audit/wirings_integration_20260222.md:1773:A	tests_unittest/test_audit_commit_hook_witness.py
workspace/audit/wirings_integration_20260222.md:1778:A	tests_unittest/test_kb_prefetch_cache.py
workspace/audit/wirings_integration_20260222.md:1799: tests_unittest/test_audit_commit_hook_witness.py   |   63 +
workspace/audit/wirings_integration_20260222.md:1804: tests_unittest/test_kb_prefetch_cache.py           |   47 +
workspace/knowledge_base/research/papers/2601.06002_molecular_structure_thought.md:6:**Tags:** #LLM #reasoning #chain-of-thought #molecular-structure #distillation
workspace/knowledge_base/research/papers/2601.06002_molecular_structure_thought.md:35:- This explains why heterogeneous distillation often fails
workspace/audit/PR_BODY_openclaw_evolution_pack_20260220.md:2:feat(evolution): proprioception + narrative distill + witness ledger (flag-gated)
workspace/audit/PR_BODY_openclaw_evolution_pack_20260220.md:7:  - Narrative distill (OPENCLAW_NARRATIVE_DISTILL): optional nightly distillation runner.
workspace/audit/PR_BODY_openclaw_evolution_pack_20260220.md:8:  - Witness ledger (OPENCLAW_WITNESS_LEDGER): hash-chain tamper-evident ledger + tests.
workspace/audit/teamchat_implementation_20260220T104111Z.md:20:- `OPENCLAW_TEAMCHAT_WITNESS` (default `0`): emits witness ledger entries for Team Chat turns.
workspace/audit/teamchat_implementation_20260220T104111Z.md:31:- `tests_unittest/test_team_chat_witness.py`
workspace/audit/teamchat_implementation_20260220T104111Z.md:54:- `tests_unittest/test_team_chat_witness.py`
workspace/audit/teamchat_implementation_20260220T104111Z.md:55:  - Verifies witness commit hook is called once per agent turn when enabled
workspace/audit/teamchat_implementation_20260220T104111Z.md:63:- `python3 -m unittest -q tests_unittest.test_team_chat_basic tests_unittest.test_team_chat_witness tests_unittest.test_team_chat_no_side_effects tests_unittest.test_policy_router_teamchat_intent tests_unittest.test_team_chat_autocommit_contract`
workspace/hivemind/TACTI_CR.md:112:cat > ~/.openclaw/env.d/tacti.flags.env <<'EOF'
workspace/hivemind/TACTI_CR.md:125:- Operational rollback (immediate): unset TACTI flags.
workspace/hivemind/TACTI_CR.md:143:- Active inference observed-outcome metrics in `policy_router.py` are lightweight proxies, not full behavioral telemetry.
workspace/docs/evidence/freecompute/config_example_redacted.env:40:FREECOMPUTE_LEDGER_PATH=.tmp/quota-ledger
workspace/hivemind/hivemind/active_inference.py:137:def counterfactual_replay_enabled() -> bool:
workspace/hivemind/hivemind/active_inference.py:147:def generate_counterfactual_routings(event: Dict[str, Any], candidates: list[str] | None = None, max_items: int = 3) -> list[Dict[str, Any]]:
workspace/hivemind/hivemind/active_inference.py:151:    if not counterfactual_replay_enabled():
workspace/hivemind/hivemind/active_inference.py:173:                "reason": f"counterfactual_from_{base_reason}",
workspace/hivemind/hivemind/active_inference.py:179:def replay_counterfactuals(event: Dict[str, Any], k: int = 3, rng_seed: int | None = None) -> Dict[str, Any]:
workspace/hivemind/hivemind/active_inference.py:181:    Generate deterministic counterfactual routing alternatives and apply
workspace/hivemind/hivemind/active_inference.py:184:    if not counterfactual_replay_enabled():
workspace/hivemind/hivemind/active_inference.py:185:        return {"ok": True, "enabled": False, "counterfactuals": [], "updates": [], "free_energy": {}}
workspace/hivemind/hivemind/active_inference.py:210:    counterfactuals = []
workspace/hivemind/hivemind/active_inference.py:215:        counterfactuals.append(
workspace/hivemind/hivemind/active_inference.py:219:                "reason": "counterfactual_replay",
workspace/hivemind/hivemind/active_inference.py:230:        "counterfactuals": counterfactuals,
workspace/hivemind/hivemind/flags.py:9:TACTI_DYNAMICS_FLAGS = (
workspace/governance/AGENTS.md:36:- This is your curated memory — the distilled essence, not raw logs
workspace/governance/AGENTS.md:203:3. Update `MEMORY.md` with distilled learnings
workspace/hivemind/hivemind/dynamics_pipeline.py:7:from .active_inference import replay_counterfactuals
workspace/hivemind/hivemind/dynamics_pipeline.py:39:    Composes Murmuration + Reservoir + Physarum + Trails under feature flags.
workspace/hivemind/hivemind/dynamics_pipeline.py:52:        self.enable_murmuration = _env_enabled("ENABLE_MURMURATION")
workspace/hivemind/hivemind/dynamics_pipeline.py:53:        self.enable_reservoir = _env_enabled("ENABLE_RESERVOIR")
workspace/hivemind/hivemind/dynamics_pipeline.py:54:        self.enable_physarum = _env_enabled("ENABLE_PHYSARUM_ROUTER")
workspace/hivemind/hivemind/dynamics_pipeline.py:55:        self.enable_trails = _env_enabled("ENABLE_TRAIL_MEMORY")
workspace/hivemind/hivemind/dynamics_pipeline.py:56:        self.enable_counterfactual = _env_enabled("OPENCLAW_COUNTERFACTUAL_REPLAY")
workspace/hivemind/hivemind/dynamics_pipeline.py:61:        self._counterfactual_depth = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_MAX_DEPTH", 2))
workspace/hivemind/hivemind/dynamics_pipeline.py:62:        self._counterfactual_budget_ms = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_BUDGET_MS", 20))
workspace/hivemind/hivemind/dynamics_pipeline.py:63:        self._counterfactual_error_limit = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_ERROR_LIMIT", 3))
workspace/hivemind/hivemind/dynamics_pipeline.py:64:        self._counterfactual_disabled_until = 0.0
workspace/hivemind/hivemind/dynamics_pipeline.py:65:        self._counterfactual_errors = 0
workspace/hivemind/hivemind/dynamics_pipeline.py:68:        if not self.enable_trails:
workspace/hivemind/hivemind/dynamics_pipeline.py:103:            if self.enable_physarum
workspace/hivemind/hivemind/dynamics_pipeline.py:114:        peer_scores = {a: self.peer_graph.edge_weight(source, a) if self.enable_murmuration else 1.0 for a in candidates}
workspace/hivemind/hivemind/dynamics_pipeline.py:122:            if self.enable_reservoir
workspace/hivemind/hivemind/dynamics_pipeline.py:137:        counterfactual_meta = {
workspace/hivemind/hivemind/dynamics_pipeline.py:138:            "enabled": bool(self.enable_counterfactual),
workspace/hivemind/hivemind/dynamics_pipeline.py:141:            "errors": int(self._counterfactual_errors),
workspace/hivemind/hivemind/dynamics_pipeline.py:143:        if self.enable_counterfactual and time.time() >= self._counterfactual_disabled_until:
workspace/hivemind/hivemind/dynamics_pipeline.py:146:                replay = replay_counterfactuals(
workspace/hivemind/hivemind/dynamics_pipeline.py:153:                    k=self._counterfactual_depth,
workspace/hivemind/hivemind/dynamics_pipeline.py:156:                if elapsed_ms <= float(self._counterfactual_budget_ms):
workspace/hivemind/hivemind/dynamics_pipeline.py:157:                    for row in replay.get("counterfactuals", []):
workspace/hivemind/hivemind/dynamics_pipeline.py:164:                    counterfactual_meta = {
workspace/hivemind/hivemind/dynamics_pipeline.py:169:                        "k": self._counterfactual_depth,
workspace/hivemind/hivemind/dynamics_pipeline.py:172:                    counterfactual_meta = {
workspace/hivemind/hivemind/dynamics_pipeline.py:177:                        "budget_ms": self._counterfactual_budget_ms,
workspace/hivemind/hivemind/dynamics_pipeline.py:179:                self._counterfactual_errors = 0
workspace/hivemind/hivemind/dynamics_pipeline.py:181:                self._counterfactual_errors += 1
workspace/hivemind/hivemind/dynamics_pipeline.py:182:                counterfactual_meta = {
workspace/hivemind/hivemind/dynamics_pipeline.py:186:                    "errors": int(self._counterfactual_errors),
workspace/hivemind/hivemind/dynamics_pipeline.py:188:                if self._counterfactual_errors >= self._counterfactual_error_limit:
workspace/hivemind/hivemind/dynamics_pipeline.py:189:                    self._counterfactual_disabled_until = time.time() + 300.0
workspace/hivemind/hivemind/dynamics_pipeline.py:190:        elif self.enable_counterfactual:
workspace/hivemind/hivemind/dynamics_pipeline.py:191:            counterfactual_meta = {
workspace/hivemind/hivemind/dynamics_pipeline.py:195:                "retry_after_epoch": round(float(self._counterfactual_disabled_until), 3),
workspace/hivemind/hivemind/dynamics_pipeline.py:204:            "counterfactual": counterfactual_meta,
workspace/hivemind/hivemind/dynamics_pipeline.py:223:                if self.enable_murmuration:
workspace/hivemind/hivemind/dynamics_pipeline.py:235:            if self.enable_physarum:
workspace/hivemind/hivemind/dynamics_pipeline.py:239:        if self.enable_trails:
workspace/hivemind/hivemind/dynamics_pipeline.py:263:                "ENABLE_MURMURATION": self.enable_murmuration,
workspace/hivemind/hivemind/dynamics_pipeline.py:264:                "ENABLE_RESERVOIR": self.enable_reservoir,
workspace/hivemind/hivemind/dynamics_pipeline.py:265:                "ENABLE_PHYSARUM_ROUTER": self.enable_physarum,
workspace/hivemind/hivemind/dynamics_pipeline.py:266:                "ENABLE_TRAIL_MEMORY": self.enable_trails,
workspace/hivemind/hivemind/dynamics_pipeline.py:267:                "OPENCLAW_COUNTERFACTUAL_REPLAY": self.enable_counterfactual,
workspace/hivemind/hivemind/integrations/main_flow_hook.py:9:from ..flags import TACTI_DYNAMICS_FLAGS, any_enabled
workspace/hivemind/hivemind/integrations/main_flow_hook.py:136:    return any_enabled(TACTI_DYNAMICS_FLAGS, environ=environ)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:319:core/system2/inference/provider_registry.js:528:          this.ledger.record(candidate.provider_id, {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:453:core/system2/inference/quota_ledger.js:6: * Daily rolling quota tracker per-provider. Tracks RPM, RPD, TPM, TPD
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:454:core/system2/inference/quota_ledger.js:8: * midnight UTC unless provider specifies otherwise.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:455:core/system2/inference/quota_ledger.js:28:    // In-memory counters: { provider_id → { rpm, rpd, tpm, tpd, windowStart, dayStart } }
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:456:core/system2/inference/quota_ledger.js:69:      provider_id: providerId,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:457:core/system2/inference/quota_ledger.js:136:   * Reset counters for a specific provider (operator override).
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:458:core/system2/inference/quota_ledger.js:138:  resetProvider(providerId) {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:464:./tests_unittest/test_teamchat_witness_verify.py:21:    route = {"provider": "mock_provider", "model": "mock_model", "reason_code": "success", "attempts": 1}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:885:./tests_unittest/test_active_inference_counterfactual.py:17:        out = replay_counterfactuals({"provider": "groq", "candidates": ["groq", "ollama"]}, k=3, rng_seed=7)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:886:./tests_unittest/test_active_inference_counterfactual.py:26:                "provider": "groq",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:887:./tests_unittest/test_active_inference_counterfactual.py:41:            "provider": "groq",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:908:./tests_unittest/test_team_chat_witness.py:23:            "provider": "mock_provider",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:930:./tests_unittest/test_witness_ledger.py:26:            "providers": {"mock_provider": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "mock-model", "maxInputChars": 8000}]}},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:931:./tests_unittest/test_witness_ledger.py:27:            "routing": {"free_order": ["mock_provider"], "intents": {"coding": {"order": ["free"], "allowPaid": False}}},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:932:./tests_unittest/test_witness_ledger.py:38:            rec1 = {"intent": "coding", "provider": "local", "ok": True}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:933:./tests_unittest/test_witness_ledger.py:39:            rec2 = {"intent": "coding", "provider": "remote", "ok": False}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:934:./tests_unittest/test_witness_ledger.py:62:            commit({"intent": "coding", "provider": "local", "ok": True}, str(ledger), timestamp_utc="2026-02-20T00:00:00Z")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:935:./tests_unittest/test_witness_ledger.py:63:            commit({"intent": "coding", "provider": "remote", "ok": False}, str(ledger), timestamp_utc="2026-02-20T00:00:01Z")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:936:./tests_unittest/test_witness_ledger.py:65:            rows[0]["record"]["provider"] = "tampered-provider"
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:937:./tests_unittest/test_witness_ledger.py:87:                        handlers={"mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:976:./tests_unittest/test_narrative_distill.py:27:            {"id": "e1", "text": "Router selected local provider for coding task", "timestamp_utc": "2026-02-20T00:00:00Z"},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:977:./tests_unittest/test_narrative_distill.py:28:            {"id": "e2", "text": "Router selected local provider for coding tasks", "timestamp_utc": "2026-02-20T00:00:01Z"},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:978:./tests_unittest/test_narrative_distill.py:47:                "fact": "Router selected local provider for coding task",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:979:./tests_unittest/test_narrative_distill.py:70:                "fact": "Router selected local provider for coding task",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1014:./scripts/system2/provider_diag.js:89:  if (!routingEnabledForProvider && !reason) reason = 'disabled_by_policy';
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1070:./tests/freecompute_cloud.test.js:531:test('ledger: reset clears provider counters', () => {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1071:./tests/freecompute_cloud.test.js:534:  ledger.resetProvider('test');
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1865:./core/system2/inference/provider_registry.js:528:          this.ledger.record(candidate.provider_id, {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2032:./core/system2/inference/quota_ledger.js:6: * Daily rolling quota tracker per-provider. Tracks RPM, RPD, TPM, TPD
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2033:./core/system2/inference/quota_ledger.js:8: * midnight UTC unless provider specifies otherwise.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2034:./core/system2/inference/quota_ledger.js:28:    // In-memory counters: { provider_id → { rpm, rpd, tpm, tpd, windowStart, dayStart } }
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2035:./core/system2/inference/quota_ledger.js:69:      provider_id: providerId,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2036:./core/system2/inference/quota_ledger.js:136:   * Reset counters for a specific provider (operator override).
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2037:./core/system2/inference/quota_ledger.js:138:  resetProvider(providerId) {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2958:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:319:core/system2/inference/provider_registry.js:528:          this.ledger.record(candidate.provider_id, {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3092:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:453:core/system2/inference/quota_ledger.js:6: * Daily rolling quota tracker per-provider. Tracks RPM, RPD, TPM, TPD
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3093:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:454:core/system2/inference/quota_ledger.js:8: * midnight UTC unless provider specifies otherwise.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3094:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:455:core/system2/inference/quota_ledger.js:28:    // In-memory counters: { provider_id → { rpm, rpd, tpm, tpd, windowStart, dayStart } }
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3095:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:456:core/system2/inference/quota_ledger.js:69:      provider_id: providerId,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3096:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:457:core/system2/inference/quota_ledger.js:136:   * Reset counters for a specific provider (operator override).
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3097:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:458:core/system2/inference/quota_ledger.js:138:  resetProvider(providerId) {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3103:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:464:./tests_unittest/test_teamchat_witness_verify.py:21:    route = {"provider": "mock_provider", "model": "mock_model", "reason_code": "success", "attempts": 1}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3524:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:885:./tests_unittest/test_active_inference_counterfactual.py:17:        out = replay_counterfactuals({"provider": "groq", "candidates": ["groq", "ollama"]}, k=3, rng_seed=7)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3525:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:886:./tests_unittest/test_active_inference_counterfactual.py:26:                "provider": "groq",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3526:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:887:./tests_unittest/test_active_inference_counterfactual.py:41:            "provider": "groq",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3547:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:908:./tests_unittest/test_team_chat_witness.py:23:            "provider": "mock_provider",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3569:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:930:./tests_unittest/test_witness_ledger.py:26:            "providers": {"mock_provider": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "mock-model", "maxInputChars": 8000}]}},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3570:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:931:./tests_unittest/test_witness_ledger.py:27:            "routing": {"free_order": ["mock_provider"], "intents": {"coding": {"order": ["free"], "allowPaid": False}}},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3571:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:932:./tests_unittest/test_witness_ledger.py:38:            rec1 = {"intent": "coding", "provider": "local", "ok": True}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3572:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:933:./tests_unittest/test_witness_ledger.py:39:            rec2 = {"intent": "coding", "provider": "remote", "ok": False}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3573:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:934:./tests_unittest/test_witness_ledger.py:62:            commit({"intent": "coding", "provider": "local", "ok": True}, str(ledger), timestamp_utc="2026-02-20T00:00:00Z")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3574:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:935:./tests_unittest/test_witness_ledger.py:63:            commit({"intent": "coding", "provider": "remote", "ok": False}, str(ledger), timestamp_utc="2026-02-20T00:00:01Z")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3575:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:936:./tests_unittest/test_witness_ledger.py:65:            rows[0]["record"]["provider"] = "tampered-provider"
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3576:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:937:./tests_unittest/test_witness_ledger.py:87:                        handlers={"mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3615:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:976:./tests_unittest/test_narrative_distill.py:27:            {"id": "e1", "text": "Router selected local provider for coding task", "timestamp_utc": "2026-02-20T00:00:00Z"},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3616:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:977:./tests_unittest/test_narrative_distill.py:28:            {"id": "e2", "text": "Router selected local provider for coding tasks", "timestamp_utc": "2026-02-20T00:00:01Z"},
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3617:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:978:./tests_unittest/test_narrative_distill.py:47:                "fact": "Router selected local provider for coding task",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3618:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:979:./tests_unittest/test_narrative_distill.py:70:                "fact": "Router selected local provider for coding task",
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3653:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1014:./scripts/system2/provider_diag.js:89:  if (!routingEnabledForProvider && !reason) reason = 'disabled_by_policy';
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3709:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1070:./tests/freecompute_cloud.test.js:531:test('ledger: reset clears provider counters', () => {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:3710:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1071:./tests/freecompute_cloud.test.js:534:  ledger.resetProvider('test');
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:4504:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:1865:./core/system2/inference/provider_registry.js:528:          this.ledger.record(candidate.provider_id, {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:4671:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2032:./core/system2/inference/quota_ledger.js:6: * Daily rolling quota tracker per-provider. Tracks RPM, RPD, TPM, TPD
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:4672:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2033:./core/system2/inference/quota_ledger.js:8: * midnight UTC unless provider specifies otherwise.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:4673:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2034:./core/system2/inference/quota_ledger.js:28:    // In-memory counters: { provider_id → { rpm, rpd, tpm, tpd, windowStart, dayStart } }
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:4674:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2035:./core/system2/inference/quota_ledger.js:69:      provider_id: providerId,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:4675:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2036:./core/system2/inference/quota_ledger.js:136:   * Reset counters for a specific provider (operator override).
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:4676:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:2037:./core/system2/inference/quota_ledger.js:138:  resetProvider(providerId) {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6044:workspace/scripts/witness_ledger.py:10:def canonicalize(obj) -> bytes:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6045:workspace/scripts/witness_ledger.py:42:    return hashlib.sha256(canonicalize(base)).hexdigest()
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6046:workspace/scripts/witness_ledger.py:110:__all__ = ["canonicalize", "commit", "verify_chain"]
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6047:workspace/teamchat/witness_verify.py:13:        MESSAGE_HASH_VERSION_LEGACY,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6048:workspace/teamchat/witness_verify.py:16:        legacy_message_hash,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6049:workspace/teamchat/witness_verify.py:20:        MESSAGE_HASH_VERSION_LEGACY,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6050:workspace/teamchat/witness_verify.py:23:        legacy_message_hash,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6051:workspace/teamchat/witness_verify.py:105:        MESSAGE_HASH_VERSION_LEGACY: legacy_message_hash(message_row),
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6052:workspace/teamchat/witness_verify.py:199:        if hash_version == MESSAGE_HASH_VERSION_LEGACY:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6053:workspace/teamchat/witness_verify.py:200:            if committed_hash != expected[MESSAGE_HASH_VERSION_LEGACY]:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6054:workspace/teamchat/witness_verify.py:203:        # Legacy compatibility: support prior entries with no explicit version.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6055:workspace/teamchat/witness_verify.py:205:            expected[MESSAGE_HASH_VERSION_LEGACY],
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6083:workspace/scripts/narrative_distill.py:42:def canonicalize(obj) -> bytes:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6084:workspace/scripts/narrative_distill.py:235:                canonicalize(
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6085:workspace/scripts/narrative_distill.py:283:                    canonicalize({"fact": str(item.get("fact", "")), "source_ids": list(item.get("source_ids", []))})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6154:workspace/audit/teamchat_witness_verify_20260220T113745Z.md:13:  - Verifier preserves compatibility with existing entries by accepting legacy hashes when version is absent/legacy:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6155:workspace/audit/teamchat_witness_verify_20260220T113745Z.md:14:    - `teamchat-msg-sha256-legacy`
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6567:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6044:workspace/scripts/witness_ledger.py:10:def canonicalize(obj) -> bytes:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6568:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6045:workspace/scripts/witness_ledger.py:42:    return hashlib.sha256(canonicalize(base)).hexdigest()
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6569:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6046:workspace/scripts/witness_ledger.py:110:__all__ = ["canonicalize", "commit", "verify_chain"]
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6570:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6047:workspace/teamchat/witness_verify.py:13:        MESSAGE_HASH_VERSION_LEGACY,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6571:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6048:workspace/teamchat/witness_verify.py:16:        legacy_message_hash,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6572:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6049:workspace/teamchat/witness_verify.py:20:        MESSAGE_HASH_VERSION_LEGACY,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6573:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6050:workspace/teamchat/witness_verify.py:23:        legacy_message_hash,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6574:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6051:workspace/teamchat/witness_verify.py:105:        MESSAGE_HASH_VERSION_LEGACY: legacy_message_hash(message_row),
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6575:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6052:workspace/teamchat/witness_verify.py:199:        if hash_version == MESSAGE_HASH_VERSION_LEGACY:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6576:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6053:workspace/teamchat/witness_verify.py:200:            if committed_hash != expected[MESSAGE_HASH_VERSION_LEGACY]:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6577:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6054:workspace/teamchat/witness_verify.py:203:        # Legacy compatibility: support prior entries with no explicit version.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6578:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6055:workspace/teamchat/witness_verify.py:205:            expected[MESSAGE_HASH_VERSION_LEGACY],
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6606:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6083:workspace/scripts/narrative_distill.py:42:def canonicalize(obj) -> bytes:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6607:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6084:workspace/scripts/narrative_distill.py:235:                canonicalize(
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6608:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6085:workspace/scripts/narrative_distill.py:283:                    canonicalize({"fact": str(item.get("fact", "")), "source_ids": list(item.get("source_ids", []))})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6677:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6154:workspace/audit/teamchat_witness_verify_20260220T113745Z.md:13:  - Verifier preserves compatibility with existing entries by accepting legacy hashes when version is absent/legacy:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6678:workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:6155:workspace/audit/teamchat_witness_verify_20260220T113745Z.md:14:    - `teamchat-msg-sha256-legacy`
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7366:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7466:workspace/scripts/narrative_distill.py:78:    for key in ("text", "content", "message", "summary"):
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7484:core/system2/inference/quota_ledger.js:10: * Storage: append-only JSONL (one file per day) for auditability.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7533:workspace/teamchat/witness_verify.py:41:    session_id: str
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7534:workspace/teamchat/witness_verify.py:52:def _session_id_from_path(session_path: Path) -> str:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7535:workspace/teamchat/witness_verify.py:88:        session_id = str(meta.get("session_id", "")).strip()
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7536:workspace/teamchat/witness_verify.py:89:        if not session_id:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7537:workspace/teamchat/witness_verify.py:95:        key = (session_id, turn, role)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7538:workspace/teamchat/witness_verify.py:102:def _expected_hashes(message_row: dict[str, Any], *, session_id: str, turn: int) -> dict[str, str]:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7539:workspace/teamchat/witness_verify.py:104:        MESSAGE_HASH_VERSION_V2: canonical_message_hash_v2(message_row, session_id=session_id, turn=turn),
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7540:workspace/teamchat/witness_verify.py:113:    session_id = _session_id_from_path(session_path)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7541:workspace/teamchat/witness_verify.py:115:        return VerificationResult(False, session_id, 0, "", "session_missing", str(session_path))
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7542:workspace/teamchat/witness_verify.py:117:        return VerificationResult(False, session_id, 0, "", "ledger_missing", str(ledger_path))
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7543:workspace/teamchat/witness_verify.py:124:            session_id,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7544:workspace/teamchat/witness_verify.py:136:        return VerificationResult(False, session_id, 0, str(chain.get("head_hash", "") or ""), "parse_error", type(exc).__name__)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7545:workspace/teamchat/witness_verify.py:146:        ref_session_id = str(record.get("session_id", "")).strip()
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7546:workspace/teamchat/witness_verify.py:147:        if not ref_session_id:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7547:workspace/teamchat/witness_verify.py:150:                session_id,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7548:workspace/teamchat/witness_verify.py:156:        if not (sessions_dir / f"{ref_session_id}.jsonl").exists():
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7549:workspace/teamchat/witness_verify.py:159:                session_id,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7550:workspace/teamchat/witness_verify.py:163:                ref_session_id,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7551:workspace/teamchat/witness_verify.py:165:        if str(record.get("session_id", "")).strip() != session_id:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7552:workspace/teamchat/witness_verify.py:170:        return VerificationResult(False, session_id, 0, str(chain.get("head_hash", "") or ""), "no_session_events", "")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7553:workspace/teamchat/witness_verify.py:174:        ref_session_id = str(record.get("session_id", "")).strip()
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7554:workspace/teamchat/witness_verify.py:175:        if ref_session_id != session_id:
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7555:workspace/teamchat/witness_verify.py:176:            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "session_reference_mismatch", ref_session_id)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7556:workspace/teamchat/witness_verify.py:180:            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "invalid_turn", str(record.get("turn")))
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7557:workspace/teamchat/witness_verify.py:182:            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "session_turn_order_invalid", f"turn={turn}")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7558:workspace/teamchat/witness_verify.py:185:        key = (session_id, turn, f"agent:{agent}")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7559:workspace/teamchat/witness_verify.py:188:            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "session_message_missing", str(key))
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7560:workspace/teamchat/witness_verify.py:190:            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "timestamp_mismatch", f"turn={turn}")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7561:workspace/teamchat/witness_verify.py:194:        expected = _expected_hashes(message_row, session_id=session_id, turn=turn)
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7562:workspace/teamchat/witness_verify.py:197:                return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "message_hash_mismatch", f"turn={turn}")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7563:workspace/teamchat/witness_verify.py:201:                return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "message_hash_mismatch", f"turn={turn}")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7564:workspace/teamchat/witness_verify.py:210:        return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "message_hash_mismatch", f"turn={turn}")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7565:workspace/teamchat/witness_verify.py:214:        session_id,
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7566:workspace/teamchat/witness_verify.py:238:            f"FAIL session={result.session_id} witnessed_events={result.witnessed_events} "
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7567:workspace/teamchat/witness_verify.py:243:        f"PASS session={result.session_id} witnessed_events={result.witnessed_events} "
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7598:workspace/scripts/run_narrative_distill.py:30:    parser.add_argument("--fallback-source", default="itc/llm_router_events.jsonl", help="fallback episodic source")
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7599:workspace/scripts/run_narrative_distill.py:75:    summary = {
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:7600:workspace/scripts/run_narrative_distill.py:84:    print(json.dumps(summary, ensure_ascii=True))
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8151:./tests_unittest/test_tacti_cr_novel_10.py:24:from tacti_cr.prefetch import PrefetchCache, predict_topics
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8172:./workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8173:./workspace/tacti_cr/prefetch.py:54:        emit("tacti_cr.prefetch.recorded", {"topic": topic, "docs_count": len(docs), "depth": int(idx.get("depth", 3))})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8174:./workspace/tacti_cr/prefetch.py:67:        emit("tacti_cr.prefetch.hit_rate", {"hit": bool(hit), "hit_rate": hit_rate, "depth": int(idx["depth"]), "total": total})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8175:./workspace/tacti_cr/prefetch.py:87:    emit("tacti_cr.prefetch.predicted_topics", {"topics": topics, "depth": cache.depth()})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8176:./workspace/tacti_cr/prefetch.py:92:    emit("tacti_cr.prefetch.cache_put", {"topics": topics, "docs_count": len(docs)})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8210:./workspace/scripts/run_novel10_fixture.py:27:from tacti_cr.novel10_contract import FEATURE_FLAGS
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8215:./workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8228:./workspace/tacti_cr/novel10_contract.py:14:    "prefetch": ["tacti_cr.prefetch.predicted_topics", "tacti_cr.prefetch.cache_put"],
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8264:./workspace/scripts/verify_tacti_cr_novel_10.sh:42:  workspace/tacti_cr/prefetch.py \
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8275:./workspace/audit/tacti_cr_event_contract_20260219T130107Z.md:34:- `workspace/tacti_cr/prefetch.py`: emits prefetch/hit-rate events.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8279:./workspace/audit/tacti_cr_event_contract_20260219T130107Z.md:58: M workspace/tacti_cr/prefetch.py
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8310:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:41:tacti_cr.prefetch.cache_put,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8311:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:42:tacti_cr.prefetch.hit_rate,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8312:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:43:tacti_cr.prefetch.predicted_topics,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8313:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:44:tacti_cr.prefetch.recorded,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8379:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:91:./workspace/state/tacti_cr/events.jsonl:1:{"ts": 1771506277399, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8381:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:93:./workspace/state/tacti_cr/events.jsonl:4:{"ts": 1771535085092, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8383:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:95:./workspace/state/tacti_cr/events.jsonl:7:{"ts": 1771535094165, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8385:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:97:./workspace/state/tacti_cr/events.jsonl:10:{"ts": 1771535104622, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8387:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:99:./workspace/state/tacti_cr/events.jsonl:13:{"ts": 1771535114296, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8389:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:101:./workspace/state/tacti_cr/events.jsonl:16:{"ts": 1771535122066, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8391:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:103:./workspace/state/tacti_cr/events.jsonl:19:{"ts": 1771535125674, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8393:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:105:./workspace/state/tacti_cr/events.jsonl:22:{"ts": 1771535797828, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8395:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:107:./workspace/state/tacti_cr/events.jsonl:25:{"ts": 1771543883143, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8397:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:109:./workspace/state/tacti_cr/events.jsonl:28:{"ts": 1771543886658, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8399:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:111:./workspace/state/tacti_cr/events.jsonl:31:{"ts": 1771543900227, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8401:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:113:./workspace/state/tacti_cr/events.jsonl:34:{"ts": 1771543903469, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8640:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8151:./tests_unittest/test_tacti_cr_novel_10.py:24:from tacti_cr.prefetch import PrefetchCache, predict_topics
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8661:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8172:./workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8662:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8173:./workspace/tacti_cr/prefetch.py:54:        emit("tacti_cr.prefetch.recorded", {"topic": topic, "docs_count": len(docs), "depth": int(idx.get("depth", 3))})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8663:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8174:./workspace/tacti_cr/prefetch.py:67:        emit("tacti_cr.prefetch.hit_rate", {"hit": bool(hit), "hit_rate": hit_rate, "depth": int(idx["depth"]), "total": total})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8664:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8175:./workspace/tacti_cr/prefetch.py:87:    emit("tacti_cr.prefetch.predicted_topics", {"topics": topics, "depth": cache.depth()})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8665:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8176:./workspace/tacti_cr/prefetch.py:92:    emit("tacti_cr.prefetch.cache_put", {"topics": topics, "docs_count": len(docs)})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8699:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8210:./workspace/scripts/run_novel10_fixture.py:27:from tacti_cr.novel10_contract import FEATURE_FLAGS
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8704:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8215:./workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8717:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8228:./workspace/tacti_cr/novel10_contract.py:14:    "prefetch": ["tacti_cr.prefetch.predicted_topics", "tacti_cr.prefetch.cache_put"],
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8721:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8232:./workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8753:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8264:./workspace/scripts/verify_tacti_cr_novel_10.sh:42:  workspace/tacti_cr/prefetch.py \
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8764:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8275:./workspace/audit/tacti_cr_event_contract_20260219T130107Z.md:34:- `workspace/tacti_cr/prefetch.py`: emits prefetch/hit-rate events.
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8768:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8279:./workspace/audit/tacti_cr_event_contract_20260219T130107Z.md:58: M workspace/tacti_cr/prefetch.py
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8799:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8310:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:41:tacti_cr.prefetch.cache_put,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8800:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8311:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:42:tacti_cr.prefetch.hit_rate,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8801:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8312:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:43:tacti_cr.prefetch.predicted_topics,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8802:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8313:./workspace/audit/tacti_cr_novel10_fixture_20260219T130947Z.md:44:tacti_cr.prefetch.recorded,1
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8868:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8379:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:91:./workspace/state/tacti_cr/events.jsonl:1:{"ts": 1771506277399, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8870:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8381:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:93:./workspace/state/tacti_cr/events.jsonl:4:{"ts": 1771535085092, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8872:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8383:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:95:./workspace/state/tacti_cr/events.jsonl:7:{"ts": 1771535094165, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8874:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8385:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:97:./workspace/state/tacti_cr/events.jsonl:10:{"ts": 1771535104622, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8876:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8387:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:99:./workspace/state/tacti_cr/events.jsonl:13:{"ts": 1771535114296, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8878:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8389:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:101:./workspace/state/tacti_cr/events.jsonl:16:{"ts": 1771535122066, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8880:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8391:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:103:./workspace/state/tacti_cr/events.jsonl:19:{"ts": 1771535125674, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8882:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8393:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:105:./workspace/state/tacti_cr/events.jsonl:22:{"ts": 1771535797828, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8884:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8395:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:107:./workspace/state/tacti_cr/events.jsonl:25:{"ts": 1771543883143, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8886:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8397:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:109:./workspace/state/tacti_cr/events.jsonl:28:{"ts": 1771543886658, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8888:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8399:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:111:./workspace/state/tacti_cr/events.jsonl:31:{"ts": 1771543900227, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8890:./workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:8401:./workspace/audit/openclaw_evolution_pack_20260219T235633Z.md:113:./workspace/state/tacti_cr/events.jsonl:34:{"ts": 1771543903469, "event": "tacti_cr.expression_profile", "detail": {"intent": "coding", "profile": {"enabled_features": ["arousal_osc", "semantic_immune", "prefetch", "mirror"], "suppressed_features": ["dream_consolidation"], "reasons": {"arousal_osc": ["enabled"], "dream_consolidation": ["activation:time_of_day"], "semantic_immune": ["enabled"], "prefetch": ["enabled"], "mirror": ["enabled"]}, "manifest_path": "/Users/heathyeager/clawd/workspace/policy/expression_manifest.json"}}}
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9047:tests_unittest/test_tacti_cr_novel_10.py:24:from tacti_cr.prefetch import PrefetchCache, predict_topics
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9053:workspace/tacti/prefetch.py:54:        emit("tacti_cr.prefetch.recorded", {"topic": topic, "docs_count": len(docs), "depth": int(idx.get("depth", 3))})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9054:workspace/tacti/prefetch.py:67:        emit("tacti_cr.prefetch.hit_rate", {"hit": bool(hit), "hit_rate": hit_rate, "depth": int(idx["depth"]), "total": total})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9055:workspace/tacti/prefetch.py:87:    emit("tacti_cr.prefetch.predicted_topics", {"topics": topics, "depth": cache.depth()})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9056:workspace/tacti/prefetch.py:92:    emit("tacti_cr.prefetch.cache_put", {"topics": topics, "docs_count": len(docs)})
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9057:workspace/knowledge_base/kb.py:25:    from tacti_cr.prefetch import prefetch_context
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9070:workspace/scripts/run_novel10_fixture.py:27:from tacti_cr.novel10_contract import FEATURE_FLAGS
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9075:workspace/scripts/run_novel10_fixture.py:32:from tacti_cr.prefetch import prefetch_context, PrefetchCache
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9078:workspace/scripts/run_narrative_distill.py:16:from tacti_cr.events_paths import resolve_events_path
workspace/audit/twenty_evolutions_impl_20260221T104827Z.md:9420: M workspace/tacti_cr/prefetch.py
```

## Flags / Defaults Source Evidence
```bash
rg -n 'OPENCLAW_|TACTI_CR_AROUSAL_OSC' core/system2/inference/router.js env.d/system1-routing.env workspace/scripts/policy_router.py workspace/scripts/audit_commit_hook.py workspace/hivemind/hivemind/dynamics_pipeline.py workspace/hivemind/hivemind/physarum_router.py workspace/automation/cron_jobs.json workspace/research/research_ingest.py workspace/knowledge_base/kb.py workspace/itc_pipeline/ingestion_boundary.py -S
env.d/system1-routing.env:6:OPENCLAW_VLLM_BASE_URL=http://127.0.0.1:8001/v1
env.d/system1-routing.env:7:TACTI_CR_AROUSAL_OSC=1
env.d/system1-routing.env:8:OPENCLAW_TRAIL_VALENCE=1
env.d/system1-routing.env:9:OPENCLAW_COUNTERFACTUAL_REPLAY=1
env.d/system1-routing.env:10:OPENCLAW_ACTIVE_INFERENCE=1
env.d/system1-routing.env:18:OPENCLAW_MINIMAX_PORTAL_API_KEY=__SET_IN_SHELL_OR_SECRET_STORE__
core/system2/inference/router.js:299:  if (_flagEnabled('OPENCLAW_ROUTER_PROPRIOCEPTION')) {
workspace/scripts/audit_commit_hook.py:37:    if not _flag_enabled("OPENCLAW_WITNESS_LEDGER", default="1"):
workspace/scripts/audit_commit_hook.py:42:        os.environ.get("OPENCLAW_WITNESS_LEDGER_PATH", str(DEFAULT_WITNESS_LEDGER_PATH))
workspace/scripts/audit_commit_hook.py:140:        strict = _flag_enabled("OPENCLAW_WITNESS_LEDGER_STRICT", default="0")
workspace/scripts/policy_router.py:34:_env_root = os.environ.get("OPENCLAW_ROOT")
workspace/scripts/policy_router.py:303:    value = str(os.environ.get("OPENCLAW_POLICY_STRICT", "1")).strip().lower()
workspace/scripts/policy_router.py:428:    return _flag_enabled("OPENCLAW_ACTIVE_INFERENCE") or _flag_enabled("ENABLE_ACTIVE_INFERENCE")
workspace/scripts/policy_router.py:863:        self._proprio_sampler = ProprioceptiveSampler() if _flag_enabled("OPENCLAW_ROUTER_PROPRIOCEPTION") and ProprioceptiveSampler else None
workspace/scripts/policy_router.py:1182:        if _flag_enabled("OPENCLAW_ROUTER_PROPRIOCEPTION"):
workspace/automation/cron_jobs.json:29:      "command": "⏰ **Daily Briefing Time**\nIt is 7 AM. Before briefing content generation, run this best-effort pre-step and continue even on failure:\nOPENCLAW_NARRATIVE_DISTILL=1 python3 workspace/scripts/run_narrative_distill.py >> reports/automation/narrative_distill.log 2>&1 || echo \"[WARN] narrative distill failed\" >> reports/automation/narrative_distill.log\n\nThen generate the daily briefing for Heath with:\n1. Literature Quote (run node scripts/get_daily_quote.js)\n2. Therapeutic Technique (run python3 scripts/daily_technique.py --format briefing)\n3. Behavioral Prime paragraph (derived from the selected technique)\n4. Apple Reminders (run remindctl today)\n5. Calendar Events (run workspace/scripts/calendar.sh today)\n6. News Article (web_search)\n7. Agent Goal\n8. Time Management Tip (run python3 workspace/time_management/time_management.py tip)\n9. Self-Care Suggestion (run python3 workspace/time_management/time_management.py self_care)\n\nFormat as a clean, inspiring briefing. Include a section to track which suggestions Heath does/dismissed so we can learn."
workspace/hivemind/hivemind/physarum_router.py:84:        trail_valence_enabled = str(os.environ.get("OPENCLAW_TRAIL_VALENCE", "0")).strip().lower() in {"1", "true", "yes", "on"}
workspace/hivemind/hivemind/dynamics_pipeline.py:56:        self.enable_counterfactual = _env_enabled("OPENCLAW_COUNTERFACTUAL_REPLAY")
workspace/hivemind/hivemind/dynamics_pipeline.py:61:        self._counterfactual_depth = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_MAX_DEPTH", 2))
workspace/hivemind/hivemind/dynamics_pipeline.py:62:        self._counterfactual_budget_ms = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_BUDGET_MS", 20))
workspace/hivemind/hivemind/dynamics_pipeline.py:63:        self._counterfactual_error_limit = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_ERROR_LIMIT", 3))
workspace/hivemind/hivemind/dynamics_pipeline.py:267:                "OPENCLAW_COUNTERFACTUAL_REPLAY": self.enable_counterfactual,
```

## Validation
```bash
npm test

> openclaw@0.0.0 test
> node scripts/run_tests.js

RUN python3  -m unittest discover -s tests_unittest -p test_*.py
.............................................................................................................................................................................................
----------------------------------------------------------------------
Ran 189 tests in 7.206s

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
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpnsjmmr7p/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpnsjmmr7p/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpnsjmmr7p/overlay/quarantine/20260222-105717/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpyek7uv22/overlay/quarantine/20260222-105718/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpv61c7gaj/overlay/quarantine/20260222-105718/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp4q68dgf5/overlay/quarantine/20260222-105718/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpvptoho4b/overlay/quarantine/20260222-105718/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpxer4ky9f/overlay/quarantine/20260222-105718/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpxer4ky9f/quarantine/openclaw-quarantine-20260222-105718
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

python3 -m unittest
.............................................................................................................................................................................................
----------------------------------------------------------------------
Ran 189 tests in 3.801s

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
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpbbm8qgxm/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpbbm8qgxm/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpbbm8qgxm/overlay/quarantine/20260222-105725/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp5seti9wd/overlay/quarantine/20260222-105727/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpysjjd2po/overlay/quarantine/20260222-105727/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpsh16i26q/overlay/quarantine/20260222-105727/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpb0bw96dn/overlay/quarantine/20260222-105727/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpocfcpx3l/overlay/quarantine/20260222-105727/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_test
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpocfcpx3l/quarantine/openclaw-quarantine-20260222-105727

python3 -m unittest tests_unittest.test_goal_identity_invariants -v
test_verifier_passes_in_repo (tests_unittest.test_goal_identity_invariants.TestGoalIdentityInvariants.test_verifier_passes_in_repo) ... ok
test_verifier_strict_fails_on_fixture_warning (tests_unittest.test_goal_identity_invariants.TestGoalIdentityInvariants.test_verifier_strict_fails_on_fixture_warning) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.376s

OK
```

## Flag Default Snippets
```bash
sed -n '240,340p' workspace/scripts/policy_router.py
def normalize_provider_id(value):
    if not isinstance(value, str):
        return value
    key = value.strip()
    if not key:
        return key
    return PROVIDER_ID_ALIASES.get(key, key)


def denormalize_provider_ids(value):
    out = []
    for raw, norm in PROVIDER_ID_ALIASES.items():
        if norm == value:
            out.append(raw)
    return out


def canonical_intent(intent):
    raw = str(intent or "")
    if raw.startswith("teamchat:"):
        return "coding"
    return raw


def _normalize_provider_order(items):
    if not isinstance(items, list):
        return []
    return [normalize_provider_id(item) for item in items if isinstance(item, str)]


def _normalize_policy_routing(policy):
    routing = policy.get("routing", {})
    if not isinstance(routing, dict):
        return
    routing["free_order"] = _normalize_provider_order(routing.get("free_order", []))
    intents = routing.get("intents", {})
    if isinstance(intents, dict):
        for cfg in intents.values():
            if isinstance(cfg, dict):
                cfg["order"] = _normalize_provider_order(cfg.get("order", []))
    rules = routing.get("rules", [])
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict) and isinstance(rule.get("provider"), str):
                rule["provider"] = normalize_provider_id(rule.get("provider"))


def _deep_merge(defaults, incoming):
    if not isinstance(defaults, dict) or not isinstance(incoming, dict):
        return incoming if incoming is not None else defaults
    merged = {}
    for key, value in defaults.items():
        if key in incoming:
            merged[key] = _deep_merge(value, incoming[key])
        else:
            merged[key] = value
    for key, value in incoming.items():
        if key not in merged:
            merged[key] = value
    return merged


def _policy_strict_enabled():
    value = str(os.environ.get("OPENCLAW_POLICY_STRICT", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _validate_policy_schema(raw):
    errors = []
    budget_intent_keys = {"dailyTokenBudget", "dailyCallBudget", "maxCallsPerRun"}
    provider_keys = {
        "enabled",
        "paid",
        "tier",
        "type",
        "baseUrl",
        "apiKeyEnv",
        "models",
        "auth",
        "readyEnv",
        "provider_id",
        "capabilities",
        "model",
    }

    for intent, cfg in (raw.get("budgets", {}).get("intents", {}) or {}).items():
        if not isinstance(cfg, dict):
            continue
        unknown = sorted(set(cfg.keys()) - budget_intent_keys)
        if unknown:
            errors.append(f"budgets.intents.{intent} unknown keys: {', '.join(unknown)}")

    for provider, cfg in (raw.get("providers", {}) or {}).items():
        if not isinstance(cfg, dict):
            continue
        unknown = sorted(set(cfg.keys()) - provider_keys)
        if unknown:
            errors.append(f"providers.{provider} unknown keys: {', '.join(unknown)}")

    if errors:
        raise PolicyValidationError("; ".join(errors))

sed -n '400,460p' workspace/scripts/policy_router.py
    entry = {
        "ts": int(time.time() * 1000),
        "event": event_type,
    }
    if detail:
        entry["detail"] = detail
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _tacti_event(event_type, detail):
    if callable(tacti_emit):
        try:
            tacti_emit(str(event_type), detail if isinstance(detail, dict) else {"detail": detail})
            return
        except Exception:
            pass
    log_event(event_type, detail=detail, path=TACTI_EVENT_LOG)


def _flag_enabled(name):
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _active_inference_enabled():
    return _flag_enabled("OPENCLAW_ACTIVE_INFERENCE") or _flag_enabled("ENABLE_ACTIVE_INFERENCE")


def tacti_features_from_proprioception(snapshot):
    snap = dict(snapshot or {})
    arousal = 0.05
    if snap.get("error_rate", 0.0) and float(snap.get("error_rate", 0.0)) > 0.2:
        arousal = 0.2
    return {"arousal": float(arousal)}


def _legacy_tacti_flags_enabled():
    return any(
        _flag_enabled(name)
        for name in (
            "ENABLE_MURMURATION",
            "ENABLE_RESERVOIR",
            "ENABLE_PHYSARUM_ROUTER",
            "ENABLE_TRAIL_MEMORY",
        )
    )


def tacti_enhance_plan(plan, *, context_metadata=None, intent=None):
    plan_dict = dict(plan or {})
    plan_dict["enabled"] = bool(plan_dict.get("enabled", True))
    agent_ids = list(plan_dict.get("agent_ids") or [])
    if not agent_ids:
        maybe_agent = (context_metadata or {}).get("agent_id")
        if maybe_agent:
            agent_ids = [str(maybe_agent)]
    plan_dict["agent_ids"] = [str(a) for a in agent_ids if str(a).strip()]
    if intent and "intent" not in plan_dict:

sed -n '1,180p' workspace/scripts/audit_commit_hook.py
#!/usr/bin/env python3
"""
Pre-commit audit hook for teamchat auto-commit.
Ensures: stability, coherence, constitution/governance/ethos adherence.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WITNESS_LEDGER_PATH = WORKSPACE_ROOT / "state_runtime" / "teamchat" / "witness_ledger.jsonl"

try:
    from witness_ledger import commit as witness_commit
except Exception:  # pragma: no cover - optional integration
    witness_commit = None

# Checks to run before commit
CHECKS = [
    ("git_dirty", "Check for uncommitted changes"),
    ("no_merge_conflicts", "No merge conflicts in staging"),
    ("tests_pass", "Critical tests pass"),
    ("no_secrets", "No secrets accidentally staged"),
    ("governance_compliant", "Governance files intact"),
]


def _flag_enabled(name: str, default: str = "0") -> bool:
    value = str(os.environ.get(name, default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _commit_witness_entry(audit_entry: dict, audit_log: Path) -> tuple[bool, str]:
    if not _flag_enabled("OPENCLAW_WITNESS_LEDGER", default="1"):
        return True, "witness_disabled"
    if not callable(witness_commit):
        return False, "witness_unavailable"
    ledger_path = Path(
        os.environ.get("OPENCLAW_WITNESS_LEDGER_PATH", str(DEFAULT_WITNESS_LEDGER_PATH))
    )
    checks = audit_entry.get("checks", [])
    record = {
        "event": "governance_audit_commit",
        "audit_path": str(audit_log),
        "audit_type": str(audit_entry.get("type", "pre_commit_audit")),
        "audit_timestamp": str(audit_entry.get("timestamp", "")),
        "passed": bool(audit_entry.get("passed", False)),
        "checks_total": len(checks) if isinstance(checks, list) else 0,
        "checks_failed": sum(1 for row in checks if isinstance(row, dict) and not bool(row.get("passed", False))),
    }
    witness_commit(record=record, ledger_path=str(ledger_path))
    return True, "ok"

def run_check(name: str) -> tuple[bool, str]:
    """Run a specific check. Returns (passed, details)."""
    try:
        if name == "git_dirty":
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=10
            )
            has_changes = bool(result.stdout.strip())
            return has_changes, f"Changes detected: {len(result.stdout.strip().split(chr(10)))} files"
        
        if name == "no_merge_conflicts":
            result = subprocess.run(
                ["git", "diff", "--check"],
                cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0, "No merge conflicts" if result.returncode == 0 else result.stdout[:200]
        
        if name == "tests_pass":
            # Quick smoke test - just import check
            result = subprocess.run(
                ["python3", "-c", "import json; import pathlib"],
                cwd=WORKSPACE_ROOT, capture_output=True, timeout=10
            )
            return result.returncode == 0, "Python imports OK" if result.returncode == 0 else "Import failed"
        
        if name == "no_secrets":
            # Check for common secret patterns
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=10
            )
            files = result.stdout.strip().split("\n")
            forbidden = ["credentials", "secrets", "token", "password"]
            risky = [f for f in files if any(b in f.lower() for b in forbidden)]
            return len(risky) == 0, f"No secrets in {len(files)} files" if not risky else f"Risky files: {risky}"
        
        if name == "governance_compliant":
            # Check key governance files exist
            required = ["CONSTITUTION.md", "AGENTS.md", "SOUL.md"]
            missing = [r for r in required if not (WORKSPACE_ROOT / r).exists()]
            return len(missing) == 0, "All governance files present" if not missing else f"Missing: {missing}"
        
    except Exception as e:
        return False, f"Check error: {e}"
    
    return True, "Unknown check"

def audit_commit() -> bool:
    """Run pre-commit audit. Returns True if safe to commit."""
    print("=" * 50)
    print("🔍 PRE-COMMIT AUDIT")
    print("=" * 50)
    
    results = []
    all_passed = True
    
    for check_name, description in CHECKS:
        passed, details = run_check(check_name)
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}: {details}")
        results.append({"check": check_name, "passed": passed, "details": details})
        if not passed:
            all_passed = False
    
    # Emit audit event
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "pre_commit_audit",
        "passed": all_passed,
        "checks": results
    }
    
    audit_log = WORKSPACE_ROOT / "audit" / "commit_audit_log.jsonl"
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_log, "a") as f:
        f.write(json.dumps(audit_entry) + "\n")

    try:
        witness_ok, witness_reason = _commit_witness_entry(audit_entry, audit_log)
    except Exception as e:
        witness_ok, witness_reason = False, f"witness_error: {e}"
    if not witness_ok:
        strict = _flag_enabled("OPENCLAW_WITNESS_LEDGER_STRICT", default="0")
        if strict:
            all_passed = False
            print(f"❌ witness ledger commit failed (strict): {witness_reason}")
        else:
            print(f"⚠️ witness ledger commit skipped: {witness_reason}")
    
    print("=" * 50)
    if all_passed:
        print("✅ AUDIT PASSED - Safe to commit")
    else:
        print("❌ AUDIT FAILED - Commit blocked")
    print("=" * 50)
    
    return all_passed

if __name__ == "__main__":
    success = audit_commit()
    sys.exit(0 if success else 1)

sed -n '1,120p' workspace/hivemind/hivemind/dynamics_pipeline.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from .active_inference import replay_counterfactuals
from .flags import is_enabled
from .peer_graph import PeerGraph
from .physarum_router import PhysarumRouter
from .reservoir import Reservoir
from .trails import TrailStore


def _env_enabled(name: str) -> bool:
    return is_enabled(name)


def _env_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name, str(default))).strip()
    try:
        return int(raw)
    except Exception:
        return int(default)


def _norm(values: Dict[str, float]) -> Dict[str, float]:
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if hi - lo <= 1e-9:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


class TactiDynamicsPipeline:
    """
    Composes Murmuration + Reservoir + Physarum + Trails under feature flags.
    """

    def __init__(
        self,
        *,
        agent_ids: List[str],
        seed: int = 0,
        peer_k: int = 5,
        trail_store: TrailStore | None = None,
    ):
        self.agent_ids = sorted(dict.fromkeys(str(a) for a in agent_ids))
        self.seed = int(seed)
        self.enable_murmuration = _env_enabled("ENABLE_MURMURATION")
        self.enable_reservoir = _env_enabled("ENABLE_RESERVOIR")
        self.enable_physarum = _env_enabled("ENABLE_PHYSARUM_ROUTER")
        self.enable_trails = _env_enabled("ENABLE_TRAIL_MEMORY")
        self.enable_counterfactual = _env_enabled("OPENCLAW_COUNTERFACTUAL_REPLAY")
        self.peer_graph = PeerGraph.init(self.agent_ids, k=peer_k, seed=self.seed)
        self.reservoir = Reservoir.init(dim=32, leak=0.35, spectral_scale=0.9, seed=self.seed + 1)
        self.physarum = PhysarumRouter(seed=self.seed + 2)
        self.trails = trail_store or TrailStore()
        self._counterfactual_depth = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_MAX_DEPTH", 2))
        self._counterfactual_budget_ms = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_BUDGET_MS", 20))
        self._counterfactual_error_limit = max(1, _env_int("OPENCLAW_COUNTERFACTUAL_REPLAY_ERROR_LIMIT", 3))
        self._counterfactual_disabled_until = 0.0
        self._counterfactual_errors = 0

    def _trail_agent_bias(self, context_text: str, candidate_agents: List[str]) -> Dict[str, float]:
        if not self.enable_trails:
            return {a: 0.0 for a in candidate_agents}
        hits = self.trails.query(context_text, k=8)
        bias = {a: 0.0 for a in candidate_agents}
        for hit in hits:
            meta = hit.get("meta", {})
            if not isinstance(meta, dict):
                continue
            target = str(meta.get("agent", ""))
            signal = float(meta.get("reward", 0.0) or 0.0)
            if target in bias:
                bias[target] += signal * float(hit.get("effective_strength", 0.0))
        return bias

    def plan_consult_order(
        self,
        *,
        source_agent: str,
        target_intent: str,
        context_text: str,
        candidate_agents: List[str],
        n_paths: int = 3,
    ) -> Dict[str, Any]:
        source = str(source_agent)
        candidates = [str(a) for a in candidate_agents if str(a) and str(a) != source]
        if not candidates:
            return {
                "consult_order": [],
                "paths": [[source]],
                "reservoir": {"routing_hints": {"confidence": 0.0}},
                "scores": {},
            }

        paths = (
            self.physarum.propose_paths(source, target_intent, self.peer_graph, n_paths=n_paths)
            if self.enable_physarum
            else [[source] + self.peer_graph.peers(source)[:1]]
        )
        first_hop_votes: Dict[str, float] = {a: 0.0 for a in candidates}
        for idx, path in enumerate(paths):
            if len(path) < 2:
                continue
            hop = path[1]
            if hop in first_hop_votes:
                first_hop_votes[hop] += 1.0 / (1.0 + idx)

        peer_scores = {a: self.peer_graph.edge_weight(source, a) if self.enable_murmuration else 1.0 for a in candidates}
        trail_bias = self._trail_agent_bias(context_text, candidates)
        state = (
            self.reservoir.step(
                {"intent": target_intent, "context": context_text},
                {"source": source, "candidates": candidates},
                {"votes": first_hop_votes},

sed -n '60,110p' workspace/hivemind/hivemind/physarum_router.py
            path = [src, first]
            second_hops = [p for p in peer_graph.peers(first) if p != src]
            if second_hops:
                second_hops.sort(
                    key=lambda node: -(
                        self._get_conductance(first, node) * max(0.01, peer_graph.edge_weight(first, node))
                    )
                )
                if self._rng.random() < self.explore_rate:
                    self._rng.shuffle(second_hops)
                best_second = second_hops[0]
                path.append(best_second)
                self._known_neighbors.setdefault(first, set()).add(best_second)
            key = tuple(path)
            if key in seen:
                continue
            seen.add(key)
            paths.append(path)
            if len(paths) >= want:
                break
        return paths if paths else [[src]]

    def update(self, path: List[str], reward_signal: float, valence: float | None = None) -> None:
        reward = float(reward_signal)
        trail_valence_enabled = str(os.environ.get("OPENCLAW_TRAIL_VALENCE", "0")).strip().lower() in {"1", "true", "yes", "on"}
        if trail_valence_enabled and isinstance(valence, (int, float)):
            valence_adj = max(-1.0, min(1.0, float(valence)))
            reward = reward * (1.0 + (0.25 * valence_adj))
        if len(path) < 2:
            return
        for i in range(len(path) - 1):
            src = str(path[i])
            dst = str(path[i + 1])
            prev = self._get_conductance(src, dst)
            if reward >= 0.0:
                nxt = prev + (0.15 * reward)
            else:
                nxt = prev + (0.25 * reward)
            self._set_conductance(src, dst, nxt)

    def prune(self, min_k: int, max_k: int) -> None:
        lower = max(1, int(min_k))
        upper = max(lower, int(max_k))
        grouped: Dict[str, List[Tuple[str, float]]] = {}
        all_nodes = set()
        for edge, cond in self._conductance.items():
            src, dst = edge.split("->", 1)
            grouped.setdefault(src, []).append((dst, cond))
            all_nodes.add(src)
            all_nodes.add(dst)
        all_nodes.update(self._known_neighbors.keys())

sed -n '260,340p' core/system2/inference/router.js
        score
      });
    }
  }

  // Sort by score desc, then deterministic tie-break (provider_id, model_id).
  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    if (a.provider_id !== b.provider_id) return a.provider_id.localeCompare(b.provider_id);
    return a.model_id.localeCompare(b.model_id);
  });

  // Hard escape hatch: if local_vllm is available+healthy, never return empty.
  if (scored.length === 0 && localEnabled && (!available || available.has('local_vllm'))) {
    const h = providerHealth.local_vllm;
    const q = quotaState.local_vllm;
    const healthy = !h || h.ok;
    const quotaOk = !q || q.allowed;
    if (healthy && quotaOk) {
      scored.push({
        provider_id: 'local_vllm',
        model_id: 'AUTO_DISCOVER',
        reason: 'escape_hatch_local_vllm',
        score: 1000
      });
      explanation.push('escape_hatch_local_vllm: injected local_vllm as final fallback');
    }
  }

  if (scored.length === 0) {
    explanation.push('No eligible providers found for this request');
  } else {
    explanation.push(`Selected ${scored.length} candidate(s), top: ${scored[0].provider_id}/${scored[0].model_id}`);
    if (resolvedTier) {
      explanation.push(`TACTI(C)-R tier=${resolvedTier}`);
    }
  }

  const result = { candidates: scored, explanation };
  if (_flagEnabled('OPENCLAW_ROUTER_PROPRIOCEPTION')) {
    result.meta = { proprioception: _proprioceptionSample(params, scored) };
  }
  return result;
}

/**
 * "Explain routing" — human-readable output of routing decision.
 * @param {object} params - Same as routeRequest
 * @returns {string}
 */
function explainRouting(params) {
  const { candidates, explanation } = routeRequest(params);
  const lines = [
    '=== FreeComputeCloud Routing Decision ===',
    `Task class: ${params.taskClass}`,
    `Context length: ${params.contextLength || 'unknown'}`,
    `Latency target: ${params.latencyTarget || 'medium'}`,
    '',
    '--- Explanation ---',
    ...explanation,
    '',
    '--- Candidates (ranked) ---'
  ];

  if (candidates.length === 0) {
    lines.push('  (none)');
  } else {
    for (let i = 0; i < candidates.length; i++) {
      const c = candidates[i];
      lines.push(`  ${i + 1}. ${c.provider_id} / ${c.model_id}  [score=${c.score}]  (${c.reason})`);
    }
  }

  lines.push('=========================================');
  return lines.join('\n');
}

module.exports = { routeRequest, explainRouting };

sed -n '1,80p' env.d/system1-routing.env
# System-1 routing profile: LOCAL_FIRST with MiniMax fallback.
# Source this file in your shell before running System-1 routing checks.

ENABLE_FREECOMPUTE_CLOUD=1
ENABLE_LOCAL_VLLM=1
OPENCLAW_VLLM_BASE_URL=http://127.0.0.1:8001/v1
TACTI_CR_AROUSAL_OSC=1
OPENCLAW_TRAIL_VALENCE=1
OPENCLAW_COUNTERFACTUAL_REPLAY=1
OPENCLAW_ACTIVE_INFERENCE=1

# Candidate order is resolved by router scoring:
# local_vllm is preferred when enabled/reachable, minimax-portal is external fallback.
FREECOMPUTE_PROVIDER_ALLOWLIST=local_vllm,minimax-portal

# Do not store real secrets in git-tracked files.
# Set this in your shell or secret store before live fallback calls.
OPENCLAW_MINIMAX_PORTAL_API_KEY=__SET_IN_SHELL_OR_SECRET_STORE__
```

## Secret Scan Assessment
- `workspace/scripts/scan_audit_secrets.sh` was not present in this worktree.
- `workspace/scripts/hooks/pre-commit` exists but read-only all-files scan mode was unclear, so it was skipped per constraint.
- High-signal grep hits were limited to intentional test fixtures and historical audit text (`sk-TEST...`, `ghp_FAKE...`, `Bearer eyJhbGciOiJ` assertion fixture). No live credential material identified.

## Branch Diff Summary
- `git diff --shortstat origin/main...HEAD` => `109 files changed, 19442 insertions(+), 2782 deletions(-)`
- Change type counts: `59 A`, `49 M`, `1 R100`
- Top touched path groups (by changed file count):
  - `workspace/tacti` (26)
  - `workspace/tacti_cr` (25)
  - `workspace/audit` (9)
  - `workspace/scripts` (4)
  - `workspace/memory` (4)
  - `workspace/knowledge_base` (4)
  - `workspace/research` (3)
  - `workspace/hivemind` (2)
  - `workspace/briefs` (2)
  - `workspace/teamchat` (1)

## PR Draft
### Title
feat(wirings): integrate router/KB/governance hooks with guarded flags and audit evidence

### Body
## Summary
- Router wiring: policy router now supports active-inference decision path behind flag (`OPENCLAW_ACTIVE_INFERENCE` / `ENABLE_ACTIVE_INFERENCE`) with fallback behavior preserved on errors.
- Router wiring: oscillatory gating is invoked under `TACTI_CR_AROUSAL_OSC`; integration is additive to existing routing flow.
- Router telemetry: JS inference router attaches proprioception sample metadata when `OPENCLAW_ROUTER_PROPRIOCEPTION=1`.
- Governance/audit: audit commit hook chains records through witness ledger when enabled and supports strict fail-closed mode via a separate strict flag.
- KB wiring: prefetch path in KB now uses `PrefetchCache` instead of stubbed context prefetch behavior.
- ITC pipeline wiring: ingestion boundary forwards parsed events to ITC classifier path instead of dead-ending.
- Hivemind wiring: physarum trail updates accept valence weighting under `OPENCLAW_TRAIL_VALENCE`; dynamics pipeline enables guarded counterfactual replay under `OPENCLAW_COUNTERFACTUAL_REPLAY` with depth/time/error circuit breakers.
- Research wiring: ingest path now runs gap analysis and publishes summarized gap artifacts into KB.
- Daily brief wiring: automation command runs best-effort narrative distillation pre-step (`OPENCLAW_NARRATIVE_DISTILL=1`) before briefing generation.
- Namespace and migration continuity: `workspace/tacti` canonical module set added while `workspace/tacti_cr` compatibility path remains and is regression-tested.

## Flags / Defaults
- `OPENCLAW_WITNESS_LEDGER` (default `1` in `workspace/scripts/audit_commit_hook.py`)  
  Effect: enables witness ledger commit chaining for governed audit commit hook.
- `OPENCLAW_WITNESS_LEDGER_STRICT` (default `0` in `workspace/scripts/audit_commit_hook.py`)  
  Effect: when `1`, witness commit errors fail closed; when `0`, they warn/degrade.
- `OPENCLAW_WITNESS_LEDGER_PATH` (default constant path in `workspace/scripts/audit_commit_hook.py`)  
  Effect: override ledger file location.
- `OPENCLAW_ACTIVE_INFERENCE` / `ENABLE_ACTIVE_INFERENCE` (default off unless env-set truthy in `workspace/scripts/policy_router.py`)  
  Effect: enables active-inference router decision path.
- `TACTI_CR_AROUSAL_OSC` (flag-gated in `workspace/scripts/policy_router.py`; set to `1` in `env.d/system1-routing.env`)  
  Effect: enables oscillatory arousal gating in routing.
- `OPENCLAW_ROUTER_PROPRIOCEPTION` (default off in router/policy code unless env truthy)  
  Effect: includes proprioception sample in router metadata.
- `OPENCLAW_TRAIL_VALENCE` (default `0` in `workspace/hivemind/hivemind/physarum_router.py`; set to `1` in `env.d/system1-routing.env`)  
  Effect: valence-weighted trail updates.
- `OPENCLAW_COUNTERFACTUAL_REPLAY` (default off in `workspace/hivemind/hivemind/dynamics_pipeline.py`; set to `1` in `env.d/system1-routing.env`)  
  Effect: enables counterfactual replay path.
- `OPENCLAW_COUNTERFACTUAL_REPLAY_MAX_DEPTH` (default `2`)  
  Effect: bounds replay exploration depth.
- `OPENCLAW_COUNTERFACTUAL_REPLAY_BUDGET_MS` (default `20`)  
  Effect: per-decision time budget for replay.
- `OPENCLAW_COUNTERFACTUAL_REPLAY_ERROR_LIMIT` (default `3`)  
  Effect: auto-disable threshold after repeated replay errors.
- `OPENCLAW_NARRATIVE_DISTILL` (set to `1` in daily briefing cron command pre-step)  
  Effect: runs distillation best-effort before briefing.

Code paths are mostly gated, but this branch also sets several env flags ON in `env.d/system1-routing.env` (`TACTI_CR_AROUSAL_OSC=1`, `OPENCLAW_TRAIL_VALENCE=1`, `OPENCLAW_COUNTERFACTUAL_REPLAY=1`, `OPENCLAW_ACTIVE_INFERENCE=1`), so behavior changes are active for deployments using that env file.

## Blast Radius
- `workspace/scripts/policy_router.py` and `core/system2/inference/router.js`: primary runtime routing and response metadata paths.
- `workspace/hivemind/hivemind/{dynamics_pipeline.py,physarum_router.py}`: routing dynamics and trail updates.
- `workspace/knowledge_base/{kb.py,...}` + `workspace/research/research_ingest.py`: prefetch/research ingest and KB write paths.
- `workspace/scripts/audit_commit_hook.py`: governance log chain behavior and commit hook outcomes.
- `workspace/automation/cron_jobs.json`: daily briefing automation command path.

Even with feature flags off, touched files alter integration seams (hook invocation points, module imports, and guard paths), so regressions can appear in router/governance entry points.

## Validation
```bash
npm test
python3 -m unittest
python3 -m unittest tests_unittest.test_goal_identity_invariants -v
```
All PASS in `/tmp/wt_wirings_integration` during this prep run.

## Governance / Evidence
- `/Users/heathyeager/clawd/workspace/audit/wirings_worktree_reconciliation_20260222T000206Z.md`
- `/Users/heathyeager/clawd/workspace/audit/stash_integration_20260222.md`
- This prep audit: `workspace/audit/wirings_pr_prep_20260222T001629Z.md`

No tracked `/tmp` paths detected in branch tree; `workspace/mlx_audit.zip` is excluded and unreferenced.

## Rollback
- If merged via merge commit:
```bash
git revert -m 1 <merge_sha>
```
- If squashed:
```bash
git revert <squash_sha>
```
Expected side effects: docs/audit artifacts, data/KB updates, and wiring changes all revert together.

## Open Questions
- `workspace/teamchat/sessions/tacti_architecture_review.jsonl` remains ignored and excluded from versioned stash integration; confirm whether session artifacts should stay non-versioned.

## No-Code-Change Confirmation
- No source code changes were made in this PR-prep pass.
- Only this append-only audit artifact was created/updated.

## Supplemental Diff Count Evidence
```bash
git diff --shortstat origin/main...HEAD
 109 files changed, 19442 insertions(+), 2782 deletions(-)

git diff --name-status origin/main...HEAD | awk '{print $1}' | sort | uniq -c
  59 A
  49 M
   1 R100
```

## Phase 0 (Execution) 2026-02-22T01:07:52Z
```bash
git status --porcelain -uall
?? workspace/audit/wirings_pr_prep_20260222T001629Z.md

git rev-parse --abbrev-ref HEAD
codex/feat/wirings-integration-20260222

git rev-parse HEAD
a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f

git fetch origin
error: cannot open '/Users/heathyeager/clawd/.git/worktrees/wt_wirings_integration/FETCH_HEAD': Operation not permitted

## Phase 0 (Execution) 2026-02-22T01:08:24Z
```bash
git status --porcelain -uall
?? workspace/audit/wirings_pr_prep_20260222T001629Z.md

git rev-parse --abbrev-ref HEAD
codex/feat/wirings-integration-20260222

git rev-parse HEAD
a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f

git fetch origin

git rev-parse origin/codex/feat/wirings-integration-20260222
a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f

git rev-parse HEAD
a3cb70f3dd0d0be0cc43a5fdc2fd93aa17224d5f
```
- parity_check: PASS
