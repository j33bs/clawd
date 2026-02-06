#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

log() {
  printf '[wire-skills] %s\n' "$*"
}

if [[ ! -f "$CONFIG_PATH" ]]; then
  log "Config file not found: $CONFIG_PATH"
  exit 1
fi

BACKUP_PATH="${CONFIG_PATH}.bak.${TIMESTAMP}"
cp "$CONFIG_PATH" "$BACKUP_PATH"
log "Backup created: $BACKUP_PATH"

python3 - "$CONFIG_PATH" "$REPO_ROOT/skills" <<'PY'
import json
import sys

config_path = sys.argv[1]
skills_dir = sys.argv[2]

with open(config_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

skills = cfg.setdefault('skills', {})
load = skills.setdefault('load', {})
extra = load.setdefault('extraDirs', [])

if skills_dir not in extra:
    extra.append(skills_dir)

load.setdefault('watch', True)
load.setdefault('watchDebounceMs', 250)

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')
PY

log "Configured skills.load.extraDirs += $REPO_ROOT/skills"
log "Restarting OpenClaw gateway to reload config"
openclaw gateway restart >/dev/null
log "Gateway restarted"
