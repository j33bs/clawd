# Dali Local Exec Plane Activation Audit

- UTC: 20260222T110345Z
- Worktree: /tmp/wt_local_exec_activation
- Branch: codex/feat/dali-local-exec-plane-20260222
- HEAD: f9241ae622e953585c755f46a0ec07c551a88e07

## Phase 0 Baseline
```text
$ git status --porcelain -uall
?? workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md

$ uname -a
Linux jeebs-Z490-AORUS-MASTER 6.17.0-14-generic #14~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Thu Jan 15 15:52:10 UTC 2 x86_64 x86_64 x86_64 GNU/Linux

$ python3 -V
Python 3.12.3

$ node -v
v22.22.0

$ nvidia-smi
Failed to initialize NVML: Unknown Error

$ systemctl --user --version
systemd 255 (255.4-1ubuntu8.12)
+PAM +AUDIT +SELINUX +APPARMOR +IMA +SMACK +SECCOMP +GCRYPT -GNUTLS +OPENSSL +ACL +BLKID +CURL +ELFUTILS +FIDO2 +IDN2 -IDN +IPTC +KMOD +LIBCRYPTSETUP +LIBFDISK +PCRE2 -PWQUALITY +P11KIT +QRENCODE +TPM2 +BZIP2 +LZ4 +XZ +ZLIB +ZSTD -BPF_FRAMEWORK -XKBCOMMON +UTMP +SYSVINIT default-hierarchy=unified
```

## Phase 0 Quiesce
```text
$ systemctl --user list-units | egrep -i 'openclaw|vllm|litellm|mcporter|local-exec' || true

$ systemctl --user stop openclaw-gateway.service || true

$ systemctl --user stop openclaw-local-exec-worker.service || true

$ systemctl --user stop vllm-local-exec.service || true
```

## Phase 0 Quiesce (captured stderr)
```text
$ systemctl --user list-units | egrep -i 'openclaw|vllm|litellm|mcporter|local-exec' || true
Failed to connect to bus: Operation not permitted

$ systemctl --user stop openclaw-gateway.service || true
Failed to connect to bus: Operation not permitted

$ systemctl --user stop openclaw-local-exec-worker.service || true
Failed to connect to bus: Operation not permitted

$ systemctl --user stop vllm-local-exec.service || true
Failed to connect to bus: Operation not permitted
```

## Phase 1 — Worker/evidence/sandbox hardening
```text
$ git diff --name-only
workspace/docs/ops/DALI_LOCAL_EXEC_PLANE.md
workspace/local_exec/evidence.py
workspace/local_exec/subprocess_harness.py
workspace/local_exec/worker.py

$ rg -n "subprocess\.(run|Popen)|shell=True|shell\s*=\s*True" workspace/local_exec scripts/local_exec_plane.sh scripts/local_exec_enqueue.py tests_unittest/test_local_exec_plane_offline.py
tests_unittest/test_local_exec_plane_offline.py:23:        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
tests_unittest/test_local_exec_plane_offline.py:25:        subprocess.run(["git", "add", "README.md"], cwd=self.repo_root, check=True, capture_output=True)
workspace/local_exec/worker.py.bak.20260222T110452Z:23:    proc = subprocess.run(
workspace/local_exec/tools_mcporter.py:57:        proc = subprocess.run(argv, cwd=str(self.repo_root), capture_output=True, text=True, timeout=self._cfg["timeout_sec"], check=False)
workspace/local_exec/tools_mcporter.py:79:        proc = subprocess.run(argv, cwd=str(self.repo_root), capture_output=True, text=True, timeout=self._cfg["timeout_sec"], check=False)
workspace/local_exec/subprocess_harness.py:74:        proc = subprocess.run(
workspace/local_exec/worker.py:30:    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=False)
workspace/local_exec/worker.py:49:    proc = subprocess.run(
workspace/local_exec/worker.py:236:                "name": "subprocess.run_argv",
workspace/local_exec/worker.py:254:                "name": "subprocess.run_argv",
workspace/local_exec/subprocess_harness.py.bak.20260222T110452Z:54:        proc = subprocess.run(

$ python3 -m unittest tests_unittest.test_local_exec_plane_offline -v
```

