# Dali Subagent Gateway Pairing Fix Audit

- UTC: 20260222T133601Z
- Worktree: /tmp/wt_local_exec_activation
- Branch: codex/feat/dali-local-exec-plane-20260222
- HEAD: 54ae7721f3c9824a0964f5e66ba5f7d7a0c9a3c3
- Objective: classify and fix sub-agent -> gateway close(1008) pairing-required failures without weakening auth.
- Constraints: minimal diff, reversible, evidence-first, no unrelated changes, no secrets in logs.
- No secrets note: outputs are redacted for token/key-like fields.

## Phase 0 Baseline
```text
$ pwd
/tmp/wt_local_exec_activation
$ git status --porcelain -uall
?? workspace/audit/dali_subagent_gateway_pairing_fix_20260222T133601Z.md
$ command -v openclaw && readlink -f "$(command -v openclaw)"
/home/jeebs/.local/bin/openclaw
/home/jeebs/.local/bin/openclaw
$ openclaw --version || true
2026.2.19-2 build_sha=9325318d0c992f1e5395a7274f98220ca7999336 build_time=2026-02-22T04:58:13Z
$ node -v || true
v22.22.0
```

## Phase 1.1 Gateway service reality
```text
$ systemctl --user status openclaw-gateway.service --no-pager || true
Failed to connect to bus: Operation not permitted

$ systemctl --user cat openclaw-gateway.service || true
Failed to connect to bus: Operation not permitted

$ systemctl --user show openclaw-gateway.service -p Environment -p EnvironmentFile --no-pager || true
Failed to connect to bus: Operation not permitted

$ journalctl --user -u openclaw-gateway.service -n 200 --no-pager || true
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER node[42041]: 2026-02-22T04:07:51.235Z [gateway] signal SIGTERM received
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER node[42041]: 2026-02-22T04:07:51.236Z [gateway] received SIGTERM; shutting down
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER node[42041]: 2026-02-22T04:07:51.253Z [gmail-watcher] gmail watcher stopped
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Unit process 57342 (bash) remains running after unit stopped.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Unit process 57343 (openclaw) remains running after unit stopped.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Unit process 57350 (openclaw-gatewa) remains running after unit stopped.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Unit process 57384 (systemctl) remains running after unit stopped.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 33.804s CPU time, 1.0G memory peak, 0B memory swap peak.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Found left-over process 57342 (bash) in control group while starting unit. Ignoring.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: This usually indicates unclean termination of a previous run, or service implementation deficiencies.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Found left-over process 57343 (openclaw) in control group while starting unit. Ignoring.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: This usually indicates unclean termination of a previous run, or service implementation deficiencies.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Found left-over process 57350 (openclaw-gatewa) in control group while starting unit. Ignoring.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: This usually indicates unclean termination of a previous run, or service implementation deficiencies.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Found left-over process 57384 (systemctl) in control group while starting unit. Ignoring.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: This usually indicates unclean termination of a previous run, or service implementation deficiencies.
Feb 22 14:07:51 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 14:07:52 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:52.933Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.844Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.884Z [heartbeat] started
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.887Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.889Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.890Z [gateway] listening on ws://127.0.0.1:18789 (PID 57386)
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.890Z [gateway] listening on ws://[::1]:18789
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.892Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 14:07:53 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:53.911Z [browser/service] Browser control service ready (profiles=2)
Feb 22 14:07:55 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:55.371Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 14:07:55 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:07:55.377Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 14:08:33 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:08:33.051Z [telegram] telegram_handler_finally chatId=8159253715 messageId=601
Feb 22 14:18:04 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (user-owned)...
Feb 22 14:18:04 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:18:04.225Z [gateway] signal SIGTERM received
Feb 22 14:18:04 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:18:04.226Z [gateway] received SIGTERM; shutting down
Feb 22 14:18:04 jeebs-Z490-AORUS-MASTER node[57386]: 2026-02-22T04:18:04.240Z [gmail-watcher] gmail watcher stopped
Feb 22 14:18:04 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:18:04 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 7.536s CPU time, 1.0G memory peak, 0B memory swap peak.
Feb 22 14:18:04 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:18:05 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:05.916Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.810Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.848Z [heartbeat] started
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.851Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.853Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.854Z [gateway] listening on ws://127.0.0.1:18789 (PID 58355)
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.854Z [gateway] listening on ws://[::1]:18789
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.856Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 14:18:06 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:06.874Z [browser/service] Browser control service ready (profiles=2)
Feb 22 14:18:08 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:08.334Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 14:18:08 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:18:08.338Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 14:19:22 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (user-owned)...
Feb 22 14:19:22 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:19:22.592Z [gateway] signal SIGTERM received
Feb 22 14:19:22 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:19:22.592Z [gateway] received SIGTERM; shutting down
Feb 22 14:19:22 jeebs-Z490-AORUS-MASTER node[58355]: 2026-02-22T04:19:22.608Z [gmail-watcher] gmail watcher stopped
Feb 22 14:19:22 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:19:22 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 4.493s CPU time, 380.9M memory peak, 0B memory swap peak.
Feb 22 14:19:22 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:19:24 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:24.284Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.173Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.210Z [heartbeat] started
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.214Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.215Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.216Z [gateway] listening on ws://127.0.0.1:18789 (PID 58498)
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.217Z [gateway] listening on ws://[::1]:18789
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.218Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 14:19:25 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:25.236Z [browser/service] Browser control service ready (profiles=2)
Feb 22 14:19:27 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:27.739Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 14:19:27 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:19:27.744Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 14:21:45 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (user-owned)...
Feb 22 14:21:45 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:21:45.506Z [gateway] signal SIGTERM received
Feb 22 14:21:45 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:21:45.507Z [gateway] received SIGTERM; shutting down
Feb 22 14:21:45 jeebs-Z490-AORUS-MASTER node[58498]: 2026-02-22T04:21:45.521Z [gmail-watcher] gmail watcher stopped
Feb 22 14:21:45 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:21:45 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 4.497s CPU time, 375.1M memory peak, 0B memory swap peak.
Feb 22 14:21:45 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:21:46 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:46.906Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.801Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.842Z [heartbeat] started
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.845Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.848Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.849Z [gateway] listening on ws://127.0.0.1:18789 (PID 58684)
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.850Z [gateway] listening on ws://[::1]:18789
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.851Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 14:21:47 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:47.870Z [browser/service] Browser control service ready (profiles=2)
Feb 22 14:21:49 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:49.326Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 14:21:49 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:21:49.329Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 14:22:55 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (user-owned)...
Feb 22 14:22:55 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:22:55.990Z [gateway] signal SIGTERM received
Feb 22 14:22:55 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:22:55.991Z [gateway] received SIGTERM; shutting down
Feb 22 14:22:55 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:22:55.993Z [gateway] signal SIGTERM received
Feb 22 14:22:55 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:22:55.993Z [gateway] received SIGTERM during shutdown; ignoring
Feb 22 14:22:56 jeebs-Z490-AORUS-MASTER openclaw[58684]: 2026-02-22T04:22:56.007Z [gmail-watcher] gmail watcher stopped
Feb 22 14:22:56 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:22:56 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 4.138s CPU time, 13.6M memory peak, 0B memory swap peak.
Feb 22 14:22:56 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:22:57 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:57.629Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.537Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.574Z [heartbeat] started
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.578Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.579Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.580Z [gateway] listening on ws://127.0.0.1:18789 (PID 59070)
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.581Z [gateway] listening on ws://[::1]:18789
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.582Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 14:22:58 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:22:58.602Z [browser/service] Browser control service ready (profiles=2)
Feb 22 14:23:00 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:23:00.940Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 14:23:00 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:23:00.944Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (user-owned)...
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:54:48.462Z [gateway] signal SIGTERM received
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:54:48.464Z [gateway] received SIGTERM; shutting down
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:54:48.465Z [gateway] signal SIGTERM received
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:54:48.466Z [gateway] received SIGTERM during shutdown; ignoring
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER openclaw[59070]: 2026-02-22T04:54:48.479Z [gmail-watcher] gmail watcher stopped
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 6.707s CPU time, 392.3M memory peak, 0B memory swap peak.
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER openclaw[64067]: openclaw_gateway build_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327 version=0.0.0 build_time=2026-02-22T04:54:48Z
Feb 22 14:54:50 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:50.087Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 14:54:50 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:50.974Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 14:54:51 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:51.011Z [heartbeat] started
Feb 22 14:54:51 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:51.014Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 14:54:51 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:51.016Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 14:54:51 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:51.017Z [gateway] listening on ws://127.0.0.1:18789 (PID 64129)
Feb 22 14:54:51 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:51.017Z [gateway] listening on ws://[::1]:18789
Feb 22 14:54:51 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:51.019Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 14:54:51 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:54:51.037Z [browser/service] Browser control service ready (profiles=2)
Feb 22 14:55:00 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:55:00.416Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 14:55:00 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:55:00.419Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 14:58:09 jeebs-Z490-AORUS-MASTER sudo[64837]: pam_unix(sudo:auth): conversation failed
Feb 22 14:58:09 jeebs-Z490-AORUS-MASTER sudo[64837]: pam_unix(sudo:auth): auth could not identify password for [jeebs]
Feb 22 14:58:12 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (user-owned)...
Feb 22 14:58:12 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:58:12.808Z [gateway] signal SIGTERM received
Feb 22 14:58:12 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:58:12.809Z [gateway] received SIGTERM; shutting down
Feb 22 14:58:12 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:58:12.810Z [gateway] signal SIGTERM received
Feb 22 14:58:12 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:58:12.811Z [gateway] received SIGTERM during shutdown; ignoring
Feb 22 14:58:12 jeebs-Z490-AORUS-MASTER openclaw[64129]: 2026-02-22T04:58:12.823Z [gmail-watcher] gmail watcher stopped
Feb 22 14:58:13 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:58:13 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 4.701s CPU time.
Feb 22 14:58:13 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 14:58:13 jeebs-Z490-AORUS-MASTER openclaw[64932]: openclaw_gateway build_sha=9325318d0c992f1e5395a7274f98220ca7999336 version=0.0.0 build_time=2026-02-22T04:58:13Z
Feb 22 14:58:14 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:14.399Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.278Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.315Z [heartbeat] started
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.319Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.320Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.321Z [gateway] listening on ws://127.0.0.1:18789 (PID 64992)
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.322Z [gateway] listening on ws://[::1]:18789
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.323Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 14:58:15 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:15.342Z [browser/service] Browser control service ready (profiles=2)
Feb 22 14:58:16 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:16.810Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 14:58:16 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T04:58:16.813Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 15:04:08 jeebs-Z490-AORUS-MASTER sudo[67103]: pam_unix(sudo:auth): conversation failed
Feb 22 15:04:08 jeebs-Z490-AORUS-MASTER sudo[67103]: pam_unix(sudo:auth): auth could not identify password for [jeebs]
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T15:04:12.973+10:00 [tools] exec failed: elevated is not available right now (runtime=direct).
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: Failing gates: allowFrom (tools.elevated.allowFrom.<provider> / agents.list[].tools.elevated.allowFrom.<provider>)
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: Context: provider=telegram session=agent:main:main
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: Fix-it keys:
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: - tools.elevated.enabled
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: - tools.elevated.allowFrom.<provider>
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: - agents.list[].tools.elevated.enabled
Feb 22 15:04:12 jeebs-Z490-AORUS-MASTER openclaw[64992]: - agents.list[].tools.elevated.allowFrom.<provider>
Feb 22 15:04:18 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T15:04:18.993+10:00 [tools] exec failed: exec host not allowed (requested gateway; configure tools.exec.host=sandbox to allow).
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T15:04:42.606+10:00 [tools] exec failed: elevated is not available right now (runtime=direct).
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: Failing gates: allowFrom (tools.elevated.allowFrom.<provider> / agents.list[].tools.elevated.allowFrom.<provider>)
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: Context: provider=telegram session=agent:main:main
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: Fix-it keys:
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: - tools.elevated.enabled
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: - tools.elevated.allowFrom.<provider>
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: - agents.list[].tools.elevated.enabled
Feb 22 15:04:42 jeebs-Z490-AORUS-MASTER openclaw[64992]: - agents.list[].tools.elevated.allowFrom.<provider>
Feb 22 15:04:48 jeebs-Z490-AORUS-MASTER sudo[67132]: pam_unix(sudo:auth): conversation failed
Feb 22 15:04:48 jeebs-Z490-AORUS-MASTER sudo[67132]: pam_unix(sudo:auth): auth could not identify password for [jeebs]
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (user-owned)...
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T06:36:27.239Z [gateway] signal SIGTERM received
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T06:36:27.240Z [gateway] received SIGTERM; shutting down
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T06:36:27.242Z [gateway] signal SIGTERM received
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T06:36:27.243Z [gateway] received SIGTERM during shutdown; ignoring
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER openclaw[64992]: 2026-02-22T06:36:27.255Z [gmail-watcher] gmail watcher stopped
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 16:36:27 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 14.397s CPU time.
Feb 22 22:37:53 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
Feb 22 22:37:53 jeebs-Z490-AORUS-MASTER openclaw[94200]: openclaw_gateway build_sha=9325318d0c992f1e5395a7274f98220ca7999336 version=0.0.0 build_time=2026-02-22T04:58:13Z
Feb 22 22:37:54 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:54.395Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.427Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.467Z [heartbeat] started
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.471Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.474Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.474Z [gateway] listening on ws://127.0.0.1:18789 (PID 94232)
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.475Z [gateway] listening on ws://[::1]:18789
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.476Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 22:37:55 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:55.495Z [browser/service] Browser control service ready (profiles=2)
Feb 22 22:37:56 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:56.988Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 22:37:56 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T12:37:56.991Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 22:38:21 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T22:38:21.743+10:00 [tools] browser failed: Can't reach the OpenClaw browser control service. Restart the OpenClaw gateway (OpenClaw.app menubar, or `openclaw gateway`). Do NOT retry the browser tool — it will keep failing. Use an alternative approach or inform the user that the browser is currently unavailable. (Error: Error: Chrome extension relay is running, but no tab is connected. Click the OpenClaw Chrome extension icon on a tab to attach it (profile "chrome").)
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:21:02.685Z [gateway] security audit: device access upgrade requested reason=scope-upgrade device=d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301 ip=unknown-ip auth=token <redacted> roleTo=operator scopesFrom=operator.admin,operator.approvals,operator.pairing scopesTo=operator.read client=gateway-client conn=7c9a162e-e49e-4c78-914b-93ba99909847
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T23:21:02.688+10:00 gateway connect failed: Error: pairing required
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T23:21:02.691+10:00 [tools] sessions_list failed: gateway closed (1008): pairing required
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: Gateway target: ws://127.0.0.1:18789
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: Source: local loopback
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: Config: /home/jeebs/.openclaw/openclaw.json
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: Bind: loopback
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:21:02.700Z [ws] closed before connect conn=7c9a162e-e49e-4c78-914b-93ba99909847 remote=127.0.0.1 fwd=n/a origin=n/a host=127.0.0.1:18789 ua=n/a code=1008 reason=pairing required

$ ss -ltnp | grep -E ':(18789|[0-9]{4,5})\\b' || true
LISTEN 0      0          127.0.0.1:4913       0.0.0.0:*          
LISTEN 0      0          127.0.0.1:18792      0.0.0.0:*          
LISTEN 0      0          127.0.0.1:18789      0.0.0.0:*          
LISTEN 0      0              [::1]:18789            *:*          
```

