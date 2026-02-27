# Dali tailscale serve privileged step audit

## Why sudo is required
`tailscale serve` configuration is managed by the local Tailscale daemon on Linux and may require elevated privileges depending on host policy. The apply step is intentionally separated into a single explicit operator command run under sudo.

## Scripts
- `tools/apply_tailscale_serve_dashboard.sh`
  - Enforces root (`Run with sudo`), verifies `tailscale` exists, applies:
    - `tailscale serve --http=18789 http://127.0.0.1:18789`
  - Prints `tailscale serve status` at the end.
- `tools/check_tailscale_serve_dashboard.sh`
  - Non-privileged verifier.
  - Checks `tailscale status`.
  - Checks `tailscale serve status` includes mapping for `18789` and `127.0.0.1:18789`.
  - Emits explicit permission guidance when serve status requires sudo.
  - Verifies local port `18789` bind from `ss -tulpn` and fails closed on `0.0.0.0`/`:::`/non-loopback bindings.

## How to run
```bash
sudo bash tools/apply_tailscale_serve_dashboard.sh
```

## Verification commands
```bash
bash tools/check_tailscale_serve_dashboard.sh
bash workspace/scripts/verify_preflight.sh
```