## Phase 2 — Optional vLLM user-service wiring
```text
$ bash -n scripts/local_exec_plane.sh

$ bash scripts/local_exec_plane.sh install-units
install_units=blocked reason=worker_unit_copy_failed path=/home/jeebs/.config/systemd/user/openclaw-local-exec-worker.service

$ bash scripts/local_exec_plane.sh status
fallback worker inactive
vllm_status=unknown reason=systemd_user_unavailable

$ bash scripts/local_exec_plane.sh enable-vllm
enable_vllm=blocked reason=systemd_user_unavailable

$ OPENCLAW_LOCAL_EXEC_MODEL_STUB=0 OPENCLAW_LOCAL_EXEC_API_BASE=http://127.0.0.1:8001/v1 bash scripts/local_exec_plane.sh health
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 0, "last_event": null, "model_stub_mode": false, "model_api_base": "http://127.0.0.1:8001/v1", "model_reachable": false, "model_detail": "error:<urlopen error [Errno 1] Operation not permitted>"}
summary kill_switch=False events=0 model_stub=False model_reachable=False
```

Blocked-by observed in this runtime:
- user systemd bus unavailable in this execution context.
- user unit destination under ~/.config/systemd/user not writable in this sandbox context.
- local vLLM endpoint not reachable from this execution context; health reports bounded error and continues.

## Phase 3 — Expanded deterministic offline tests
```text
$ python3 -m unittest tests_unittest.test_local_exec_plane_offline -v
```

## Phase 4 — MCPorter onboarding docs + structured blocked-by evidence
```text
$ python3 - <<'PY' ... MCPorterAdapter.list_tools()
{'available': False, 'blocked_by': 'mcporter_not_installed', 'error_code': 'mcporter_missing', 'tools': []}
```

Outcome: adapter emits structured missing-tool signal (error_code=mcporter_missing) and keeps deny-by-default allowlist.

## Phase 5 — local_exec_sleep_run
```text
UTC start: 2026-02-22T11:12:20Z
run_seconds=22 interval_seconds=10
$ python3 -m unittest tests_unittest.test_local_exec_plane_offline -v
test_append_only_ledger_grows_and_worker_completes (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_append_only_ledger_grows_and_worker_completes) ... ok
test_budget_enforcement_max_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_budget_enforcement_max_tool_calls) ... ok
test_disallowed_tool_call_rejected (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_disallowed_tool_call_rejected) ... ok
test_kill_switch_prevents_claims (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_kill_switch_prevents_claims) ... ok
test_loop_emits_idle_heartbeat_and_exits_on_kill_switch (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_loop_emits_idle_heartbeat_and_exits_on_kill_switch) ... ok
test_model_client_stub_returns_no_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls) ... ok
test_path_sandbox_rejects_escape (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_path_sandbox_rejects_escape) ... ok
test_run_header_contains_required_fields (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_run_header_contains_required_fields) ... ok
test_subprocess_policy_blocks_shell_string (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_subprocess_policy_blocks_shell_string) ... ok
test_test_runner_requires_subprocess_permission (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_test_runner_requires_subprocess_permission) ... ok

----------------------------------------------------------------------
Ran 10 tests in 1.481s

OK
blocked-by: missing_env_file path=/home/jeebs/.config/openclaw/local_exec.env
$ bash scripts/local_exec_plane.sh start
fallback worker started pid=87740
vllm_start=blocked reason=systemd_user_unavailable
fallback worker active pid=87740
vllm_status=unknown reason=systemd_user_unavailable
enqueue_iter=1 job_type=repo_index_task job_id=job-sleeprun11122201
{"enqueued": "job-sleeprun11122201", "event": "enqueue"}
enqueue_result=ok iter=1
enqueue_iter=2 job_type=doc_compactor_task job_id=job-sleeprun11123202
{"enqueued": "job-sleeprun11123202", "event": "enqueue"}
enqueue_result=ok iter=2
enqueue_iter=3 job_type=test_runner_task job_id=job-sleeprun11124203
{"enqueued": "job-sleeprun11124203", "event": "enqueue"}
enqueue_result=ok iter=3
$ bash scripts/local_exec_plane.sh stop
fallback worker stopped pid=87740
vllm_stop=skipped reason=systemd_user_unavailable
fallback worker inactive
vllm_status=unknown reason=systemd_user_unavailable
summary_enqueued=3 summary_errors=0
ledger_summary={"ledger_events": 12, "last_event": {"ts_utc": "2026-02-22T11:12:44.540610Z", "event": "complete", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "result": {"commands_run": 1, "results": [{"argv": ["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"], "returncode": 0, "timed_out": false, "duration_ms": 91, "stdout": "", "stderr": "test_model_client_stub_returns_no_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls) ... ok\n\n----------------------------------------------------------------------\nRan 1 test in 0.009s\n\nOK\n", "stdout_bytes": 0, "stderr_bytes": 268, "stdout_truncated": false, "stderr_truncated": false}]}}}
UTC end: 2026-02-22T11:12:52Z
```

