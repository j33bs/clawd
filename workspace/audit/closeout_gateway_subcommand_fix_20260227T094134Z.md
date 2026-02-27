# Closeout: gateway subcommand fix
timestamp_utc: 20260227T094134Z
merged_from: codex/fix/launchd-gateway-subcommand-20260227
post_merge_checks:
- listener on 127.0.0.1:18789: yes
- curl /health: 200
- openclaw gateway status --deep: runtime running, rpc probe ok
