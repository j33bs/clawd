# Change Admission Gate Record — Telegram/local-fallback merge

## Design brief
- Merge feature-telegram-local-fallback into main; scope limited to docs/design, tests, core telegram + continuity + local providers, and .gitignore ignores.

## Evidence pack
- All tests passing (telegram/backoff/continuity/local_fallback + chain suite).
- Commit history: design brief (baf7ded), tests (3e385dc), implementation (b981c2b).

## Rollback plan
- git revert the merge commit (and any follow-up .gitignore conflict-resolution commit) if instability is detected.

## Budget envelope
- Token budget: none required for runtime; CI/local tests only.
- Time budget: single merge + verification sweep.

## Expected ROI
- Enables governed Telegram/local-fallback + continuity modules on main with tests and design brief; improves reliability and auditability.

## Kill-switch
- Disable gateway/telegram invocation via existing router/config toggles; revert commits if needed.

## Post-mortem
- Record any merge issues (gitignore conflicts, permissions) and mitigations after completion.
