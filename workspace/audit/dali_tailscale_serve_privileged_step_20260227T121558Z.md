# Dali Tailscale Serve Privileged Step

UTC: 2026-02-27

## Summary
Added a privileged apply script and a non-privileged verifier for dashboard tailnet exposure, then wired the verifier into preflight.

## Why sudo is required
On this Linux host, `tailscale serve` writes daemon-managed serve config. Without root/operator capability it is denied:
- `tailscale serve --http=18789 http://127.0.0.1:18789` -> `Access denied: serve config denied`
- `sudo tailscale serve ...` requires interactive sudo credentials on Dali.

## Files added/changed
- `tools/apply_tailscale_serve_dashboard.sh` (new, root-only apply)
- `tools/check_tailscale_serve_dashboard.sh` (new, non-privileged verifier)
- `workspace/scripts/verify_preflight.sh` (wired verifier call)
- `workspace/docs/ops/TAILSCALE_SERVE_DASHBOARD.md` (operator note)

## Script behaviors
### `tools/apply_tailscale_serve_dashboard.sh`
- `set -euo pipefail`
- refuses non-root with `Run with sudo`
- checks `tailscale` exists
- applies idempotent mapping:
  - `tailscale serve --http=18789 http://127.0.0.1:18789`
- prints `tailscale serve status`

### `tools/check_tailscale_serve_dashboard.sh`
- `set -euo pipefail`
- checks `tailscale` exists and `tailscale status` works
- checks `tailscale serve status`
  - if permission-related failure, prints:
    - `tailscale serve status requires sudo on this system; run: sudo tools/apply_tailscale_serve_dashboard.sh`
- asserts mapping includes `18789` and `127.0.0.1:18789`
- asserts dashboard listener on port 18789 is loopback-only (no `0.0.0.0` / `:::`)
- prints `ok` on success, explicit `FAIL:` on failure

## Verification commands run
- `OPENCLAW_QUIESCE=1 node --test` -> pass (60/60)
- `OPENCLAW_QUIESCE=1 python3 -m unittest -v` -> pass (276, skipped=1)
- `bash tools/apply_tailscale_serve_dashboard.sh` -> `Run with sudo` (expected)
- `bash tools/check_tailscale_serve_dashboard.sh` (host context) -> currently fails until serve mapping is applied:
  - `FAIL: tailscale serve dashboard mapping missing (expected 18789 -> 127.0.0.1:18789)`

## Manual operator step
- `sudo bash tools/apply_tailscale_serve_dashboard.sh`

## Post-step verify
- `bash tools/check_tailscale_serve_dashboard.sh`
- `tailscale serve status`
- `curl -sf http://127.0.0.1:18789/`

