#!/bin/bash
# Nightly Build - Autonomous work while you sleep
# Usage: ./nightly_build.sh [research|health|memory|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWD_DIR="$HOME/clawd"
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
    all)
        log "=== Nightly Build Starting ==="
        run_research
        run_health
        run_memory
        run_kb_sync
        run_kb_decisions
        log "=== Nightly Build Complete ==="
        ;;
    *)
        echo "Usage: $0 [research|health|memory|all]"
        exit 1
        ;;
esac
