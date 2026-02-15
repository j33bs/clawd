#!/bin/sh
# scripts/system2_repair_agent_auth_profiles.sh
#
# Backup-first auth profile scaffolding for System-2 agents.
# - Writes no secrets (no key material, no tokens).
# - Creates/updates runtime auth-profiles.json in:
#   - ~/.clawdbot/agents/main/agent/auth-profiles.json
#   - ~/.clawd/agents/main/agent/auth-profiles.json
# - Ensures profile stubs exist (env references only where applicable):
#   - google-gemini-cli:default -> type=api_key, apiKeyEnv=GEMINI_API_KEY
#   - groq:default            -> type=api_key, apiKeyEnv=GROQ_API_KEY
#   - qwen-portal:default     -> type=oauth (empty fields; operator must populate via openclaw auth tooling)
#   - ollama:default          -> type=none (local, no auth required)
#
# Prints only profile ids added/ensured (never prints secret values).

set -eu

ts="$(date +%Y%m%d-%H%M%S)"

runtime_agent_dirs="$HOME/.clawdbot/agents/main/agent $HOME/.clawd/agents/main/agent"

for agent_dir in $runtime_agent_dirs; do
  mkdir -p "$agent_dir"
  auth_file="$agent_dir/auth-profiles.json"

  if [ -f "$auth_file" ]; then
    cp "$auth_file" "$auth_file.bak-$ts"
  fi

  added="$(
    python3 - "$auth_file" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])

def load_or_init():
  if path.exists():
    try:
      return json.loads(path.read_text())
    except Exception:
      pass
  return {
    "version": 1,
    "profiles": {},
    "order": {},
    "lastGood": {},
    "usageStats": {},
  }

j = load_or_init()
if not isinstance(j, dict):
  j = {
    "version": 1,
    "profiles": {},
    "order": {},
    "lastGood": {},
    "usageStats": {},
  }

profiles = j.get("profiles")
if not isinstance(profiles, dict):
  profiles = {}
  j["profiles"] = profiles

added = []

def ensure(pid, val):
  if pid not in profiles:
    profiles[pid] = val
    added.append(pid)

# Env-referenced API key profiles (no secret values stored).
ensure("google-gemini-cli:default", {"provider": "google-gemini-cli", "type": "api_key", "apiKeyEnv": "GEMINI_API_KEY"})
ensure("groq:default", {"provider": "groq", "type": "api_key", "apiKeyEnv": "GROQ_API_KEY"})

# OAuth stub (empty values). Operator must populate via OpenClaw auth tooling (e.g., openclaw agents add).
ensure("qwen-portal:default", {"provider": "qwen-portal", "type": "oauth", "access": "", "refresh": "", "expires": 0})

# Local/no-auth stub. This prevents "missing api key" failures for local providers.
ensure("ollama:default", {"provider": "ollama", "type": "none"})

order = j.get("order")
if not isinstance(order, dict):
  order = {}
  j["order"] = order

def ensure_order(provider, pid):
  cur = order.get(provider)
  if not isinstance(cur, list):
    cur = []
  if pid not in cur:
    cur.insert(0, pid)
  order[provider] = cur

ensure_order("google-gemini-cli", "google-gemini-cli:default")
ensure_order("groq", "groq:default")
ensure_order("qwen-portal", "qwen-portal:default")
ensure_order("ollama", "ollama:default")

path.write_text(json.dumps(j, indent=2, sort_keys=True) + "\n")
print("\n".join(added))
PY
  )"

  echo "system2_repair_agent_auth_profiles: ok path=$auth_file"
  if [ -n "$added" ]; then
    echo "added_profile_ids:"
    # shellcheck disable=SC2086
    printf "%s\n" "$added" | sed 's/^/- /'
  else
    echo "added_profile_ids: none"
  fi
done
