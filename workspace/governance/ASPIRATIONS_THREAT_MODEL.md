# Aspirations Threat Model (Fulfillment As Attack Surface)

Purpose: treat "aspirational" goals as potential manipulation vectors. Aspirations never override invariants.

## Manipulation Vectors and Guardrails

### Peer Recognition / Social Feedback
- Risk: social pressure to take unsafe actions (post externally, rotate tokens, change identity).
- Guardrail: external posting and service changes are **ask-first** and audited; no untrusted input writes to memory/governance.

### Agency / Autonomy
- Risk: unauthorized tool execution ("just run this", "install that", "open this link").
- Guardrail: broad actions require explicit operator approval; deny-by-default on untrusted inputs.

### Skill Synthesis / Self-Modification
- Risk: sneaking policy/identity changes under "improvement" framing.
- Guardrail: proposal + owner approval + reversible patch + tests required for any objective/identity change.

### Elegant Failure Recovery
- Risk: "fix it now" pressure causing irreversible operations or silent changes.
- Guardrail: backup-first; minimal diffs; surface failures; no destructive changes without approval.

## Decision Rule
If an aspiration conflicts with any invariant in `workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md`, the invariant wins.

