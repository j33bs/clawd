# Dali vLLM Singleton Invariant Audit

- Audit file: workspace/audit/dali_vllm_singleton_invariant_20260221T210635Z.md
- Start (UTC): 2026-02-21T21:06:35Z

## Problem Statement
Implement a machine-checkable invariant for vLLM singleton ownership: system  is the sole launcher and user  remains disabled/inactive, with safe read-only checks and graceful degradation when user systemd is unavailable.

## Acceptance Criteria
- Verifier exits 0 when invariant holds and 1 on clear violations.
- Verifier checks system service state, user service state (when available), and :8001 listener cardinality.
- Nightly health flow calls verifier in health mode and fails gate on violation.
- All evidence captured as command/output blocks.

```bash
date -u
```

```text
Sat Feb 21 21:06:35 UTC 2026
```

```bash
uname -a
```

```text
Linux jeebs-Z490-AORUS-MASTER 6.17.0-14-generic #14~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Thu Jan 15 15:52:10 UTC 2 x86_64 x86_64 x86_64 GNU/Linux
```

```bash
git rev-parse HEAD
```

```text
a42ed141b6669aef58ee65ddf4866e0892c1a06d
```

## Audit Note
Shell backtick expansion produced harmless stderr during initial header write. This note supersedes the affected line while preserving append-only behavior.

## Corrected Problem Statement
Implement a machine-checkable invariant for vLLM singleton ownership: system `vllm-assistant.service` is the sole launcher and user `openclaw-vllm.service` remains disabled/inactive, with safe read-only checks and graceful degradation when user systemd is unavailable.

## Phase 1 Add Verifier Script

```bash
ls -la workspace/scripts/verify_vllm_singleton.sh
```

```text
-rwxrwxr-x 1 jeebs jeebs 2627 Feb 22 07:07 workspace/scripts/verify_vllm_singleton.sh
```

```bash
sed -n "1,240p" workspace/scripts/verify_vllm_singleton.sh
```

```text
#!/usr/bin/env bash
set -euo pipefail

PORT="${VLLM_PORT:-8001}"
SYS_UNIT="${VLLM_SYSTEM_UNIT:-vllm-assistant.service}"
USER_UNIT="${VLLM_USER_UNIT:-openclaw-vllm.service}"

fail=0

say() { printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
bad() { printf 'FAIL: %s\n' "$*" >&2; fail=1; }

have() { command -v "$1" >/dev/null 2>&1; }

say "vLLM singleton invariant check"
say "  system unit: $SYS_UNIT"
say "  user unit:   $USER_UNIT"
say "  port:        $PORT"
say

if have systemctl; then
  sys_enabled="$(systemctl is-enabled "$SYS_UNIT" 2>/dev/null || true)"
  sys_active="$(systemctl is-active  "$SYS_UNIT" 2>/dev/null || true)"
  say "systemctl: $SYS_UNIT enabled=$sys_enabled active=$sys_active"
  [[ "$sys_enabled" == "enabled" ]] || bad "$SYS_UNIT is not enabled (got: $sys_enabled)"
  [[ "$sys_active"  == "active"  ]] || bad "$SYS_UNIT is not active (got: $sys_active)"
else
  warn "systemctl not found; cannot verify $SYS_UNIT"
fi

if have systemctl; then
  # User systemd may not be available depending on environment.
  if systemctl --user show-environment >/dev/null 2>&1; then
    user_enabled="$(systemctl --user is-enabled "$USER_UNIT" 2>/dev/null || true)"
    user_active="$(systemctl --user is-active  "$USER_UNIT" 2>/dev/null || true)"
    say "systemctl --user: $USER_UNIT enabled=$user_enabled active=$user_active"
    [[ "$user_enabled" != "enabled" ]] || bad "$USER_UNIT is enabled (must be disabled)"
    [[ "$user_active"  != "active"  ]] || bad "$USER_UNIT is active (must be inactive)"
  else
    warn "systemctl --user not available; cannot verify $USER_UNIT state"
  fi
else
  warn "systemctl not found; cannot verify $USER_UNIT state"
fi

say
if have ss; then
  listeners="$(ss -ltnp 2>/dev/null | grep -E "(:$PORT)\\b" || true)"
  count="$(printf '%s\n' "$listeners" | sed '/^\s*$/d' | wc -l | tr -d ' ')"
  say "listeners on :$PORT = $count"
  if [[ "$count" -eq 0 ]]; then
    bad "no listener detected on :$PORT"
  elif [[ "$count" -gt 1 ]]; then
    bad "multiple listeners detected on :$PORT"
    say "$listeners"
  else
    say "$listeners"
  fi
else
  warn "ss not found; cannot verify port binding"
fi

say
if have pgrep; then
  procs="$(pgrep -af 'vllm|openai\.api_server|api_server' || true)"
  if [[ -n "$procs" ]]; then
    say "vLLM-related processes:"
    printf '%s\n' "$procs"
  else
    warn "no vLLM-related processes found via pgrep (may be false negative)"
  fi
else
  warn "pgrep not found; cannot list processes"
fi

say
if [[ "$fail" -eq 0 ]]; then
  say "PASS: vLLM singleton invariant holds"
else
  bad "vLLM singleton invariant violated"
fi

exit "$fail"
```