## Phase 1.2 Gateway endpoint probes
```text
$ curl -sv http://127.0.0.1:18789/ 2>&1 | head -n 40 || true
* Failed to connect to 127.0.0.1 port 18789 after 0 ms: Couldn't connect to server
* Closing connection

$ curl -sv http://localhost:18789/ 2>&1 | head -n 40 || true
* Host localhost:18789 was resolved.
* IPv6: ::1
* IPv4: 127.0.0.1
* Failed to connect to localhost port 18789 after 0 ms: Couldn't connect to server
* Closing connection
```

## Phase 1.3 CLI device/pairing/config state
```text
$ openclaw devices list || true
[openclaw] Failed to start CLI: SystemError [ERR_SYSTEM_ERROR]: A system error occurred: uv_interface_addresses returned Unknown system error 1 (Unknown system error 1)
    at Object.networkInterfaces (node:os:217:16)
    at listTailnetAddresses (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/tailnet-2NwZRUW_.js:18:20)
    at pickPrimaryTailnetIPv4 (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/tailnet-2NwZRUW_.js:35:9)
    at buildGatewayConnectionDetails (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/call-DZzTR0NL.js:298:22)
    at callGatewayWithScopes (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/call-DZzTR0NL.js:459:28)
    at callGatewayCli (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/call-DZzTR0NL.js:484:15)
    at callGateway (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/call-DZzTR0NL.js:493:103)
    at file:///home/jeebs/src/clawd/.runtime/openclaw/dist/devices-cli-BT6TSfHM.js:21:22
    at withProgress (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/progress-Clpi3Ckj.js:116:16)
    at callGatewayCli (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/devices-cli-BT6TSfHM.js:17:56)

$ openclaw devices pending || true
error: unknown command 'pending'

$ openclaw config get gateway.remote.url || true
Config path not found: gateway.remote.url

$ openclaw config get gateway.auth.mode || true
token
```

