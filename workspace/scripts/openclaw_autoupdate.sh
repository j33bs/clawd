#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

state_file="${OPENCLAW_AUTOUPDATE_STATE:-$repo_root/workspace/.runtime_autoupdate_state}"
log_file="${OPENCLAW_AUTOUPDATE_LOG:-$repo_root/workspace/audit/runtime_autoupdate.log}"
dry_run="${OPENCLAW_AUTOUPDATE_DRYRUN:-0}"

mkdir -p "$(dirname "$state_file")" "$(dirname "$log_file")"

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

old_sha=""
new_sha="$(git rev-parse HEAD)"
target_branch="${OPENCLAW_AUTOUPDATE_BRANCH:-main}"
current_branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo DETACHED)"
if [[ -f "$state_file" ]]; then
  old_sha="$(awk -F= '/^sha=/{print $2}' "$state_file" | tail -n 1)"
fi

changed_files=()
commands_executed=()
quiesce_method="none"
verify_outcome="skipped"
result="success"
error_detail=""
state_write_pending=0

join_csv() {
  local IFS=,
  echo "$*"
}

log_action() {
  commands_executed+=("$1")
}

has_file_changed() {
  local target="$1"
  local file
  for file in "${changed_files[@]}"; do
    [[ "$file" == "$target" ]] && return 0
  done
  return 1
}

any_build_relevant_change() {
  local file
  for file in "${changed_files[@]}"; do
    if [[ "$file" =~ ^src/ ]] || [[ "$file" =~ ^workspace/scripts/ ]] || [[ "$file" =~ ^package(-lock)?\.json$ ]] || [[ "$file" =~ \.ts$ ]] || [[ "$file" =~ \.js$ ]] || [[ "$file" =~ ^tsconfig ]]; then
      return 0
    fi
  done
  return 1
}

run_cmd() {
  local label="$1"
  shift
  log_action "$label: $*"
  if [[ "$dry_run" == "1" ]]; then
    return 0
  fi
  "$@"
}

exact_gateway_pids() {
  local line pid cmd first base
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    pid="${line%% *}"
    cmd="${line#* }"
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    [[ "$pid" == "$$" || "$pid" == "$PPID" ]] && continue

    first="${cmd%% *}"
    base="${first##*/}"

    if [[ "$base" == "openclaw-gateway" ]]; then
      echo "$pid"
      continue
    fi

    if [[ "$base" == "openclaw" ]] && [[ "$cmd" =~ (^|[[:space:]])gateway([[:space:]]|$) ]]; then
      echo "$pid"
      continue
    fi
  done < <(pgrep -af 'openclaw-gateway|openclaw.*gateway' || true)
}

