# HEARTBEAT.md

Check these in order. Skip any that were checked <2h ago.

## 1. Memory freshness
- Does `memory/YYYY-MM-DD.md` exist for today? If not, create it.
- Has MEMORY.md been reviewed in the last 3 days? If not, read recent daily logs and update it.

## 2. System health
- Run `openclaw health` via exec. If Telegram is down, attempt recovery.
- Check `openclaw sessions --active 60` for stuck sessions.

## 3. Regression check
- Run `bash workspace/scripts/regression.sh` if not run today. Log result to daily memory.

## 4. Handoff inbox
- Check `workspace/handoffs/` for any files from `claude-code`. Execute simple follow-ups, archive completed ones.

---

## Cron Semantics

| Job | Schedule (UTC) | Schedule (AEST, Brisbane) | Agent |
|---|---|---|---|
| Telegram Messaging Health Check | every 4h | every 4h | main |
| Enhanced Telegram Health Monitoring | every 4h | every 4h | main |
| Daily Regression Validation | 02:00 UTC | 12:00 AEST | claude-code |

**Operational intent**: Daily regression runs midday Brisbane time (lunchtime check, not overnight). If the intent shifts to overnight Brisbane, adjust to ~18:00 UTC (04:00 AEST).

## Cron Guardrails

- Cron jobs are **observe/report only**.
- **Allowed write scope**: `workspace/handoffs/*` and `workspace/memory/*.md`. Nothing else.
- **Disallowed**: code/config edits, git commits, deploy actions, network exfiltration.
- Failures produce handoff entries, not auto-fixes.
- No cron job may bypass the Change Admission Gate.
