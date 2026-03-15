#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IDLE_THRESHOLD_SECONDS="${OPENCLAW_MARKET_SENTIMENT_IDLE_THRESHOLD_SECONDS:-900}"
CONFIG_PATH="${OPENCLAW_MARKET_SENTIMENT_CONFIG:-${ROOT_DIR}/workspace/config/market_sentiment_sources.json}"
OUTPUT_PATH="${OPENCLAW_MARKET_SENTIMENT_OUTPUT:-${ROOT_DIR}/workspace/state/external/macbook_sentiment.json}"
OLLAMA_BIN="${OPENCLAW_OLLAMA_BIN:-/opt/homebrew/bin/ollama}"
SHOULD_STOP_MODELS=0

stop_models() {
  [[ "${SHOULD_STOP_MODELS}" == "1" ]] || return 0
  [[ -x "${OLLAMA_BIN}" ]] || return 0

  /usr/bin/python3 - <<'PY' "${OLLAMA_BIN}"
import subprocess
import sys

ollama = sys.argv[1]
models = ("phi4-mini:latest", "phi3:mini")

try:
    proc = subprocess.run(
        [ollama, "ps"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
except Exception:
    raise SystemExit(0)

loaded = set()
for line in proc.stdout.splitlines()[1:]:
    line = line.strip()
    if not line:
        continue
    loaded.add(line.split()[0])

for model in models:
    if model not in loaded:
        continue
    try:
        subprocess.run(
            [ollama, "stop", model],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        pass
PY
}

idle_seconds() {
  /usr/bin/python3 - <<'PY'
import re
import subprocess

proc = subprocess.run(
    ["ioreg", "-c", "IOHIDSystem"],
    capture_output=True,
    text=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit(1)

match = re.search(r'HIDIdleTime"?\s*=\s*(\d+)', proc.stdout)
if not match:
    raise SystemExit(1)

print(int(int(match.group(1)) / 1_000_000_000))
PY
}

recommended_interval() {
  /usr/bin/python3 - <<'PY' "${CONFIG_PATH}"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print(900)
    raise SystemExit(0)
poll = payload.get("poll") if isinstance(payload.get("poll"), dict) else {}
print(int(poll.get("recommended_interval_seconds") or 900))
PY
}

artifact_recent() {
  /usr/bin/python3 - <<'PY' "${OUTPUT_PATH}" "${1}"
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
limit = int(sys.argv[2])
if not path.exists():
    raise SystemExit(1)
age = max(0.0, __import__("time").time() - path.stat().st_mtime)
raise SystemExit(0 if age < limit else 1)
PY
}

trap stop_models EXIT

if [[ "${OPENCLAW_MARKET_SENTIMENT_IDLE_OVERRIDE:-}" != "1" ]]; then
  current_idle="$(idle_seconds || echo 0)"
  if [[ "${current_idle}" -lt "${IDLE_THRESHOLD_SECONDS}" ]]; then
    echo "status=skipped reason=active_use idle_seconds=${current_idle}"
    exit 0
  fi
fi

interval_seconds="$(recommended_interval)"
if [[ "${OPENCLAW_MARKET_SENTIMENT_FORCE:-0}" != "1" ]] && artifact_recent "${interval_seconds}"; then
  echo "status=skipped reason=artifact_recent"
  exit 0
fi

export OPENCLAW_MARKET_SENTIMENT_IDLE_OVERRIDE=1
SHOULD_STOP_MODELS=1
/bin/bash "${ROOT_DIR}/workspace/scripts/run_market_sentiment_feed.sh" --config "${CONFIG_PATH}" --output "${OUTPUT_PATH}"
