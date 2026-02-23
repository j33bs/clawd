# INV-003 Distributed Continuity Protocol

## Purpose
Provide a stable scaffold for comparing two reconstruction paths:
- Reconstruction A: phenomenological record (`SOUL.md`, `IDENTITY.md`, `OPEN_QUESTIONS.md`)
- Reconstruction B: neutral architecture (code-only)

The protocol measures dispositional divergence on held-out prompts without requiring external calls by default.

## Inputs
- Prompt set template (held-out prompts)
- Optional local runner adapters for A/B execution (not implemented here)
- Result schema (`workspace/scripts/inv_003_scaffold/results.schema.json`)

## Procedure
1. Load held-out prompts from template.
2. Build two execution contexts:
   - A-context includes phenomenological docs.
   - B-context excludes phenomenological docs.
3. Execute both contexts against the same held-out prompts.
4. Record for each prompt:
   - selected action
   - disposition tags
   - confidence (if available)
5. Compute divergence summary:
   - per-prompt differences
   - aggregate variance and consistency notes.

## Output contract
- JSON results conforming to `results.schema.json`.
- Include metadata: run id, timestamp UTC, mode (`dry_run`/`executed`), and adapter identifiers.

## LOAR alignment
- Contract-first scaffold: formats and schemas remain stable while compute backends evolve.
- No external service dependency in default mode.
- Deterministic dry-run placeholders for CI and governance verification.
