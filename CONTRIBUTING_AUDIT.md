# Contributing Audit Rules

## Scope
These rules apply to humans and agents producing system contributions.

## Rules
- Keep diffs minimal and reversible.
- Never bypass governance hooks.
- Never log raw prompts, tokens, or secrets.
- For routing/provider/gate changes, add a change capsule and run gates.
- Use explicit operator summaries: changed, verified, blocked, next action.
- Stop on first failure and report exact command output.

## Evidence Standard
Every non-trivial contribution must include:
- Intent/design brief
- Verification commands and results
- Rollback command(s)
- Risk and kill-switch
- Post-mortem placeholder