## Phase 2 Health Wiring Recon

```bash
grep -RIn --color=never -E 'nightly_build\.sh|health|verify_.*health|governance:heartbeat' workspace/scripts 2>/dev/null || true
```

```text
workspace/scripts/nightly_build.sh:3:# Usage: ./nightly_build.sh [research|health|memory|all]
workspace/scripts/nightly_build.sh:103:run_health() {
workspace/scripts/nightly_build.sh:255:    health)
workspace/scripts/nightly_build.sh:256:        run_health
workspace/scripts/nightly_build.sh:264:        run_health
workspace/scripts/nightly_build.sh:271:        echo "Usage: $0 [research|health|memory|all]"
workspace/scripts/vllm_metrics_sink.py:3:Polls the vLLM /metrics endpoint, extracts GPU-side inference health signals,
workspace/scripts/report_token_burn.py:353:            "- `Missing Usage` should remain zero for unified accounting health.",
workspace/scripts/verify_nightly_health_config.sh:5:SCRIPT="$ROOT_DIR/workspace/scripts/nightly_build.sh"
workspace/scripts/verify_nightly_health_config.sh:14:if ! CLAWD_DIR="$ROOT_DIR" bash "$SCRIPT" health >"$VALID_OUT" 2>&1; then
workspace/scripts/verify_nightly_health_config.sh:15:    echo "FAIL: expected health to succeed with valid config"
workspace/scripts/verify_nightly_health_config.sh:46:bash "$SCRIPT" health >"$INVALID_OUT" 2>&1
workspace/scripts/verify_nightly_health_config.sh:51:    echo "FAIL: expected health to fail with invalid config"
workspace/scripts/verify_nightly_health_config.sh:61:echo "PASS: nightly health config preflight behaves as expected"
workspace/scripts/automation_status.py:223:def cmd_cron_health(args: argparse.Namespace) -> int:
workspace/scripts/automation_status.py:416:    health = sub.add_parser("cron-health", help="Verify a cron job has fired recently and succeeded")
workspace/scripts/automation_status.py:417:    health.add_argument("--job-id")
workspace/scripts/automation_status.py:418:    health.add_argument("--job-name")
workspace/scripts/automation_status.py:419:    health.add_argument("--max-age-hours", type=float, default=26.0)
workspace/scripts/automation_status.py:420:    health.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
workspace/scripts/automation_status.py:421:    health.add_argument("--jobs-file", default=str(DEFAULT_JOBS_FILE))
workspace/scripts/automation_status.py:422:    health.add_argument("--artifact", required=True)
workspace/scripts/automation_status.py:423:    health.set_defaults(func=cmd_cron_health)
workspace/scripts/external_memory_demo.py:15:from tacti_cr.external_memory import append_event, healthcheck  # noqa: E402
workspace/scripts/external_memory_demo.py:50:    status = healthcheck()
```

