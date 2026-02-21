#!/usr/bin/env bash
# Scan workspace/audit artifacts for potential secrets.
set -euo pipefail

ALLOWLIST_FILE="workspace/governance/audit_secret_allowlist.txt"
BASE_SHA="${1:-}"
HEAD_SHA="${2:-}"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "FAIL audit-secret-scan: not inside a git repository"
  exit 1
fi

if [[ ! -f "$ALLOWLIST_FILE" ]]; then
  echo "FAIL audit-secret-scan: missing allowlist file: $ALLOWLIST_FILE"
  exit 1
fi

ALLOWLIST_REGEXES=()
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line_without_comment="${raw_line%%#*}"
  trimmed_line="$(printf '%s' "$line_without_comment" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
  if [[ -z "$trimmed_line" ]]; then
    continue
  fi
  ALLOWLIST_REGEXES+=("$trimmed_line")
done < "$ALLOWLIST_FILE"

collect_staged_audit_files() {
  git diff --cached --name-only --diff-filter=ACMR | rg '^workspace/audit/' || true
}

collect_diff_audit_files() {
  local base="$1"
  local head="$2"
  git diff --name-only --diff-filter=ACMR "$base" "$head" | rg '^workspace/audit/' || true
}

collect_all_tracked_audit_files() {
  git ls-files 'workspace/audit/**' || true
}

is_text_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    return 1
  fi
  if [[ ! -s "$path" ]]; then
    return 0
  fi
  LC_ALL=C grep -Iq . "$path"
}

is_allowlisted_match() {
  local match_text="$1"
  local regex
  for regex in "${ALLOWLIST_REGEXES[@]}"; do
    if printf '%s\n' "$match_text" | rg -q -e "$regex"; then
      return 0
    fi
  done
  return 1
}

SCAN_MODE="staged"
SCAN_FILES_RAW="$(collect_staged_audit_files)"

if [[ -z "${SCAN_FILES_RAW//[[:space:]]/}" && -n "$BASE_SHA" && -n "$HEAD_SHA" ]]; then
  SCAN_MODE="diff"
  SCAN_FILES_RAW="$(collect_diff_audit_files "$BASE_SHA" "$HEAD_SHA")"
fi

if [[ -z "${SCAN_FILES_RAW//[[:space:]]/}" && ( "${CI:-}" = "true" || "${GITHUB_ACTIONS:-}" = "true" ) ]]; then
  SCAN_MODE="all-tracked"
  SCAN_FILES_RAW="$(collect_all_tracked_audit_files)"
fi

if [[ -z "${SCAN_FILES_RAW//[[:space:]]/}" ]]; then
  if [[ "$SCAN_MODE" = "staged" ]]; then
    echo "PASS audit-secret-scan: no staged workspace/audit files to scan"
  else
    echo "PASS audit-secret-scan: no workspace/audit files to scan"
  fi
  exit 0
fi

SCAN_FILES=()
while IFS= read -r maybe_file; do
  if [[ -n "$maybe_file" ]]; then
    SCAN_FILES+=("$maybe_file")
  fi
done <<< "$SCAN_FILES_RAW"

FINDINGS=()
scan_one_file() {
  local display_path="$1"
  local scan_path="$2"
  local rg_hit
  local rg_line
  local rg_match

  if ! is_text_file "$scan_path"; then
    return 0
  fi

  while IFS= read -r rg_hit; do
    if [[ -z "$rg_hit" ]]; then
      continue
    fi
    rg_line="${rg_hit%%:*}"
    rg_match="${rg_hit#*:}"
    if is_allowlisted_match "$rg_match"; then
      continue
    fi
    FINDINGS+=("${display_path}:${rg_line}:${rg_match}")
  done < <(
    rg --no-heading --color=never -n -o \
      -e 'OPENCLAW_TOKEN\s*[:=]\s*[A-Za-z0-9._~+/=-]{8,}' \
      -e '\bsk-[A-Za-z0-9_-]{16,}\b' \
      -e '\bghp_[A-Za-z0-9]{20,}\b' \
      -e '\bAKIA[0-9A-Z]{16}\b' \
      -e '-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----' \
      -e '(?i)\b(api[_-]?key|token|secret)\b\s*[:=]\s*[A-Za-z0-9+/_=.-]{20,}' \
      "$scan_path" || true
  )
}

for repo_file in "${SCAN_FILES[@]}"; do
  if [[ "$SCAN_MODE" = "staged" ]]; then
    staged_tmp="$(mktemp)"
    if git show ":$repo_file" > "$staged_tmp" 2>/dev/null; then
      scan_one_file "$repo_file" "$staged_tmp"
    fi
    rm -f "$staged_tmp"
  else
    if [[ -f "$repo_file" ]]; then
      scan_one_file "$repo_file" "$repo_file"
    fi
  fi
done

if [[ "${#FINDINGS[@]}" -gt 0 ]]; then
  echo "FAIL audit-secret-scan: potential secret material detected in workspace/audit artifacts."
  printf '%s\n' "${FINDINGS[@]}" | sort -u
  echo "Guidance: redact, replace with placeholders, re-run."
  exit 1
fi

echo "PASS audit-secret-scan: no non-allowlisted matches in ${#SCAN_FILES[@]} file(s) [mode=$SCAN_MODE]"
exit 0
