#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

AUDIT_FILE="${LOCAL_EXEC_ACTIVATION_AUDIT:-$(ls -1t workspace/audit/dali_local_exec_plane_activation_20260222T*.md 2>/dev/null | head -n1)}"
if [[ -z "${AUDIT_FILE:-}" ]]; then
  AUDIT_FILE="workspace/audit/dali_local_exec_plane_activation_20260222T$(date -u +%Y%m%dT%H%M%SZ).md"
  mkdir -p "$(dirname "$AUDIT_FILE")"
  printf '# Dali Local Exec Plane Activation Audit\n\n' > "$AUDIT_FILE"
fi

RUN_SECONDS="${LOCAL_EXEC_SLEEP_RUN_SECONDS:-10800}"
INTERVAL_SECONDS="${LOCAL_EXEC_SLEEP_RUN_INTERVAL:-600}"
LEAVE_RUNNING="${LOCAL_EXEC_SLEEP_RUN_LEAVE_RUNNING:-0}"

log_audit() {
  printf '%s\n' "$1" >> "$AUDIT_FILE"
}

log_audit ""
log_audit "## Phase 5 — local_exec_sleep_run"
log_audit '```text'
log_audit "UTC start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log_audit "run_seconds=$RUN_SECONDS interval_seconds=$INTERVAL_SECONDS"

log_audit "$ python3 -m unittest tests_unittest.test_local_exec_plane_offline -v"
if ! python3 -m unittest tests_unittest.test_local_exec_plane_offline -v >> "$AUDIT_FILE" 2>&1; then
  log_audit "result=failure reason=offline_tests_failed"
  log_audit '```'
  exit 1
fi

mkdir -p workspace/local_exec/state workspace/local_exec/evidence

if [[ "${LOCAL_EXEC_ENABLE_VLLM:-0}" == "1" ]]; then
  if [[ ! -f "$HOME/.config/openclaw/local_exec.env" ]]; then
    log_audit "blocked-by: missing_env_file path=$HOME/.config/openclaw/local_exec.env"
    export OPENCLAW_LOCAL_EXEC_MODEL_STUB=1
  fi
fi

log_audit "$ bash scripts/local_exec_plane.sh start"
bash scripts/local_exec_plane.sh start >> "$AUDIT_FILE" 2>&1 || true

start_ts="$(date +%s)"
end_ts="$((start_ts + RUN_SECONDS))"
iter=0
enqueued=0
errors=0

while [[ "$(date +%s)" -lt "$end_ts" ]]; do
  iter="$((iter + 1))"

  if [[ -f workspace/local_exec/state/KILL_SWITCH ]]; then
    log_audit "kill_switch_detected=1 action=stop_enqueue_loop iter=$iter"
    break
  fi

  job_selector="$((iter % 3))"
  if [[ "$job_selector" -eq 1 ]]; then
    job_type="repo_index_task"
  elif [[ "$job_selector" -eq 2 ]]; then
    job_type="doc_compactor_task"
  else
    job_type="test_runner_task"
  fi

  job_id="job-sleeprun$(date -u +%H%M%S)$(printf '%02d' "$iter")"
  log_audit "enqueue_iter=$iter job_type=$job_type job_id=$job_id"

  if ! JOB_TYPE="$job_type" JOB_ID="$job_id" AUDIT_FILE="$AUDIT_FILE" python3 - <<'PY' >> "$AUDIT_FILE" 2>&1
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from workspace.local_exec.queue import enqueue_job

repo = Path('.').resolve()
job_type = os.environ['JOB_TYPE']
job_id = os.environ['JOB_ID']
audit_rel = os.path.relpath(os.environ['AUDIT_FILE'], str(repo))

base = {
    "job_id": job_id,
    "job_type": job_type,
    "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "budgets": {
        "max_wall_time_sec": 180,
        "max_tool_calls": 8,
        "max_output_bytes": 131072,
        "max_concurrency_slots": 1,
    },
    "tool_policy": {
        "allow_network": False,
        "allow_subprocess": job_type == "test_runner_task",
        "allowed_tools": [],
    },
    "meta": {"source": "sleep_run"},
}
if job_type == "repo_index_task":
    base["payload"] = {
        "include_globs": ["workspace/local_exec/*.py", "workspace/docs/ops/*.md", "scripts/*.sh"],
        "exclude_globs": ["**/*.bak.*"],
        "max_files": 60,
        "max_file_bytes": 16384,
        "keywords": ["kill_switch", "evidence", "worker"],
    }
elif job_type == "doc_compactor_task":
    base["payload"] = {
        "inputs": [audit_rel],
        "max_input_bytes": 32768,
        "max_output_bytes": 8192,
        "title": "Sleep-run evidence compaction",
    }
else:
    base["payload"] = {
        "commands": [["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"]],
        "timeout_sec": 90,
        "cwd": ".",
        "env_allow": [],
    }

event = enqueue_job(repo, base)
print(json.dumps({"enqueued": job_id, "event": event.get("event")}, ensure_ascii=False))
PY
  then
    errors="$((errors + 1))"
    log_audit "enqueue_result=error iter=$iter"
  else
    enqueued="$((enqueued + 1))"
    log_audit "enqueue_result=ok iter=$iter"
  fi

  sleep "$INTERVAL_SECONDS"
done

if [[ "$LEAVE_RUNNING" != "1" ]]; then
  log_audit "$ bash scripts/local_exec_plane.sh stop"
  bash scripts/local_exec_plane.sh stop >> "$AUDIT_FILE" 2>&1 || true
fi

summary_json="$(python3 - <<'PY'
import json
from pathlib import Path

root = Path('.').resolve()
ledger = root / 'workspace' / 'local_exec' / 'state' / 'jobs.jsonl'
rows = []
if ledger.exists():
    for line in ledger.read_text(encoding='utf-8').splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
print(json.dumps({
    "ledger_events": len(rows),
    "last_event": rows[-1] if rows else None,
}, ensure_ascii=False))
PY
)"

log_audit "summary_enqueued=$enqueued summary_errors=$errors"
log_audit "ledger_summary=$summary_json"
log_audit "UTC end: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log_audit '```'

echo "sleep_run_complete enqueued=$enqueued errors=$errors audit=$AUDIT_FILE"