## Phase 1.4 Cron context drift check
```text
$ crontab -l || true
crontabs/jeebs/: fopen: Permission denied
```

## Phase 2 Applied fix (Case A: pending repair pairing request)
```text
$ openclaw devices list --json
{
  "pending": [],
  "paired": [
    {
      "deviceId": "d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301",
      "publicKey": "cciOUMewwV-1Z5hvEFMxwnZ8zo7iMXeu5jMH0GA6jD4",
      "platform": "linux",
      "clientId": "cli",
      "clientMode": "cli",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing",
        "operator.read"
      ],
      "createdAtMs": 1771311120916,
      "approvedAtMs": 1771768620670,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing"
          ],
          "createdAtMs": 1771311120916,
          "rotatedAtMs": 1771768955463,
          "lastUsedAtMs": 1771484248970
        }
      ]
    },
    {
      "deviceId": "cf4e0b24aeaa879608c15454f8e4976f8ec648c656b06960e41d14618d0b378b",
      "publicKey": "3-6dDf3MCikaZqcnkEpnHd_A2oBwzHTPo_xpsVk_z2k",
      "platform": "Linux x86_64",
      "clientId": "openclaw-control-ui",
      "clientMode": "webchat",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing"
      ],
      "createdAtMs": 1771441549064,
      "approvedAtMs": 1771441549064,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing"
          ],
          "createdAtMs": 1771441549064,
          "lastUsedAtMs": 1771502457549
        }
      ]
    },
    {
      "deviceId": "b3f91ba144ed6ecc1a0140facd0a2c35cac0ba0812951d9e03edc1a59bda89a3",
      "publicKey": "cl6ukD4V4vug0PxZF2HYp9sKon7pcXhHaic_2O4afts",
      "platform": "Linux x86_64",
      "clientId": "openclaw-control-ui",
      "clientMode": "webchat",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing"
      ],
      "createdAtMs": 1771359006652,
      "approvedAtMs": 1771359006652,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing"
          ],
          "createdAtMs": 1771359006652,
          "lastUsedAtMs": 1771668565977
        }
      ]
    }
  ]
}

$ openclaw devices rotate --device d59e... --role operator --scope operator.admin --scope operator.approvals --scope operator.pairing --scope operator.read --json
{
  "deviceId": "d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301",
  "role": "operator",
  "token": "<redacted>",
  "scopes": [
    "operator.admin",
    "operator.approvals",
    "operator.pairing",
    "operator.read"
  ],
  "rotatedAtMs": 1771768956600
}

$ openclaw devices list --json
{
  "pending": [],
  "paired": [
    {
      "deviceId": "d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301",
      "publicKey": "cciOUMewwV-1Z5hvEFMxwnZ8zo7iMXeu5jMH0GA6jD4",
      "platform": "linux",
      "clientId": "cli",
      "clientMode": "cli",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing",
        "operator.read"
      ],
      "createdAtMs": 1771311120916,
      "approvedAtMs": 1771768620670,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing",
            "operator.read"
          ],
          "createdAtMs": 1771311120916,
          "rotatedAtMs": 1771768956600,
          "lastUsedAtMs": 1771484248970
        }
      ]
    },
    {
      "deviceId": "cf4e0b24aeaa879608c15454f8e4976f8ec648c656b06960e41d14618d0b378b",
      "publicKey": "3-6dDf3MCikaZqcnkEpnHd_A2oBwzHTPo_xpsVk_z2k",
      "platform": "Linux x86_64",
      "clientId": "openclaw-control-ui",
      "clientMode": "webchat",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing"
      ],
      "createdAtMs": 1771441549064,
      "approvedAtMs": 1771441549064,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing"
          ],
          "createdAtMs": 1771441549064,
          "lastUsedAtMs": 1771502457549
        }
      ]
    },
    {
      "deviceId": "b3f91ba144ed6ecc1a0140facd0a2c35cac0ba0812951d9e03edc1a59bda89a3",
      "publicKey": "cl6ukD4V4vug0PxZF2HYp9sKon7pcXhHaic_2O4afts",
      "platform": "Linux x86_64",
      "clientId": "openclaw-control-ui",
      "clientMode": "webchat",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing"
      ],
      "createdAtMs": 1771359006652,
      "approvedAtMs": 1771359006652,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing"
          ],
          "createdAtMs": 1771359006652,
          "lastUsedAtMs": 1771668565977
        }
      ]
    }
  ]
}

$ openclaw devices approve c4391666-faeb-43b3-9fdd-656b46e90780 --json
[openclaw] Failed to start CLI: Error: unknown requestId
    at GatewayClient.handleMessage (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/client-DoSZFvf3.js:1670:25)
    at WebSocket.<anonymous> (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/client-DoSZFvf3.js:1520:40)
    at WebSocket.emit (node:events:519:28)
    at Receiver.receiverOnMessage (/home/jeebs/src/clawd/.runtime/openclaw/node_modules/ws/lib/websocket.js:1225:20)
    at Receiver.emit (node:events:519:28)
    at Receiver.dataMessage (/home/jeebs/src/clawd/.runtime/openclaw/node_modules/ws/lib/receiver.js:596:14)
    at Receiver.getData (/home/jeebs/src/clawd/.runtime/openclaw/node_modules/ws/lib/receiver.js:496:10)
    at Receiver.startLoop (/home/jeebs/src/clawd/.runtime/openclaw/node_modules/ws/lib/receiver.js:167:16)
    at Receiver._write (/home/jeebs/src/clawd/.runtime/openclaw/node_modules/ws/lib/receiver.js:94:10)
    at writeOrBuffer (node:internal/streams/writable:572:12)

$ systemctl --user restart openclaw-gateway.service && systemctl --user status openclaw-gateway.service --no-pager
● openclaw-gateway.service - OpenClaw Gateway (user-owned)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-gateway.service; enabled; preset: enabled)
    Drop-In: /home/jeebs/.config/systemd/user/openclaw-gateway.service.d
             └─10-provider-lock.conf, 99-userprefix-execstart.conf, override.conf, zzzz-userprefix-execstart.conf
     Active: active (running) since Mon 2026-02-23 00:02:39 AEST; 3ms ago
   Main PID: 104765 (bash)
      Tasks: 2 (limit: 38169)
     Memory: 1.7M (peak: 1.7M)
        CPU: 2ms
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-gateway.service
             ├─104765 bash /home/jeebs/.local/bin/openclaw gateway --port 18789
             └─104769 node -e "const fs=require(\"fs\"); const p=process.argv[1]; const k=process.argv[2]; try { const o=JSON.parse(fs.readFileSync(p,\"utf8\")); const v=Object.prototype.hasOwnProperty.call(o,k) ? String(o[k]) : \"\"; process.stdout.write(v); } catch {}" /home/jeebs/.local/share/openclaw-build/version_build.json build_sha

Feb 23 00:02:39 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (user-owned).
```

