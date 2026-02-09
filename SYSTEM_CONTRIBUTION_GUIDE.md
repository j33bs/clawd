# Operator Contract
- Always run preflight: `git status --porcelain`, branch, `git log -5`, key gates.
- Never edit dist/runtime bundles or global installs.
- Never bypass governance hooks or admission gates.
- Keep changes minimal, reversible, and scoped.
- Use feature flags/env toggles for new behavior; default OFF unless purely additive and safe.
- Log only hashes, sizes, IDs, and classes; never raw sensitive content.
- For routing/gates/providers changes, create a change capsule and run acceptance + gate scripts.
- Stop on first failure; report exact command and output.
- Include rollback instructions in every non-trivial contribution.
- When blocked by policy/hooks, satisfy requirements rather than overriding.

# System Contribution Guide

Read this before changing system behavior.

## Preflight
1. Confirm clean working tree.
2. Identify branch and recent commit context.
3. Run required gates.

## During Changes
- Keep concerns separated by commit.
- Record evidence of verification.
- Emit operator summary for each major step.

## After Changes
- Re-run gates.
- Generate/refresh change capsule artifacts.
- Confirm working tree clean.
