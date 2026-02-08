# Verification Commands

## Bash
- `./workspace/scripts/verify_preflight.sh`
- `python3 workspace/scripts/verify_allowlist.py`
- `./workspace/scripts/intent_failure_report.sh`
- `node workspace/system_check_telegram.js`

## Windows PowerShell Wrappers
- `./scripts/run_preflight.ps1` -> `python workspace/scripts/preflight_check.py`
- `./scripts/run_verify_allowlist.ps1` -> `python workspace/scripts/verify_allowlist.py`
- `./scripts/run_intent_scan.ps1` -> `python workspace/scripts/intent_failure_scan.py --stdout`
- `./scripts/run_system_check_telegram.ps1` -> `node workspace/system_check_telegram.js`

Each wrapper prints a header and propagates exit codes.
