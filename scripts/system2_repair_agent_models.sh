#!/bin/sh
# scripts/system2_repair_agent_models.sh
#
# System-2 audit agent repair (backup-first, POSIX sh + python3 only):
# - Validate repo-canonical agents/main/agent/models.json
# - Copy canonical models.json into runtime locations (backup-first)
# - Scrub OpenAI/Codex lanes: remove provider lanes: openai, openai-codex, openai_codex, system2-litellm
# - Scrub any model ids starting with "openai/" or "openai-codex/" anywhere in JSON (keys/values/nested lists)
# - Reset cooldown/circuit/resilience/backoff/failover/provider-state files (backup-first) to {}
# - Print summary counts only (no JSON contents, no secrets)

set -eu

ts="$(date +%Y%m%d-%H%M%S)"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

canonical_models="$repo_root/agents/main/agent/models.json"
if [ ! -f "$canonical_models" ]; then
  echo "ERROR: canonical models not found: $canonical_models" >&2
  exit 2
fi

# Validate canonical JSON shape before touching runtime.
python3 - "$canonical_models" <<'PY'
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
try:
  j = json.loads(p.read_text())
except Exception as e:
  print(f"ERROR: failed to parse canonical models json: {p}: {e}", file=sys.stderr)
  raise SystemExit(2)

if not isinstance(j, dict) or "providers" not in j or not isinstance(j["providers"], dict):
  print(f"ERROR: unexpected canonical models shape (expected top-level dict.providers): {p}", file=sys.stderr)
  raise SystemExit(2)
PY

tmp_dir="${TMPDIR:-/tmp}/openclaw-system2-repair.${ts}.$$"
mkdir -p "$tmp_dir"
state_list="$tmp_dir/state_list"
scrub_py="$tmp_dir/scrub_runtime_models.py"

cat >"$scrub_py" <<'PY'
import json, sys
from pathlib import Path

MARKERS = ("openai/", "openai-codex/")
BANNED_PROVIDER_KEYS = ("openai", "openai-codex", "openai_codex", "system2-litellm")
DROP = object()

path = Path(sys.argv[1])
j = json.loads(path.read_text())

counts = {"provider_keys_removed": 0, "items_removed": 0}

def contains_marker_str(s: str) -> bool:
  # Only treat these as model-id markers; do not match substrings in URLs like ".../openai/v1".
  return any(s.startswith(m) for m in MARKERS)

def contains_marker_any(obj) -> bool:
  if obj is None or isinstance(obj, (bool, int, float)):
    return False
  if isinstance(obj, str):
    return contains_marker_str(obj)
  if isinstance(obj, list):
    return any(contains_marker_any(x) for x in obj)
  if isinstance(obj, dict):
    for k, v in obj.items():
      if isinstance(k, str) and contains_marker_str(k):
        return True
      if contains_marker_any(v):
        return True
    return False
  return False

def scrub(obj):
  # Returns cleaned obj or DROP.
  if obj is None or isinstance(obj, (bool, int, float)):
    return obj

  if isinstance(obj, str):
    if contains_marker_str(obj):
      counts["items_removed"] += 1
      return DROP
    return obj

  if isinstance(obj, list):
    new = []
    for item in obj:
      # Delete any list element (string OR object) that contains model-id markers anywhere.
      if contains_marker_any(item):
        counts["items_removed"] += 1
        continue
      cleaned = scrub(item)
      if cleaned is DROP:
        continue
      new.append(cleaned)
    return new

  if isinstance(obj, dict):
    # If this dict has an "id" field containing markers, drop the whole object.
    mid = obj.get("id")
    if isinstance(mid, str) and contains_marker_str(mid):
      counts["items_removed"] += 1
      return DROP

    # If this dict has a providers map, drop banned provider lanes.
    prov = obj.get("providers")
    if isinstance(prov, dict):
      for k in list(prov.keys()):
        if k in BANNED_PROVIDER_KEYS:
          prov.pop(k, None)
          counts["provider_keys_removed"] += 1

    out = {}
    for k, v in obj.items():
      # Delete any dict entry whose key is a banned model-id reference.
      if isinstance(k, str) and contains_marker_str(k):
        counts["items_removed"] += 1
        continue

      # Delete any dict entry whose value is a banned model-id reference.
      if isinstance(v, str) and contains_marker_str(v):
        counts["items_removed"] += 1
        continue

      cleaned = scrub(v)
      if cleaned is DROP:
        continue
      out[k] = cleaned
    return out

  # Unknown types shouldn't exist in JSON; drop fail-closed.
  counts["items_removed"] += 1
  return DROP

