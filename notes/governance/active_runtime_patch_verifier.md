# Active Runtime Patch Verifier

This tests-only verifier checks that the active installed `openclaw` runtime loader still contains the required prompt-budget patch markers.

## What it checks
- Resolves active `openclaw` from `which openclaw` + symlink realpath.
- Reads active loader file `dist/loader-BAZoAqqR.js` from that package directory.
- Verifies markers exist:
  - `MAX_SYSTEM_PROMPT_CHARS`
  - `STRICT_MAX_SYSTEM_PROMPT_CHARS`
  - `embedded_prompt_before`
  - `embedded_attempt`
  - `projectContextIncludedChars`
- Verifies missing-marker simulation by replacing exact token `"embedded_attempt"` with `"EMBEDDED_ATTEMPT_REMOVED"`.

## How to run
`node tests/verify_active_runtime_patch.test.cjs`

## Why tests-only and safe
- Read-only verification against installed runtime bytes.
- No edits to runtime bundles or `~/.npm-global`.
- No package script changes; manual runbook invocation.

## Hash allowlist gate
- Run `node tests/verify_active_runtime_patch_hash.test.cjs` to confirm the active loader SHA256 is allowlisted.
- Governed update workflow for intentional upgrades:
  1. Run `node tests/verify_active_runtime_patch.test.cjs` and confirm PASS.
  2. Compute the new active loader SHA256 and add it to `notes/governance/active_runtime_loader_hash_allowlist.json` with date and notes.
  3. Commit the allowlist update and governance note together.
- Hash allowlist updates are governance-significant and must be reviewed.
