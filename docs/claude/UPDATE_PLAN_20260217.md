# Update Plan (Normalized, 20 Items) - 2026-02-17

Scope note:
- This roadmap is evidence-based for this repository and current branch state.
- System-1 trading activation and behavior changes are explicitly out-of-scope for this PR.

Normalized backlog count:
- 20 items total.
- Stage 0 complete: 11 items.
- Stage 1-3 queued: 9 items.

## Stage 0 (Already Done)

1. `U01` Policy split for Tier-2 OpenAI brain/muscle.
- Scope: System-2
- Target files: `workspace/policy/llm_policy.json`, `workspace/scripts/verify_coding_ladder.sh`, `workspace/scripts/verify_policy_router.sh`, `workspace/MODEL_ROUTING.md`
- Acceptance: coding order is free -> brain -> muscle, verify scripts pass
- Gates: `bash workspace/scripts/verify_llm_policy.sh`, `bash workspace/scripts/verify_policy_router.sh`, `bash workspace/scripts/verify_coding_ladder.sh`
- Risks: policy drift without loader-time schema checks

2. `U02` Runtime integrity guard + baseline approval path.
- Scope: System-2
- Target files: `core/system2/security/integrity_guard.js`, `workspace/governance/INTEGRITY_BASELINE.json`, `workspace/scripts/approve_integrity_baseline.sh`
- Acceptance: fail-closed on hash drift, explicit approval updates baseline
- Gates: `node tests/integrity_guard.test.js`
- Risks: baseline update discipline required

3. `U03` Hook integrity guard at inference choke point.
- Scope: System-2
- Target files: `core/system2/inference/provider_registry.js`
- Acceptance: request path enforces integrity before dispatch
- Gates: `node tests/integrity_guard.test.js`
- Risks: runtime stop if baseline missing/invalid

4. `U04` Context sanitizer module and canonical memory write seam.
- Scope: System-2
- Target files: `core/system2/context_sanitizer.js`, `core/system2/memory/memory_writer.js`
- Acceptance: tool-shaped/role-shaped injections redacted, human text preserved
- Gates: `node tests/context_sanitizer.test.js`, `node tests/memory_writer.test.js`
- Risks: false positives in sanitization patterns

5. `U05` Central tool governance decision policy.
- Scope: System-2
- Target files: `core/system2/security/tool_governance.js`, `core/system2/security/ask_first.js`, `scripts/system2_http_edge.js`
- Acceptance: deterministic allow/ask/deny for exec/network/write-outside-workspace
- Gates: `node tests/tool_governance.test.js`, `node tests/ask_first_tool_governance.test.js`, `node tests/tool_governance_edge_hook.test.js`
- Risks: policy tuning tradeoffs for operator friction

6. `U06` Session pattern detector (offline report).
- Scope: System-2
- Target files: `scripts/analyze_session_patterns.js`, `workspace/reports/README.md`
- Acceptance: deterministic report generation from local artifacts
- Gates: `node tests/analyze_session_patterns.test.js`
- Risks: heuristic categorization quality

7. `U07` Feature-flagged skill composer constrained by tool governance.
- Scope: System-2
- Target files: `core/system2/skill_composer.js`
- Acceptance: default-off, cannot bypass governance decisions
- Gates: `node tests/skill_composer.test.js`
- Risks: workflow composition quality under sparse context

8. `U08` Feature-flagged moltbook tracker (local/stub default).
- Scope: System-2
- Target files: `scripts/moltbook_activity.js`
- Acceptance: monthly report output with local input source
- Gates: `node tests/moltbook_activity.test.js`
- Risks: stub-vs-live ingestion confusion

9. `U09` Suggestion-only anticipation module.
- Scope: System-2
- Target files: `core/system2/anticipate.js`
- Acceptance: suggestions only; no auto-enable side effects
- Gates: `node tests/anticipate.test.js`
- Risks: noisy suggestions

10. `U10` TACTI(C)-R append-only feedback log + writer.
- Scope: System-2
- Target files: `workspace/memory/tacticr_feedback.jsonl`, `core/system2/memory/tacticr_feedback_writer.js`
- Acceptance: atomic append and schema-enforced write path
- Gates: `node tests/tacticr_feedback_writer.test.js`
- Risks: concurrency edge cases on non-POSIX filesystems

