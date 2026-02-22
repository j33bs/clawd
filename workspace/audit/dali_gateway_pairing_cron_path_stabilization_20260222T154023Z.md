# Dali gateway pairing cron path stabilization

- UTC: 20260222T154023Z
- Branch: codex/chore/dali-gateway-pairing-preflight-20260223
- HEAD: 222b4df0c2fb3a4413e7a4d421e75569a4b149e0

## Objective
Replace volatile `/tmp` cron wrapper path with a stable user-owned shim while preserving schedule, command, and log redirection behavior.

## Constraints
- Minimal diff, reversible, evidence-first.
- No security weakening.
- No secrets in output.

## Phase 0 Baseline

Current relevant cron line (before):
- `30 2 * * * /tmp/wt_local_exec_activation/workspace/scripts/cron_with_gateway_preflight.sh -- $HOME/bin/openclaw-backup.sh >> $HOME/.local/state/openclaw/backup.log 2>&1`

## Phase 1 - Stable user shim

- Installed user-owned shim: `~/.local/bin/openclaw-cron-preflight` (outside git).
- Shim behavior: resolve repo root from `OPENCLAW_REPO_ROOT` when set; fallback to canonical local paths; exec repo wrapper unchanged.

```
$ command -v openclaw-cron-preflight
/home/jeebs/.local/bin/openclaw-cron-preflight
$ ~/.local/bin/openclaw-cron-preflight -- echo OK
INFO: recent scope-upgrade/pairing-required log lines were found; ensure devices list remains pending-free.
OK: no pending pairing/repair detected.
OK
(exit_code=0)
```

## Phase 2 - Crontab update (surgical)

Before:
- `2:30 2 * * * /tmp/wt_local_exec_activation/workspace/scripts/cron_with_gateway_preflight.sh -- $HOME/bin/openclaw-backup.sh >> $HOME/.local/state/openclaw/backup.log 2>&1`
After:
- `2:30 2 * * * $HOME/.local/bin/openclaw-cron-preflight -- $HOME/bin/openclaw-backup.sh >> $HOME/.local/state/openclaw/backup.log 2>&1`

Installed crontab excerpt:
```
# OpenClaw maintenance
30 2 * * * $HOME/.local/bin/openclaw-cron-preflight -- $HOME/bin/openclaw-backup.sh >> $HOME/.local/state/openclaw/backup.log 2>&1
45 3 * * * $HOME/bin/python-env-audit.sh $HOME/security-audits >> $HOME/.local/state/openclaw/python-audit.log 2>&1
15 4 * * * $HOME/bin/cleanup-temp.sh >> $HOME/.local/state/openclaw/cleanup.log 2>&1
*/5 * * * * $HOME/bin/system-monitor.sh >> $HOME/.local/state/openclaw/monitor-cron.log 2>&1
```

## Notes
- Schedule unchanged: `30 2 * * *`.
- Underlying backup command unchanged: `$HOME/bin/openclaw-backup.sh`.
- Log target unchanged: `$HOME/.local/state/openclaw/backup.log`.
