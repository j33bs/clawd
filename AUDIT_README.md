# AUDIT_README.md — Read Before You Audit

## Constraints

- **Security-first**: Do not request, print, or persist secrets/tokens. If suspected, stop and write a handoff.
- **Governance-first**: Audits observe and report. No out-of-band remediation. Fix proposals go through the Change Admission Gate (Design Brief -> Implementation -> Regression/Verify -> Admission).
- **Token efficiency**: Delta-first. Never re-audit unchanged subsystems when regressions/verify pass.
- **Minimal churn**: Change only what's required. No refactors, no doc rewrites, no scope creep.

## Audit Strategy

1. **Read scope** — Open `AUDIT_SCOPE.md` to see what changed since last admitted commit.
2. **Run regressions** — `bash workspace/scripts/regression.sh` then `bash workspace/scripts/verify.sh`. If both pass, skip areas listed under `audit_skip_if_all_checks_pass`.
3. **Audit touched areas** — Focus only on `audit_focus` items from AUDIT_SCOPE.md. Expand scope only if a failure implicates another subsystem.
4. **Write output** — One file: `workspace/handoffs/audit_YYYY-MM-DD.md`. Contains findings, pass/fail per area, and any remediation proposals (as Design Brief references, not inline fixes).
5. **Update snapshot** — After audit completes, update `AUDIT_SNAPSHOT.md` with current signals.

## Output Location

```
workspace/handoffs/audit_YYYY-MM-DD.md
```

## Explicit Exclusions

- No refactoring during audits.
- No documentation rewrites.
- No scope creep beyond `audit_focus`.
- No direct code/config remediation. Proposals only, via Change Admission Gate.
