# Build SHA stamp (CLI + gateway) + autoupdate verification

- UTC: 20260222T042952Z
- Repo: /tmp/wt_merge_main

## Baseline
```
Sun Feb 22 04:29:52 UTC 2026
## codex/feat/userprefix-openclaw-gateway-20260222...origin/codex/feat/userprefix-openclaw-gateway-20260222
?? workspace/audit/runtime_build_sha_stamp_20260222T042952Z.md
b624896e94de03c5216ee692fac8a2e3209f044c
/home/jeebs/.local/bin/openclaw
2026.2.19-2
```

## Phase 0 — Version source findings
```
Sun Feb 22 04:47:48 UTC 2026
$ rg -n "2026\\.2\\.19-2" -S .

$ package.json excerpt
{
  "name": "openclaw",
  "private": true,
  "version": "0.0.0",
  "scripts": {
    "test": "node scripts/run_tests.js",
    "governance:heartbeat": "sh workspace/scripts/sync_heartbeat.sh",
    "gate:module-resolution": "node scripts/module_resolution_gate.js --json",
    "redact:audit-evidence": "node scripts/redact_audit_evidence.js",
    "check:redaction-fixtures": "node scripts/redact_audit_evidence.js --in fixtures/redaction/in --out .tmp/redaction_out --json --dry-run",
    "lint:legacy-node-names": "node scripts/lint_legacy_node_names.js",
    "system2:snapshot": "node scripts/system2_snapshot_capture.js",
    "system2:evidence": "node scripts/system2_evidence_bundle.js",
    "system2:diff": "node scripts/system2_snapshot_diff.js",
    "system2:experiment": "node scripts/system2_experiment.js",
    "system2:experiment:auth": "npm run system2:experiment -- --fail-on log_signature_counts.auth_error",
    "secrets": "node scripts/openclaw_secrets_cli.js"
  }
}
```

Finding: package.json version is 0.0.0; reported openclaw version 2026.2.19-2 is sourced elsewhere in runtime/CLI code or installed artifacts.

## Phase 1 — Branch
```
Sun Feb 22 04:47:54 UTC 2026
/tmp/wt_merge_main
codex/feat/build-sha-stamp-20260222
6b967909c0001772505eb3fe8fffebc47776338f
## codex/feat/build-sha-stamp-20260222
?? workspace/audit/runtime_build_sha_stamp_20260222T042952Z.md
```

## Phase 2 — Build stamp implementation
```
Sun Feb 22 04:57:28 UTC 2026
Added scripts:
-rwxrwxr-x 1 jeebs jeebs  857 Feb 22 14:52 workspace/scripts/gen_build_stamp.sh
-rwxrwxr-x 1 jeebs jeebs 1412 Feb 22 14:52 workspace/scripts/openclaw_build_wrapper.sh

Wrapper source marker:
#!/usr/bin/env bash
set -euo pipefail

# OPENCLAW_BUILD_STAMP_WRAPPER=1
REAL_BIN="${OPENCLAW_REAL_BIN:-$HOME/.local/bin/openclaw.real}"
STAMP_FILE="${OPENCLAW_BUILD_STAMP_FILE:-$HOME/.local/share/openclaw-build/version_build.json}"

stamp_field() {
  local key="$1"
  if [[ ! -f "$STAMP_FILE" ]]; then
    return 0
  fi
  if ! command -v node >/dev/null 2>&1; then
    return 0
  fi
  node -e 'const fs=require("fs"); const p=process.argv[1]; const k=process.argv[2]; try { const o=JSON.parse(fs.readFileSync(p,"utf8")); const v=Object.prototype.hasOwnProperty.call(o,k) ? String(o[k]) : ""; process.stdout.write(v); } catch {}' "$STAMP_FILE" "$key"
}

build_sha="$(stamp_field build_sha)"
build_time="$(stamp_field build_time_utc)"
```

Implementation note: OpenClaw core source is not present in this repo; build stamp emission is added at the repo-controlled wrapper + autoupdate layer.

## Phase 3 — Autoupdate SHA verification behavior
```
14:allow_sha_mismatch="${OPENCLAW_AUTOUPDATE_ALLOW_SHA_MISMATCH:-0}"
43:expected_sha="$new_sha"
44:observed_cli_sha=""
46:observed_gateway_sha=""
199:    log_action "planned:gen_build_stamp:bash workspace/scripts/gen_build_stamp.sh"
203:  if [[ ! -x "$repo_root/workspace/scripts/gen_build_stamp.sh" ]]; then
204:    log_action "gen_build_stamp: missing workspace/scripts/gen_build_stamp.sh"
208:  run_cmd "gen_build_stamp" bash "$repo_root/workspace/scripts/gen_build_stamp.sh"
214:install_openclaw_wrapper() {
216:    log_action "planned:install_openclaw_wrapper:$wrapper_target"
221:    log_action "install_openclaw_wrapper: missing template $wrapper_template"
228:    log_action "install_openclaw_wrapper: openclaw missing"
241:  log_action "executed:install_openclaw_wrapper:$wrapper_target real=$wrapper_real"
244:observe_cli_build() {
252:  observed_cli_sha="$(printf '%s' "$version_line" | sed -n 's/.*build_sha=\([0-9a-fA-F]\{7,40\}\).*/\1/p')"
257:  if [[ -z "$observed_cli_sha" ]] && [[ -f "$build_stamp_user" ]] && command -v node >/dev/null 2>&1; then
258:    observed_cli_sha="$(json_field "$build_stamp_user" "build_sha")"
262:  log_action "observed:cli_build_sha:${observed_cli_sha:-missing}"
265:observe_gateway_build() {
273:  observed_gateway_sha="$(printf '%s' "$line" | sed -n 's/.*build_sha=\([0-9a-fA-F]\{7,40\}\).*/\1/p')"
276:  log_action "observed:gateway_build_sha:${observed_gateway_sha:-missing}"
280:enforce_build_sha() {
282:    log_action "planned:verify_build_sha:expected=$expected_sha"
290:  if [[ "$allow_sha_mismatch" == "1" ]]; then
294:  log_action "expected_sha:$expected_sha"
296:  if [[ -z "$observed_cli_sha" || "$observed_cli_sha" != "$expected_sha" ]]; then
299:  if [[ -z "$observed_gateway_sha" || "$observed_gateway_sha" != "$expected_sha" ]]; then
304:    log_action "verify_build_sha:mismatch expected=$expected_sha cli=${observed_cli_sha:-missing} gateway=${observed_gateway_sha:-missing}"
313:  log_action "verify_build_sha:match expected=$expected_sha"
358:    printf 'allow_sha_mismatch=%s\n' "$allow_sha_mismatch"
374:    printf 'expected_sha=%s\n' "$expected_sha"
375:    printf 'observed_cli_sha=%s\n' "${observed_cli_sha:-<none>}"
377:    printf 'observed_gateway_sha=%s\n' "${observed_gateway_sha:-<none>}"
472:install_openclaw_wrapper
475:observe_cli_build
476:observe_gateway_build
477:enforce_build_sha
```

