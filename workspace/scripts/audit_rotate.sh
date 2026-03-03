#!/usr/bin/env bash
# audit_rotate.sh — CSA CCM v4 LOG-02, LOG-06
#
# Prunes old audit snapshot files from workspace/audit/ according to
# the retention policy.  Preserves critical forensic artifacts.
#
# Usage:
#   bash workspace/scripts/audit_rotate.sh [--dry-run]
#
# Configuration (env vars):
#   AUDIT_RETAIN_DAYS       — retain .md snapshots newer than N days (default: 90)
#   AUDIT_DIR               — path to audit directory (default: <repo-root>/workspace/audit)
#
# Preserved files (never deleted):
#   agent_actions.jsonl*                — live action audit log and rotated archives
#   commit_audit_log.jsonl              — git commit audit chain
#   _evidence/                          — evidence subdirectory (entire tree)
#   evidence/                           — alternate evidence subdirectory
#   worktree_dirty_snapshot_*_CANON.md  — CANON worktree snapshots (30-day retention)
#
# Cron wiring example (daily at 03:00):
#   0 3 * * * cd /path/to/repo && bash workspace/scripts/audit_rotate.sh >> /var/log/audit_rotate.log 2>&1
# See also: workspace/HEARTBEAT.md

set -euo pipefail

DRY_RUN=0
for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=1 ;;
    *) echo "audit_rotate: unknown argument: ${arg}" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

AUDIT_DIR="${AUDIT_DIR:-${REPO_ROOT}/workspace/audit}"
RETAIN_DAYS="${AUDIT_RETAIN_DAYS:-90}"
CANON_RETAIN_DAYS=30

if [[ ! -d "${AUDIT_DIR}" ]]; then
  echo "audit_rotate: audit directory not found: ${AUDIT_DIR}" >&2
  exit 1
fi

if [[ ! "${RETAIN_DAYS}" =~ ^[0-9]+$ ]] || (( RETAIN_DAYS < 1 )); then
  echo "audit_rotate: AUDIT_RETAIN_DAYS must be a positive integer (got: ${RETAIN_DAYS})" >&2
  exit 1
fi

echo "audit_rotate: scanning ${AUDIT_DIR} (retain_days=${RETAIN_DAYS}, dry_run=${DRY_RUN})"

deleted_count=0
deleted_bytes=0
retained_count=0

# Compute cutoff timestamps (seconds since epoch).
cutoff_ts=$(( $(date +%s) - RETAIN_DAYS * 86400 ))
canon_cutoff_ts=$(( $(date +%s) - CANON_RETAIN_DAYS * 86400 ))

# Iterate over .md files in the audit directory (non-recursive to avoid
# deleting files inside _evidence/ or evidence/ subdirectories).
while IFS= read -r -d '' filepath; do
  filename="$(basename "${filepath}")"

  # Always preserve agent_actions* files.
  if [[ "${filename}" == agent_actions* ]]; then
    retained_count=$(( retained_count + 1 ))
    continue
  fi

  # Always preserve commit_audit_log.jsonl.
  if [[ "${filename}" == "commit_audit_log.jsonl" ]]; then
    retained_count=$(( retained_count + 1 ))
    continue
  fi

  # CANON worktree snapshots: apply shorter retention window.
  if [[ "${filename}" == worktree_dirty_snapshot_*_CANON.md ]]; then
    mtime=$(stat -c '%Y' "${filepath}" 2>/dev/null || echo 0)
    if (( mtime > canon_cutoff_ts )); then
      retained_count=$(( retained_count + 1 ))
      continue
    fi
  fi

  # For other .md files: check modification time against retention cutoff.
  mtime=$(stat -c '%Y' "${filepath}" 2>/dev/null || echo 0)
  if (( mtime > cutoff_ts )); then
    retained_count=$(( retained_count + 1 ))
    continue
  fi

  # File is eligible for deletion.
  fsize=$(stat -c '%s' "${filepath}" 2>/dev/null || echo 0)
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "audit_rotate: [dry-run] would delete ${filepath} (${fsize} bytes, mtime=$(date -d "@${mtime}" '+%Y-%m-%d' 2>/dev/null || echo "${mtime}"))"
  else
    rm -f "${filepath}"
    echo "audit_rotate: deleted ${filepath} (${fsize} bytes)"
  fi
  deleted_count=$(( deleted_count + 1 ))
  deleted_bytes=$(( deleted_bytes + fsize ))

done < <(find "${AUDIT_DIR}" -maxdepth 1 -type f -name '*.md' -print0 2>/dev/null)

# Also scan top-level .jsonl files (except preserved ones) for retention.
while IFS= read -r -d '' filepath; do
  filename="$(basename "${filepath}")"

  if [[ "${filename}" == agent_actions* ]] || [[ "${filename}" == "commit_audit_log.jsonl" ]]; then
    retained_count=$(( retained_count + 1 ))
    continue
  fi

  mtime=$(stat -c '%Y' "${filepath}" 2>/dev/null || echo 0)
  if (( mtime > cutoff_ts )); then
    retained_count=$(( retained_count + 1 ))
    continue
  fi

  fsize=$(stat -c '%s' "${filepath}" 2>/dev/null || echo 0)
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "audit_rotate: [dry-run] would delete ${filepath} (${fsize} bytes)"
  else
    rm -f "${filepath}"
    echo "audit_rotate: deleted ${filepath} (${fsize} bytes)"
  fi
  deleted_count=$(( deleted_count + 1 ))
  deleted_bytes=$(( deleted_bytes + fsize ))

done < <(find "${AUDIT_DIR}" -maxdepth 1 -type f -name '*.jsonl' -print0 2>/dev/null)

# Human-readable disk freed.
if command -v numfmt >/dev/null 2>&1; then
  freed_human="$(numfmt --to=iec-i --suffix=B "${deleted_bytes}" 2>/dev/null || echo "${deleted_bytes} bytes")"
else
  freed_human="${deleted_bytes} bytes"
fi

echo "audit_rotate: summary — deleted=${deleted_count}, retained=${retained_count}, freed=${freed_human}${DRY_RUN:+ (dry-run)}"
