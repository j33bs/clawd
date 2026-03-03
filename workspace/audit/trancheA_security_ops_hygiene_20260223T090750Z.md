# Tranche A - Security + Ops Hygiene (20260223T090750Z)

## Baseline
$ git rev-parse --abbrev-ref HEAD
main
$ git rev-parse HEAD
ee738372e846ecf671f041288c52e69936d10839
$ git status --porcelain -uall
 M workspace/scripts/nightly_build.sh
 M workspace/scripts/openclaw_autoupdate.sh
 M workspace/scripts/preflight_check.py
 M workspace/scripts/verify_nightly_health_config.sh
 M workspace/scripts/verify_runtime_autoupdate.sh
 M workspace/scripts/verify_security_config.sh
?? tests_unittest/test_openclaw_config_guard.py
?? tests_unittest/test_runtime_autoupdate_gate.py
?? tests_unittest/test_tmp_logrotate_dryrun.py
?? workspace/audit/trancheA_security_ops_hygiene_20260223T090750Z.md
?? workspace/config/logrotate/openclaw-tmp.conf
?? workspace/scripts/openclaw_config_guard.py
?? workspace/scripts/verify_openclaw_tmp_logrotate.sh
$ node -v
v22.22.0
$ python3 --version
Python 3.12.3

## Targeted Tests
$ python3 -m unittest -v tests_unittest.test_openclaw_config_guard tests_unittest.test_runtime_autoupdate_gate tests_unittest.test_tmp_logrotate_dryrun

$ bash workspace/scripts/verify_nightly_health_config.sh
[verify] valid-config path
FAIL: expected health to succeed with valid config
[2026-02-23 19:07:51] === System Health ===
[2026-02-23 19:07:51] OpenClaw config source: /tmp/wt_merge_main/workspace/config/openclaw.json
[2026-02-23 19:07:52] ⚠️ OpenClaw doctor returned non-zero during preflight (continuing; no config-invalid signature detected)
[2026-02-23 19:07:52]   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
[2026-02-23 19:07:52]   ██░▄▄▄░██░▄▄░██░▄▄▄██░▀██░██░▄▄▀██░████░▄▄▀██░███░██
[2026-02-23 19:07:52]   ██░███░██░▀▀░██░▄▄▄██░█░█░██░█████░████░▀▀░██░█░█░██
[2026-02-23 19:07:52]   ██░▀▀▀░██░█████░▀▀▀██░██▄░██░▀▀▄██░▀▀░█░██░██▄▀▄▀▄██
[2026-02-23 19:07:52]   ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
[2026-02-23 19:07:52]                     🦞 OPENCLAW 🦞                    
[2026-02-23 19:07:52]    
[2026-02-23 19:07:52]   ┌  OpenClaw doctor
[2026-02-23 19:07:52]   SystemError [ERR_SYSTEM_ERROR]: A system error occurred: uv_interface_addresses returned Unknown system error 1 (Unknown system error 1)
[2026-02-23 19:07:54] ⚠️ Gateway: Issues detected
[2026-02-23 19:07:54] ⚠️ Ollama: Not responding

## Retest (Tranche A acceptance set)
$ python3 -m unittest -v tests_unittest.test_openclaw_config_guard tests_unittest.test_runtime_autoupdate_gate tests_unittest.test_tmp_logrotate_dryrun

$ bash workspace/scripts/verify_security_config.sh
WARN: openclaw.json not found in repo; skipping repo-local node.id enforcement
FAIL: agents/main/agent/models.json: groq.enabled must be false
FAIL: agents/main/agent/models.json: groq.apiKey must be empty (no secrets)

## Note
verify_security_config.sh currently fails on pre-existing Groq policy in agents/main/agent/models.json (out of scope for Tranche A).

$ bash workspace/scripts/verify_runtime_autoupdate.sh
ok: runtime autoupdate dry-run verified

$ bash workspace/scripts/verify_openclaw_tmp_logrotate.sh
PASS: openclaw tmp logrotate dry-run

$ OPENCLAW_AUTOUPDATE_DRYRUN=1 OPENCLAW_AUTOUPDATE_TARGET_BRANCH=$(git rev-parse --abbrev-ref HEAD) bash workspace/scripts/openclaw_autoupdate.sh

$ tail -n 30 workspace/audit/runtime_autoupdate.log
[2026-02-23T09:08:45Z] openclaw_autoupdate
result=success
dry_run=1
force_run=0
old_sha=<none>
new_sha=ee738372e846ecf671f041288c52e69936d10839
current_branch=codex/feat/tranche-a-20260223
target_branch=codex/feat/tranche-a-20260223
changed_files_count=1
changed_files=<state_bootstrap>
quiesce_method=planned
commands=planned:branch_gate:bypass_dry_run,planned:health_gate:pre:python3 /tmp/wt_merge_main/workspace/scripts/openclaw_config_guard.py --strict,planned:quiesce:systemctl --user stop openclaw-gateway.service (or pid_fallback),planned:deps:npm ci,planned:gateway_install:openclaw gateway install --force,planned:restart:systemctl --user start openclaw-gateway.service (if systemctl path),planned:verify:bash workspace/scripts/verify_policy_router.sh,planned:health_gate:post:python3 /tmp/wt_merge_main/workspace/scripts/openclaw_config_guard.py --strict
verify_outcome=dryrun
exit_code=0
---

$ python3 -m py_compile workspace/scripts/openclaw_config_guard.py workspace/scripts/preflight_check.py