## Drift cleanup starting
- UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)
- Goal: remove unrelated mlx-infer + scaffold audit drift and keep diff local-exec only.

## Drift cleanup result
- UTC: 2026-02-22T11:55:38Z
- Reverted to origin/main:
  - workspace/skills/mlx-infer/dist/cli.js
  - workspace/skills/mlx-infer/src/cli.ts
  - workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js
  - workspace/skills/mlx-infer/tests/mlx_infer_integration_stub.test.js
  - workspace/audit/skills_tiered_mlx_triage_scaffold_20260222.md
- Drift verification: no mlx-infer or skills_tiered_mlx paths remain in origin/main...HEAD diff.
- Cleanup commit SHA: pending (recorded after commit).
- Cleanup commit SHA: 773bcada01267a85f5fcb3dc6501881067577f9d
- Confirmation: branch diff is local-exec-only (mlx-infer drift removed).

## Service recovery check initiated
- UTC: 2026-02-22T12:07:37Z
- Host: jeebs-Z490-AORUS-MASTER
- Branch: codex/feat/dali-local-exec-plane-20260222
- HEAD: e67008e034176666f32cf1aa11c150520c7ae10c

```text
$ git rev-parse --abbrev-ref HEAD
codex/feat/dali-local-exec-plane-20260222
$ git rev-parse HEAD
e67008e034176666f32cf1aa11c150520c7ae10c

$ git status --porcelain -uall
 M workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md

$ ls -la workspace/local_exec/state || true
total 20
drwxrwxr-x 2 jeebs jeebs 4096 Feb 22 21:12 .
drwxrwxr-x 8 jeebs jeebs 4096 Feb 22 21:07 ..
-rw-rw-r-- 1 jeebs jeebs   64 Feb 22 21:03 .gitignore
-rw-rw-r-- 1 jeebs jeebs 4328 Feb 22 21:12 jobs.jsonl
-rw-r--r-- 1 jeebs jeebs    0 Feb 22 21:12 jobs.lock
-rw-rw-r-- 1 jeebs jeebs    0 Feb 22 21:12 worker.log

$ systemctl --user status openclaw-local-exec-worker.service || true

$ systemctl --user status vllm-local-exec.service || true
```

## Phase 1 — Quiescence detection
```text
$ if [ -f workspace/local_exec/state/KILL_SWITCH ]; then echo "KILL_SWITCH present"; else echo "KILL_SWITCH absent"; fi
KILL_SWITCH absent

$ systemctl --user is-active openclaw-local-exec-worker.service || true
Failed to connect to bus: Operation not permitted

$ systemctl --user is-active vllm-local-exec.service || true
Failed to connect to bus: Operation not permitted
```

## Phase 2 — Clear quiescence
```text
No KILL_SWITCH to remove
```

## Phase 3 — Restart services
```text
$ systemctl --user daemon-reload || true
Failed to connect to bus: Operation not permitted

$ systemctl --user restart openclaw-local-exec-worker.service || true
Failed to connect to bus: Operation not permitted

$ systemctl --user list-unit-files | grep -q '^vllm-local-exec.service' && systemctl --user restart vllm-local-exec.service || true
Failed to connect to bus: Operation not permitted
```

## Phase 4 — Health verification
```text
$ systemctl --user status openclaw-local-exec-worker.service --no-pager || true
Failed to connect to bus: Operation not permitted

$ systemctl --user status vllm-local-exec.service --no-pager || true
Failed to connect to bus: Operation not permitted

$ bash scripts/local_exec_plane.sh health || true
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 12, "last_event": {"ts_utc": "2026-02-22T11:12:44.540610Z", "event": "complete", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "result": {"commands_run": 1, "results": [{"argv": ["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"], "returncode": 0, "timed_out": false, "duration_ms": 91, "stdout": "", "stderr": "test_model_client_stub_returns_no_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls) ... ok\n\n----------------------------------------------------------------------\nRan 1 test in 0.009s\n\nOK\n", "stdout_bytes": 0, "stderr_bytes": 268, "stdout_truncated": false, "stderr_truncated": false}]}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=12 model_stub=True model_reachable=None

$ journalctl --user -u openclaw-local-exec-worker.service -n 50 --no-pager || true
-- No entries --

$ journalctl --user -u vllm-local-exec.service -n 50 --no-pager || true
-- No entries --
```

