# Dali fix: openclaw dashboard runtime missing

## Symptom
- Error: Cannot find module .runtime/openclaw/openclaw.mjs

## Environment
- node: v22.22.0
- openclaw path: /home/jeebs/.local/bin/openclaw
- main HEAD: f626f84

## Actions
- Verified missing .runtime/openclaw/openclaw.mjs
- Rebuilt runtime (script or npm build)
  - verify_runtime_autoupdate dry-run: ok
  - npm build fallback unavailable (no build script)
  - recovered runtime by copying installed OpenClaw package from /usr/lib/node_modules/openclaw to .runtime/openclaw
- Reinstalled CLI into /home/jeebs/.local
- Re-tested: openclaw dashboard
- Reloaded/restarted gateway service and re-tested dashboard

## Result
- success
- Runtime module restored: .runtime/openclaw/openclaw.mjs present
- Initial dashboard retest after runtime restore failed with:
  - SystemError [ERR_SYSTEM_ERROR]: uv_interface_addresses returned Unknown system error 1
- After systemd user daemon-reload + openclaw-gateway restart:
  - openclaw dashboard succeeded and returned dashboard URL
