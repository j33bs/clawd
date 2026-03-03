# Dali Local Exec Plane Audit

- UTC: 20260222T063625Z
- Goal: governed local execution plane for bounded overnight sub-agent work
- Constraint: no-sudo-by-default; deny-by-default tools; append-only evidence

## Phase 0 Baseline
```text
Sun Feb 22 06:36:25 UTC 2026
/home/jeebs/src/clawd
 M workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md
 M workspace/policy/llm_policy.json
 M workspace/scripts/rebuild_runtime_openclaw.sh
 M workspace/scripts/telegram_hardening_helpers.js
 M workspace/scripts/verify_policy_router.sh
 M workspace/state/tacti_cr/events.jsonl
?? docs/GPU_SETUP.md
?? scripts/vllm_prefix_warmup.js
?? tests/safe_error_surface.test.js.bak.20260221T234009Z
?? tests/safe_error_surface.test.js.bak.20260221T234700Z
?? tests/safe_error_surface.test.js.bak.20260221T235149Z
?? tests_unittest/test_discord_thin_adapter.py
?? tests_unittest/test_mcporter_tool_plane.py
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234009Z
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T234700Z
?? tests_unittest/test_policy_router_capability_classes.py.bak.20260221T235149Z
?? tests_unittest/test_safe_error_surface.py.bak.20260221T234700Z
?? tests_unittest/test_safe_error_surface.py.bak.20260221T235149Z
?? workspace/NOVELTY_LOVE_ALIGNMENT_RECS.md
?? workspace/NOVELTY_LOVE_ALIGNMENT_TODO.md
?? workspace/artifacts/itc/events/itc_events.jsonl
?? workspace/audit/dali_cbp_discord_vllm_redaction_20260221T232545Z.md
?? workspace/audit/dali_local_exec_plane_20260222T063625Z.md
?? workspace/audit/dali_safe_surface_intent_gates_20260221T234003Z.md.bak.20260221T235149Z
?? workspace/audit/dali_vllm_duplicate_audit_20260221T204359Z.md
?? workspace/audit/net_github_push_instability_20260222T021057Z.md
?? workspace/audit/runtime_autoupdate_hardening_20260222T021057Z.md
?? workspace/audit/runtime_autoupdate_userprefix_migration_20260222T041229Z.md
?? workspace/docs/ops/DISCORD_THIN_ADAPTER.md
?? workspace/policy/llm_policy.json.bak.20260221T231425Z
?? workspace/scripts/discord_adapter.py
?? workspace/scripts/gateway_router.py
?? workspace/scripts/mcporter_tool_plane.py
?? workspace/scripts/policy_router.py.bak.20260221T231425Z
?? workspace/scripts/policy_router.py.bak.20260221T234009Z
?? workspace/scripts/policy_router.py.bak.20260221T234700Z
?? workspace/scripts/policy_router.py.bak.20260221T235149Z
?? workspace/scripts/rebuild_runtime_openclaw.sh.bak.20260221T231425Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T234009Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T234700Z
?? workspace/scripts/safe_error_surface.js.bak.20260221T235149Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T234009Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T234700Z
?? workspace/scripts/safe_error_surface.py.bak.20260221T235149Z
?? workspace/scripts/telegram_hardening_helpers.js.bak.20260221T231425Z
?? workspace/scripts/verify_policy_router.sh.bak.20260221T231425Z
7480b24da4e0ac8994f28acd47eb4891ccc8e4db
origin	git@github.com:j33bs/clawd.git (fetch)
origin	git@github.com:j33bs/clawd.git (push)
v22.22.0
Python 3.12.3
Sun Feb 22 16:36:26 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 590.48.01              Driver Version: 590.48.01      CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3090        Off |   00000000:01:00.0  On |                  N/A |
|  0%   31C    P5             41W /  350W |   23383MiB /  24576MiB |     18%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            1790      G   /usr/lib/xorg/Xorg                      258MiB |
|    0   N/A  N/A            2099      G   /usr/bin/gnome-shell                    126MiB |
|    0   N/A  N/A            2639      G   ...exec/xdg-desktop-portal-gnome          6MiB |
|    0   N/A  N/A            3361      C   VLLM::EngineCore                      22382MiB |
|    0   N/A  N/A            4605      G   ...6899/usr/bin/telegram-desktop          4MiB |
|    0   N/A  N/A            7211      G   .../7836/usr/lib/firefox/firefox        453MiB |
|    0   N/A  N/A           27833      G   /usr/share/code/code                     70MiB |
+-----------------------------------------------------------------------------------------+
/home/jeebs/.local/bin/openclaw
2026.2.19-2 build_sha=9325318d0c992f1e5395a7274f98220ca7999336 build_time=2026-02-22T04:58:13Z

git worktree list
/home/jeebs/src/clawd                                     7480b24 [codex/fix-safe-surface-and-intent-gates-20260222]
/home/jeebs/src/clawd__verify_teamchat__20260220T050832Z  7a4c2b0 [fix/dali-audit-remediation-20260220]
/tmp/wt_follow                                            70637db [codex/chore-audit-quiesce-fallback-and-negative-redaction-test-20260222]
/tmp/wt_merge_main                                        2cb77d5 [codex/feat/build-sha-stamp-20260222]
/tmp/wt_runtime_auto                                      f9e294d [codex/feat/runtime-autoupdate-after-merge-20260222]
/tmp/wt_safe_surface                                      1324f31 [codex/fix-safe-surface-and-intent-gates-20260222-clean]
```

