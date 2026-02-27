# Gateway crashloop fix: ensure wrapper starts gateway subcommand
timestamp_utc: 20260227T092143Z

Chosen VERB (help-discovered): start
Final wrapper exec verb: run

## Rationale
- 'start' is a service-manager verb and fails foreground proof after bootout ('Gateway service not loaded').
- Wrapper now uses 'run' so LaunchAgent owns a long-running gateway process.

## Evidence
- openclaw --version:
2026.2.26

- gateway help captured: /tmp/oc_gateway_help_20260227T092143Z.txt
- wrapper foreground log: /tmp/wrapper_fg_20260227T092143Z.log
- gateway.err tail (redacted): /tmp/gateway_err_tail_20260227T092143Z.txt

## Verification
- lsof :18789 LISTEN (post-launchd):
COMMAND   PID        USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
node    77529 heathyeager   15u  IPv4 0x1b5bfc91b1a379fd      0t0  TCP 127.0.0.1:18789 (LISTEN)
node    77529 heathyeager   17u  IPv6 0xc857ff03160ca31d      0t0  TCP [::1]:18789 (LISTEN)

- curl /health headers:
HTTP/1.1 200 OK
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' ws: wss:
Content-Type: text/html; charset=utf-8
Cache-Control: no-cache
Date: Fri, 27 Feb 2026 09:28:46 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 692


- openclaw gateway status --deep (tail):
Service: LaunchAgent (loaded)
File logs: /tmp/openclaw/openclaw-2026-02-27.log
Command: /bin/zsh /Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh
Service file: ~/Library/LaunchAgents/ai.openclaw.gateway.plist
Working dir: ~/clawd
Service env: OPENCLAW_GATEWAY_PORT=18789

Service config looks out of date or non-standard.
Service config issue: Service command does not include the gateway subcommand
Recommendation: run "openclaw doctor" (or "openclaw doctor --repair").
Config (cli): ~/.openclaw/openclaw.json
Config (service): ~/.openclaw/openclaw.json

Gateway: bind=loopback (127.0.0.1), port=18789 (env/config)
Probe target: ws://127.0.0.1:18789
Dashboard: http://127.0.0.1:18789/
Probe note: Loopback-only gateway; only local clients can connect.

Runtime: running (pid 77520, state active)
RPC probe: ok

Listening: 127.0.0.1:18789
Other gateway-like services detected (best effort):
- ai.openclaw.env-bootstrap (user, plist: /Users/heathyeager/Library/LaunchAgents/ai.openclaw.env-bootstrap.plist)
Cleanup hint: launchctl bootout gui/$UID/ai.openclaw.gateway
Cleanup hint: rm ~/Library/LaunchAgents/ai.openclaw.gateway.plist

Recommendation: run a single gateway per machine for most setups. One gateway supports multiple agents (see docs: /gateway#multiple-gateways-same-host).
If you need multiple gateways (e.g., a rescue bot on the same host), isolate ports + config/state (see docs: /gateway#multiple-gateways-same-host).

Troubles: run openclaw status
Troubleshooting: https://docs.openclaw.ai/troubleshooting
