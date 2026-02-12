# Redaction Workflow

## Purpose
Use the redaction tool to produce a sanitized evidence bundle before sharing or proposing docs changes.

## Local command
```bash
npm run redact:audit-evidence -- --in workspace/docs/audits/<RAW_BUNDLE> --out workspace/docs/audits/<REDACTED_BUNDLE>
```

Optional flags:
- `--dry-run`: preview summary without writing output files
- `--json`: emit machine-readable summary
- `--max-bytes <n>`: skip files larger than `n` bytes

## Safety rules
- Never commit raw evidence bundles.
- Commit only manifests or redacted outputs, and only when explicitly intended.
- Keep outputs size-bounded and review diffs before staging.
- Use repo-relative input/output paths; avoid host-specific absolute paths in committed files.

## Verification
Run these checks before opening a PR:
```bash
npm test
npm run gate:module-resolution
npm run check:redaction-fixtures
```

## CI behavior
CI runs `check:redaction-fixtures` against synthetic fixtures only. It does not read real audit evidence and does not upload artifacts.