## Phase 0 Quiesce
```text
jeebs       3285  0.0  3.1 11374464 1034472 ?    Ssl  06:35   0:21 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
jeebs       3360  0.0  0.0  30968 12728 ?        S    06:35   0:00 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
jeebs       3361  0.6  6.6 43173500 2164308 ?    Sl   06:35   3:50 VLLM::EngineCore
jeebs      64932  0.0  0.1 1012612 55768 ?       Ssl  14:58   0:00 openclaw
jeebs      64992  0.2  1.3 23951168 431616 ?     Sl   14:58   0:12 openclaw-gateway
jeebs      73247  0.0  0.0  18400  2248 ?        S    16:36   0:00 grep -E -i openclaw|vllm|uvicorn|python.*worker|mcporter|ollama|litellm
  openclaw-gateway.service                                                             loaded active running   OpenClaw Gateway (user-owned)

$ systemctl --user stop openclaw-gateway.service || true

$ kill exact vLLM PIDs (if present)
vllm_pids=3285
3360
3361
73170
73253

$ post-quiesce process check (corrected exact-match capture)
jeebs      73381  0.0  0.0  18400  2292 ?        S    16:37   0:00 grep -E -i openclaw|vllm|uvicorn|python.*worker|mcporter|ollama|litellm

$ systemctl --user status openclaw-gateway.service || true
Failed to connect to bus: Operation not permitted
```

## Worktree Cleanliness Decision
- Canonical checkout /home/jeebs/src/clawd is dirty (blocked for direct edits).
- Safe fallback selected: create clean worktree from origin/main and implement there.
- No hard stop applied; proceeding with governed fallback.

## Rollback Plan (initial)
1. Stop local-exec worker/services via scripts/local_exec_plane.sh stop (or pidfile fallback).
2. Revert commits on feature branch via git revert, or delete branch if unmerged.
3. Restore any modified pre-existing files from *.bak.<timestamp>.

## Phase 0b — Clean Worktree Fallback
```text
Sun Feb 22 06:37:38 UTC 2026
/tmp/wt_local_exec
codex/feat/dali-local-exec-plane-20260222
5d8cea3c74a45020f6033016d787d641a9b17c01
## codex/feat/dali-local-exec-plane-20260222
?? workspace/audit/dali_local_exec_plane_20260222T063625Z.md
```

## Phase 1 — Inventory
```text
$ key files
workspace/scripts/policy_router.py
workspace/scripts/ensure_cron_jobs.py
workspace/automation/cron_jobs.json
workspace/audit/*
workspace/state/*
```

Routing/policy notes:
- \ is the central policy plane for provider selection, budgets, circuit-breaking, and capability routing; it already logs to JSONL under \ and references runtime state files under \.
- Existing design supports intent/capability selection but not a bounded offline execution queue with lease/heartbeat semantics. New local execution plane should remain a separate, swappable subsystem that can be invoked by policy/ops rather than replacing router logic.

