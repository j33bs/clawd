# CI authoritative regression gate
timestamp_utc: 20260227T055447Z

Intent
- Make regression gate blocking (no warn-only).
- Enforce reliability by preventing regressions from merging to main.

Change
- .github/workflows/regression-gate.yml: continue-on-error set to false.

Verification
- workflow YAML parses locally
- local regression.sh executed (passed)

Rollback
- git revert <commit_sha>
