# Wirings Merge Evidence Remediation

## What Went Wrong
- PR #40 was merged to `main` at `dbbb1909ad550e76080aba98255b95ac54da436f`.
- Merge evidence file was created in the wirings feature worktree/branch instead of canonical `main`.
- Expected `main` worktree path `/private/tmp/wt_docs_main` was missing even though `git worktree list` still showed it as `prunable`.

## Remediation Performed
1. Re-established a usable `main` worktree at `/tmp/wt_docs_main`.
2. Fast-forwarded `main` to `origin/main` (`dbbb190...`).
3. Copied merge evidence file from wirings worktree source:
   - Source: `/tmp/wt_wirings_integration/workspace/audit/wirings_pr_merge_evidence_20260222T011423Z.md`
   - Target: `workspace/audit/wirings_pr_merge_evidence_20260222T011423Z.md`
4. Committed and pushed on `main`:
   - Commit: `852b4bb`
   - Message: `docs(audit): record PR#40 merge evidence for wirings integration`

## Evidence (Concise)
- `git branch -r --contains dbbb1909ad550e76080aba98255b95ac54da436f` => `origin/main`.
- `git log -1 --oneline origin/main` after push => `852b4bb docs(audit): record PR#40 merge evidence for wirings integration`.
- `git show --name-only --oneline origin/main` includes:
  - `workspace/audit/wirings_pr_merge_evidence_20260222T011423Z.md`

## Policy Decision: Feature Branch Cleanup
- Default policy applied: **NO rewrite performed** on `codex/feat/wirings-integration-20260222`.
- Reason: branch is already merged; post-merge feature-branch commit is harmless.
- Optional cleanup (not executed unless explicitly requested):
  - `git reset --hard 9cb160b`
  - `git push --force-with-lease`
