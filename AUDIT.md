# Audit Guide

## How This System Should Be Audited
- Treat this repository as canonical source of truth.
- Run preflight checks before any modification.
- Record evidence as structured, redacted JSONL events.
- Validate event schema and hash integrity before trust.
- Require a change capsule for all non-trivial changes.
- Require rollback and kill-switch instructions per capsule.

## Minimal Audit Run
1. `git status --porcelain`
2. `node scripts/verify_model_routing.js`
3. `node tests/sys_acceptance.test.js`
4. `sh scripts/gate_lint_substitute.sh`
5. `scripts/audit_snapshot` (opt-in)
6. `scripts/audit_verify` (opt-in)