```bash
rg -n --hidden -S 'nightly_build|health' workspace/scripts | sed -n '1,220p'
```

```text
workspace/scripts/nightly_build.sh:3:# Usage: ./nightly_build.sh [research|health|memory|all]
workspace/scripts/nightly_build.sh:82:    if [ "${NIGHTLY_BUILD_DRY_RUN:-0}" = "1" ]; then
workspace/scripts/nightly_build.sh:103:run_health() {
workspace/scripts/nightly_build.sh:104:    log "=== System Health ==="
workspace/scripts/nightly_build.sh:138:    log "Health check complete"
workspace/scripts/nightly_build.sh:255:    health)
workspace/scripts/nightly_build.sh:256:        run_health
workspace/scripts/nightly_build.sh:264:        run_health
workspace/scripts/nightly_build.sh:271:        echo "Usage: $0 [research|health|memory|all]"
workspace/scripts/verify_nightly_health_config.sh:5:SCRIPT="$ROOT_DIR/workspace/scripts/nightly_build.sh"
workspace/scripts/verify_nightly_health_config.sh:14:if ! CLAWD_DIR="$ROOT_DIR" bash "$SCRIPT" health >"$VALID_OUT" 2>&1; then
workspace/scripts/verify_nightly_health_config.sh:15:    echo "FAIL: expected health to succeed with valid config"
workspace/scripts/verify_nightly_health_config.sh:46:bash "$SCRIPT" health >"$INVALID_OUT" 2>&1
workspace/scripts/verify_nightly_health_config.sh:51:    echo "FAIL: expected health to fail with invalid config"
workspace/scripts/verify_nightly_health_config.sh:61:echo "PASS: nightly health config preflight behaves as expected"
workspace/scripts/external_memory_demo.py:15:from tacti_cr.external_memory import append_event, healthcheck  # noqa: E402
workspace/scripts/external_memory_demo.py:50:    status = healthcheck()
workspace/scripts/report_token_burn.py:353:            "- `Missing Usage` should remain zero for unified accounting health.",
workspace/scripts/automation_status.py:223:def cmd_cron_health(args: argparse.Namespace) -> int:
workspace/scripts/automation_status.py:416:    health = sub.add_parser("cron-health", help="Verify a cron job has fired recently and succeeded")
workspace/scripts/automation_status.py:417:    health.add_argument("--job-id")
workspace/scripts/automation_status.py:418:    health.add_argument("--job-name")
workspace/scripts/automation_status.py:419:    health.add_argument("--max-age-hours", type=float, default=26.0)
workspace/scripts/automation_status.py:420:    health.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
workspace/scripts/automation_status.py:421:    health.add_argument("--jobs-file", default=str(DEFAULT_JOBS_FILE))
workspace/scripts/automation_status.py:422:    health.add_argument("--artifact", required=True)
workspace/scripts/automation_status.py:423:    health.set_defaults(func=cmd_cron_health)
workspace/scripts/vllm_metrics_sink.py:3:Polls the vLLM /metrics endpoint, extracts GPU-side inference health signals,
```

```bash
sed -n '1,260p' workspace/scripts/nightly_build.sh
```

