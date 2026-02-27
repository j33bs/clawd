# Tailscale gateway mesh investigation
timestamp_utc: 20260227T120144Z

## Node addresses
local_tailscale_ipv4: 100.84.143.50
peer_lines:
100.84.143.50 heaths-macbook-pro macOS
100.113.160.1 jeebs-z490-aorus-master linux

## Binding mode results
phase2_default_mode: loopback
phase6_enable_attempt: OPENCLAW_GATEWAY_BIND=tailscale
phase6_result: blocked
block_reason: non-loopback Control UI requires gateway.controlUi.allowedOrigins
rollback_applied: OPENCLAW_GATEWAY_BIND reset to loopback

## Health probes
probe_local_ts_ip: 000 0.002268
PROBE_FAILED
probe_peer_ip: 000 0.069650
PROBE_FAILED

## Listener evidence (post-rollback)
COMMAND   PID        USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
node    95039 heathyeager   16u  IPv4 0x60d2b1b3d69f528b      0t0  TCP 127.0.0.1:18789 (LISTEN)
node    95039 heathyeager   17u  IPv6 0xe4c2dab7d0f236e4      0t0  TCP [::1]:18789 (LISTEN)

## Rollback instructions
launchctl setenv OPENCLAW_GATEWAY_BIND loopback
launchctl kickstart -k gui/501/ai.openclaw.gateway
(if plist env changed) set :EnvironmentVariables:OPENCLAW_GATEWAY_BIND to loopback and bootstrap
