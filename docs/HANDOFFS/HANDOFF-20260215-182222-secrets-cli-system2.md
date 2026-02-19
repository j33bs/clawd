# System-2: Restore `openclaw secrets` via Plugin + Secret-Safe Status

## Symptom
- `openclaw secrets --help` returned the global CLI help (exit 0), not secrets help.
- `openclaw secrets status` failed (unknown subcommand / exit 1).

## Root Cause (Evidence)
- `which -a openclaw` resolved to a global install: `~/.npm-global/bin/openclaw` (OpenClaw `2026.2.12`).
- That CLI version did not ship a built-in `secrets` subcommand.
- This repo *does* include a secret-safe secrets bridge CLI: `scripts/openclaw_secrets_cli.js`.
- OpenClaw supports dynamic CLI command registration via plugins.

## Fix (What Changed In-Repo)
- `scripts/openclaw_secrets_cli.js`
  - `status` now prints:
    - `secrets_bridge_enabled=true|false`
    - `secrets_backend=<label>`
    - followed by provider rows (names only; no values)
- Added an OpenClaw CLI plugin to expose the repo secrets bridge as `openclaw secrets ...`:
  - `scripts/openclaw_secrets_plugin.js`
  - `scripts/openclaw.plugin.json`
- Added a deterministic unit test:
  - `tests/secrets_cli_plugin.test.js`

## Operator Install (System-2)
This links the repo plugin path into the OpenClaw plugin loader.

```bash
openclaw plugins install -l /Users/heathyeager/clawd/scripts/openclaw_secrets_plugin.js
```

Verify:
```bash
openclaw secrets --help | head -n 80
openclaw secrets status | head -n 20
```

## Notes / Safety
- `openclaw secrets status` output is secret-safe: it prints only booleans, backend labels, provider ids, and env var *names*.
- Enablement is governed by `ENABLE_SECRETS_BRIDGE=1` (in the secrets bridge config).

## Revert
- Repo changes: `git revert <commit>`
- Operator uninstall/disable:
  - `openclaw plugins disable openclaw_secrets_plugin`
  - Remove the linked load path from `~/.openclaw/openclaw.json` if desired (keep a backup first).