Automation/evidence notes:
- \ + \ define cron templates and enforce them through OpenClaw CLI. This is the right place to reference or enqueue local-exec jobs later, without hard coupling into router internals.
- \ and JSONL state artifacts are already established; new plane should write append-only JSONL ledgers + per-job evidence bundles under a dedicated subtree.

Planned minimal subtree mapping:
- \ (core queue/worker/harness/schemas/evidence)
- \ (operator surface)
- \ (enqueue helper)
- \ + \ (model + runtime templates, no secrets)
- \ (deterministic offline tests)

## Phase 1b — Inventory (corrected notes)

Key files:
- `workspace/scripts/policy_router.py`
- `workspace/scripts/ensure_cron_jobs.py`
- `workspace/automation/cron_jobs.json`
- `workspace/audit/*`
- `workspace/state/*`

Routing/policy notes:
- `workspace/scripts/policy_router.py` is the central policy plane for provider selection, budgets, circuit-breaking, and capability routing; it already logs JSONL under `itc/` and reads/writes runtime state under `workspace/state`.
- Existing design supports intent/capability selection, but there is no bounded offline execution queue with lease/heartbeat semantics. The new local execution plane should remain separate and swappable, not replace policy-router logic.

Automation/evidence notes:
- `workspace/scripts/ensure_cron_jobs.py` and `workspace/automation/cron_jobs.json` define/enforce cron templates via OpenClaw CLI. This is the best insertion point to schedule local-exec jobs without coupling to router internals.
- `workspace/audit/` and JSONL state artifacts are established conventions; local-exec should emit append-only ledgers and per-job evidence bundles under a dedicated subtree.

Planned minimal subtree mapping:
- `workspace/local_exec/` (core queue/worker/harness/schemas/evidence)
- `scripts/local_exec_plane.sh` (operator surface)
- `scripts/local_exec_enqueue.py` (enqueue helper)
- `config/local_exec/` and `config/vllm/` (model/runtime templates, no secrets)
- `tests_unittest/test_local_exec_plane_offline.py` (deterministic offline tests)

## Phase 2 — Governed model menu
```text
Sun Feb 22 06:38:46 UTC 2026
-rw-rw-r-- 1 jeebs jeebs 1218 Feb 22 16:38 config/local_exec/models.json
-rw-rw-r-- 1 jeebs jeebs 1981 Feb 22 16:38 workspace/local_exec/MODELS.md
models.json: valid JSON
```

Summary: Added RTX-3090 model menu with coordinator/coder/verifier/doc_compactor logical roles, tool parser metadata, and bounded vLLM hints. No weights downloaded in this phase.

## Phase 3 — Governed queue/worker core + offline tests
```text
Sun Feb 22 06:45:35 UTC 2026
$ python3 -m unittest tests_unittest.test_local_exec_plane_offline -v

test_append_only_ledger_grows_and_worker_completes ... ok
test_budget_enforcement_max_tool_calls ... ok
test_disallowed_tool_call_rejected ... ok
test_kill_switch_prevents_claims ... ok
test_model_client_stub_returns_no_tool_calls ... ok
test_subprocess_policy_blocks_shell_string ... ok
test_test_runner_requires_subprocess_permission ... ok

Ran 7 tests in 0.043s
OK
```

Phase 3 outcome:
- Added JSON schemas + validator (jsonschema when available, lite validator fallback).
- Added append-only queue ledger with lock-based claim + lease heartbeat.
- Added budget guardrails + kill switch gate.
- Added argv-only subprocess harness with shell-like string rejection.
- Added worker handlers for `repo_index_task`, `test_runner_task`, `doc_compactor_task` with deny-by-default policy checks.
- Added deterministic offline test suite: `tests_unittest/test_local_exec_plane_offline.py`.

## Phase 4 — Optional MCPorter harness (best effort)
```text
Sun Feb 22 06:47:36 UTC 2026
$ command -v mcporter
(not found)
```

Outcome:
- blocked-by: `mcporter` not installed on runner.
- added optional adapter `workspace/local_exec/tools_mcporter.py` with:
  - deny-by-default allowlist,
  - strict timeout/response-size bounds,
  - explicit `tool_not_allowed` and `blocked_by:mcporter_not_installed` behavior.
- added config stub `config/mcporter.json` with zero enabled tools by default.

