# Branch Audit: regression bootstrap config contract

- Timestamp (UTC): 2026-02-21T08:11:28Z
- Branch: fix/regression-bootstrap-config-20260221T080905Z
- Head: a2a0aa5

## Baseline
```bash
$ date -u
Sat Feb 21 08:11:28 UTC 2026
$ git rev-parse --short HEAD
a2a0aa5
$ git status --porcelain -uall
?? tests/regression_bootstrap_contract.test.js
?? workspace/audit/c_lawd_pr_merge_and_followups_20260221T080418Z.md
?? workspace/audit/fix_regression_bootstrap_config_20260221T081128Z.md
?? workspace/audit/pr_body_c_lawd_full_remediation_20260221.md
```

## Scope
Ensure regression bootstrap contract is explicit and tested:
1. Honor OPENCLAW_CONFIG_PATH when set
2. Else use ./openclaw.json when present
3. Else create ephemeral secret-free config

## Evidence: Existing Contract in Main
- File: `workspace/scripts/regression.sh`
- Bootstrap block lines: 24-43
- Behavior: exports OPENCLAW_CONFIG_PATH to mktemp config when no config path/file exists

## Reproduction + Verification
```bash
$ bash workspace/scripts/regression.sh
==========================================
  OpenClaw Regression Validation
==========================================

[regression] Using ephemeral OPENCLAW_CONFIG_PATH=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp.bFrNN1sWub/openclaw.json
[1/9] Checking constitutional invariants...
[0;32m  ✓ PASS[0m
[2/9] Verifying governance substrate...
[0;32m  ✓ PASS[0m
[3/9] Scanning for secrets in tracked files...
[0;32m  ✓ PASS[0m
[4/9] Checking for forbidden files...
[0;32m  ✓ PASS[0m
[5/9] Verifying git hooks...
    pre-commit hook missing or not executable
    pre-push hook missing or not executable
[1;33m  ⚠ WARN: Git hooks not installed (run: bash workspace/scripts/install-hooks.sh)[0m
[6/9] Checking documentation completeness...
[0;32m  ✓ PASS[0m
[0;32m  ✓ PASS[0m
[7/9] Checking provider env gating (profile=core)...
ok
[0;32m  ✓ PASS[0m
    Checking system_map aliases...
ok
[0;32m  ✓ PASS[0m
[8/9] Checking heartbeat dependency invariant...
[1;33m  ⚠ WARN: Heartbeat cadence unavailable from openclaw config; heartbeat invariant skipped (non-fatal)[0m
[9/9] Checking branch state...
    Current branch: fix/regression-bootstrap-config-20260221T080905Z
[0;32m  ✓ PASS[0m

==========================================
[0;32m  REGRESSION PASSED[0m
  Warnings: 2 (review recommended)
==========================================
$ node tests/regression_bootstrap_contract.test.js
PASS regression.sh bootstraps ephemeral config when openclaw.json is absent
```

## Changes
- Added focused guard test: `tests/regression_bootstrap_contract.test.js`
  - Asserts regression script exits 0 when `openclaw.json` is absent
  - Asserts ephemeral bootstrap log is emitted
  - Asserts missing-config hard-fail text is not emitted

## Outcome
- Contract validated and now covered by a targeted test to prevent drift/regression.
