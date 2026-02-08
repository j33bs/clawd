# Operations Runbook

## Scope
- Safe operator workflow for preflight, allowlist checks, intent scans, Telegram system checks, and token-burn snapshots.
- Routing, budgets, and ladder policy are unchanged by this runbook.

## Run Checks (Bash)
- `./workspace/scripts/verify_preflight.sh`
- `python3 workspace/scripts/verify_allowlist.py`
- `python3 workspace/scripts/intent_failure_scan.py --stdout`
- `node workspace/system_check_telegram.js`
- `python3 workspace/scripts/report_token_burn.py --stdout`

## Run Checks (PowerShell)
- `./scripts/run_preflight.ps1`
- `./scripts/run_verify_allowlist.ps1`
- `./scripts/run_intent_scan.ps1`
- `./scripts/run_system_check_telegram.ps1`

## Configure ALLOWED_CHAT_IDS (no secrets)
- Session-only (PowerShell):
  - `$ids = Read-Host "Enter allowed Telegram chat IDs (comma-separated)"`
  - `$env:ALLOWED_CHAT_IDS = $ids`
- Persist for future shells:
  - `setx ALLOWED_CHAT_IDS "$ids"`

## Telegram Reason Codes
- `telegram_not_configured`: no allowlist resolved from env or credentials JSON.
- `telegram_chat_not_allowed`: target chat ID is not in the resolved allowlist.
- `telegram_chat_not_found`: genuine resolve/send failure after allowlist passes.
- `openclaw_status_unavailable`: `openclaw status --deep`/`openclaw status` unavailable; check continues in limited mode.

## Token Burn Report
- Command: `python3 workspace/scripts/report_token_burn.py --stdout`
- Read this first:
  - `Failed Tokens` approximates spend on failed calls.
  - `Timeout Waste` highlights timeout-related waste.
  - `Missing Usage` should remain `0` for accounting health.

## What To Do When Checks Fail
- Preflight fails:
  - Resolve missing env/runtime prerequisites shown in output.
  - Re-run `./workspace/scripts/verify_preflight.sh`.
- Allowlist fails:
  - Set `ALLOWED_CHAT_IDS` or add `allow_chat_ids` in `credentials/telegram-allowFrom.json`.
  - Re-run `python3 workspace/scripts/verify_allowlist.py`.
- `openclaw_status_unavailable` appears:
  - Run `openclaw status` manually.
  - Check CLI path/service responsiveness.
  - Treat as OpenClaw status telemetry issue, not direct Telegram ingestion failure.

## Don’t Do This
- Do not paste or commit secrets/tokens.
- Do not force-add ignored paths unless policy explicitly tracks them.
- Do not bypass preflight/allowlist checks when debugging Telegram issues.
