#!/usr/bin/env bash
set -euo pipefail

SOURCE_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "${SOURCE_PATH}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

RUNTIME_DIR="$REPO_ROOT/workspace/runtime"
PREPARED_PATH="$RUNTIME_DIR/codex_prepared_prompt.json"
mkdir -p "$RUNTIME_DIR"

PROMPT_FILE="$(mktemp "$RUNTIME_DIR/cel_smoke_prompt.XXXXXX.md")"
trap 'rm -f "$PROMPT_FILE"' EXIT

cat > "$PROMPT_FILE" <<'MD'
GOAL
Return exactly CEL_SMOKE_OK.

INPUTS
- none

OUTPUTS
- CEL_SMOKE_OK

CONSTRAINTS
- Output exactly CEL_SMOKE_OK and nothing else.

SUCCESS_CRITERIA
- Response is exactly CEL_SMOKE_OK.
MD

python3 tools/codex_prepare_prompt.py "$PROMPT_FILE" --output "$PREPARED_PATH" >/dev/null

set +e
SPAWN_OUTPUT="$(python3 tools/codex_spawn_session.py --prepared "$PREPARED_PATH" 2>&1)"
SPAWN_RC=$?
set -e

if [[ $SPAWN_RC -ne 0 ]]; then
  SKIP_REASON="$(SPAWN_TEXT="$SPAWN_OUTPUT" python3 - <<'PY'
import json
import os
import re
import sys

text = os.environ.get("SPAWN_TEXT", "")

candidates = [text]
for line in text.splitlines():
    stripped = line.strip()
    if not stripped:
        continue
    try:
        obj = json.loads(stripped)
    except Exception:
        continue
    stack = [obj]
    seen = set()
    while stack:
        node = stack.pop()
        marker = id(node)
        if marker in seen:
            continue
        seen.add(marker)
        if isinstance(node, dict):
            for value in node.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                elif isinstance(value, (str, int, float, bool)):
                    candidates.append(str(value))
        elif isinstance(node, list):
            for item in node:
                stack.append(item)

patterns = [
    r"no provider available",
    r"provider unavailable",
    r"provider_not_available",
    r"model unavailable",
    r"no models? available",
    r"no enabled providers?",
]
for value in candidates:
    lowered = value.lower()
    for pattern in patterns:
        if re.search(pattern, lowered):
            print("no_provider_available")
            sys.exit(0)

print("")
PY
)"
  if [[ -n "$SKIP_REASON" ]]; then
    echo "CEL_SMOKE_TEST: SKIP (reason=$SKIP_REASON)"
    exit 0
  fi
  printf '%s\n' "$SPAWN_OUTPUT" >&2
  exit "$SPAWN_RC"
fi

SESSION_ID="$(SPAWN_TEXT="$SPAWN_OUTPUT" python3 - <<'PY'
import json
import os
import re
import sys

text = os.environ.get("SPAWN_TEXT", "").strip()

obj = None
try:
    obj = json.loads(text)
except Exception:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            break
        except Exception:
            continue

def pick_id(mapping):
    if not isinstance(mapping, dict):
        return ""
    for key in ("session_id", "sessionId", "id", "key"):
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""

session_id = ""
if isinstance(obj, dict):
    session_id = pick_id(obj)
    if not session_id and isinstance(obj.get("response"), dict):
        session_id = pick_id(obj["response"])
    if not session_id and isinstance(obj.get("log"), dict):
        value = obj["log"].get("session_id")
        if isinstance(value, str) and value.strip():
            session_id = value.strip()

if not session_id:
    m = re.search(r"session[_-]?id\s*[:=]\s*([A-Za-z0-9._:-]+)", text, flags=re.I)
    if m:
        session_id = m.group(1)

print(session_id)
PY
)"

if [[ -z "$SESSION_ID" ]]; then
  printf '%s\n' "$SPAWN_OUTPUT" >&2
  echo "cel_smoke_test: unable to extract session id" >&2
  exit 1
fi

python3 tools/codex_finalize_session.py --session-id "$SESSION_ID" >/dev/null

ARTIFACT_DIR="$RUNTIME_DIR/codex_outputs/$SESSION_ID"
if [[ ! -d "$ARTIFACT_DIR" ]]; then
  echo "cel_smoke_test: missing artifact dir $ARTIFACT_DIR" >&2
  exit 1
fi

echo "CEL_SMOKE_TEST: PASS"
