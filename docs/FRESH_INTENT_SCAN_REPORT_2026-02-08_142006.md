# Fresh Intent Scan Report

## Commands Run
1. node workspace/system_check_telegram.js
2. python3 workspace/scripts/preflight_check.py
3. python3 workspace/scripts/intent_failure_scan.py --since 2026-02-08T04:19:54Z --stdout

## Preflight Allowlist Resolution
Resolved Telegram allowlist (credentials:allow_chat_ids): [-1002117631304, -1001700695156, -1001445373305, -1001369282532]

## Fresh Scan Summary
- since: 2026-02-08T04:19:54Z
- total_errors: 0
- categories: none
- router_failures: 0

## Acceptance Criteria
- No legacy carryover: PASS (fresh window contained 0 entries)
- Telegram errors classification: PASS (no errors)

Overall: PASS
