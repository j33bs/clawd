# System-2 Notes (2026-02-17)

This note is evidence-based from the current branch and repository paths. It is not an exhaustive codebase audit.

## Branch And Landed Commits

- Branch: `codex/task-system2-policy-hardening-cap-20260217`
- Commit range reviewed: `79eda82..587a011`

1. `79eda82` `policy(routing): Tier-2 OpenAI split brain (5.2) then muscle (5.3 codex)`
2. `7f72687` `harden(integrity): enforce governance hash anchors at runtime`
3. `c1e79e3` `harden(context): add sanitizer + canonical memory writer`
4. `858fac7` `harden(tools): enforce allow/ask/deny policy at edge boundary`
5. `47bc0a6` `cap(patterns): add session inefficiency detector and report output`
6. `5f2708b` `cap(skill): add feature-flagged skill composer constrained by governance`
7. `0fc110a` `cap(moltbook): add feature-flagged local activity tracker`
8. `1ba79a4` `cap(anticipate): add suggestion-only proactive workflow hints`
9. `050cbb2` `cap(tacticr): add append-only feedback log and atomic writer`
10. `587a011` `test(gov): ignore local .claude/.openclaw root artifacts in auto-ingest gate`

## What Failed And Why (Auto-Ingest)

Observed failure mode before fix:
- Governance auto-ingest gate treated local-only root artifacts as drift and was inconsistent on partial known sets/non-regular entries.
- Runtime expectation needed to allow local-only artifacts while preserving fail-closed behavior for unknown repo-root drift.

Fix intent and policy impact:
- Added narrow explicit ignore set for local-only root artifacts.
- Kept fail-closed behavior for any non-ignorable untracked root path.
- Enforced exact known governance stray set before ingest and fail-closed on non-regular file types.

Behavior after fix:
- Ignored artifacts: `.claude/*`, `.openclaw/*` (including `.openclaw/workspace-state.json`), `.DS_Store`.
- Unknown root drift still stops preflight.

## Observed Invariants And Operational Constraints

- Governance canonicality verifier remains fail-closed and must keep passing:
  - `workspace/scripts/verify_goal_identity_invariants.py`
- Allowed local untracked artifacts for this workspace:
  - `.claude/worktrees/*`
  - `.openclaw/workspace-state.json`
- Those artifacts remain uncommitted by policy.

## Evidence Anchors

Policy split and coding ladder:
- `workspace/policy/llm_policy.json:119`
- `workspace/policy/llm_policy.json:132`
- `workspace/policy/llm_policy.json:214`
- `workspace/policy/llm_policy.json:215`

Governance auto-ingest hardening:
- `workspace/scripts/preflight_check.py:73`
- `workspace/scripts/preflight_check.py:166`
- `workspace/scripts/preflight_check.py:423`

Auto-ingest tests:
- `tests_unittest/test_governance_auto_ingest.py:28`
- `tests_unittest/test_governance_auto_ingest.py:80`
- `tests_unittest/test_governance_auto_ingest.py:116`
- `tests_unittest/test_governance_auto_ingest.py:156`

Integrity anchor enforcement and hook point:
- `core/system2/security/integrity_guard.js:7`
- `core/system2/security/integrity_guard.js:252`
- `core/system2/inference/provider_registry.js:374`
- `workspace/scripts/approve_integrity_baseline.sh:15`

Context sanitizer and memory writer seam:
- `core/system2/context_sanitizer.js:20`
- `core/system2/memory/memory_writer.js:43`

Tool governance decision seam:
- `core/system2/security/tool_governance.js:32`
- `core/system2/security/ask_first.js:21`
- `core/system2/security/ask_first.js:51`

CAP modules:
- `scripts/analyze_session_patterns.js:172`
- `core/system2/skill_composer.js:9`
- `scripts/moltbook_activity.js:53`
- `core/system2/anticipate.js:18`
- `core/system2/memory/tacticr_feedback_writer.js:39`

Policy load point for next hardening slice:
- `workspace/scripts/policy_router.py:203`
- `workspace/scripts/policy_router.py:496`

## Residual Risks And Next Work

1. `load_policy()` currently merges defaults and logs parse failures, but does not hard-fail on policy shape drift/typos.
2. Unknown whether any external runtime path (outside this repo) loads `llm_policy.json` in JS; no in-repo JS policy loader was found.
3. Router safety relies on policy correctness; schema validation at load time is the smallest next hardening step.
4. System-1 trading files exist (`scripts/sim_runner.py`, `core_infra/*`, `pipelines/system1_trading.features.yaml`) but are out-of-scope for this System-2 PR.
