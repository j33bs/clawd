#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
TEMPLATE_FILE="${OPENCLAW_CRON_TEMPLATE:-$REPO_ROOT/workspace/automation/cron_jobs.json}"
ENSURE_SCRIPT="${REPO_ROOT}/workspace/scripts/ensure_cron_jobs.py"
STATUS_HELPER="${OPENCLAW_STATUS_HELPER:-$REPO_ROOT/workspace/scripts/automation_status.py}"
AUTOMATION_REPORT_DIR="${OPENCLAW_REPORT_DIR:-reports/automation}"
HEARTBEAT_SNAPSHOT_FILE="${AUTOMATION_REPORT_DIR}/heartbeat_config_snapshot.json"

usage() {
  cat <<'EOF'
Usage: ./scripts/run_job_now.sh [briefing|hivemind_ingest]
EOF
}

resolve_job_id() {
  local job_name="$1"
  python3 - "$job_name" "${OPENCLAW_BIN}" <<'PY'
import json
import subprocess
from pathlib import Path
import sys

needle = sys.argv[1].strip().lower()
openclaw_bin = sys.argv[2]

proc = subprocess.run(
    [openclaw_bin, "cron", "list", "--all", "--json"],
    capture_output=True,
    text=True,
    check=False,
)
if proc.returncode != 0:
    print("")
    raise SystemExit(0)

text = (proc.stdout or "").strip()
payload = {}
for idx, ch in enumerate(text):
    if ch in "{[":
        payload = json.loads(text[idx:])
        break
if not payload:
    print("")
    raise SystemExit(0)

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

ensure_jobs_from_template() {
  python3 "${ENSURE_SCRIPT}" \
    --template-file "${TEMPLATE_FILE}" \
    --openclaw-bin "${OPENCLAW_BIN}" >/dev/null
}

record_heartbeat_snapshot() {
  local before_value="$1"
  local after_value="$2"
  local mutated="$3"
  mkdir -p "${AUTOMATION_REPORT_DIR}"
  python3 - "$HEARTBEAT_SNAPSHOT_FILE" "$before_value" "$after_value" "$mutated" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

artifact = Path(sys.argv[1])
payload = {
    "before_value": sys.argv[2],
    "after_value": sys.argv[3],
    "mutated": sys.argv[4].lower() == "true",
    "ts": datetime.now(timezone.utc).isoformat(),
}
artifact.parent.mkdir(parents=True, exist_ok=True)
artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

ensure_heartbeat_enabled() {
  local before_value after_value mutated
  before_value="$("${OPENCLAW_BIN}" config get agents.defaults.heartbeat.every 2>/dev/null || true)"
  after_value="${before_value}"
  mutated="false"

  if [[ "${before_value}" == "0m" || -z "${before_value}" ]]; then
    "${OPENCLAW_BIN}" config set agents.defaults.heartbeat.every 30m >/dev/null
    after_value="$("${OPENCLAW_BIN}" config get agents.defaults.heartbeat.every 2>/dev/null || true)"
    mutated="true"
  fi
  record_heartbeat_snapshot "${before_value}" "${after_value}" "${mutated}"
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
    ;;
  hivemind_ingest|hivemind)
    job_name="HiveMind Ingest"
    job_key="hivemind_ingest"
    ;;
  *)
    usage
    exit 1
    ;;
esac

ensure_jobs_from_template
job_id="$(resolve_job_id "${job_name}")"
if [[ -z "${job_id}" ]]; then
  echo "Unable to find cron job: ${job_name}" >&2
  exit 1
fi

artifact="${AUTOMATION_REPORT_DIR}/job_status/${job_key}.json"
ensure_heartbeat_enabled

python3 "${STATUS_HELPER}" record \
  --job-id "${job_key}" \
  --job-name "${job_name}" \
  --status running \
  --artifact "${artifact}" >/dev/null || true

echo "Running cron job now: ${job_name} (${job_id})"
run_start_ms="$(python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
)"
set +e
run_output="$("${OPENCLAW_BIN}" cron run "${job_id}" --timeout 600000 2>&1)"
run_rc=$?
if [[ ${run_rc} -ne 0 ]] && grep -Eiq "gateway (closed|timeout)" <<<"${run_output}"; then
  "${OPENCLAW_BIN}" gateway restart >/dev/null 2>&1 || true
  run_output="$("${OPENCLAW_BIN}" cron run "${job_id}" --timeout 600000 2>&1)"
  run_rc=$?
fi
set -e
if [[ -n "${run_output}" ]]; then
  echo "${run_output}"
fi

status_rc=1
for _attempt in {1..30}; do
  set +e
  python3 "${STATUS_HELPER}" latest-run \
    --job-id "${job_id}" \
    --job-name "${job_name}" \
    --min-run-at-ms "${run_start_ms}" \
    --artifact "${artifact}" >/dev/null
  status_rc=$?
  set -e
  if [[ ${status_rc} -eq 0 ]]; then
    break
  fi
  sleep 2
done

if [[ ${status_rc} -ne 0 ]]; then
  python3 "${STATUS_HELPER}" latest-run \
    --job-id "${job_id}" \
    --job-name "${job_name}" \
    --min-run-at-ms "${run_start_ms}" \
    --artifact "${artifact}" || true
  if [[ ${run_rc} -ne 0 ]]; then
    echo "Cron run command failed for ${job_name}" >&2
  fi
fi
exit "${status_rc}"