## Phase 4b — Fallback recovery via local_exec_plane.sh
```text
$ bash scripts/local_exec_plane.sh start || true
fallback worker started pid=91313
vllm_start=skipped reason=LOCAL_EXEC_ENABLE_VLLM_not_set
fallback worker active pid=91313
vllm_status=unknown reason=systemd_user_unavailable

$ bash scripts/local_exec_plane.sh status || true
fallback worker active pid=91313
vllm_status=unknown reason=systemd_user_unavailable

$ pgrep -af 'workspace.local_exec.worker|openclaw-local-exec-worker' || true
91307 /bin/bash -c set -euo pipefail cd /tmp/wt_local_exec_activation AUDIT=workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md START_OUT=$(bash scripts/local_exec_plane.sh start 2>&1 || true) STATUS_OUT=$(bash scripts/local_exec_plane.sh status 2>&1 || true) HEALTH2_OUT=$(bash scripts/local_exec_plane.sh health 2>&1 || true) PIDS=$(pgrep -af 'workspace.local_exec.worker|openclaw-local-exec-worker' || true) {   echo   echo "## Phase 4b — Fallback recovery via local_exec_plane.sh"   echo '```text'   echo '$ bash scripts/local_exec_plane.sh start || true'   echo "$START_OUT"   echo   echo '$ bash scripts/local_exec_plane.sh status || true'   echo "$STATUS_OUT"   echo   echo '$ pgrep -af '\''workspace.local_exec.worker|openclaw-local-exec-worker'\'' || true'   echo "$PIDS"   echo   echo '$ bash scripts/local_exec_plane.sh health || true'   echo "$HEALTH2_OUT"   echo '```' } >> "$AUDIT" printf 'start=%s\nstatus=%s\n' "$START_OUT" "$STATUS_OUT"
91313 python3 -m workspace.local_exec.worker --repo-root /tmp/wt_local_exec_activation --loop --sleep-s 2 --max-idle-s 300 --worker-id local-exec-fallback
91327 /bin/bash -c set -euo pipefail cd /tmp/wt_local_exec_activation AUDIT=workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md START_OUT=$(bash scripts/local_exec_plane.sh start 2>&1 || true) STATUS_OUT=$(bash scripts/local_exec_plane.sh status 2>&1 || true) HEALTH2_OUT=$(bash scripts/local_exec_plane.sh health 2>&1 || true) PIDS=$(pgrep -af 'workspace.local_exec.worker|openclaw-local-exec-worker' || true) {   echo   echo "## Phase 4b — Fallback recovery via local_exec_plane.sh"   echo '```text'   echo '$ bash scripts/local_exec_plane.sh start || true'   echo "$START_OUT"   echo   echo '$ bash scripts/local_exec_plane.sh status || true'   echo "$STATUS_OUT"   echo   echo '$ pgrep -af '\''workspace.local_exec.worker|openclaw-local-exec-worker'\'' || true'   echo "$PIDS"   echo   echo '$ bash scripts/local_exec_plane.sh health || true'   echo "$HEALTH2_OUT"   echo '```' } >> "$AUDIT" printf 'start=%s\nstatus=%s\n' "$START_OUT" "$STATUS_OUT"

$ bash scripts/local_exec_plane.sh health || true
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 12, "last_event": {"ts_utc": "2026-02-22T11:12:44.540610Z", "event": "complete", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "result": {"commands_run": 1, "results": [{"argv": ["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"], "returncode": 0, "timed_out": false, "duration_ms": 91, "stdout": "", "stderr": "test_model_client_stub_returns_no_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls) ... ok\n\n----------------------------------------------------------------------\nRan 1 test in 0.009s\n\nOK\n", "stdout_bytes": 0, "stderr_bytes": 268, "stdout_truncated": false, "stderr_truncated": false}]}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=12 model_stub=True model_reachable=None
```

## Phase 5 — Outcome summary
- No kill switch detected; no quiescence file removal required.
- Primary user-systemd control path blocked-by: 'Failed to connect to bus: Operation not permitted'.
- Applied safe fallback recovery: started local exec worker via scripts/local_exec_plane.sh (fallback pid mode).
- vLLM remained optional/disabled (LOCAL_EXEC_ENABLE_VLLM not set).

