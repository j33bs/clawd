#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
export PATH="$HOME/.local/bin:$PATH"

state_file="${OPENCLAW_AUTOUPDATE_STATE:-$repo_root/workspace/.runtime_autoupdate_state}"
log_file="${OPENCLAW_AUTOUPDATE_LOG:-$repo_root/workspace/audit/runtime_autoupdate.log}"
dry_run="${OPENCLAW_AUTOUPDATE_DRYRUN:-0}"
target_branch="${OPENCLAW_AUTOUPDATE_TARGET_BRANCH:-main}"
allow_branches_raw="${OPENCLAW_AUTOUPDATE_ALLOW_BRANCHES:-}"
force_run="${OPENCLAW_AUTOUPDATE_FORCE:-0}"
allow_sha_mismatch="${OPENCLAW_AUTOUPDATE_ALLOW_SHA_MISMATCH:-0}"
gateway_unit="${OPENCLAW_GATEWAY_UNIT:-openclaw-gateway.service}"
build_stamp_repo="${OPENCLAW_BUILD_STAMP_PATH:-$repo_root/workspace/version_build.json}"
build_stamp_user="${OPENCLAW_BUILD_STAMP_USER_PATH:-$HOME/.local/share/openclaw-build/version_build.json}"
wrapper_template="${OPENCLAW_OPENCLAW_WRAPPER_TEMPLATE:-$repo_root/workspace/scripts/openclaw_build_wrapper.sh}"
wrapper_target="${OPENCLAW_OPENCLAW_WRAPPER_TARGET:-$HOME/.local/bin/openclaw}"
wrapper_real="${OPENCLAW_OPENCLAW_REAL_TARGET:-$HOME/.local/bin/openclaw.real}"

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
expected_sha="$new_sha"
observed_cli_sha=""
observed_cli_version=""
observed_gateway_sha=""
observed_gateway_version=""
sha_check_mode="inactive"

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

json_field() {
  local file_path="$1"
  local key="$2"
  node -e 'const fs=require("fs"); const p=process.argv[1]; const k=process.argv[2]; try { const o=JSON.parse(fs.readFileSync(p,"utf8")); const v=Object.prototype.hasOwnProperty.call(o,k) ? String(o[k]) : ""; process.stdout.write(v); } catch {}' "$file_path" "$key"
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
    stop_out="$(systemctl --user stop "$gateway_unit" 2>&1 || true)"
    if [[ -z "$stop_out" ]]; then
      quiesce_method="systemctl"
      log_action "systemctl --user stop $gateway_unit"
      return 0
    fi

    log_action "systemctl --user stop $gateway_unit (output: ${stop_out//$'\n'/ })"
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
    log_action "planned:restart:systemctl --user start $gateway_unit (if systemctl path)"
    return 0
  fi

  if [[ "$quiesce_method" == "systemctl" ]] && command -v systemctl >/dev/null 2>&1; then
    run_cmd "restart" systemctl --user start "$gateway_unit"
    return 0
  fi

  echo "OpenClaw gateway not auto-started; start it manually for this environment."
  log_action "restart: manual_start_required"
}

generate_build_stamp() {
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:gen_build_stamp:bash workspace/scripts/gen_build_stamp.sh"
    return 0
  fi

  if [[ ! -x "$repo_root/workspace/scripts/gen_build_stamp.sh" ]]; then
    log_action "gen_build_stamp: missing workspace/scripts/gen_build_stamp.sh"
    return 1
  fi

  run_cmd "gen_build_stamp" bash "$repo_root/workspace/scripts/gen_build_stamp.sh"
  mkdir -p "$(dirname "$build_stamp_user")"
  cp "$build_stamp_repo" "$build_stamp_user"
  log_action "executed:publish_build_stamp:$build_stamp_repo->$build_stamp_user"
}

install_openclaw_wrapper() {
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:install_openclaw_wrapper:$wrapper_target"
    return 0
  fi

  if [[ ! -f "$wrapper_template" ]]; then
    log_action "install_openclaw_wrapper: missing template $wrapper_template"
    return 1
  fi

  local current_cmd
  current_cmd="$(command -v openclaw || true)"
  if [[ -z "$current_cmd" ]]; then
    log_action "install_openclaw_wrapper: openclaw missing"
    return 1
  fi

  mkdir -p "$(dirname "$wrapper_target")"
  if [[ ! -x "$wrapper_real" ]]; then
    cp "$current_cmd" "$wrapper_real"
    chmod +x "$wrapper_real"
    log_action "executed:openclaw_real_init:$wrapper_real from $current_cmd"
  fi

  cp "$wrapper_template" "$wrapper_target"
  chmod +x "$wrapper_target"
  log_action "executed:install_openclaw_wrapper:$wrapper_target real=$wrapper_real"
}

