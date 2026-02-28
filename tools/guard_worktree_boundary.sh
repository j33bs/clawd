#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  exit 0
fi

mode="${MODE:-}"
if [[ -z "${mode}" ]]; then
  mode="$("${repo_root}/tools/print_worktree_mode.sh")"
fi

case "${mode}" in
  CANON|LIVEWIRE) ;;
  *)
    echo "FAIL: invalid MODE=${mode} (expected CANON or LIVEWIRE)" >&2
    exit 1
    ;;
esac

allowlist_file="${ALLOWLIST_FILE:-${repo_root}/tools/worktree_dirty_allowlist.txt}"
snapshot_dir="${repo_root}/workspace/audit"
mkdir -p "${snapshot_dir}"

trim_ws() {
  local v="$1"
  v="${v#"${v%%[![:space:]]*}"}"
  v="${v%"${v##*[![:space:]]}"}"
  printf '%s' "${v}"
}

extract_paths() {
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    local path="${line:3}"
    if [[ "${path}" == *" -> "* ]]; then
      path="${path##* -> }"
    fi
    printf '%s\n' "${path}"
  done
}

is_internal_snapshot_path() {
  local path="$1"
  [[ "${path}" == workspace/audit/worktree_dirty_snapshot_*.md ]]
}

filter_status_lines() {
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    local path="${line:3}"
    if [[ "${path}" == *" -> "* ]]; then
      path="${path##* -> }"
    fi
    if is_internal_snapshot_path "${path}"; then
      continue
    fi
    printf '%s\n' "${line}"
  done
}

matches_allowlist() {
  local path="$1"
  local pattern_raw=""
  local pattern=""
  if [[ ! -f "${allowlist_file}" ]]; then
    return 1
  fi
  while IFS= read -r pattern_raw; do
    pattern_raw="${pattern_raw%%#*}"
    pattern="$(trim_ws "${pattern_raw}")"
    [[ -n "${pattern}" ]] || continue
    if [[ "${path}" == ${pattern} ]]; then
      return 0
    fi
  done < "${allowlist_file}"
  return 1
}

write_snapshot() {
  local snapshot_mode="$1"
  local status_body="$2"
  local ts
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  local snapshot_path="${snapshot_dir}/worktree_dirty_snapshot_${ts}_${snapshot_mode}.md"
  local diff_file
  diff_file="$(mktemp)"
  git -C "${repo_root}" diff > "${diff_file}" || true
  local diff_lines
  diff_lines="$(wc -l < "${diff_file}" | tr -d '[:space:]')"

  {
    echo "# Worktree Dirty Snapshot (${snapshot_mode})"
    echo
    echo "timestamp_utc: ${ts}"
    echo "mode: ${snapshot_mode}"
    echo "repo_root: ${repo_root}"
    echo "pwd: $(pwd -P)"
    echo "branch: $(git -C "${repo_root}" branch --show-current)"
    echo "head: $(git -C "${repo_root}" rev-parse HEAD)"
    echo
    echo "## git status --porcelain=v1"
    printf '%s\n' "${status_body}"
    echo
    echo "## git diff --stat"
    git -C "${repo_root}" diff --stat || true
    echo
    echo "## git diff"
    if (( diff_lines > 2000 )); then
      echo "_truncated: total_lines=${diff_lines}, showing first 500 and last 200_"
      echo
      echo "### first_500"
      sed -n '1,500p' "${diff_file}"
      echo
      echo "### last_200"
      tail -n 200 "${diff_file}"
    else
      cat "${diff_file}"
    fi
  } > "${snapshot_path}"

  rm -f "${diff_file}"
  printf '%s\n' "${snapshot_path}"
}

status_raw="$(git -C "${repo_root}" status --porcelain=v1)"
status_now="$(printf '%s\n' "${status_raw}" | filter_status_lines)"
if [[ -z "${status_now}" ]]; then
  exit 0
fi

snapshot_path="$(write_snapshot "${mode}" "${status_now}")"

if [[ "${mode}" == "LIVEWIRE" ]]; then
  exit 0
fi

mapfile -t dirty_paths < <(printf '%s\n' "${status_now}" | extract_paths)
if [[ "${#dirty_paths[@]}" -eq 0 ]]; then
  exit 0
fi

all_allowlisted=1
for path in "${dirty_paths[@]}"; do
  if ! matches_allowlist "${path}"; then
    all_allowlisted=0
    break
  fi
done

if [[ "${all_allowlisted}" -eq 1 ]]; then
  exit 0
fi

echo "CANON boundary blocked; non-allowlisted workspace drift detected (no auto-restore performed)." >&2
while IFS= read -r rem; do
  [[ -n "${rem}" ]] || continue
  echo "- ${rem}" >&2
done < <(printf '%s\n' "${status_now}" | extract_paths)
echo "snapshot: ${snapshot_path}" >&2
exit 2