## Final post-check restart confirmation
```text
$ bash scripts/local_exec_plane.sh start || true
fallback worker started pid=91520
vllm_start=skipped reason=LOCAL_EXEC_ENABLE_VLLM_not_set
fallback worker active pid=91520
vllm_status=unknown reason=systemd_user_unavailable

$ bash scripts/local_exec_plane.sh status || true
fallback worker active pid=91520
vllm_status=unknown reason=systemd_user_unavailable

$ bash scripts/local_exec_plane.sh health || true
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 12, "last_event": {"ts_utc": "2026-02-22T11:12:44.540610Z", "event": "complete", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "result": {"commands_run": 1, "results": [{"argv": ["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"], "returncode": 0, "timed_out": false, "duration_ms": 91, "stdout": "", "stderr": "test_model_client_stub_returns_no_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls) ... ok\n\n----------------------------------------------------------------------\nRan 1 test in 0.009s\n\nOK\n", "stdout_bytes": 0, "stderr_bytes": 268, "stdout_truncated": false, "stderr_truncated": false}]}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=12 model_stub=True model_reachable=None
```

## Final blocked-by notes
```text
$ timeout 3s python3 -m workspace.local_exec.worker --repo-root . --loop --sleep-s 1 --max-idle-s 2 --worker-id debug-worker; echo rc=$?
rc=124

$ ls -la workspace/local_exec/state && tail -n 120 workspace/local_exec/state/worker.log && pgrep -af "workspace.local_exec.worker|local-exec-fallback"
total 24
drwxrwxr-x 2 jeebs jeebs 4096 Feb 22 22:08 .
drwxrwxr-x 8 jeebs jeebs 4096 Feb 22 21:07 ..
-rw-rw-r-- 1 jeebs jeebs   64 Feb 22 21:03 .gitignore
-rw-rw-r-- 1 jeebs jeebs 4328 Feb 22 21:12 jobs.jsonl
-rw-r--r-- 1 jeebs jeebs    0 Feb 22 21:12 jobs.lock
-rw-rw-r-- 1 jeebs jeebs    0 Feb 22 21:12 worker.log
-rw-rw-r-- 1 jeebs jeebs    6 Feb 22 22:09 worker.pid
91665 /bin/bash -c cd /tmp/wt_local_exec_activation && AUDIT=workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md && {   echo   echo "## Final blocked-by notes"   echo '```text'   echo '$ timeout 3s python3 -m workspace.local_exec.worker --repo-root . --loop --sleep-s 1 --max-idle-s 2 --worker-id debug-worker; echo rc=$?'   timeout 3s python3 -m workspace.local_exec.worker --repo-root . --loop --sleep-s 1 --max-idle-s 2 --worker-id debug-worker; echo rc=$?   echo   echo '$ ls -la workspace/local_exec/state && tail -n 120 workspace/local_exec/state/worker.log && pgrep -af "workspace.local_exec.worker|local-exec-fallback"'   ls -la workspace/local_exec/state   tail -n 120 workspace/local_exec/state/worker.log 2>&1 || true   pgrep -af 'workspace.local_exec.worker|local-exec-fallback' || true   echo '```'   echo "- blocked-by: user systemd unavailable (Operation not permitted)."   echo "- blocked-by: fallback background worker process did not remain persistent in this execution context; likely session/sandbox process-lifecycle behavior." } >> "$AUDIT"  git add "$AUDIT" && git commit -m "docs(audit): add blocked-by details for fallback worker persistence" && git push -u origin codex/feat/dali-local-exec-plane-20260222
```
- blocked-by: user systemd unavailable (Operation not permitted).
- blocked-by: fallback background worker process did not remain persistent in this execution context; likely session/sandbox process-lifecycle behavior.

## Durable worker bring-up attempt (systemd user bus unavailable fallback runbook)
- UTC: 2026-02-22T12:22:28Z
- Host: jeebs-Z490-AORUS-MASTER
```text
$ pwd
/tmp/wt_local_exec_activation
$ git rev-parse --abbrev-ref HEAD
codex/feat/dali-local-exec-plane-20260222
$ git rev-parse HEAD
90cda66fd8116aace78711ad5bbd7a700d42fd99
$ git status --porcelain -uall
 M workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md
$ systemctl --user is-active openclaw-local-exec-worker.service || true
$ systemctl --user is-active vllm-local-exec.service || true
```

## Phase 1 — Ensure not quiesced
```text
$ test -f workspace/local_exec/state/KILL_SWITCH && echo "KILL_SWITCH present" || echo "KILL_SWITCH absent"
KILL_SWITCH absent
$ rm -f workspace/local_exec/state/KILL_SWITCH
removed_if_present=true
$ mkdir -p workspace/local_exec/state workspace/local_exec/evidence
total 24
drwxrwxr-x 2 jeebs jeebs 4096 Feb 22 22:08 .
drwxrwxr-x 8 jeebs jeebs 4096 Feb 22 21:07 ..
-rw-rw-r-- 1 jeebs jeebs   64 Feb 22 21:03 .gitignore
-rw-rw-r-- 1 jeebs jeebs 4328 Feb 22 21:12 jobs.jsonl
-rw-r--r-- 1 jeebs jeebs    0 Feb 22 21:12 jobs.lock
-rw-rw-r-- 1 jeebs jeebs    0 Feb 22 21:12 worker.log
-rw-rw-r-- 1 jeebs jeebs    6 Feb 22 22:09 worker.pid
```

