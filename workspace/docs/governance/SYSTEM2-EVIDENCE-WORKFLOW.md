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