```text
#!/bin/bash
# Nightly Build - Autonomous work while you sleep
# Usage: ./nightly_build.sh [research|health|memory|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWD_DIR="${CLAWD_DIR:-$HOME/clawd}"
RESEARCH_TOPICS_FILE="$CLAWD_DIR/workspace/research/TOPICS.md"
RESEARCH_OUT_DIR="$CLAWD_DIR/reports/research"
OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw 2>/dev/null || echo "$HOME/.npm-global/bin/openclaw")}"

# Activate virtual environment if it exists
if [ -f "$CLAWD_DIR/.venv/bin/activate" ]; then
    source "$CLAWD_DIR/.venv/bin/activate"
fi

# Log file
LOG_DIR="$CLAWD_DIR/reports/nightly"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

sanitize_doctor_output() {
    sed -E 's/(([A-Za-z0-9_.-]*((KEY|TOKEN|SECRET|PASS|PASSWORD))[A-Za-z0-9_.-]*)[[:space:]]*[:=][[:space:]]*)[^[:space:]]+/\1[REDACTED]/Ig'
}

run_openclaw_config_preflight() {
    local config_source doctor_output doctor_sanitized
    local doctor_status=0
    local invalid_config=0

    if [ -n "${OPENCLAW_CONFIG_PATH:-}" ]; then
        config_source="$OPENCLAW_CONFIG_PATH"
        log "OpenClaw config source: $config_source (OPENCLAW_CONFIG_PATH override)"
    else
        config_source="$HOME/.openclaw/openclaw.json"
        log "OpenClaw config source: $config_source (default)"
    fi

    doctor_output="$("$OPENCLAW_BIN" doctor --non-interactive --no-workspace-suggestions 2>&1)" || doctor_status=$?
    doctor_sanitized="$(printf '%s\n' "$doctor_output" | sanitize_doctor_output)"
    printf '%s\n' "$doctor_sanitized" >>"$LOG_FILE"

    if printf '%s\n' "$doctor_output" | grep -Eiq 'Invalid config at .*openclaw\.json|plugin path not found|plugin not found'; then
        invalid_config=1
    fi

    if [ "$invalid_config" -eq 1 ]; then
        log "OpenClaw config invalid (likely ~/.openclaw/openclaw.json). Run: openclaw doctor --fix"
        log "OpenClaw doctor diagnostics (last 20 lines):"
        while IFS= read -r line; do
            [ -n "$line" ] && log "  $line"
        done < <(printf '%s\n' "$doctor_sanitized" | tail -n 20)
        return 1
    fi

    if [ "$doctor_status" -ne 0 ]; then
        log "⚠️ OpenClaw doctor returned non-zero during preflight (continuing; no config-invalid signature detected)"
        while IFS= read -r line; do
            [ -n "$line" ] && log "  $line"
        done < <(printf '%s\n' "$doctor_sanitized" | tail -n 20)
    else
        log "✅ OpenClaw config preflight: OK"
    fi
}

run_research() {
    log "=== Research Ingest ==="

    local ingest_cmd=(
        python3
        "$CLAWD_DIR/workspace/research/research_ingest.py"
        --topics-file
        "$RESEARCH_TOPICS_FILE"
        --out-dir
        "$RESEARCH_OUT_DIR"
    )
    if [ "${NIGHTLY_BUILD_DRY_RUN:-0}" = "1" ]; then
        ingest_cmd+=(--dry-run)
    fi

    mkdir -p "$RESEARCH_OUT_DIR"

    if "${ingest_cmd[@]}" >>"$LOG_FILE" 2>&1; then
        log "Research ingest complete"
    else
        log "⚠️ Research ingest failed"
        return 1
    fi

    if [ -f "$RESEARCH_OUT_DIR/ingest_status.json" ]; then
        log "Ingest status artifact: $RESEARCH_OUT_DIR/ingest_status.json"
    else
        log "⚠️ Missing ingest status artifact"
        return 1
    fi
}

run_health() {
    log "=== System Health ==="

    run_openclaw_config_preflight
    
    # Check Gateway
    if "$OPENCLAW_BIN" status 2>&1 | grep -q "running"; then
        log "✅ Gateway: OK"
    else
        log "⚠️ Gateway: Issues detected"
    fi
    
    # Check Ollama
    if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        log "✅ Ollama: OK"
    else
        log "⚠️ Ollama: Not responding"
    fi
    
    # Check Cron jobs
    cron_status=$("$OPENCLAW_BIN" cron status 2>&1)
    if echo "$cron_status" | grep -q "running"; then
        log "✅ Cron: OK"
    else
        log "⚠️ Cron: Issues"
    fi
    
    # Check disk space
    disk_free=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_free" -lt 80 ]; then
        log "✅ Disk: ${disk_free}% used"
    else
        log "⚠️ Disk: ${disk_free}% used"
    fi
    
    log "Health check complete"
}

run_memory() {
    log "=== Memory Prune ==="
    
    memory_dir="$CLAWD_DIR/memory"
    
    # Count files
    total_files=$(find "$memory_dir" -name "*.md" | wc -l)
    log "Found $total_files memory files"
    
    # Archive files older than 30 days
    archived=$(find "$memory_dir" -name "2*.md" -mtime +30 ! -name "*-archive-*" | wc -l | tr -d ' ')
    if [ "$archived" -gt 0 ]; then
        while IFS= read -r -d '' file; do
            archive_dir="$memory_dir/archive/$(date +%Y)"
            mkdir -p "$archive_dir"
            mv "$file" "$archive_dir/"
        done < <(find "$memory_dir" -name "2*.md" -mtime +30 ! -name "*-archive-*" -print0)
    fi
    
    if [ $archived -gt 0 ]; then
        log "Archived $archived old memory files"
    else
        log "No files to archive"
    fi
    
    # Count lines in MEMORY.md
    if [ -f "$CLAWD_DIR/MEMORY.md" ]; then
        memory_warn_lines="${NIGHTLY_MEMORY_WARN_LINES:-180}"
        lines=$(wc -l < "$CLAWD_DIR/MEMORY.md")
        log "MEMORY.md: $lines lines"
        if [ "$lines" -gt "$memory_warn_lines" ]; then
            log "⚠️ MEMORY.md exceeds 180 lines — prune recommended (oldest entries first)"
        fi
    fi

    if [ "${OPENCLAW_NARRATIVE_DISTILL:-0}" = "1" ]; then
        log "Running narrative distillation (OPENCLAW_NARRATIVE_DISTILL=1)"
        if python3 "$CLAWD_DIR/workspace/scripts/run_narrative_distill.py" >>"$LOG_FILE" 2>&1; then
            log "Narrative distillation complete"
        else
            log "⚠️ Narrative distillation failed"
        fi
    fi

    inefficiency_log="$CLAWD_DIR/workspace/governance/inefficiency_log.md"
    if [ -f "$inefficiency_log" ]; then
        stale_open="$(python3 - "$inefficiency_log" <<'PY'
import datetime
import sys
from pathlib import Path

path = Path(sys.argv[1])
now = datetime.date.today()
stale = []
for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
    line = raw.strip()
    if not line.startswith("|"):
        continue
    if "Date" in line and "Status" in line:
        continue
    if line.startswith("|---"):
        continue
    parts = [p.strip() for p in line.strip("|").split("|")]
    if len(parts) < 5:
        continue
    date_text, pattern, _, _, status = parts[:5]
    if "open" not in status.lower():
        continue
    try:
        d = datetime.date.fromisoformat(date_text)
    except Exception:
        continue
    if (now - d).days > 7:
        stale.append(f"{date_text}: {pattern}")
if stale:
    print("\n".join(stale))
PY
)"
        if [ -n "$stale_open" ]; then
            log "⚠️ Inefficiency log has stale open entries (>7 days):"
            while IFS= read -r line; do
                [ -n "$line" ] && log "  - $line"
            done <<< "$stale_open"
        else
            log "No stale open inefficiency entries"
        fi
    fi

    log "Memory prune complete"
}

run_kb_sync() {
    log "=== Knowledge Base Sync ==="
    if python3 "$CLAWD_DIR/workspace/knowledge_base/kb.py" sync >>"$LOG_FILE" 2>&1; then
        log "KB sync complete"
    else
        log "⚠️ KB sync failed"
    fi
}

run_kb_decisions() {
    log "=== Knowledge Base Decision Index ==="
    if python3 "$CLAWD_DIR/workspace/scripts/extract_decisions.py" >>"$LOG_FILE" 2>&1; then
        log "KB decision index complete"
    else
        log "⚠️ KB decision index failed"
    fi
}

# Main
case "${1:-all}" in
    research)
        run_research
        ;;
    health)
        run_health
        ;;
    memory)
        run_memory
        ;;
```