11. `U11` Governance auto-ingest local-artifact ignore fix while preserving fail-closed unknown drift behavior.
- Scope: System-2 governance preflight
- Target files: `workspace/scripts/preflight_check.py`, `tests_unittest/test_governance_auto_ingest.py`
- Acceptance: `.claude/.openclaw` ignored; unknown root files still stop
- Gates: `python3 -m unittest -v tests_unittest.test_governance_auto_ingest`
- Risks: allowlist must remain narrow

## Stage 1 (Immediate Next, High Leverage, System-2 Safe)

12. `U12` Fail-closed `llm_policy` schema validation at load time.
- Scope: System-2
- Target files: `workspace/policy/llm_policy.schema.json`, `workspace/scripts/policy_router.py`, `tests_unittest/test_llm_policy_schema_validation.py`
- Acceptance: invalid shape/typo policy raises deterministic validation error in strict mode
- Gates: `python3 -m unittest -v tests_unittest.test_llm_policy_schema_validation`, `bash workspace/scripts/verify_llm_policy.sh`, `bash workspace/scripts/verify_policy_router.sh`
- Risks: legacy permissive policy files break until fixed

13. `U13` Document strict-mode override semantics if needed.
- Scope: System-2
- Target files: `workspace/MODEL_ROUTING.md` (or focused policy docs)
- Acceptance: explicit default strict behavior and override caveat documented
- Gates: docs review
- Risks: operational misuse of override

14. `U14` Add a bad-policy fixture/regression test in verify layer.
- Scope: System-2
- Target files: `workspace/scripts/verify_policy_router.sh` and/or Python unittest fixture
- Acceptance: typo in critical key fails CI gate
- Gates: `bash workspace/scripts/verify_policy_router.sh`
- Risks: brittle fixture maintenance

15. `U15` Add preflight check integration assertion for strict loader errors.
- Scope: System-2
- Target files: `workspace/scripts/preflight_check.py`, relevant tests
- Acceptance: preflight reports clear policy validation failure
- Gates: targeted unittest + `npm test`
- Risks: duplicate error surfaces if not normalized

## Stage 2 (Near-Term)

16. `U16` Add deterministic policy schema evolution/versioning note.
- Scope: System-2
- Target files: `workspace/policy/llm_policy.schema.json`, policy docs
- Acceptance: controlled additions without breaking strict checks
- Gates: schema + verifier tests
- Risks: accidental over-specification blocking valid configs

17. `U17` Extend context-boundary sanitizer test corpus from real local fixtures.
- Scope: System-2
- Target files: `tests/context_sanitizer.test.js`, optional fixture files
- Acceptance: increased coverage of tool-shaped payload variants
- Gates: `node tests/context_sanitizer.test.js`
- Risks: false positive/false negative balance

18. `U18` Add observability counters for tool governance decisions.
- Scope: System-2
- Target files: `core/system2/security/ask_first.js`, `core/system2/observability/*`
- Acceptance: emits allow/ask/deny decision events without leaking secrets
- Gates: governance + observability tests
- Risks: log volume increase

## Stage 3 (Later / Explicitly Out-of-Scope For This PR)

19. `U19` Evaluate System-2 pre-dispatch context limit hard-stop strategy.
- Scope: System-2
- Target files: `core/system2/inference/provider_registry.js`, tests around dispatch compaction/limits
- Acceptance: deterministic local stop on over-context policy where desired
- Gates: targeted JS tests + `npm test`
- Risks: behavior change from current compaction-first approach

20. `U20` System-1 trading activation and feature toggles (out-of-scope for this PR).
- Scope: System-1
- Target files (exist in repo, not changed in this PR): `scripts/sim_runner.py`, `core_infra/*`, `pipelines/system1_trading.features.yaml`
- Acceptance: separate PR with its own validation gates
- Gates: System-1 simulation/test pipeline only
- Risks: cross-system coupling if mixed into System-2 PR
