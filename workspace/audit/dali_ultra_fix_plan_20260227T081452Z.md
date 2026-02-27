# DALI ULTRA Fix Plan (Proposal Only)

- UTC generated: 2026-02-27T08:17:42Z
- Scope: resolve Phase 1 drift gate blockers with smallest reversible actions first.
- Mode: proposal only, no code edits performed.

## Proposed Changes (Smallest Reversible First)

1. Isolate runtime/state artifacts from canonical repo checks.
- File path: .gitignore (or equivalent repo ignore policy file)
- Insertion point: existing runtime/state ignore section
- Proposal: ensure generated paths are ignored if intentional:
  - workspace/state_runtime/
  - workspace/audit/evidence/
  - workspace/audit/*.md (only if audit docs are ephemeral)

2. Remove or formalize skip-worktree usage for policy-critical files.
- File path: workspace/state/tacti_cr/events.jsonl (currently skip-worktree)
- Insertion point: git hygiene policy doc / setup scripts
- Proposal: replace ad-hoc skip-worktree with explicit generated-file policy and validation gate.

3. Add pre-audit drift gate automation.
- File path: workspace/scripts/pre_audit_gate.sh (new)
- Insertion point: workspace/scripts/
- Proposal: script exits non-zero if tracked drift or unexpected skip-worktree entries are present; prints deterministic remediation guidance.

4. Add CI guard for repository hygiene.
- File path: CI workflow config (e.g. .github/workflows/repo_hygiene.yml)
- Insertion point: workflow list
- Proposal: scheduled/manual job that runs:
  - git status --porcelain
  - git ls-files -v | grep '^S'
  - audit artifact policy check

5. Optional: separate audit outputs into dedicated ignored workspace root.
- File path: AGENTS.md or audit runbook doc
- Insertion point: audit output conventions section
- Proposal: route all generated audit artifacts to an ignored, policy-approved directory to avoid contaminating drift checks.

## Rollback Steps

1. Revert ignore-policy edits with git checkout -- <file> (for only files touched by the fix PR).
2. Remove added script/workflow files with git rm and revert commit.
3. Disable CI hygiene job by reverting workflow commit.

## Validation Tests

1. Run pre-audit gate on a clean tree; expect pass.
2. Introduce synthetic untracked/runtime file; expect gate fail with clear message.
3. Add synthetic skip-worktree mark; expect gate fail.
4. Confirm audit start no longer self-triggers drift from expected generated artifacts.

## Why LOAR-Aligned

- Uses policy knobs and guardrails (ignore policy, gates, CI checks) rather than runtime rewrites.
- Reversible and incremental; each change can be independently rolled back.
- Deterministic outcomes with explicit pass/fail conditions.
