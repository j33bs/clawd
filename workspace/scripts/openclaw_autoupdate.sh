#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

state_file="${OPENCLAW_AUTOUPDATE_STATE:-$repo_root/workspace/.runtime_autoupdate_state}"
log_file="${OPENCLAW_AUTOUPDATE_LOG:-$repo_root/workspace/audit/runtime_autoupdate.log}"
dry_run="${OPENCLAW_AUTOUPDATE_DRYRUN:-0}"
target_branch="${OPENCLAW_AUTOUPDATE_TARGET_BRANCH:-main}"
allow_branches_raw="${OPENCLAW_AUTOUPDATE_ALLOW_BRANCHES:-}"
force_run="${OPENCLAW_AUTOUPDATE_FORCE:-0}"
config_path_override="${OPENCLAW_CONFIG_PATH:-}"

mkdir -p "$(dirname "$state_file")" "$(dirname "$log_file")"

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

old_sha=""
new_sha="$(git rev-parse HEAD)"
current_branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo "<detached>")"
if [[ -f "$state_file" ]]; then
  old_sha="$(awk -F= '/^sha=/{print $2}' "$state_file" | tail -n 1)"
fi

changed_files=()
commands_executed=()
quiesce_method="none"
verify_outcome="skipped"
result="success"
reason=""
error_detail=""
state_write_pending=0
state_backup_file=""

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
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:$label:$*"
    return 0
  fi
  log_action "executed:$label:$*"
  "$@"
}

trim_spaces() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  echo "$s"
}

branch_matches_allowlist() {
  local pattern
  local -a patterns=()
  IFS=',' read -r -a patterns <<< "$allow_branches_raw"
  for pattern in "${patterns[@]}"; do
    pattern="$(trim_spaces "$pattern")"
    [[ -z "$pattern" ]] && continue
    if [[ "$current_branch" == $pattern ]]; then
      return 0
    fi
  done
  return 1
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
    quiesce_method="planned"
    log_action "planned:quiesce:systemctl --user stop openclaw-gateway.service (or pid_fallback)"
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
    log_action "planned:restart:systemctl --user start openclaw-gateway.service (if systemctl path)"
    return 0
  fi

  if [[ "$quiesce_method" == "systemctl" ]] && command -v systemctl >/dev/null 2>&1; then
    run_cmd "restart" systemctl --user start openclaw-gateway.service
    return 0
  fi

  echo "OpenClaw gateway not auto-started; start it manually for this environment."
  log_action "restart: manual_start_required"
}

restore_state_backup() {
  if [[ -n "$state_backup_file" ]] && [[ -f "$state_backup_file" ]]; then
    cp "$state_backup_file" "$state_file"
    log_action "rollback:state_restore:$state_file"
  fi
}

run_health_gate() {
  local stage="$1"
  local guard_cmd=(python3 "$repo_root/workspace/scripts/openclaw_config_guard.py")
  if [[ -n "$config_path_override" ]]; then
    guard_cmd+=(--config "$config_path_override")
  fi
  guard_cmd+=(--strict)

  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:health_gate:$stage:${guard_cmd[*]}"
    return 0
  fi

  if "${guard_cmd[@]}" >/dev/null 2>&1; then
    log_action "executed:health_gate:$stage:pass"
    return 0
  fi

  log_action "executed:health_gate:$stage:fail"
  return 1
}

finalize() {
  local exit_code="$1"
  if [[ "$exit_code" -ne 0 ]]; then
    result="failure"
  fi

  if [[ "$exit_code" -ne 0 ]] && [[ "$dry_run" != "1" ]]; then
    restore_state_backup
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
    if [[ -n "$reason" ]]; then
      printf 'reason=%s\n' "$reason"
    fi
    printf 'dry_run=%s\n' "$dry_run"
    printf 'force_run=%s\n' "$force_run"
    printf 'old_sha=%s\n' "${old_sha:-<none>}"
    printf 'new_sha=%s\n' "$new_sha"
    printf 'current_branch=%s\n' "$current_branch"
    printf 'target_branch=%s\n' "$target_branch"
    if [[ -n "$allow_branches_raw" ]]; then
      printf 'allow_branches=%s\n' "$allow_branches_raw"
    fi
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

if [[ "$dry_run" == "1" ]]; then
  log_action "planned:branch_gate:bypass_dry_run"
elif [[ "$force_run" == "1" ]]; then
  log_action "executed:branch_gate:force_override"
elif [[ "$current_branch" == "$target_branch" ]]; then
  log_action "executed:branch_gate:target_branch_match"
elif branch_matches_allowlist; then
  log_action "executed:branch_gate:allowlist_match"
else
  result="skipped"
  reason="branch_gate"
  log_action "executed:branch_gate:skip current=$current_branch target=$target_branch allow=$allow_branches_raw"
  exit 0
fi

if [[ -n "$old_sha" ]] && [[ "$old_sha" == "$new_sha" ]]; then
  result="noop"
  log_action "head unchanged; no actions"
  exit 0
fi

if [[ -n "$old_sha" ]] && git cat-file -e "${old_sha}^{commit}" >/dev/null 2>&1; then
  while IFS= read -r changed; do
    [[ -n "$changed" ]] && changed_files+=("$changed")
  done < <(git diff --name-only "$old_sha" "$new_sha")
else
  changed_files=("<state_bootstrap>")
fi

state_write_pending=1
if [[ "$dry_run" != "1" ]] && [[ -f "$state_file" ]]; then
  state_backup_file="${state_file}.bak.$$"
  cp "$state_file" "$state_backup_file"
  log_action "executed:state_backup:$state_backup_file"
fi

if ! run_health_gate "pre"; then
  verify_outcome="health_gate_pre_fail"
  reason="health_gate_pre"
  exit 1
fi

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
    if [[ "$dry_run" == "1" ]]; then
      log_action "planned:gateway_install:skip_unavailable"
    else
      log_action "gateway_install: openclaw present but gateway install unavailable"
    fi
  fi
else
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:gateway_install:skip_openclaw_missing"
  else
    log_action "gateway_install: openclaw command missing"
  fi
fi

restart_gateway

if [[ -f "$repo_root/workspace/scripts/verify_policy_router.sh" ]]; then
  if [[ "$dry_run" == "1" ]]; then
    verify_outcome="dryrun"
    log_action "planned:verify:bash workspace/scripts/verify_policy_router.sh"
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

if ! run_health_gate "post"; then
  verify_outcome="health_gate_post_fail"
  reason="health_gate_post"
  exit 1
fi
