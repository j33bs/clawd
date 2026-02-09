# Audit Hardening 2026-02

## Purpose
Audit Layer v1 provides additive, opt-in audit scaffolding for OpenClaw system contributions. It is designed to make future audits cheaper without altering runtime behavior by default.

## Audit Model
Evidence types:
- `audit.snapshot`: environment and repo fingerprint, hash-only config fingerprints.
- `audit.run.start` / `audit.run.end`: bounded run metadata.
- `audit.change.detected`: git diff fingerprint metadata.
- `audit.external.health`: provider/model health summary (no payload content).
- `audit.invariant.pass` / `audit.invariant.fail`: gate outcomes.
- `audit.operator.notice`: controlled operator messages.

Event retention:
- JSONL append-only log at `~/.openclaw/logs/audit.jsonl` (override via env).
- Keep events small (sizes, hashes, IDs, classes only).

Redaction rules:
- Never log secrets, tokens, raw prompts, or message content.
- Log only identifiers, hashes, sizes, error classes, model/provider IDs, and invariant results.

## Operator Flows
1. Preflight (`git status --porcelain`, branch, log, gates).
2. Run `scripts/audit_snapshot` with audit flag enabled.
3. Run `scripts/audit_verify` to validate schema/hash invariants.
4. For non-trivial changes, create a change capsule pair (`.md` + `.json`).

## Threat Model (Audit-Centric)
- Unauthorized history drift.
- Missing provenance for critical changes.
- Secret leakage in logs.
- Non-reproducible operator runs.

Mitigations:
- Hash-chained event fields (per-event content hash).
- Deterministic snapshot fingerprints.
- Redaction policy and tests.
- Governance gate docs + rollback instructions.

## Acceptance Criteria
- Audit schema validates required fields.
- Snapshot and verify scripts produce deterministic, redacted outputs.
- Capsule generator emits required sections/keys and collision-safe filenames.
- Existing gates remain green:
  - `node tests/sys_acceptance.test.js`
  - `sh scripts/gate_lint_substitute.sh`
  - `node scripts/verify_model_routing.js`

## Audit Checklist
- [ ] Preflight logs recorded.
- [ ] Audit events written with hashes and no sensitive content.
- [ ] Change capsule created for non-trivial changes.
- [ ] Tests and gates passed.
- [ ] Rollback command documented.

## Change Capsule Workflow
1. Generate capsule pair:
   - `node scripts/audit_capsule_new.mjs --slug <short-slug>`
2. Fill capsule markdown and json with intent, evidence, rollback, and risk.
3. Keep capsule filenames immutable after publication.
4. Link capsule in verification/gate notes for governed changes.

## Opt-In Integration Hook
- `scripts/sys_evolution_self_test.js` now calls `scripts/audit_snapshot.mjs` and `scripts/audit_verify.mjs` only when `OPENCLAW_AUDIT_LOGGING=1`.
- Default behavior is unchanged when the flag is unset.