## Phase 3 Verification
```text
$ openclaw status
[plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
OpenClaw status

Overview
┌─────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Item            │ Value                                                                                             │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Dashboard       │ http://127.0.0.1:18789/                                                                           │
│ OS              │ linux 6.17.0-14-generic (x64) · node 22.22.0                                                      │
│ Tailscale       │ off                                                                                               │
│ Channel         │ stable (default)                                                                                  │
│ Update          │ available · pnpm · npm update 2026.2.21-2                                                         │
│ Gateway         │ local · ws://127.0.0.1:18789 (local loopback) · unreachable (timeout)                             │
│ Gateway service │ systemd installed · enabled · running (pid 104765, state active)                                  │
│ Node service    │ systemd not installed                                                                             │
│ Agents          │ 1 · 1 bootstrapping · sessions 9 · default main active 8m ago                                     │
│ Memory          │ 0 files · 0 chunks · sources memory · plugin memory-core · vector unknown · fts ready · cache on  │
│                 │ (0)                                                                                               │
│ Probes          │ skipped (use --deep)                                                                              │
│ Events          │ none                                                                                              │
│ Heartbeat       │ 30m (main)                                                                                        │
│ Sessions        │ 9 active · default MiniMax-M2.5 (200k ctx) · ~/.openclaw/agents/main/sessions/sessions.json       │
└─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

Security audit
Summary: 0 critical · 1 warn · 1 info
  WARN Reverse proxy headers are not trusted
    gateway.bind is loopback and gateway.trustedProxies is empty. If you expose the Control UI through a reverse proxy, configure trusted proxies so local-client c…
    Fix: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
Full report: openclaw security audit
Deep probe: openclaw security audit --deep

Channels
┌──────────┬─────────┬────────┬───────────────────────────────────────────────────────────────────────────────────────┐
│ Channel  │ Enabled │ State  │ Detail                                                                                │
├──────────┼─────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────┤
│ Telegram │ ON      │ OK     │ token config (8517…TcJk · len 46) · accounts 1/1                                      │
└──────────┴─────────┴────────┴───────────────────────────────────────────────────────────────────────────────────────┘

Sessions
┌───────────────────────────────────────────────────────────────┬────────┬─────────┬──────────────┬───────────────────┐
│ Key                                                           │ Kind   │ Age     │ Model        │ Tokens            │
├───────────────────────────────────────────────────────────────┼────────┼─────────┼──────────────┼───────────────────┤
│ agent:main:main                                               │ direct │ 8m ago  │ MiniMax-M2.5 │ 83k/200k (41%)    │
│ agent:main:cron:3d7aa458-12a9-4…                              │ direct │ 14h ago │ MiniMax-M2.5 │ unknown/200k (?%) │
│ agent:main:cron:3d7aa458-12a9-4…                              │ direct │ 14h ago │ MiniMax-M2.5 │ unknown/200k (?%) │
│ agent:main:cron:500367aa-d5c7-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.9k/200k (5%)    │
│ agent:main:cron:500367aa-d5c7-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.9k/200k (5%)    │
│ agent:main:cron:32bfc7b3-4ea1-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.4k/200k (5%)    │
│ agent:main:cron:32bfc7b3-4ea1-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.4k/200k (5%)    │
│ agent:main:cron:b1a26796-f74b-4…                              │ direct │ 17h ago │ MiniMax-M2.5 │ 11k/200k (6%)     │
│ agent:main:cron:b1a26796-f74b-4…                              │ direct │ 17h ago │ MiniMax-M2.5 │ 11k/200k (6%)     │
└───────────────────────────────────────────────────────────────┴────────┴─────────┴──────────────┴───────────────────┘

FAQ: https://docs.openclaw.ai/faq
Troubleshooting: https://docs.openclaw.ai/troubleshooting

Update available (npm 2026.2.21-2). Run: openclaw update

Next steps:
  Need to share?      openclaw status --all
  Need to debug live? openclaw logs --follow
  Fix reachability first: openclaw gateway probe

$ journalctl --user -u openclaw-gateway.service -n 200 --no-pager | grep -E "pairing required|scope-upgrade|security audit" || true
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:21:02.685Z [gateway] security audit: device access upgrade requested reason=scope-upgrade device=d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301 ip=unknown-ip auth=token <redacted> roleTo=operator scopesFrom=operator.admin,operator.approvals,operator.pairing scopesTo=operator.read client=gateway-client conn=7c9a162e-e49e-4c78-914b-93ba99909847
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T23:21:02.688+10:00 gateway connect failed: Error: pairing required
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T23:21:02.691+10:00 [tools] sessions_list failed: gateway closed (1008): pairing required
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:21:02.700Z [ws] closed before connect conn=7c9a162e-e49e-4c78-914b-93ba99909847 remote=127.0.0.1 fwd=n/a origin=n/a host=127.0.0.1:18789 ua=n/a code=1008 reason=pairing required
Feb 22 23:55:03 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:55:03.811Z [gateway] security audit: device access upgrade requested reason=scope-upgrade device=d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301 ip=unknown-ip auth=token <redacted> roleTo=operator scopesFrom=operator.admin,operator.approvals,operator.pairing scopesTo=operator.read client=gateway-client conn=7116e2e5-22e5-45ae-9f0b-463db35479ad
```

