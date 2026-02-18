#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATUS_HELPER="${REPO_ROOT}/workspace/scripts/automation_status.py"

usage() {
  cat <<'EOF'
Usage: ./scripts/run_job_now.sh [briefing|hivemind_ingest]
EOF
}

resolve_job_id() {
  local job_name="$1"
  python3 - "$job_name" "$HOME/.openclaw/cron/jobs.json" <<'PY'
import json
from pathlib import Path
import sys

needle = sys.argv[1].strip().lower()
store_path = Path(sys.argv[2]).expanduser()
if not store_path.exists():
    print("")
    raise SystemExit(0)

payload = json.loads(store_path.read_text(encoding="utf-8"))
matches = []
for job in payload.get("jobs", []):
    if not isinstance(job, dict):
        continue
    name = str(job.get("name", "")).strip().lower()
    enabled = job.get("enabled", True) is not False
    if name == needle and enabled:
        matches.append(job)

if not matches:
    print("")
    raise SystemExit(0)

def order_key(job):
    created = job.get("createdAtMs")
    updated = job.get("updatedAtMs")
    return (
        int(created) if isinstance(created, (int, float)) else 0,
        int(updated) if isinstance(updated, (int, float)) else 0,
    )

matches.sort(key=order_key)
print(str(matches[0].get("id", "")))
PY
}

ensure_hivemind_job() {
  local existing
  existing="$(resolve_job_id "HiveMind Ingest")"
  if [[ -n "${existing}" ]]; then
    echo "${existing}"
    return 0
  fi

  local message
  message=$'Run HiveMind ingest pipelines:\n1. PYTHONPATH=workspace/hivemind python3 -m hivemind.ingest.memory_md\n2. PYTHONPATH=workspace/hivemind python3 -m hivemind.ingest.handoffs\n3. PYTHONPATH=workspace/hivemind python3 -m hivemind.ingest.git_commits\n4. Summarize stored/skipped/error counts.\n\nWrite a short ingest note to reports/automation/hivemind_ingest.log.'

  openclaw cron add \
    --name "HiveMind Ingest" \
    --cron "30 7 * * *" \
    --tz "Australia/Brisbane" \
    --session isolated \
    --wake now \
    --message "${message}" \
    --no-deliver >/dev/null

  existing="$(resolve_job_id "HiveMind Ingest")"
  if [[ -z "${existing}" ]]; then
    echo "Failed to create HiveMind Ingest cron job." >&2
    exit 1
  fi
  echo "${existing}"
}

ensure_briefing_job() {
  local existing
  existing="$(resolve_job_id "Daily Morning Briefing")"
  if [[ -n "${existing}" ]]; then
    echo "${existing}"
    return 0
  fi

  local system_event
  system_event=$'Daily Briefing Time\nIt is 7 AM. Generate the daily briefing for Heath with:\n1. Literature Quote (node scripts/get_daily_quote.js)\n2. Apple Reminders (remindctl today)\n3. Calendar Events (workspace/scripts/calendar.sh today)\n4. One relevant news item\n5. Agent Goal\n6. Therapeutic Technique (python3 scripts/daily_technique.py)\n7. Time Management Tip (python3 workspace/time_management/time_management.py tip)\n8. Self-Care Suggestion (python3 workspace/time_management/time_management.py self_care)'

  openclaw cron add \
    --name "Daily Morning Briefing" \
    --cron "0 7 * * *" \
    --tz "Australia/Brisbane" \
    --session main \
    --wake now \
    --system-event "${system_event}" >/dev/null

  existing="$(resolve_job_id "Daily Morning Briefing")"
  if [[ -z "${existing}" ]]; then
    echo "Failed to create Daily Morning Briefing cron job." >&2
    exit 1
  fi
  echo "${existing}"
}

ensure_heartbeat_enabled() {
  local current
  current="$(openclaw config get agents.defaults.heartbeat.every 2>/dev/null || true)"
  if [[ "${current}" == "0m" || -z "${current}" ]]; then
    openclaw config set agents.defaults.heartbeat.every 30m >/dev/null
  fi
}

target="${1:-}"
if [[ -z "${target}" ]]; then
  usage
  exit 1
fi

job_name=""
job_key=""
job_id=""

case "${target}" in
  briefing)
    job_name="Daily Morning Briefing"
    job_key="briefing"
    job_id="$(ensure_briefing_job)"
    ;;
  hivemind_ingest|hivemind)
    job_name="HiveMind Ingest"
    job_key="hivemind_ingest"
    job_id="$(ensure_hivemind_job)"
    ;;
  *)
    usage
    exit 1
    ;;
esac

if [[ -z "${job_id}" ]]; then
  echo "Unable to find cron job: ${job_name}" >&2
  exit 1
fi

artifact="reports/automation/job_status/${job_key}.json"
ensure_heartbeat_enabled

python3 "${STATUS_HELPER}" record \
  --job-id "${job_key}" \
  --job-name "${job_name}" \
  --status running \
  --artifact "${artifact}" >/dev/null || true

echo "Running cron job now: ${job_name} (${job_id})"
set +e
run_output="$(openclaw cron run "${job_id}" --timeout 600000 2>&1)"
run_rc=$?
set -e
if [[ -n "${run_output}" ]]; then
  echo "${run_output}"
fi

set +e
python3 "${STATUS_HELPER}" latest-run \
  --job-id "${job_id}" \
  --job-name "${job_name}" \
  --artifact "${artifact}"
status_rc=$?
set -e

if [[ ${run_rc} -ne 0 && ${status_rc} -eq 0 ]]; then
  status_rc=${run_rc}
fi
exit "${status_rc}"