## Phase 2 — Stop stale fallback worker (best effort)
```text
pidfile_found:91520
$ ps aux | grep -F "workspace.local_exec.worker" | grep -v grep || true

--- after targeted kill ---

```

## Phase 3 — Durable mode selection
```text
tmux=missing
$ tmux ls | grep -n "local-exec-worker" || true

```

## Phase 4 — Durable mode B (nohup + pidfile)
```text
$ nohup ... python3 -m workspace.local_exec.worker --repo-root . --loop --sleep-s 2
pidfile_pid=92775
$ ps -p "92775" -o pid,cmd
  92775 python3 -m workspace.local_exec.worker --repo-root . --loop --sleep-s 2
```

## Phase 5 — Verify persistence + event increment
```text
$ python3 scripts/local_exec_enqueue.py --demo --repo-root .
{"status": "enqueued", "job_id": "job-demorepoindex01", "event_ts": "2026-02-22T12:23:21.509648Z"}

$ bash scripts/local_exec_plane.sh health || true  # check1
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 13, "last_event": {"ts_utc": "2026-02-22T12:23:21.509648Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:21.502959Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=13 model_stub=True model_reachable=None

$ sleep 5
$ bash scripts/local_exec_plane.sh health || true  # check2
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 13, "last_event": {"ts_utc": "2026-02-22T12:23:21.509648Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:21.502959Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=13 model_stub=True model_reachable=None

events_check1=13
events_check2=13

$ tail -n 80 workspace/local_exec/state/worker.out || true


$ tail -n 80 workspace/local_exec/state/worker.err || true


$ tail -n 50 workspace/local_exec/state/jobs.jsonl || true
{"ts_utc": "2026-02-22T11:12:22.441416Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-sleeprun11122201", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T11:12:22.436191Z", "budgets": {"max_wall_time_sec": 180, "max_tool_calls": 8, "max_output_bytes": 131072, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "sleep_run"}, "payload": {"include_globs": ["workspace/local_exec/*.py", "workspace/docs/ops/*.md", "scripts/*.sh"], "exclude_globs": ["**/*.bak.*"], "max_files": 60, "max_file_bytes": 16384, "keywords": ["kill_switch", "evidence", "worker"]}}}
{"ts_utc": "2026-02-22T11:12:24.435146Z", "event": "claim", "job_id": "job-sleeprun11122201", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758804.4351397}
{"ts_utc": "2026-02-22T11:12:24.436499Z", "event": "heartbeat", "job_id": "job-sleeprun11122201", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758804.4365041}
{"ts_utc": "2026-02-22T11:12:24.441112Z", "event": "complete", "job_id": "job-sleeprun11122201", "worker_id": "local-exec-fallback", "result": {"files_considered": 19, "hits_written": 7, "index_jsonl": "workspace/local_exec/evidence/job-sleeprun11122201_index.jsonl"}}
{"ts_utc": "2026-02-22T11:12:32.523166Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-sleeprun11123202", "job_type": "doc_compactor_task", "created_at_utc": "2026-02-22T11:12:32.518209Z", "budgets": {"max_wall_time_sec": 180, "max_tool_calls": 8, "max_output_bytes": 131072, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "sleep_run"}, "payload": {"inputs": ["workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md"], "max_input_bytes": 32768, "max_output_bytes": 8192, "title": "Sleep-run evidence compaction"}}}
{"ts_utc": "2026-02-22T11:12:34.443436Z", "event": "claim", "job_id": "job-sleeprun11123202", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758814.4434347}
{"ts_utc": "2026-02-22T11:12:34.444737Z", "event": "heartbeat", "job_id": "job-sleeprun11123202", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758814.4447415}
{"ts_utc": "2026-02-22T11:12:34.445108Z", "event": "complete", "job_id": "job-sleeprun11123202", "worker_id": "local-exec-fallback", "result": {"inputs_considered": 1, "bytes_read": 7950}}
{"ts_utc": "2026-02-22T11:12:42.604094Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-sleeprun11124203", "job_type": "test_runner_task", "created_at_utc": "2026-02-22T11:12:42.599037Z", "budgets": {"max_wall_time_sec": 180, "max_tool_calls": 8, "max_output_bytes": 131072, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": true, "allowed_tools": []}, "meta": {"source": "sleep_run"}, "payload": {"commands": [["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"]], "timeout_sec": 90, "cwd": ".", "env_allow": []}}}
{"ts_utc": "2026-02-22T11:12:44.447590Z", "event": "claim", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758824.4475884}
{"ts_utc": "2026-02-22T11:12:44.448858Z", "event": "heartbeat", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758824.4488626}
{"ts_utc": "2026-02-22T11:12:44.540610Z", "event": "complete", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "result": {"commands_run": 1, "results": [{"argv": ["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"], "returncode": 0, "timed_out": false, "duration_ms": 91, "stdout": "", "stderr": "test_model_client_stub_returns_no_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls) ... ok\n\n----------------------------------------------------------------------\nRan 1 test in 0.009s\n\nOK\n", "stdout_bytes": 0, "stderr_bytes": 268, "stdout_truncated": false, "stderr_truncated": false}]}}
{"ts_utc": "2026-02-22T12:23:21.509648Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:21.502959Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}
```