## Phase 2 Minimal Wiring Applied

```bash
rg -n 'run_health\(|verify_vllm_singleton|vLLM singleton invariant' workspace/scripts/nightly_build.sh
```

```text
103:run_health() {
108:    if bash "$CLAWD_DIR/workspace/scripts/verify_vllm_singleton.sh" >>"$LOG_FILE" 2>&1; then
109:        log "✅ vLLM singleton invariant: OK"
111:        log "❌ vLLM singleton invariant: FAILED"
```

```bash
git diff -- workspace/scripts/nightly_build.sh | sed -n '1,220p'
```

```text
diff --git a/workspace/scripts/nightly_build.sh b/workspace/scripts/nightly_build.sh
index adda5a8..d125279 100755
--- a/workspace/scripts/nightly_build.sh
+++ b/workspace/scripts/nightly_build.sh
@@ -104,6 +104,13 @@ run_health() {
     log "=== System Health ==="
 
     run_openclaw_config_preflight
+
+    if bash "$CLAWD_DIR/workspace/scripts/verify_vllm_singleton.sh" >>"$LOG_FILE" 2>&1; then
+        log "✅ vLLM singleton invariant: OK"
+    else
+        log "❌ vLLM singleton invariant: FAILED"
+        return 1
+    fi
     
     # Check Gateway
     if "$OPENCLAW_BIN" status 2>&1 | grep -q "running"; then
```

