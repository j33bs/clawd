# Dali Tailscale Implementation + Hardening Audit

UTC: 2026-02-27

## Outcome
Repo-governed hardening checks were implemented and wired into preflight. Host-level Tailscale installation/activation is blocked in this execution context because privileged commands require interactive sudo credentials.

## Files changed
- `tools/check_tailscale_surface.sh`
- `workspace/scripts/verify_preflight.sh`

## Install steps + versions
Evidence:
- `workspace/audit/evidence/tailscale_20260227T114739Z/install.txt`
- `workspace/audit/evidence/tailscale_20260227T114759Z/install.txt`
- `workspace/audit/evidence/tailscale_20260227T114947Z/install_blocker.txt`

Observed:
- Ubuntu: `ID=ubuntu VERSION_CODENAME=noble VERSION_ID=24.04`
- `tailscale` binary not present
- Privileged install blocked: `sudo: a password is required`

## Tailscale status / netcheck / serve status evidence
Evidence directory:
- `workspace/audit/evidence/tailscale_20260227T114947Z/`

Files:
- `status.txt` (`tailscale status/ip/netcheck` unavailable because binary missing)
- `serve_status.txt` (`tailscale serve status` unavailable because binary missing)
- `e2e.txt` (local dashboard health check available; no tailnet verification possible)

## Exposed endpoints + hardening state
Current observed listeners (from `serve_status.txt`):
- `127.0.0.1:18789`
- `127.0.0.1:8001`
- `[::1]:18789`

No `0.0.0.0` binding was observed for the target OpenClaw surfaces.

Tailscale Serve exposure was not configured because Tailscale is not installed in this host context.

## Obligatory hardening checker
Added `tools/check_tailscale_surface.sh` with deterministic checks:
- tailscale installed and version callable
- `tailscaled` active (`systemctl is-active tailscaled`)
- `tailscale status` succeeds
- OpenClaw watched ports (`18789`, `8001`, optional `OPENCLAW_GATEWAY_PORT`) not exposed on non-loopback addresses
- `tailscale serve status` exists and is configured
- serve proxy targets restricted to allowlist:
  - `127.0.0.1:18789`
  - optional `127.0.0.1:$OPENCLAW_GATEWAY_PORT` when set and not `18789`

Wired into preflight:
- `workspace/scripts/verify_preflight.sh` now runs `./tools/check_tailscale_surface.sh`

Deterministic invocation evidence:
- `workspace/audit/evidence/tailscale_20260227T114947Z/check_tailscale_surface.txt`
- Current result: `FAIL: tailscale not installed (tailscale binary missing)`

## Regression tests
- `OPENCLAW_QUIESCE=1 node --test` => pass (60/60)
- `OPENCLAW_QUIESCE=1 python3 -m unittest -v` => pass (276 tests, skipped=1)

## Completion commands required on Dali host (interactive sudo)
Run these on host with sudo credentials, then re-run the checker:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null
sudo apt-get update
sudo apt-get install -y tailscale
sudo systemctl enable --now tailscaled
sudo tailscale up
sudo tailscale serve --http=18789 http://127.0.0.1:18789
bash tools/check_tailscale_surface.sh
```

## Rollback
Host:
- `sudo tailscale serve reset`
- `sudo tailscale down`
- `sudo systemctl disable --now tailscaled`
- optional: `sudo apt remove tailscale`

Repo:
- `git revert <sha>`
