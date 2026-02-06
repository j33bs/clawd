# Handoff: Audit Protocol Implementation
- **From**: claude-code
- **Date**: 2026-02-06
- **Status**: complete

## Files Created

| File | Purpose |
|---|---|
| `AUDIT_README.md` | Constraints, strategy, exclusions for auditors |
| `AUDIT_SCOPE.md` | Structured template: last commit, changed areas, focus, skip-if-pass |
| `AUDIT_SNAPSHOT.md` | Compact last-audit signals (commit, pass/fail, gateway, cron, agents) |

## Files Modified

| File | Change |
|---|---|
| `workspace/HEARTBEAT.md` | Added Cron Semantics table (UTC + AEST) and Cron Guardrails section |
| `workspace/CLAUDE_CODE.md` | Added Audit Entrypoint section before Session Protocol |
| `workspace/AGENTS.md` | Added audit pointer line in delegation Rules |

## Policies/Guardrails Added

1. **Audit protocol** (AUDIT_README.md): security-first, governance-first, delta-first, no scope creep. Outputs to `workspace/handoffs/audit_YYYY-MM-DD.md`.
2. **Cron semantics** (HEARTBEAT.md): All schedules documented in both UTC and Australia/Brisbane AEST. Daily regression = 02:00 UTC = 12:00 AEST (midday Brisbane intent).
3. **Cron guardrails** (HEARTBEAT.md): Observe/report only. Allowed writes limited to `workspace/handoffs/*` and `workspace/memory/*.md`. No code edits, git commits, deploys, or exfil.
4. **Agent discoverability**: Both CLAUDE_CODE.md and AGENTS.md now point to AUDIT_README.md + AUDIT_SCOPE.md as audit entrypoints.

## Validation

- `regression.sh`: **PASS** (8/8)
- `verify.sh`: **PASS** (all steps)
- No new bypass channels introduced.

## Remaining Risks / TODOs

1. **Cron schedule intent**: 02:00 UTC = 12:00 AEST is midday, not overnight. If overnight Brisbane is preferred, change to ~18:00 UTC. Needs user confirmation.
2. **AUDIT_SCOPE.md is manual**: Must be updated by the auditor before each audit. No automation enforces this yet.
3. **Cron guardrails are policy, not code**: The guardrails in HEARTBEAT.md are advisory. There is no runtime enforcement preventing a cron-spawned agent from writing outside allowed scope.
4. **ITC sources not yet committed**: 20 files in `workspace/sources/itc/` are untracked. Should be committed with the next admission.
5. **Audit cron job not yet created**: The daily regression cron exists, but there is no periodic audit cron. Current design is manual/on-demand audits only, which is appropriate for now.
