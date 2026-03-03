# Secrets contract gate (Groq SecretRef inline schema)

timestamp: 20260227T044831Z

Intent
- Prevent regression to plaintext or unallowlisted env ids for Groq apiKey.
- Enforce this OpenClaw build contract: inline SecretRef at `models.providers.groq.apiKey`.

Work performed
- Added `tools/check_openclaw_secrets_contract.sh`.
- Wired checker into `tools/run_checks.sh` under `OPENCLAW_LOCAL_GATES=1` macOS local gates.
- Added deterministic test `tests/check_openclaw_secrets_contract.test.js` using HOME override fixtures.

Commands and outcomes
- `node --test tests/check_openclaw_secrets_contract.test.js`
  - PASS (2 tests): valid inline SecretRef passes; plaintext apiKey fails.
- `tools/check_openclaw_secrets_contract.sh`
  - PASS: contract holds on local config.
- `OPENCLAW_LOCAL_GATES=1 tools/run_checks.sh || true`
  - Local-gate run started and failed early at pre-existing launchagent alignment check:
    - `FAIL: ProgramArguments does not reference expected wrapper: /Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh`

Security note
- No secret values were printed during this change.
