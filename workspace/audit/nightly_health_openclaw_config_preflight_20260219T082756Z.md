# Nightly Health OpenClaw Config Preflight Audit

- Timestamp (UTC): 2026-02-19T08:27:56Z
- Branch: codex/fix/nightly-health-openclaw-config-preflight

## Before

Observed opaque failures in nightly health when OpenClaw user-local config was invalid (for example missing plugin paths in ~/.openclaw/openclaw.json), with insufficient attribution in nightly diagnostics.

## Change

- Added OpenClaw config preflight to   "/Users/heathyeager/clawd/workspace/scripts/nightly_build.sh" (health path).
- Preflight runs:     `openclaw doctor --non-interactive --no-workspace-suggestions`
- On config-invalid signatures (Invalid config / plugin path not found / plugin not found), health now fails fast with explicit remediation:
  - `OpenClaw config invalid (likely ~/.openclaw/openclaw.json). Run: openclaw doctor --fix`
- Added minimal redaction for token-like key/value lines before writing doctor output to nightly log.
- Added optional config source logging:
  - default: `~/.openclaw/openclaw.json`
  - override: `OPENCLAW_CONFIG_PATH`
- Added verifier script:   "/Users/heathyeager/clawd/workspace/scripts/verify_nightly_health_config.sh"

## Commands Run + Outcomes

1. `bash workspace/scripts/nightly_build.sh health`
- Result: PASS (exit 0)
- Evidence excerpt:
  - `OpenClaw config source: /Users/heathyeager/.openclaw/openclaw.json (default)`
  - `✅ OpenClaw config preflight: OK`

2. `bash workspace/scripts/verify_nightly_health_config.sh`
- Result: PASS (exit 0)
- Coverage:
  - valid-config path: expects health exit 0
  - invalid-config path (temp HOME + temp OPENCLAW_CONFIG_PATH): expects health exit 1 and explicit remediation message

## Notes

- No repo application runtime behavior changed outside nightly health diagnostics/preflight.
- No secrets printed; redaction added for token-like key/value output lines.
