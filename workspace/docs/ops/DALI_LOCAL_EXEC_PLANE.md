# DALI Local Execution Plane

## Quick Start

```bash
cd /tmp/wt_local_exec
bash scripts/local_exec_plane.sh status
python3 scripts/local_exec_enqueue.py --demo --repo-root .
python3 -m workspace.local_exec.worker --repo-root . --once
bash scripts/local_exec_plane.sh health
```

## Gateway Pairing Preflight

Run this before sub-agent or browser-relay operations:

```bash
workspace/scripts/check_gateway_pairing_health.sh
```

This check fails fast if pending pairing/repair exists; follow the printed approve steps before continuing.

Cron path stabilization:
- Cron should call `$HOME/.local/bin/openclaw-cron-preflight` (stable user-owned shim), not a `/tmp` worktree path.
- If your canonical repo path differs, set `OPENCLAW_REPO_ROOT` in cron environment before invoking the shim.

## Start and Stop

```bash
# systemd user mode when bus is available; fallback to pidfile/nohup otherwise
bash scripts/local_exec_plane.sh start
bash scripts/local_exec_plane.sh status
bash scripts/local_exec_plane.sh stop
```

## Worker Loop Mode

```bash
# run one job and exit
python3 -m workspace.local_exec.worker --repo-root . --once

# continuous mode with idle heartbeats and bounded poll interval
python3 -m workspace.local_exec.worker --repo-root . --loop --sleep-s 2 --max-idle-s 300
```

Loop behavior:
- Emits periodic worker idle-heartbeat evidence records when idle.
- Renews queue lease heartbeats while processing jobs.
- Uses bounded exponential backoff (1s -> 2s -> 4s ... max 30s) on transient loop errors.

## Enqueue Jobs

```bash
# demo job
python3 scripts/local_exec_enqueue.py --demo --repo-root .

# custom job payload
python3 scripts/local_exec_enqueue.py --job-file /path/to/job.json --repo-root .
```

Job schema:
- `workspace/local_exec/schemas/job.schema.json`
- `workspace/local_exec/schemas/repo_index_task.schema.json`
- `workspace/local_exec/schemas/test_runner_task.schema.json`
- `workspace/local_exec/schemas/doc_compactor_task.schema.json`

## Evidence and State

- Queue ledger: `workspace/local_exec/state/jobs.jsonl` (append-only)
- Kill switch: `workspace/local_exec/state/KILL_SWITCH`
- Per-job evidence JSONL: `workspace/local_exec/evidence/<job_id>.jsonl`
- Worker evidence JSONL: `workspace/local_exec/evidence/worker_<worker_id>.jsonl`
- Per-job summary markdown: `workspace/local_exec/evidence/<job_id>.md`

## Budgets and Guardrails

- Required budgets: wall-time, tool-calls, output-bytes, concurrency-slots
- Deny-by-default tool policy per job
- Subprocess execution is argv-only and shell-like strings are rejected
- Network is disabled by default in worker policies
- Path sandbox rejects absolute paths, parent escapes (`..`), and symlink escapes outside repo root.
- Every run writes a `run_header` evidence event with immutable run metadata (validator mode, worker version, policy/budget hashes, model mode).

Kill switch semantics:
- Create `workspace/local_exec/state/KILL_SWITCH` to stop new job claims.
- Worker checks kill switch before claim and between steps.
- Current step is allowed to complete; worker then exits loop and records `loop_exit`.

## Optional MCPorter Enablement

Default is deny-by-default (`config/mcporter.json` has empty `enabled_tools`).

1. Install `mcporter` on host.
2. Edit `config/mcporter.json` and add exact tool names to `enabled_tools`.
3. Keep timeout/response-size bounds in place.

Example: enable one read-only tool only.

```json
{
  "enabled_tools": ["repo.search"],
  "timeout_sec": 30,
  "max_response_bytes": 131072
}
```

`workspace/local_exec/tools_mcporter.py` writes structured worker evidence events when `mcporter` is missing or a tool is rejected.

## Optional vLLM Enablement

Template config: `config/vllm/dali_local_exec.yaml`

Example launch:

```bash
export OPENCLAW_LOCAL_EXEC_VLLM_API_KEY='replace-me'
# adjust model path/served name as needed for local host
vllm serve <model> \
  --host 127.0.0.1 --port 8001 \
  --api-key "$OPENCLAW_LOCAL_EXEC_VLLM_API_KEY" \
  --served-model-name local-exec-coordinator \
  --gpu-memory-utilization 0.85 --max-model-len 8192 --max-num-seqs 8
```

Then point model client to `http://127.0.0.1:8001/v1`.
