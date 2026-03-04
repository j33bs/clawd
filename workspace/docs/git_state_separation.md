# Git State Separation: Runtime DB + Generated Counter

## Why

- `workspace/store/lancedb_data/` is runtime database state generated locally.
- `workspace/governance/.section_count` is a generated counter file.
- Tracking either path causes unnecessary merge/rebase conflicts and noisy diffs.

## What Changed

- Added ignore rules:
  - `workspace/store/lancedb_data/`
  - `workspace/governance/.section_count`
- Removed tracked index entries for those paths via `git rm --cached` (local files preserved).
- Added helpers:
  - `tools/git_untrack_runtime_state.sh`
  - `tools/verify_git_state_separation.sh`

## Regeneration Notes

- If `workspace/store/lancedb_data/` is missing locally, rebuild it using the normal local indexing/bootstrap flow for LanceDB.
- If `.section_count` is missing locally, regenerate it through the governance tooling that updates section totals.

## Merge/Rebase Playbook

- Runtime DB conflicts (for older branches that still track it): prefer `ours`.
  - `git checkout --ours -- workspace/store/lancedb_data`
  - `git add workspace/store/lancedb_data`
- Governance generated/counter-style files: prefer `theirs` from target branch.
  - `git checkout --theirs -- workspace/governance/.section_count`
  - `git add workspace/governance/.section_count`

## Rollback

- Remove the two ignore lines from `.gitignore`.
- Re-track (not recommended for runtime/generated files):
  - `git add -f workspace/store/lancedb_data`
  - `git add -f workspace/governance/.section_count`