observe_cli_build() {
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:verify_build_sha:cli"
    return 0
  fi

  local version_line
  version_line="$(openclaw --version 2>/dev/null | head -n 1 || true)"
  observed_cli_sha="$(printf '%s' "$version_line" | sed -n 's/.*build_sha=\([0-9a-fA-F]\{7,40\}\).*/\1/p')"
  observed_cli_version="$(printf '%s' "$version_line" | sed -n 's/.*version=\([^ ]*\).*/\1/p')"
  if [[ -z "$observed_cli_version" ]]; then
    observed_cli_version="$(printf '%s' "$version_line" | awk '{print $1}')"
  fi
  if [[ -z "$observed_cli_sha" ]] && [[ -f "$build_stamp_user" ]] && command -v node >/dev/null 2>&1; then
    observed_cli_sha="$(json_field "$build_stamp_user" "build_sha")"
  fi

  log_action "observed:cli_version:${observed_cli_version:-missing}"
  log_action "observed:cli_build_sha:${observed_cli_sha:-missing}"
}

observe_gateway_build() {
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:verify_build_sha:gateway"
    return 0
  fi

  local line
  line="$(journalctl --user -u "$gateway_unit" -n 200 --no-pager 2>/dev/null | grep 'openclaw_gateway build_sha=' | tail -n 1 || true)"
  observed_gateway_sha="$(printf '%s' "$line" | sed -n 's/.*build_sha=\([0-9a-fA-F]\{7,40\}\).*/\1/p')"
  observed_gateway_version="$(printf '%s' "$line" | sed -n 's/.*version=\([^ ]*\).*/\1/p')"

  log_action "observed:gateway_build_sha:${observed_gateway_sha:-missing}"
  log_action "observed:gateway_version:${observed_gateway_version:-missing}"
}

enforce_build_sha() {
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:verify_build_sha:expected=$expected_sha"
    return 0
  fi

  sha_check_mode="observe"
  if [[ "$current_branch" == "main" ]]; then
    sha_check_mode="enforce"
  fi
  if [[ "$allow_sha_mismatch" == "1" ]]; then
    sha_check_mode="allow_override"
  fi

  log_action "expected_sha:$expected_sha"
  local mismatch=0
  if [[ -z "$observed_cli_sha" || "$observed_cli_sha" != "$expected_sha" ]]; then
    mismatch=1
  fi
  if [[ -z "$observed_gateway_sha" || "$observed_gateway_sha" != "$expected_sha" ]]; then
    mismatch=1
  fi

  if [[ "$mismatch" == "1" ]]; then
    log_action "verify_build_sha:mismatch expected=$expected_sha cli=${observed_cli_sha:-missing} gateway=${observed_gateway_sha:-missing}"
    if [[ "$sha_check_mode" == "enforce" ]]; then
      reason="sha_mismatch"
      exit 1
    fi
    log_action "warning:sha_mismatch_allowed mode=$sha_check_mode"
    return 0
  fi

  log_action "verify_build_sha:match expected=$expected_sha"
}

log_openclaw_resolution() {
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:openclaw_resolution:command -v openclaw && openclaw --version"
    return 0
  fi

  if ! command -v openclaw >/dev/null 2>&1; then
    log_action "observed:openclaw_path:missing"
    log_action "observed:openclaw_version:missing"
    return 0
  fi

  local oc_path oc_real oc_version
  oc_path="$(command -v openclaw)"
  oc_real="$(readlink -f "$oc_path" 2>/dev/null || echo "$oc_path")"
  oc_version="$(openclaw --version 2>/dev/null || echo unavailable)"

  log_action "observed:openclaw_path:$oc_real"
  log_action "observed:openclaw_version:$oc_version"
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
    if [[ -n "$reason" ]]; then
      printf 'reason=%s\n' "$reason"
    fi
    printf 'dry_run=%s\n' "$dry_run"
    printf 'force_run=%s\n' "$force_run"
    printf 'allow_sha_mismatch=%s\n' "$allow_sha_mismatch"
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
    printf 'sha_check_mode=%s\n' "$sha_check_mode"
    printf 'expected_sha=%s\n' "$expected_sha"
    printf 'observed_cli_sha=%s\n' "${observed_cli_sha:-<none>}"
    printf 'observed_cli_version=%s\n' "${observed_cli_version:-<none>}"
    printf 'observed_gateway_sha=%s\n' "${observed_gateway_sha:-<none>}"
    printf 'observed_gateway_version=%s\n' "${observed_gateway_version:-<none>}"
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

generate_build_stamp

if [[ -f package.json ]] && command -v npm >/dev/null 2>&1; then
  run_cmd "gateway_install" npm install -g . --prefix "$HOME/.local"
else
  if [[ "$dry_run" == "1" ]]; then
    log_action "planned:gateway_install:skip_missing_package_or_npm"
  else
    log_action "gateway_install: skipped (missing package.json or npm)"
  fi
fi

install_openclaw_wrapper

restart_gateway
observe_cli_build
observe_gateway_build
enforce_build_sha
log_openclaw_resolution

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
