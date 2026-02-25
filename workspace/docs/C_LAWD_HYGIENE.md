# C_LAWD Hygiene (Operational)

## Tracked vs Local-Only
- Tracked files are for durable source, tests, and governed docs.
- Local-only artifacts must not be left as untracked noise in source trees.
- If content is temporary/scratch, keep it in `workspace/audit/_scratch_local/` or outside the repo.

## Local Excludes (Repo-Local)
- Use `.git/info/exclude` for local-only artifact roots:
  - `.worktrees/`
  - `workspace/research/pdfs/`
  - `workspace/state_runtime/memory_ext/`
- Use helper (opt-in write only):
  - `python3 -m workspace.scripts.local_git_exclude --print`
  - `OPENCLAW_ALLOW_LOCAL_GIT_EXCLUDE_WRITE=1 python3 -m workspace.scripts.local_git_exclude --install`

## Clean Commit Window
- Before merges/tags/commits:
  - enable quiesce (`source workspace/scripts/quiesce_on.sh`)
  - verify clean tracked state (`git status --porcelain`)
  - run preflight and tests
- Do not snapshot runtime drift together with feature changes.