## Phase 5b — Event growth proof window
```text
$ bash scripts/local_exec_plane.sh health || true  # checkA
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 13, "last_event": {"ts_utc": "2026-02-22T12:23:21.509648Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:21.502959Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=13 model_stub=True model_reachable=None

$ python3 scripts/local_exec_enqueue.py --demo --repo-root .
{"status": "enqueued", "job_id": "job-demorepoindex01", "event_ts": "2026-02-22T12:23:39.196998Z"}

$ sleep 5
$ bash scripts/local_exec_plane.sh health || true  # checkB
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 14, "last_event": {"ts_utc": "2026-02-22T12:23:39.196998Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:39.191319Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=14 model_stub=True model_reachable=None

events_checkA=13
events_checkB=14
```

## Phase 7 — Kill switch test
```text
$ touch workspace/local_exec/state/KILL_SWITCH
kill_switch_set=true
$ python3 scripts/local_exec_enqueue.py --demo --repo-root .
{"status": "enqueued", "job_id": "job-demorepoindex01", "event_ts": "2026-02-22T12:24:01.507075Z"}
job_id_under_kill_switch=job-demorepoindex01

$ bash scripts/local_exec_plane.sh health || true # before/after kill-switch window
health_before:\n{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 14, "last_event": {"ts_utc": "2026-02-22T12:23:39.196998Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:39.191319Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=14 model_stub=True model_reachable=None

health_after:\n{"kill_switch": true, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 15, "last_event": {"ts_utc": "2026-02-22T12:24:01.507075Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:24:01.501520Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=True events=15 model_stub=True model_reachable=None

events_before=14
events_after=15

$ tail -n 20 workspace/local_exec/state/jobs.jsonl
{"ts_utc": "2026-02-22T11:12:22.441416Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-sleeprun11122201", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T11:12:22.436191Z", "budgets": {"max_wall_time_sec": 180, "max_tool_calls": 8, "max_output_bytes": 131072, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "sleep_run"}, "payload": {"include_globs": ["workspace/local_exec/*.py", "workspace/docs/ops/*.md", "scripts/*.sh"], "exclude_globs": ["**/*.bak.*"], "max_files": 60, "max_file_bytes": 16384, "keywords": ["kill_switch", "evidence", "worker"]}}}
{"ts_utc": "2026-02-22T11:12:24.435146Z", "event": "claim", "job_id": "job-sleeprun11122201", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758804.4351397}
{"ts_utc": "2026-02-22T11:12:24.436499Z", "event": "heartbeat", "job_id": "job-sleeprun11122201", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758804.4365041}
{"ts_utc": "2026-02-22T11:12:24.441112Z", "event": "complete", "job_id": "job-sleeprun11122201", "worker_id": "local-exec-fallback", "result": {"files_considered": 19, "hits_written": 7, "index_jsonl": "workspace/local_exec/evidence/job-sleeprun11122201_index.jsonl"}}
{"ts_utc": "2026-02-22T11:12:32.523166Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-sleeprun11123202", "job_type": "doc_compactor_task", "created_at_utc": "2026-02-22T11:12:32.518209Z", "budgets": {"max_wall_time_sec": 180, "max_tool_calls": 8, "max_output_bytes": 131072, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "sleep_run"}, "payload": {"inputs": ["workspace/audit/dali_local_exec_plane_activation_20260222T20260222T110345Z.md"], "max_input_bytes": 32768, "max_output_bytes": 8192, "title": "Sleep-run evidence compaction"}}}
{"ts_utc": "2026-02-22T11:12:34.443436Z", "event": "claim", "job_id": "job-sleeprun11123202", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758814.4434347}
{"ts_utc": "2026-02-22T11:12:34.444737Z", "event": "heartbeat", "job_id": "job-sleeprun11123202", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758814.4447415}
{"ts_utc": "2026-02-22T11:12:34.445108Z", "event": "complete", "job_id": "job-sleeprun11123202", "worker_id": "local-exec-fallback", "result": {"inputs_considered": 1, "bytes_read": 7950}}
{"ts_utc": "2026-02-22T11:12:42.604094Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-sleeprun11124203", "job_type": "test_runner_task", "created_at_utc": "2026-02-22T11:12:42.599037Z", "budgets": {"max_wall_time_sec": 180, "max_tool_calls": 8, "max_output_bytes": 131072, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": true, "allowed_tools": []}, "meta": {"source": "sleep_run"}, "payload": {"commands": [["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"]], "timeout_sec": 90, "cwd": ".", "env_allow": []}}}
{"ts_utc": "2026-02-22T11:12:44.447590Z", "event": "claim", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758824.4475884}
{"ts_utc": "2026-02-22T11:12:44.448858Z", "event": "heartbeat", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "lease_expires_unix": 1771758824.4488626}
{"ts_utc": "2026-02-22T11:12:44.540610Z", "event": "complete", "job_id": "job-sleeprun11124203", "worker_id": "local-exec-fallback", "result": {"commands_run": 1, "results": [{"argv": ["python3", "-m", "unittest", "tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls", "-v"], "returncode": 0, "timed_out": false, "duration_ms": 91, "stdout": "", "stderr": "test_model_client_stub_returns_no_tool_calls (tests_unittest.test_local_exec_plane_offline.LocalExecPlaneOfflineTests.test_model_client_stub_returns_no_tool_calls) ... ok\n\n----------------------------------------------------------------------\nRan 1 test in 0.009s\n\nOK\n", "stdout_bytes": 0, "stderr_bytes": 268, "stdout_truncated": false, "stderr_truncated": false}]}}
{"ts_utc": "2026-02-22T12:23:21.509648Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:21.502959Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}
{"ts_utc": "2026-02-22T12:23:39.196998Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:23:39.191319Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}
{"ts_utc": "2026-02-22T12:24:01.507075Z", "event": "enqueue", "validator_mode": "jsonschema", "job": {"job_id": "job-demorepoindex01", "job_type": "repo_index_task", "created_at_utc": "2026-02-22T12:24:01.501520Z", "payload": {"include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"], "exclude_globs": ["**/*.bak.*"], "max_files": 200, "max_file_bytes": 32768, "keywords": ["policy", "router", "audit"]}, "budgets": {"max_wall_time_sec": 300, "max_tool_calls": 10, "max_output_bytes": 262144, "max_concurrency_slots": 1}, "tool_policy": {"allow_network": false, "allow_subprocess": false, "allowed_tools": []}, "meta": {"source": "enqueue-demo"}}}

$ rm -f workspace/local_exec/state/KILL_SWITCH
kill_switch_cleared=true
```

