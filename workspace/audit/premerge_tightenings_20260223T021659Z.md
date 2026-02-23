# Premerge Tightenings Evidence (20260223T021659Z)

## Scope
- Branch: `codex/feat/audit-clawd-10changes-20260223`
- Objective: apply premerge tightenings A/B before merge to `main`.

## Tightening A — Path sanity + guardrails

### Check 1: branch diff scope
Command:
- `git diff --name-status origin/main...HEAD`

Summary:
- Changes remain repo-relative under `workspace/...` and `tests_unittest/...`.
- No worktree-prefixed tracked paths present.

### Check 2: tracked path prefix sanity
Command:
- `git ls-files | grep -E '^/private/tmp|^private/tmp|^tmp/wt_|^/tmp/wt_' || true`

Output:
```text
<no matches>
```

### .gitignore guardrails added
Change:
- Added default ignores for derived/state artifacts:
  - `workspace/reports/**`
  - `workspace/probes/*_log.jsonl`
- Added explicit governed witness exception:
  - `!workspace/probes/dispositional_log.jsonl`

Rationale:
- Prevent recurrence of incidental derived/state churn while preserving explicit append-only witness tracking for dispositional probe logs.

## Tightening B — Φ blocked-session evidence precision

Updated files:
- `workspace/audit/phi_metrics_session_20260223T005118Z.md`
- `workspace/research/phi_metrics.md`

Added precision details:
- Exact searched module/function symbols and repo grep patterns.
- Expected canonical entrypoint targets.
- File paths inspected.
- Precise unresolved interface dependency.
- Table row now references this evidence doc and method target interface.

## Verification

### OPEN_QUESTIONS append-only hook test
Command:
- `bash workspace/scripts/tests/test_guard_open_questions_append_only.sh`

Output summary:
- PASS (expected rejection path observed)
- PASS (bypass path with `OPENCLAW_GOV_BYPASS=1` observed)

### Φ runner dry-run deterministic blocked state
Command:
- `python3 workspace/scripts/phi_session_runner.py --dry-run --json || true`

Output excerpt:
```json
{
  "status": "blocked",
  "method_ref": "AIN_PHI_CALCULATOR_MISSING",
  "wiring_snapshot_ref": "DRY_RUN::workspace/phi_sessions/<timestamp>_wiring_snapshot.json"
}
```

### Doc lint/format check availability
Command:
- `node -e "const p=require('./package.json'); console.log(JSON.stringify(p.scripts||{}, null, 2));"`

Summary:
- No dedicated markdown/doc lint script is defined in current npm scripts.
- No additional doc-lint command was run.

## Reversibility
- Revert commits in reverse order:
  1. `docs(audit): add premerge tightenings evidence`
  2. `docs(audit): sharpen Φ blocked-session evidence and targets`
  3. `chore(phi): add dry-run mode to deterministic phi session runner`
  4. `chore(gitignore): guardrails for state/derived artifacts`