## Phase 5 — Operator surface + user-service templates
```text
Sun Feb 22 06:52:18 UTC 2026
$ bash -n scripts/local_exec_plane.sh
OK

$ python3 scripts/local_exec_enqueue.py --help
usage: local_exec_enqueue.py [-h] [--repo-root REPO_ROOT] [--job-file JOB_FILE] [--demo]

$ bash scripts/local_exec_plane.sh health
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec/workspace/local_exec/state/jobs.jsonl", "events": 0, "last_event": null}
```

Outcome:
- Added `scripts/local_exec_plane.sh` with `start|stop|status|health|enqueue-demo`.
- Added `scripts/local_exec_enqueue.py` for schema-validated queue insertion.
- Added user service template `workspace/local_exec/systemd/openclaw-local-exec-worker.service`.
- Added vLLM template config `config/vllm/dali_local_exec.yaml` (loopback, conservative GPU settings, env-key).
- Non-blocking behavior: systemd user preferred; pidfile/nohup fallback if bus unavailable.

## Phase 6 — Specialist prompt dictionary + cross-check protocol
```text
Sun Feb 22 06:55:34 UTC 2026
Added:
- workspace/local_exec/agents/AGENT_PROMPTS.json
- workspace/local_exec/agents/README.md
```

Outcome:
- Added governed prompts for `coordinator`, `coder_python`, `coder_js`, `verifier_tests`, `auditor_evidence`, `doc_compactor`.
- Each prompt includes scope constraints, tool policy constraints, evidence requirements, and cross-check protocol.
- Added concise README with required cross-check sequence.

## Phase 7 — Final integration + evidence bundle
```text
Sun Feb 22 06:48:40 UTC 2026
$ python3 -m unittest tests_unittest.test_local_exec_plane_offline -v

$ python3 scripts/local_exec_enqueue.py --repo-root /tmp/wt_local_exec --demo
{"status": "enqueued", "job_id": "job-demorepoindex01", "event_ts": "2026-02-22T06:48:17.211629Z"}

$ python3 -m workspace.local_exec.worker --repo-root /tmp/wt_local_exec --once
{"status": "complete", "job_id": "job-demorepoindex01", "result": {"files_considered": 200, "hits_written": 89, "index_jsonl": "workspace/local_exec/evidence/job-demorepoindex01_index.jsonl"}}

$ ls -la workspace/local_exec/evidence
total 28
drwxrwxr-x 2 jeebs jeebs  4096 Feb 22 16:48 .
drwxrwxr-x 8 jeebs jeebs  4096 Feb 22 16:45 ..
-rw-rw-r-- 1 jeebs jeebs   374 Feb 22 16:48 job-demorepoindex01.jsonl
-rw-rw-r-- 1 jeebs jeebs   164 Feb 22 16:48 job-demorepoindex01.md
-rw-rw-r-- 1 jeebs jeebs 10910 Feb 22 16:48 job-demorepoindex01_index.jsonl

$ bash scripts/local_exec_plane.sh health
{"kill_switch": false, "ledger_path": "/tmp/wt_local_exec/workspace/local_exec/state/jobs.jsonl", "events": 4, "last_event": {"ts_utc": "2026-02-22T06:48:17.301521Z", "event": "complete", "job_id": "job-demorepoindex01", "worker_id": "local-exec-worker", "result": {"files_considered": 200, "hits_written": 89, "index_jsonl": "workspace/local_exec/evidence/job-demorepoindex01_index.jsonl"}}}
```

Outcome:
- Added operator handoff doc: workspace/docs/ops/DALI_LOCAL_EXEC_PLANE.md.
- Demo offline pipeline succeeded: enqueue -> claim -> complete -> evidence artifacts produced.
- blocked-by summary: mcporter unavailable on runner; adapter remains deny-by-default stubbed path.
- blocked-by summary: vLLM not started/managed in this pass; config and activation instructions provided.

Next steps (priority):
1. Install mcporter and explicitly allowlist safe tools in config/mcporter.json.
2. Launch local vLLM endpoint and switch model client out of stub mode for selected job classes.
3. Optionally wire cron templates to enqueue bounded local_exec jobs overnight.

### Phase 7b — Post-fix re-run
```text
$ python3 -m unittest tests_unittest.test_local_exec_plane_offline -v
Ran 7 tests in 0.048s
OK
```
