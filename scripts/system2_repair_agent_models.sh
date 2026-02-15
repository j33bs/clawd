#!/usr/bin/env bash
set -euo pipefail

ts="$(date +%Y%m%d-%H%M%S)"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

canonical_models="$repo_root/agents/main/agent/models.json"
if [ ! -f "$canonical_models" ]; then
  echo "ERROR: canonical models not found: $canonical_models" >&2
  exit 2
fi

# Validate canonical JSON shape before touching runtime files.
python3 - "$canonical_models" <<'PY'
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
try:
  j = json.loads(p.read_text())
except Exception as e:
  print(f"ERROR: failed to parse canonical models json: {p}: {e}", file=sys.stderr)
  sys.exit(2)

if not isinstance(j, dict) or "providers" not in j or not isinstance(j["providers"], dict):
  print(f"ERROR: unexpected canonical models shape (expected top-level dict.providers): {p}", file=sys.stderr)
  sys.exit(2)
PY

runtime_agent_dirs=(
  "$HOME/.clawdbot/agents/main/agent"
  "$HOME/.clawd/agents/main/agent"
)

declare -a updated_models=()
removed_oauth_provider_keys_any=0
removed_oauth_model_ids_total=0
declare -a reset_state_files=()
pre_copy_oauth_provider_keys_found=0
pre_copy_oauth_model_ids_found=0

for agent_dir in "${runtime_agent_dirs[@]}"; do
  mkdir -p "$agent_dir"

  runtime_models="$agent_dir/models.json"
  if [ -f "$runtime_models" ]; then
    pre_summary="$(
      python3 - "$runtime_models" <<'PY' 2>/dev/null || true
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
try:
  j = json.loads(path.read_text())
except Exception:
  print("")
  raise SystemExit(0)

bad_providers = 0
prov = j.get("providers")
if isinstance(prov, dict):
  for k in ("openai", "openai-codex", "openai_codex"):
    if k in prov:
      bad_providers += 1

bad_model_ids = 0
def scan(obj):
  global bad_model_ids
  if isinstance(obj, list):
    for item in obj:
      if isinstance(item, str) and (item.startswith("openai/") or item.startswith("openai-codex/")):
        bad_model_ids += 1
      elif isinstance(item, dict):
        mid = item.get("id")
        if isinstance(mid, str) and (mid.startswith("openai/") or mid.startswith("openai-codex/")):
          bad_model_ids += 1
        scan(item)
      else:
        scan(item)
  elif isinstance(obj, dict):
    for v in obj.values():
      scan(v)

scan(j)
print(f"{bad_providers} {bad_model_ids}")
PY
    )"
    if [ -n "$pre_summary" ]; then
      set -- $pre_summary
      pre_copy_oauth_provider_keys_found=$((pre_copy_oauth_provider_keys_found + ${1:-0}))
      pre_copy_oauth_model_ids_found=$((pre_copy_oauth_model_ids_found + ${2:-0}))
    fi
    cp "$runtime_models" "$runtime_models.bak-$ts"
  fi

  cp "$canonical_models" "$runtime_models"
  updated_models+=("$runtime_models")

  # Strip OpenAI/Codex provider keys and any flat model id list entries after copy.
  # IMPORTANT: Never print secret values; only provider key names + counts.
  summary_json="$(
    python3 - "$runtime_models" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
j = json.loads(path.read_text())

removed_provider_keys = []
removed_model_ids = 0

prov = j.get("providers")
if isinstance(prov, dict):
  for k in ("openai", "openai-codex", "openai_codex"):
    if k in prov:
      prov.pop(k, None)
      removed_provider_keys.append(k)

def drop_oauth_model_ids(obj):
  global removed_model_ids
  if isinstance(obj, list):
    new = []
    for item in obj:
      if isinstance(item, str) and (item.startswith("openai/") or item.startswith("openai-codex/")):
        removed_model_ids += 1
        continue
      if isinstance(item, dict):
        mid = item.get("id")
        if isinstance(mid, str) and (mid.startswith("openai/") or mid.startswith("openai-codex/")):
          removed_model_ids += 1
          continue
      new.append(item)
    obj[:] = new
    for item in obj:
      drop_oauth_model_ids(item)
  elif isinstance(obj, dict):
    for v in obj.values():
      drop_oauth_model_ids(v)

drop_oauth_model_ids(j)

path.write_text(json.dumps(j, indent=2, sort_keys=True) + "\n")
print(json.dumps({"removed_provider_keys": removed_provider_keys, "removed_model_ids": removed_model_ids}))
PY
  )"

  removed_keys_count="$(python3 -c 'import json,sys; o=json.loads(sys.stdin.read() or "{}"); print(len(o.get("removed_provider_keys") or []))' <<<"$summary_json")"
  removed_ids_count="$(python3 -c 'import json,sys; o=json.loads(sys.stdin.read() or "{}"); print(int(o.get("removed_model_ids") or 0))' <<<"$summary_json")"

  if [ "$removed_keys_count" -gt 0 ]; then
    removed_oauth_provider_keys_any=1
  fi
  removed_oauth_model_ids_total=$((removed_oauth_model_ids_total + removed_ids_count))

  # Reset cooldown/circuit/resiliency state files under the runtime agent dir (backup-first).
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    case "$f" in
      */models.json|*/auth-profiles.json) continue ;;
    esac
    cp "$f" "$f.bak-$ts"
    printf "%s\n" "{}" > "$f"
    reset_state_files+=("$f")
  done < <(
    find "$agent_dir" -maxdepth 3 -type f \( \
      -iname "*cooldown*" -o \
      -iname "*circuit*" -o \
      -iname "*resilien*" -o \
      -iname "*backoff*" -o \
      -iname "*failover*" -o \
      -iname "*provider*state*" \
    \) 2>/dev/null | sort
  )
done

echo "system2_repair_agent_models: ok"
echo "updated_models:"
for p in "${updated_models[@]}"; do
  echo "- $p"
done
echo "pre_copy_openai_or_codex_provider_keys_found: $pre_copy_oauth_provider_keys_found"
echo "pre_copy_openai_or_codex_model_ids_found: $pre_copy_oauth_model_ids_found"
echo "openai_or_codex_provider_keys_removed: $removed_oauth_provider_keys_any"
echo "openai_or_codex_model_ids_removed_from_lists: $removed_oauth_model_ids_total"
echo "state_files_reset: ${#reset_state_files[@]}"
if [ "${#reset_state_files[@]}" -gt 0 ]; then
  for f in "${reset_state_files[@]}"; do
    echo "- $f"
  done
fi
