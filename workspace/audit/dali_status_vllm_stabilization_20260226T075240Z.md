# Dali Status + vLLM Stabilization

- date_utc: 2026-02-26T07:52:40Z
- branch: codex/fix/dali-audit-hardening-mcp-client-20260226
- sha: 0cf7c63efd192f8004a7894a21792bc2d26954bb

## Changes
- Added runtime network-enumeration guard to prevent openclaw status hard-fail on uv_interface_addresses errors.
- Rebuild now injects runtime overlay into dist/entry.js (actual CLI entrypoint), not only dist/index.js.
- Added assistant vLLM launch wrapper with preflight checks (python/entrypoint/model/port/GPU memory) and clear error markers.
- Added user systemd unit template with Restart=on-failure, RestartSec=10, StartLimitIntervalSec=60, StartLimitBurst=3.

## Before: openclaw status
```text
Gateway connection:
  Gateway target: ws://127.0.0.1:18789
  Source: local loopback
  Config: /home/jeebs/.openclaw/openclaw.json
  Bind: loopback

[openclaw] Failed to start CLI: SystemError [ERR_SYSTEM_ERROR]: A system error occurred: uv_interface_addresses returned Unknown system error 1 (Unknown system error 1)
    at Object.networkInterfaces (node:os:217:16)
    at listTailnetAddresses (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/tailnet-BOWO-AaH.js:16:20)
    at pickPrimaryTailnetIPv4 (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/tailnet-BOWO-AaH.js:33:9)
    at resolveControlUiLinks (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/onboard-helpers-DOdss3HD.js:368:22)
    at file:///home/jeebs/src/clawd/.runtime/openclaw/dist/status-akosBtzI.js:1733:10
    at statusCommand (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/status-akosBtzI.js:1739:4)
    at async Object.run (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/run-main-BUdbv390.js:150:3)
    at async runCli (file:///home/jeebs/src/clawd/.runtime/openclaw/dist/run-main-BUdbv390.js:393:6)
```

## After: openclaw status (with ANTHROPIC_API_KEY=dummy)
```text
{"ts":"2026-02-26T07:51:34.272Z","level":"info","msg":"outbound_fetch_sanitizer_installed","service":"runtime-hardening","module":"runtime-hardening-overlay"}
{"ts":"2026-02-26T07:51:34.273Z","level":"info","msg":"runtime_hardening_initialized","service":"runtime-hardening","module":"runtime-hardening-overlay","config":{"anthropicApiKey":"<redacted>","nodeEnv":"development","workspaceRoot":"/home/jeebs/src/clawd","agentWorkspaceRoot":"/home/jeebs/src/clawd/.agent_workspace","skillsRoot":"/home/jeebs/src/clawd/skills","sessionTtlMs":21600000,"sessionMax":50,"historyMaxMessages":200,"mcpServerStartTimeoutMs":30000,"logLevel":"info","fsAllowOutsideWorkspace":false,"telegramReplyMode":"never"}}
{"ts":"2026-02-26T07:51:34.310Z","level":"info","msg":"outbound_fetch_sanitizer_installed","service":"runtime-hardening","module":"runtime-hardening-overlay"}
{"ts":"2026-02-26T07:51:34.311Z","level":"info","msg":"runtime_hardening_initialized","service":"runtime-hardening","module":"runtime-hardening-overlay","config":{"anthropicApiKey":"<redacted>","nodeEnv":"development","workspaceRoot":"/home/jeebs/src/clawd","agentWorkspaceRoot":"/home/jeebs/src/clawd/.agent_workspace","skillsRoot":"/home/jeebs/src/clawd/skills","sessionTtlMs":21600000,"sessionMax":50,"historyMaxMessages":200,"mcpServerStartTimeoutMs":30000,"logLevel":"info","fsAllowOutsideWorkspace":false,"telegramReplyMode":"never"}}
Gateway connection:
  Gateway target: ws://127.0.0.1:18789
  Source: local loopback
  Config: /home/jeebs/.openclaw/openclaw.json
  Bind: loopback

{"ts":"2026-02-26T07:51:38.866Z","level":"warn","msg":"network_enum_degraded","service":"runtime-hardening","module":"runtime-hardening-overlay","code":"NETWORK_ENUM_DEGRADED","error":"A system error occurred: uv_interface_addresses returned Unknown system error 1 (Unknown system error 1)"}
NETWORK_ENUM_DEGRADED: A system error occurred: uv_interface_addresses returned Unknown system error 1 (Unknown system error 1)
OpenClaw status

Overview
┌─────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Item            │ Value                                                                                             │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Dashboard       │ http://127.0.0.1:18789/                                                                           │
│ OS              │ linux 6.17.0-14-generic (x64) · node 22.22.0                                                      │
│ Tailscale       │ off                                                                                               │
│ Channel         │ stable (default)                                                                                  │
│ Update          │ pnpm · npm latest unknown                                                                         │
│ Gateway         │ local · ws://127.0.0.1:18789 (local loopback) · unreachable (connect failed: connect EPERM 127.0. │
│                 │ 0.1:18789 - Local (undefined:undefined))                                                          │
│ Gateway service │ systemd installed · disabled · unknown (Error: systemctl --user unavailable: Failed to connect    │
│                 │ to bus: Operation not permitted)                                                                  │
│ Node service    │ systemd not installed                                                                             │
│ Agents          │ 1 · no bootstrap files · sessions 31 · default main active 48m ago                                │
│ Memory          │ 0 files · 0 chunks · sources memory · plugin memory-core · vector unknown · fts ready · cache on  │
│                 │ (0)                                                                                               │
│ Probes          │ skipped (use --deep)                                                                              │
│ Events          │ none                                                                                              │
│ Heartbeat       │ 30m (main)                                                                                        │
│ Sessions        │ 31 active · default MiniMax-M2.5 (200k ctx) · ~/.openclaw/agents/main/sessions/sessions.json      │
└─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

Security audit
Summary: 0 critical · 1 warn · 1 info
  WARN Reverse proxy headers are not trusted
```