cleaned = scrub(j)
if cleaned is DROP or not isinstance(cleaned, dict):
  raise SystemExit(3)

# Fail closed if any banned model-id survived in keys/values after scrub.
def assert_clean(obj):
  if obj is None or isinstance(obj, (bool, int, float)):
    return
  if isinstance(obj, str):
    if contains_marker_str(obj):
      raise SystemExit(4)
    return
  if isinstance(obj, list):
    for x in obj:
      assert_clean(x)
    return
  if isinstance(obj, dict):
    for k, v in obj.items():
      if isinstance(k, str) and contains_marker_str(k):
        raise SystemExit(4)
      assert_clean(v)
    return
  raise SystemExit(4)

assert_clean(cleaned)

path.write_text(json.dumps(cleaned, indent=2, sort_keys=True) + "\n")
print(f"{counts['provider_keys_removed']} {counts['items_removed']}")
PY

cleanup() {
  rm -rf "$tmp_dir" 2>/dev/null || true
}
trap cleanup 0 INT HUP TERM

models_backed_up=0
models_written=0
openai_codex_provider_keys_removed=0
openai_codex_model_ids_removed=0
state_files_cleared=0

for agent_dir in "$HOME/.clawdbot/agents/main/agent" "$HOME/.clawd/agents/main/agent"; do
  mkdir -p "$agent_dir"

  runtime_models="$agent_dir/models.json"
  if [ -f "$runtime_models" ]; then
    cp "$runtime_models" "${runtime_models}.bak-${ts}"
    models_backed_up=$((models_backed_up + 1))
  fi

  cp "$canonical_models" "$runtime_models"
  models_written=$((models_written + 1))

  # Scrub OpenAI/Codex *model ids* ("openai/..." and "openai-codex/...") and remove banned provider lanes.
  # Prints: "<provider_keys_removed> <items_removed>"
  scrub_counts="$(python3 "$scrub_py" "$runtime_models")"

  providers_removed="$(printf "%s" "$scrub_counts" | awk '{print $1+0}')"
  items_removed="$(printf "%s" "$scrub_counts" | awk '{print $2+0}')"
  openai_codex_provider_keys_removed=$((openai_codex_provider_keys_removed + providers_removed))
  openai_codex_model_ids_removed=$((openai_codex_model_ids_removed + items_removed))

  # Reset cooldown/circuit/resilience/backoff/failover/provider-state files (backup-first, overwrite with {}).
  : >"$state_list"
  find "$agent_dir" -maxdepth 6 -type f \( \
    -name "*cooldown*" -o \
    -name "*circuit*" -o \
    -name "*resilien*" -o \
    -name "*backoff*" -o \
    -name "*failover*" -o \
    -name "*provider*state*" \
  \) 2>/dev/null | sort >"$state_list"

  while IFS= read -r f; do
    [ -f "$f" ] || continue
    case "$f" in
      */models.json|*/auth-profiles.json) continue ;;
    esac
    cp "$f" "${f}.bak-${ts}"
    printf "%s\n" "{}" >"$f"
    state_files_cleared=$((state_files_cleared + 1))
  done <"$state_list"
done

echo "system2_repair_agent_models: ok"
echo "models_backed_up=$models_backed_up"
echo "models_written=$models_written"
echo "openai_codex_provider_keys_removed=$openai_codex_provider_keys_removed"
echo "openai_codex_model_ids_removed=$openai_codex_model_ids_removed"
echo "state_files_cleared=$state_files_cleared"