quiesce_gateway() {
  if [[ "$dry_run" == "1" ]]; then
    quiesce_method="dryrun"
    log_action "quiesce: dry-run skip stop"
    return 0
  fi

  if command -v systemctl >/dev/null 2>&1; then
    local stop_out
    stop_out="$(systemctl --user stop openclaw-gateway.service 2>&1 || true)"
    if [[ -z "$stop_out" ]]; then
      quiesce_method="systemctl"
      log_action "systemctl --user stop openclaw-gateway.service"
      return 0
    fi

    log_action "systemctl --user stop openclaw-gateway.service (output: ${stop_out//$'\n'/ })"
    if [[ "$stop_out" =~ Failed[[:space:]]to[[:space:]]connect[[:space:]]to[[:space:]]bus ]]; then
      quiesce_method="pid_fallback"
      local pids=()
      local pid
      while IFS= read -r pid; do
        [[ -n "$pid" ]] && pids+=("$pid")
      done < <(exact_gateway_pids | sort -u)

      if [[ ${#pids[@]} -gt 0 ]]; then
        log_action "kill ${pids[*]}"
        kill "${pids[@]}"
      else
        log_action "pid_fallback: no exact openclaw gateway pid found"
      fi
      return 0
    fi

    quiesce_method="systemctl_error"
    return 0
  fi

  quiesce_method="systemctl_missing"
  log_action "systemctl missing; gateway stop skipped"
}

restart_gateway() {
  if [[ "$dry_run" == "1" ]]; then
    log_action "restart: dry-run skip start"
    return 0
  fi

  if [[ "$quiesce_method" == "systemctl" ]] && command -v systemctl >/dev/null 2>&1; then
    run_cmd "restart" systemctl --user start openclaw-gateway.service
    return 0
  fi

  echo "OpenClaw gateway not auto-started; start it manually for this environment."
  log_action "restart: manual_start_required"
}

finalize() {
  local exit_code="$1"
  if [[ "$exit_code" -ne 0 ]]; then
    result="failure"
  fi

  if [[ "$exit_code" -eq 0 ]] && [[ "$dry_run" != "1" ]] && [[ "$state_write_pending" == "1" ]]; then
    {
      printf 'sha=%s\n' "$new_sha"
      printf 'updated_at=%s\n' "$(timestamp_utc)"
    } > "$state_file"
  fi

  {
    printf '[%s] openclaw_autoupdate\n' "$(timestamp_utc)"
    printf 'result=%s\n' "$result"
    printf 'dry_run=%s\n' "$dry_run"
    printf 'old_sha=%s\n' "${old_sha:-<none>}"
    printf 'new_sha=%s\n' "$new_sha"
    printf 'current_branch=%s\n' "$current_branch"
    printf 'target_branch=%s\n' "$target_branch"
    printf 'changed_files_count=%s\n' "${#changed_files[@]}"
    if [[ ${#changed_files[@]} -gt 0 ]]; then
      printf 'changed_files=%s\n' "$(join_csv "${changed_files[@]}")"
    else
      printf 'changed_files=<none>\n'
    fi
    printf 'quiesce_method=%s\n' "$quiesce_method"
    if [[ ${#commands_executed[@]} -gt 0 ]]; then
      printf 'commands=%s\n' "$(join_csv "${commands_executed[@]}")"
    else
      printf 'commands=<none>\n'
    fi
    printf 'verify_outcome=%s\n' "$verify_outcome"
    if [[ -n "$error_detail" ]]; then
      printf 'error_detail=%s\n' "$error_detail"
    fi
    printf 'exit_code=%s\n' "$exit_code"
    printf -- '---\n'
  } >> "$log_file"
}

on_err() {
  error_detail="command failed: ${BASH_COMMAND}"
}

trap 'on_err' ERR
trap 'finalize "$?"' EXIT

if [[ "$current_branch" != "$target_branch" ]]; then
  result="noop"
  log_action "branch $current_branch is not target $target_branch; no actions"
  exit 0
fi

if [[ -n "$old_sha" ]] && [[ "$old_sha" == "$new_sha" ]]; then
  result="noop"
  log_action "head unchanged; no actions"
  exit 0
fi

if [[ -n "$old_sha" ]] && git cat-file -e "${old_sha}^{commit}" >/dev/null 2>&1; then
  mapfile -t changed_files < <(git diff --name-only "$old_sha" "$new_sha")
else
  changed_files=("<state_bootstrap>")
fi

state_write_pending=1

quiesce_gateway

should_npm_ci=0
if has_file_changed "package.json" || has_file_changed "package-lock.json"; then
  should_npm_ci=1
elif [[ "${changed_files[*]}" == *"<state_bootstrap>"* ]] && [[ -f package.json ]]; then
  should_npm_ci=1
fi

if [[ "$should_npm_ci" == "1" ]]; then
  run_cmd "deps" npm ci
fi

has_build_script=0
if [[ -f package.json ]] && command -v node >/dev/null 2>&1; then
  if node -e 'const fs=require("fs"); const p=JSON.parse(fs.readFileSync("package.json","utf8")); process.exit(p.scripts && p.scripts.build ? 0 : 1);' >/dev/null 2>&1; then
    has_build_script=1
  fi
fi

should_build=0
if [[ "$has_build_script" == "1" ]]; then
  if [[ "$should_npm_ci" == "1" ]] || any_build_relevant_change || [[ "${changed_files[*]}" == *"<state_bootstrap>"* ]]; then
    should_build=1
  fi
fi

if [[ "$should_build" == "1" ]]; then
  run_cmd "build" npm run -s build
fi

if command -v openclaw >/dev/null 2>&1; then
  if openclaw gateway --help >/dev/null 2>&1; then
    run_cmd "gateway_install" openclaw gateway install --force
  else
    log_action "gateway_install: openclaw present but gateway install unavailable"
  fi
else
  log_action "gateway_install: openclaw command missing"
fi

restart_gateway

if [[ -f "$repo_root/workspace/scripts/verify_policy_router.sh" ]]; then
  if [[ "$dry_run" == "1" ]]; then
    verify_outcome="dryrun"
    log_action "verify: dry-run skip bash workspace/scripts/verify_policy_router.sh"
  else
    if bash "$repo_root/workspace/scripts/verify_policy_router.sh"; then
      verify_outcome="pass"
      log_action "verify: pass"
    else
      verify_outcome="fail"
      log_action "verify: fail"
      exit 1
    fi
  fi
else
  verify_outcome="missing"
  log_action "verify: missing workspace/scripts/verify_policy_router.sh"
fi
