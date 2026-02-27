# Tailnet Bind + Control UI Guard Fix (2026-02-27T12:22:18Z)

## Original Guard Error Signature

Observed gateway startup guard in OpenClaw runtime:

`non-loopback Control UI requires gateway.controlUi.allowedOrigins (set explicit origins), or set gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback=true to use Host-header origin fallback mode`

## Chosen Mechanism

- No `openclaw gateway run` CLI flag exists to disable Control UI or set allowed origins directly.
- Implemented safe wrapper behavior using an ephemeral config overlay file in `/tmp`.
- Wrapper sets `OPENCLAW_CONFIG_PATH` to the overlay for this process only.
- No persistent edits are made to `~/.openclaw/openclaw.json`.
- `tailnet` bind now requires explicit `OPENCLAW_TAILNET_CONTROL_UI=off|allowlist`.
- Default remains `loopback`; no policy-router edits; no `0.0.0.0`/`::` bind allowed.

## Env Examples

RPC-only (recommended):

```bash
launchctl setenv OPENCLAW_GATEWAY_BIND tailnet
launchctl setenv OPENCLAW_TAILNET_CONTROL_UI off
launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway
```

Remote UI via Tailscale allowlist (optional):

```bash
TS_IP=$(tailscale ip -4 | head -n1)
launchctl setenv OPENCLAW_GATEWAY_BIND tailnet
launchctl setenv OPENCLAW_TAILNET_CONTROL_UI allowlist
launchctl setenv OPENCLAW_TAILNET_ALLOWED_ORIGINS "http://${TS_IP}:18789"
launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway
```

Rollback:

```bash
launchctl unsetenv OPENCLAW_GATEWAY_BIND
launchctl unsetenv OPENCLAW_TAILNET_CONTROL_UI
launchctl unsetenv OPENCLAW_TAILNET_ALLOWED_ORIGINS
launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway
```
