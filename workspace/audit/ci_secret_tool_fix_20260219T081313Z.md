# CI secret-tool determinism fix

## Why CI failed
GitHub Actions (Linux) failed `tests/secrets_cli_exec.test.js` with:
- `secrets command failed: secret-tool exited 1`

The test invoked `openclaw secrets exec` with secrets bridge enabled and only one provider override. On Linux, unresolved providers can trigger Secret Service reads, making the test depend on host secret-service state.

## Approach chosen
**Option B (optional external dependency): deterministic test path without secret-tool execution.**

Instead of requiring `secret-tool` runtime behavior for this test, the test now:
- forces `SECRETS_BACKEND=file`
- uses an isolated temp HOME (`HOME`/`USERPROFILE`)
- sets non-secret dummy overrides for all provider env vars so no external secret-store lookup occurs

This preserves security assertions:
- still verifies alias env key injection
- still verifies secret values are not printed

## Files changed
- `tests/secrets_cli_exec.test.js`

## Commands and outcomes
- `node tests/secrets_cli_exec.test.js` -> PASS
- `NODE_DIR=$(dirname "$(command -v node)") && PATH="$NODE_DIR:/usr/bin:/bin" node tests/secrets_cli_exec.test.js` -> PASS
- `npm test` -> PASS