## Phase 4 — Tests
```
$ bash -n workspace/scripts/openclaw_autoupdate.sh
$ bash -n workspace/scripts/verify_runtime_autoupdate.sh
$ bash workspace/scripts/verify_runtime_autoupdate.sh
ok: runtime autoupdate dry-run verified
$ python3 -m unittest tests_unittest.test_runtime_build_stamp -v
/tmp/tmplink_flc/version_build.json
```

## Phase 5 — Live evidence
```
$ openclaw --version
2026.2.19-2 build_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327 build_time=2026-02-22T04:54:48Z

$ journalctl --user -u openclaw-gateway.service -n 120 --no-pager | grep "openclaw_gateway build_sha=" | tail -n 1
Feb 22 14:54:48 jeebs-Z490-AORUS-MASTER openclaw[64067]: openclaw_gateway build_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327 version=0.0.0 build_time=2026-02-22T04:54:48Z

$ tail -n 40 workspace/audit/runtime_autoupdate.log
verify_outcome=dryrun
exit_code=0
---
[2026-02-22T04:22:57Z] openclaw_autoupdate
result=success
dry_run=0
force_run=0
old_sha=8be6a6d95eee3462263b8fa7de4029d69d4b6c6f
new_sha=d58a62595d74ac641a4766e73c6b44ca8d6ceea8
current_branch=codex/feat/userprefix-openclaw-gateway-20260222
target_branch=codex/feat/userprefix-openclaw-gateway-20260222
changed_files_count=1
changed_files=workspace/audit/runtime_autoupdate_merge_note_20260222T020520Z.md
quiesce_method=systemctl
commands=executed:branch_gate:target_branch_match,systemctl --user stop openclaw-gateway.service,executed:gateway_install:npm install -g . --prefix /home/jeebs/.local,executed:restart:systemctl --user start openclaw-gateway.service,observed:openclaw_path:/home/jeebs/.local/bin/openclaw,observed:openclaw_version:2026.2.19-2,verify: pass
verify_outcome=pass
exit_code=0
---
[2026-02-22T04:54:51Z] openclaw_autoupdate
result=success
dry_run=0
force_run=0
allow_sha_mismatch=0
old_sha=6b967909c0001772505eb3fe8fffebc47776338f
new_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327
current_branch=codex/feat/build-sha-stamp-20260222
target_branch=codex/feat/build-sha-stamp-20260222
changed_files_count=3
changed_files=workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md,workspace/scripts/openclaw_autoupdate.sh,workspace/scripts/verify_runtime_autoupdate.sh
quiesce_method=systemctl
sha_check_mode=observe
expected_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327
observed_cli_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327
observed_cli_version=2026.2.19-2
observed_gateway_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327
observed_gateway_version=0.0.0
commands=executed:branch_gate:target_branch_match,systemctl --user stop openclaw-gateway.service,executed:gen_build_stamp:bash /tmp/wt_merge_main/workspace/scripts/gen_build_stamp.sh,executed:publish_build_stamp:/tmp/wt_merge_main/workspace/version_build.json->/home/jeebs/.local/share/openclaw-build/version_build.json,executed:gateway_install:npm install -g . --prefix /home/jeebs/.local,executed:openclaw_real_init:/home/jeebs/.local/bin/openclaw.real from /home/jeebs/.local/bin/openclaw,executed:install_openclaw_wrapper:/home/jeebs/.local/bin/openclaw real=/home/jeebs/.local/bin/openclaw.real,executed:restart:systemctl --user start openclaw-gateway.service,observed:cli_version:2026.2.19-2,observed:cli_build_sha:ab59070a7ed5da428ef6a9c514e41a4e24664327,observed:gateway_build_sha:ab59070a7ed5da428ef6a9c514e41a4e24664327,observed:gateway_version:0.0.0,expected_sha:ab59070a7ed5da428ef6a9c514e41a4e24664327,verify_build_sha:match expected=ab59070a7ed5da428ef6a9c514e41a4e24664327,observed:openclaw_path:/home/jeebs/.local/bin/openclaw,observed:openclaw_version:2026.2.19-2 build_sha=ab59070a7ed5da428ef6a9c514e41a4e24664327 build_time=2026-02-22T04:54:48Z,verify: pass
verify_outcome=pass
exit_code=0
---
```
