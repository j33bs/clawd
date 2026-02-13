# System-2 Evidence Workflow

## Purpose
Capture a bounded System-2 snapshot locally, redact it, and produce a stable summary JSON for diffing without committing raw evidence.

## Commands
Capture snapshot only:
```bash
npm run system2:snapshot -- --out .tmp/system2_snapshot --json
```

## Observability Seam (Default-Off)
Config:
- `system2.observability.enabled` (default false)
- `system2.observability.jsonlPath` (default empty string)
- env fallbacks: `SYSTEM2_OBSERVABILITY_ENABLED=1`, `SYSTEM2_OBSERVABILITY_JSONL_PATH=/path/events.jsonl`

Behavior:
- disabled: no file writes
- enabled + missing/blank path: warn once, no writes (fail-closed)
- enabled + parent dir missing: warn once, no writes (fail-closed)
- enabled + valid path: append exactly one JSONL line per snapshot capture

Capture + redact bundle:
```bash
npm run system2:evidence -- --out .tmp/system2_evidence
```

Run redaction directly on an existing raw bundle:
```bash
npm run redact:audit-evidence -- --in .tmp/system2_evidence/raw --out .tmp/system2_evidence/redacted --json
```

## Rules
- Never commit raw evidence from `.tmp/**`.
- Commit only manifests or redacted outputs when explicitly intended.
- Keep outputs bounded via `--max-log-lines` and `--max-bytes`.
- Review redacted output before sharing.
- Never paste tokens into terminals or chat logs while running System-2 workflows.
- Treat any pasted token as compromised.
- Rotate compromised tokens immediately.

## Verification
Before opening a PR that touches evidence workflows:
```bash
npm test
npm run gate:module-resolution
npm run check:redaction-fixtures
```

## Compare two runs
Human-readable diff:
```bash
npm run system2:diff -- --a <run1>/snapshot_summary.json --b <run2>/snapshot_summary.json
```

Machine-readable diff:
```bash
npm run system2:diff -- --a <run1>/snapshot_summary.json --b <run2>/snapshot_summary.json --json
```

Regression-focused diff (fails on increases for selected counters):
```bash
npm run system2:diff -- --a <run1>/snapshot_summary.json --b <run2>/snapshot_summary.json --fail-on snapshot_summary.log_signature_counts.auth_error,snapshot_summary.log_signature_counts.quota_error,snapshot_summary.log_signature_counts.fetch_error
```

## A/B experiment protocol
Run a two-step operator experiment with one change between runs:
```bash
npm run system2:experiment -- --out .tmp/system2_experiments/exp1 --fail-on snapshot_summary.log_signature_counts.auth_error,snapshot_summary.log_signature_counts.quota_error,snapshot_summary.log_signature_counts.fetch_error
```

Protocol rules:
- Change exactly one operator setting between run A and run B.
- Do not batch multiple changes in a single experiment.
- Use decision output from `report.json`:
  - `KEEP`: measurable change without fail-on regressions
  - `REVERT`: fail-on regression detected
  - `INCONCLUSIVE`: no measurable delta

## Auth experiment (calibrated)
Calibrated auth regression path (empirically calibrated on the operator environment):
`log_signature_counts.auth_error`

Run auth-focused experiment with explicit fail-on:
```bash
npm run system2:experiment -- --fail-on log_signature_counts.auth_error
```

Run auth-focused experiment via preset:
```bash
npm run system2:experiment:auth
```
