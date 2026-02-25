# Dali audit — merge PR #43

## Starting state
- Branch (pre-merge): codex/fix/baseline-governance-unittest-20260224
- HEAD (pre-merge): fb3b2be08a157409c5773c439af88996b4873118
- Known pre-existing drift: workspace/state/tacti_cr/events.jsonl (stashed to prevent scope creep)

## PR
- PR: #43 (j33bs/clawd)
- Merge method: squash
- Branch delete: true
- PR state: MERGED at 2026-02-24T21:15:06Z
- Merge commit (GitHub): b7f7a43c3dee3669f945390b19be53ac1c8750cd

## Commands run (verbatim)
```bash
git status --porcelain
git restore --staged workspace/state/tacti_cr/events.jsonl
 git stash push -m "preexisting-drift:tacti_cr/events.jsonl" -- workspace/state/tacti_cr/events.jsonl

gh auth status
gh pr view 43 --repo j33bs/clawd --json state,mergeStateStatus,headRefName,baseRefName,title,url
gh pr checks 43 --repo j33bs/clawd
gh pr merge 43 --repo j33bs/clawd --squash --delete-branch

git fetch origin
git worktree prune
git checkout main
git pull --ff-only origin main
git log --oneline --decorate -3

python3 -m unittest -v
node --test tests/freecompute_cloud.test.js
node --test tests/integrity_guard.test.js
node --test tests/model_routing_no_oauth.test.js
node --test tests/provider_diag_coder_reason.test.js

git stash list | head
git stash show -p stash@{0} | head -50
git stash pop || true
git status --porcelain
```

## Results
- PR pre-merge checks:
  - ci: pass
  - node-test: pass
- Merge command exit: 0
- Local main sync:
  - checkout main: success
  - pull --ff-only: success
  - local main HEAD after sync: e97d210e52a2dc5779538241d51e7b28d2f5bf39
  - PR merge commit is ancestor of local main: exit code 0 (0 means yes)
- Post-merge sanity exits:
  - python3 -m unittest -v: 0
  - node --test tests/freecompute_cloud.test.js: 0
  - node --test tests/integrity_guard.test.js: 0
  - node --test tests/model_routing_no_oauth.test.js: 0
  - node --test tests/provider_diag_coder_reason.test.js: 0
- Key summaries:
  - unittest: Ran 242 tests (exit 0)
  - freecompute/integrity/model_routing/provider_diag TAP suites: pass 1, fail 0

## Drift handling
- events.jsonl was stashed before merge and kept out of merge/doc commits.
- stash pop was attempted after sanity and safely aborted due existing local changes to the same file.
- current local drift remains uncommitted:
  - workspace/state/tacti_cr/events.jsonl

## Rollback
- Revert merge on main (if needed): git revert b7f7a43c3dee3669f945390b19be53ac1c8750cd
- Re-run: python3 -m unittest -v