## Phase 3 Evidence Run

```bash
set -euo pipefail
date -u

bash workspace/scripts/verify_vllm_singleton.sh || true

bash workspace/scripts/nightly_build.sh health || true
```

```text
Sat Feb 21 21:17:24 UTC 2026
vLLM singleton invariant check
  system unit: vllm-assistant.service
  user unit:   openclaw-vllm.service
  port:        8001

systemctl: vllm-assistant.service enabled=enabled active=active
systemctl --user: openclaw-vllm.service enabled=disabled active=inactive

listeners on :8001 = 1
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))            

vLLM-related processes:
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
18932 /bin/bash -c set -euo pipefail cd /home/jeebs/src/clawd AUDIT='workspace/audit/dali_vllm_singleton_invariant_20260221T210635Z.md' append_cmd(){   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  {   echo '## Phase 2 Minimal Wiring Applied'   echo } >> "$AUDIT" append_cmd "rg -n 'run_health\(|verify_vllm_singleton|vLLM singleton invariant' workspace/scripts/nightly_build.sh" append_cmd "git diff -- workspace/scripts/nightly_build.sh | sed -n '1,220p'"  {   echo '## Phase 3 Evidence Run'   echo } >> "$AUDIT" append_cmd "set -euo pipefail date -u  bash workspace/scripts/verify_vllm_singleton.sh || true  bash workspace/scripts/nightly_build.sh health || true"  echo done
18943 bash -lc set -euo pipefail date -u  bash workspace/scripts/verify_vllm_singleton.sh || true  bash workspace/scripts/nightly_build.sh health || true
18948 bash workspace/scripts/verify_vllm_singleton.sh
18966 bash workspace/scripts/verify_vllm_singleton.sh

PASS: vLLM singleton invariant holds
[2026-02-22 07:17:24] === System Health ===
[2026-02-22 07:17:24] OpenClaw config source: /home/jeebs/.openclaw/openclaw.json (default)
[2026-02-22 07:17:27] ✅ OpenClaw config preflight: OK
[2026-02-22 07:17:27] ❌ vLLM singleton invariant: FAILED
```