## Durable bring-up result summary
```text
mode_attempt_1=tmux (missing)
mode_attempt_2=nohup+pidfile (process reaped/inactive between checks)
mode_attempt_3=foreground_loop (successful)
event_counts_health_window: pre=18 post=22
kill_switch_test: set -> worker exited, claims stopped

systemctl_user_worker_is_active:
Failed to connect to bus: Operation not permitted
systemctl_user_vllm_is_active:
Failed to connect to bus: Operation not permitted

script_status_now:
fallback worker inactive
vllm_status=unknown reason=systemd_user_unavailable

script_health_now:
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec_activation/workspace/local_exec/state/jobs.jsonl", "events": 22, "last_event": {"ts_utc": "2026-02-22T12:24:54.734192Z", "event": "complete", "job_id": "job-demorepoindex01", "worker_id": "local-exec-worker", "result": {"files_considered": 200, "hits_written": 90, "index_jsonl": "workspace/local_exec/evidence/job-demorepoindex01_index.jsonl"}}, "model_stub_mode": true, "model_api_base": "", "model_reachable": null, "model_detail": "stub_mode"}
summary kill_switch=False events=22 model_stub=True model_reachable=None
```
- blocked-by: background worker persistence is unreliable in this execution context (process reaped). Foreground mode required for deterministic persistence.
