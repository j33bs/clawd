# Dali Tailscale Post-Install Hardening

UTC: 2026-02-27

## Precondition verification
Evidence: `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/precondition.txt`

- `tailscale version` -> 1.94.2
- `tailscale status` -> authenticated, node present (`100.113.160.1`)
- `tailscale ip -4` -> `100.113.160.1`
- `tailscale netcheck` -> UDP/IPv4/IPv6 OK, nearest DERP `Sydney`

## OpenClaw local surface discovery
Evidence: `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/surfaces.txt`

- Dashboard/gateway on loopback: `127.0.0.1:18789` (+ `[::1]:18789`)
- vLLM health on loopback: `127.0.0.1:8001`
- `openclaw health` reports Telegram OK

## Tailscale serve configuration attempt
Evidence:
- `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/serve_status.txt`
- `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/serve_sudo_attempt.txt`

Attempted dashboard-only scheme:
- `tailscale serve --http=18789 http://127.0.0.1:18789`

Result:
- denied without root operator rights (`Access denied: serve config denied`)
- `sudo tailscale serve ...` blocked in this execution context because interactive password is required.
- current serve status: `No serve config`

## Port binding proof
Evidence: `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/serve_status.txt`

Observed listeners remain local-only:
- `127.0.0.1:18789`
- `[::1]:18789`
- `127.0.0.1:8001`

No `0.0.0.0` exposure for target OpenClaw surfaces was observed.

## Repo-governed checker
Updated: `tools/check_tailscale_surface.sh`

Implemented behavior:
- verifies `tailscale` binary + `tailscale status`
- verifies `tailscaled` active via `systemctl is-active tailscaled`
  - falls back to status-only path when systemd is unavailable in current execution context
- verifies watched ports (`18789`, `8001`, optional gateway env) are loopback-only
- verifies `tailscale serve status --json` is configured and only proxies allowlisted loopback backends:
  - `127.0.0.1:18789`
  - optional `127.0.0.1:<gateway_port>` via `OPENCLAW_TAILSCALE_GATEWAY_PORT` or `OPENCLAW_GATEWAY_PORT`
- silent on success, explicit `FAIL:` lines on failure

Wiring:
- `workspace/scripts/verify_preflight.sh` already includes `./tools/check_tailscale_surface.sh` (kept single-call, non-noisy on pass)

Checker evidence:
- host-context run: `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/check_tailscale_surface_host.txt`
  - current result: `FAIL: tailscale serve is not configured`
- preflight evidence: `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/verify_preflight.txt`

## E2E evidence
Evidence: `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/e2e.txt`

- local dashboard reachable: `curl -sf http://127.0.0.1:18789/health`
- tailnet dashboard curl (`http://100.113.160.1:18789/`) did not return content because serve is not configured.

## Regression tests
Evidence:
- `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/tests_node_after.txt` -> pass (60/60)
- `workspace/audit/evidence/tailscale_postinstall_20260227T115739Z/tests_python_after.txt` -> pass (276, skipped=1)

## Rollback
- `sudo tailscale serve reset`