Diagnosis summary:
- Primary classification: Case A (pending repair pairing request surfaced for gateway-client).
- Supporting indicator: earlier journal contained scope-upgrade + close code 1008 pairing required on loopback target ws://127.0.0.1:18789.
- Not selected: Case C (remote URL) because logs show local loopback target and bind.
- Not selected as primary: Case B drift, because service and CLI both resolve to /home/jeebs/.openclaw; issue reproduced as scope/repair approval flow.

Rollback steps:
1. Revoke rotated operator token for device d59e... if needed: openclaw devices revoke --device d59e... --role operator
2. Remove repaired device entry if needed: openclaw devices remove d59e...
3. Restart gateway: systemctl --user restart openclaw-gateway.service

## Phase 3b Final verification after gateway restart
```text
$ systemctl --user status openclaw-gateway.service --no-pager
● openclaw-gateway.service - OpenClaw Gateway (user-owned)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-gateway.service; enabled; preset: enabled)
    Drop-In: /home/jeebs/.config/systemd/user/openclaw-gateway.service.d
             └─10-provider-lock.conf, 99-userprefix-execstart.conf, override.conf, zzzz-userprefix-execstart.conf
     Active: active (running) since Mon 2026-02-23 00:02:39 AEST; 4min 26s ago
   Main PID: 104765 (openclaw)
      Tasks: 38 (limit: 38169)
     Memory: 329.4M (peak: 609.9M)
        CPU: 4.916s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-gateway.service
             ├─104765 openclaw
             └─104838 openclaw-gateway

Feb 23 00:02:41 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:41.300Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 23 00:02:41 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:41.301Z [gateway] listening on ws://127.0.0.1:18789 (PID 104838)
Feb 23 00:02:41 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:41.302Z [gateway] listening on ws://[::1]:18789
Feb 23 00:02:41 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:41.303Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-23.log
Feb 23 00:02:41 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:41.322Z [browser/service] Browser control service ready (profiles=2)
Feb 23 00:02:41 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:41.816Z [ws] ⇄ res ✓ config.get 431ms conn=5ec37c72…1dba id=85662d62…ce21
Feb 23 00:02:41 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:41.818Z [ws] ⇄ res ✓ status 436ms conn=5ec37c72…1dba id=2f6c1223…0478
Feb 23 00:02:45 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:45.245Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 23 00:02:45 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:45.254Z [telegram] autoSelectFamily=true (default-node22)
Feb 23 00:02:48 jeebs-Z490-AORUS-MASTER openclaw[104838]: 2026-02-22T14:02:48.302Z [ws] ⇄ res ✓ health 6920ms conn=5ec37c72…1dba id=16e33329…ef61

$ openclaw health || true
[plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Telegram: ok (@jeebsdalibot) (2313ms)
Agents: main (default)
Heartbeat interval: 30m (main)
Session store (main): /home/jeebs/.openclaw/agents/main/sessions/sessions.json (9 entries)
- agent:main:main (12m ago)
- agent:main:cron:3d7aa458-12a9-4501-bcb1-6853ec0e6fb0 (847m ago)
- agent:main:cron:3d7aa458-12a9-4501-bcb1-6853ec0e6fb0:run:fc24f385-379e-4b44-bdf9-c7bcfbf4103c (847m ago)
- agent:main:cron:500367aa-d5c7-4f52-9893-f501d6684067 (907m ago)
- agent:main:cron:500367aa-d5c7-4f52-9893-f501d6684067:run:68f73745-88ec-4966-93e2-b5e5c8c72c3a (907m ago)

$ openclaw status || true
[plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
OpenClaw status

Overview
┌─────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Item            │ Value                                                                                             │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Dashboard       │ http://127.0.0.1:18789/                                                                           │
│ OS              │ linux 6.17.0-14-generic (x64) · node 22.22.0                                                      │
│ Tailscale       │ off                                                                                               │
│ Channel         │ stable (default)                                                                                  │
│ Update          │ available · pnpm · npm update 2026.2.21-2                                                         │
│ Gateway         │ local · ws://127.0.0.1:18789 (local loopback) · reachable 16ms · auth token · jeebs-Z490-AORUS-   │
│                 │ MASTER (192.168.0.162) app unknown linux 6.17.0-14-generic                                        │
│ Gateway service │ systemd installed · enabled · running (pid 104765, state active)                                  │
│ Node service    │ systemd not installed                                                                             │
│ Agents          │ 1 · 1 bootstrapping · sessions 9 · default main active 13m ago                                    │
│ Memory          │ 0 files · 0 chunks · sources memory · plugin memory-core · vector unknown · fts ready · cache on  │
│                 │ (0)                                                                                               │
│ Probes          │ skipped (use --deep)                                                                              │
│ Events          │ none                                                                                              │
│ Heartbeat       │ 30m (main)                                                                                        │
│ Sessions        │ 9 active · default MiniMax-M2.5 (200k ctx) · ~/.openclaw/agents/main/sessions/sessions.json       │
└─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

Security audit
Summary: 0 critical · 1 warn · 1 info
  WARN Reverse proxy headers are not trusted
    gateway.bind is loopback and gateway.trustedProxies is empty. If you expose the Control UI through a reverse proxy, configure trusted proxies so local-client c…
    Fix: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
Full report: openclaw security audit
Deep probe: openclaw security audit --deep

Channels
┌──────────┬─────────┬────────┬───────────────────────────────────────────────────────────────────────────────────────┐
│ Channel  │ Enabled │ State  │ Detail                                                                                │
├──────────┼─────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────┤
│ Telegram │ ON      │ OK     │ token config (8517…TcJk · len 46) · accounts 1/1                                      │
└──────────┴─────────┴────────┴───────────────────────────────────────────────────────────────────────────────────────┘

Sessions
┌───────────────────────────────────────────────────────────────┬────────┬─────────┬──────────────┬───────────────────┐
│ Key                                                           │ Kind   │ Age     │ Model        │ Tokens            │
├───────────────────────────────────────────────────────────────┼────────┼─────────┼──────────────┼───────────────────┤
│ agent:main:main                                               │ direct │ 13m ago │ MiniMax-M2.5 │ 83k/200k (41%)    │
│ agent:main:cron:3d7aa458-12a9-4…                              │ direct │ 14h ago │ MiniMax-M2.5 │ unknown/200k (?%) │
│ agent:main:cron:3d7aa458-12a9-4…                              │ direct │ 14h ago │ MiniMax-M2.5 │ unknown/200k (?%) │
│ agent:main:cron:500367aa-d5c7-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.9k/200k (5%)    │
│ agent:main:cron:500367aa-d5c7-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.9k/200k (5%)    │
│ agent:main:cron:32bfc7b3-4ea1-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.4k/200k (5%)    │
│ agent:main:cron:32bfc7b3-4ea1-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ 9.4k/200k (5%)    │
│ agent:main:cron:b1a26796-f74b-4…                              │ direct │ 18h ago │ MiniMax-M2.5 │ 11k/200k (6%)     │
│ agent:main:cron:b1a26796-f74b-4…                              │ direct │ 18h ago │ MiniMax-M2.5 │ 11k/200k (6%)     │
└───────────────────────────────────────────────────────────────┴────────┴─────────┴──────────────┴───────────────────┘

FAQ: https://docs.openclaw.ai/faq
Troubleshooting: https://docs.openclaw.ai/troubleshooting

Update available (npm 2026.2.21-2). Run: openclaw update

Next steps:
  Need to share?      openclaw status --all
  Need to debug live? openclaw logs --follow
  Need to test channels? openclaw status --deep

$ journalctl --user -u openclaw-gateway.service -n 120 --no-pager | grep -E "pairing required|scope-upgrade" || true
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:21:02.685Z [gateway] security audit: device access upgrade requested reason=scope-upgrade device=d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301 ip=unknown-ip auth=token <redacted> roleTo=operator scopesFrom=operator.admin,operator.approvals,operator.pairing scopesTo=operator.read client=gateway-client conn=7c9a162e-e49e-4c78-914b-93ba99909847
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T23:21:02.688+10:00 gateway connect failed: Error: pairing required
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T23:21:02.691+10:00 [tools] sessions_list failed: gateway closed (1008): pairing required
Feb 22 23:21:02 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:21:02.700Z [ws] closed before connect conn=7c9a162e-e49e-4c78-914b-93ba99909847 remote=127.0.0.1 fwd=n/a origin=n/a host=127.0.0.1:18789 ua=n/a code=1008 reason=pairing required
Feb 22 23:55:03 jeebs-Z490-AORUS-MASTER openclaw[94232]: 2026-02-22T13:55:03.811Z [gateway] security audit: device access upgrade requested reason=scope-upgrade device=d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301 ip=unknown-ip auth=token <redacted> roleTo=operator scopesFrom=operator.admin,operator.approvals,operator.pairing scopesTo=operator.read client=gateway-client conn=7116e2e5-22e5-45ae-9f0b-463db35479ad
```
