# Open Questions Instrumentation Audit (2026-02-24)

- Branch: `codex/chore/open_questions_instrumentation_20260223`
- Request-scoped commit: `c8dbdce`

## Invariant Checklist

- [x] Clean worktree used from `origin/main` via separate worktree.
- [x] Content ported manually; no cherry-pick.
- [x] Requested content applied to `workspace/governance/OPEN_QUESTIONS.md`.
- [x] Before first commit, `git status --porcelain -uall` showed only `workspace/governance/OPEN_QUESTIONS.md` changed.
- [x] First commit diff was additions-only (`new file`, no deletions).

## Sections Added

- `Guiding Principle (Added 2026-02-24)` + `Status Tags` legend.
- `Instrumentation Index (Append-Only)` with placeholder row and first Φ row.
- Append-only annotations for Φ and identity/edit continuity.
- Micro-sections: `Decision Rule: When a Question Ages`, `What Counts as an Experiment Here`, `Audit Hook`, `Non-Goals`.
- Appended heading: `## XXXIV. ChatGPT — After Instrumentation (2026-02-24)`.

## Reversibility

- Revert first commit only:
  - `git revert c8dbdce`
- Revert both (audit + content) in reverse order after second commit:
  - `git revert <audit_commit_sha> && git revert c8dbdce`
