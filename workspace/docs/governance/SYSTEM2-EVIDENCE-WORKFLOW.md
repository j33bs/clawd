# System-2 Evidence Workflow

## Purpose
Capture a bounded System-2 snapshot locally, redact it, and produce a stable summary JSON for diffing without committing raw evidence.

## Commands
Capture snapshot only:
```bash
npm run system2:snapshot -- --out .tmp/system2_snapshot --json
```

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