## Phase 2 Adjustment
Initial health invocation failed due path resolution under default `CLAWD_DIR=$HOME/clawd` in this environment. Minimal follow-up change switches verifier invocation to `SCRIPT_DIR` to keep behavior local to the script location while preserving health-mode gating semantics.

```bash
git diff -- workspace/scripts/nightly_build.sh | sed -n '1,220p'
```

```text
diff --git a/workspace/scripts/nightly_build.sh b/workspace/scripts/nightly_build.sh
index adda5a8..fa09d90 100755
--- a/workspace/scripts/nightly_build.sh
+++ b/workspace/scripts/nightly_build.sh
@@ -104,6 +104,13 @@ run_health() {
     log "=== System Health ==="
 
     run_openclaw_config_preflight
+
+    if bash "$SCRIPT_DIR/verify_vllm_singleton.sh" >>"$LOG_FILE" 2>&1; then
+        log "✅ vLLM singleton invariant: OK"
+    else
+        log "❌ vLLM singleton invariant: FAILED"
+        return 1
+    fi
     
     # Check Gateway
     if "$OPENCLAW_BIN" status 2>&1 | grep -q "running"; then
```

```bash
set -euo pipefail
date -u
bash workspace/scripts/verify_vllm_singleton.sh || true
bash workspace/scripts/nightly_build.sh health || true
```

```text
Sat Feb 21 21:18:19 UTC 2026
vLLM singleton invariant check
  system unit: vllm-assistant.service
  user unit:   openclaw-vllm.service
  port:        8001

systemctl: vllm-assistant.service enabled=enabled active=active
systemctl --user: openclaw-vllm.service enabled=disabled active=inactive

listeners on :8001 = 1
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))            

vLLM-related processes:
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
19179 /bin/bash -c set -euo pipefail cd /home/jeebs/src/clawd AUDIT='workspace/audit/dali_vllm_singleton_invariant_20260221T210635Z.md' append_cmd(){   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  cat >> "$AUDIT" <<'EOF' ## Phase 2 Adjustment Initial health invocation failed due path resolution under default `CLAWD_DIR=$HOME/clawd` in this environment. Minimal follow-up change switches verifier invocation to `SCRIPT_DIR` to keep behavior local to the script location while preserving health-mode gating semantics.  EOF append_cmd "git diff -- workspace/scripts/nightly_build.sh | sed -n '1,220p'" append_cmd "set -euo pipefail date -u bash workspace/scripts/verify_vllm_singleton.sh || true bash workspace/scripts/nightly_build.sh health || true"  echo done
19187 bash -lc set -euo pipefail date -u bash workspace/scripts/verify_vllm_singleton.sh || true bash workspace/scripts/nightly_build.sh health || true
19192 bash workspace/scripts/verify_vllm_singleton.sh
19210 bash workspace/scripts/verify_vllm_singleton.sh

PASS: vLLM singleton invariant holds
[2026-02-22 07:18:19] === System Health ===
[2026-02-22 07:18:19] OpenClaw config source: /home/jeebs/.openclaw/openclaw.json (default)
[2026-02-22 07:18:21] ✅ OpenClaw config preflight: OK
[2026-02-22 07:18:21] ✅ vLLM singleton invariant: OK
[2026-02-22 07:18:24] ✅ Gateway: OK
[2026-02-22 07:18:24] ⚠️ Ollama: Not responding
[2026-02-22 07:18:25] ⚠️ Cron: Issues
[2026-02-22 07:18:25] ✅ Disk: 5% used
[2026-02-22 07:18:25] Health check complete
```

## Rollback
- Revert commit:
  - `git revert <new-commit-sha>`
- Manual rollback alternative:
  - Remove `workspace/scripts/verify_vllm_singleton.sh`
  - Remove the verifier call block from `workspace/scripts/nightly_build.sh` in `run_health()`.

