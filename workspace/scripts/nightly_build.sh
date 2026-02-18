#!/bin/bash
# Nightly Build - Autonomous work while you sleep
# Usage: ./nightly_build.sh [research|health|memory|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWD_DIR="$HOME/clawd"
RESEARCH_TOPICS_FILE="$CLAWD_DIR/workspace/research/TOPICS.md"
RESEARCH_OUT_DIR="$CLAWD_DIR/reports/research"

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
    if ~/.npm-global/bin/openclaw status 2>&1 | grep -q "running"; then
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
    cron_status=$(~/.npm-global/bin/openclaw cron status 2>&1)
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
    archived=0
    find "$memory_dir" -name "2*.md" -mtime +30 | while read -r file; do
        # Check if already archived
        if [[ ! "$file" =~ \-archive\- ]]; then
            archive_dir="$memory_dir/archive/$(date +%Y)"
            mkdir -p "$archive_dir"
            mv "$file" "$archive_dir/"
            archived=$((archived + 1))
        fi
    done
    
    if [ $archived -gt 0 ]; then
        log "Archived $archived old memory files"
    else
        log "No files to archive"
    fi
    
    # Count lines in MEMORY.md
    if [ -f "$CLAWD_DIR/MEMORY.md" ]; then
        lines=$(wc -l < "$CLAWD_DIR/MEMORY.md")
        log "MEMORY.md: $lines lines"
    fi
    
    log "Memory prune complete"
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
        log "=== Nightly Build Complete ==="
        ;;
    *)
        echo "Usage: $0 [research|health|memory|all]"
        exit 1
        ;;
esac
