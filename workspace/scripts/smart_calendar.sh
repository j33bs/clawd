#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PREFS_FILE="${REPO_ROOT}/workspace/time_management/data/preferences.json"
CALENDAR_SCRIPT="${REPO_ROOT}/workspace/scripts/calendar.sh"

if ! calendar_out="$(bash "${CALENDAR_SCRIPT}" today 2>&1)"; then
  echo "smart_calendar: calendar.sh failed" >&2
  echo "${calendar_out}" >&2
  exit 1
fi

python3 - "$PREFS_FILE" <<'PY' <<<"${calendar_out}"
import json, re, sys
prefs_file = sys.argv[1]
lines = sys.stdin.read().splitlines()
low = "afternoon"
try:
    prefs = json.loads(open(prefs_file, "r", encoding="utf-8").read())
    categories = prefs.get("categories", {}) if isinstance(prefs, dict) else {}
    scored = []
    for k, v in categories.items():
        t = int(v.get("total", 0)) if isinstance(v, dict) else 0
        d = int(v.get("done", 0)) if isinstance(v, dict) else 0
        if t > 0:
            scored.append((d / t, str(k)))
    if scored:
        scored.sort(key=lambda x: (x[0], x[1]))
        low = scored[0][1]
except Exception:
    pass

def win(h):
    if 5 <= h < 10: return "morning"
    if 10 <= h < 14: return "midday"
    if 14 <= h < 18: return "afternoon"
    if 18 <= h < 22: return "evening"
    return "night"

print(f"# Smart Calendar (low-energy window: {low})")
for line in lines:
    m = re.search(r"(\d{1,2}):(\d{2})\s*([ap]m)?", line, flags=re.I)
    if m:
        hour = int(m.group(1))
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour != 12: hour += 12
        if ampm == "am" and hour == 12: hour = 0
        if win(hour) == low:
            line = f"{line} ⚠️ [low-energy window]"
    print(line)
PY