## Before: vLLM flapping evidence
```text
9:Feb 26 17:41:22 jeebs-Z490-AORUS-MASTER python3.12[409240]: (EngineCore_DP0 pid=409240) ValueError: Free memory on device cuda:0 (0.32/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
67:Feb 26 17:41:24 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
70:Feb 26 17:41:29 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 2740.
109:Feb 26 17:41:39 jeebs-Z490-AORUS-MASTER python3.12[409441]: (EngineCore_DP0 pid=409441) ERROR 02-26 17:41:39 [core.py:946] ValueError: Free memory on device cuda:0 (0.34/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
138:Feb 26 17:41:39 jeebs-Z490-AORUS-MASTER python3.12[409441]: (EngineCore_DP0 pid=409441) ValueError: Free memory on device cuda:0 (0.34/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
196:Feb 26 17:41:40 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
199:Feb 26 17:41:45 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 2741.
```

## After: vLLM controlled backoff/preflight
```text
Restart=on-failure
RestartUSec=10s
Result=exit-code
NRestarts=3
ExecMainStatus=42
StartLimitIntervalUSec=1min
StartLimitBurst=3
---
92:Feb 26 17:48:53 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=42/n/a
94:Feb 26 17:49:03 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 1.
96:Feb 26 17:49:03 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=42/n/a
98:Feb 26 17:49:14 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 2.
100:Feb 26 17:49:14 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=42/n/a
102:Feb 26 17:49:24 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 3.
103:Feb 26 17:49:24 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Start request repeated too quickly.
107:Feb 26 17:51:50 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=42/n/a
109:Feb 26 17:52:01 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 1.
111:Feb 26 17:52:01 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=42/n/a
113:Feb 26 17:52:11 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 2.
115:Feb 26 17:52:11 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Main process exited, code=exited, status=42/n/a
117:Feb 26 17:52:21 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Scheduled restart job, restart counter is at 3.
118:Feb 26 17:52:21 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Start request repeated too quickly.
---
VLLM_ASSISTANT_PREFLIGHT_FAILED reason=port_in_use port=8001
VLLM_ASSISTANT_PREFLIGHT_FAILED reason=port_in_use port=8001
VLLM_ASSISTANT_PREFLIGHT_FAILED reason=port_in_use port=8001
VLLM_ASSISTANT_PREFLIGHT_FAILED reason=port_in_use port=8001 listener="LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3259,fd=25))           "
VLLM_ASSISTANT_PREFLIGHT_FAILED reason=port_in_use port=8001 listener="LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3259,fd=25))           "
VLLM_ASSISTANT_PREFLIGHT_FAILED reason=port_in_use port=8001 listener="LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3259,fd=25))           "
```

## Verification Commands
```bash
npm run typecheck:hardening
npm run test:hardening
npm run runtime:rebuild
openclaw status --verbose
ANTHROPIC_API_KEY=dummy openclaw status --verbose
systemctl --user show -p Restart,RestartUSec,StartLimitIntervalUSec,StartLimitBurst,NRestarts,Result,ExecMainStatus openclaw-vllm.service
journalctl --user -u openclaw-vllm.service -n 120 --no-pager
```
