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
