# Dali Canary Timer + VRAM Guard + Event Envelope Hardening

- Timestamp (UTC): 2026-02-23T00:34:20Z
- Branch: codex/harden/dali-canary-timer-vram-guard-envelope-20260223
- Worktree: /tmp/wt_canary_timer_vram_env_20260223
- Base ref: origin/main

## Phase 0.1 Setup + Cleanliness

```bash
$ git rev-parse HEAD
2e02e515c150318ca1a775132c2fed822c0b136c

$ git rev-parse origin/main
2e02e515c150318ca1a775132c2fed822c0b136c

$ git status --porcelain -uall
# (empty)
```

## Phase 0.2 Baseline

```bash
$ node -v
v22.22.0

$ python3 --version
Python 3.12.3
```

## Phase 0.3 Recon

### Target surfaces presence

```bash
$ ls -l scripts/system2/provider_diag.js workspace/scripts/system_health_monitor.py scripts/replay_inspector.py workspace/scripts/pairing_preflight.py scripts/vllm_launch_coder.sh workspace/systemd/openclaw-vllm-coder.service workspace/systemd/openclaw-vllm.service
-rw-rw-r-- ... scripts/system2/provider_diag.js
-rwxrwxr-x ... workspace/scripts/system_health_monitor.py
ls: cannot access 'scripts/replay_inspector.py': No such file or directory
ls: cannot access 'workspace/scripts/pairing_preflight.py': No such file or directory
ls: cannot access 'scripts/vllm_launch_coder.sh': No such file or directory
ls: cannot access 'workspace/systemd/openclaw-vllm-coder.service': No such file or directory
ls: cannot access 'workspace/systemd/openclaw-vllm.service': No such file or directory
```

### Existing routing / coder lane markers

```bash
$ rg -n "REMOTE_FALLBACK|context_guard|replay|SUBAGENT|local_vllm_coder|8002" workspace/scripts/policy_router.py workspace/policy/llm_policy.json scripts/system2/provider_diag.js core/system2/inference/router.js
workspace/policy/llm_policy.json:152:    "local_vllm_coder": {
workspace/policy/llm_policy.json:158:      "baseUrl": "http://127.0.0.1:8002/v1",
workspace/policy/llm_policy.json:281:        "name": "coding_prefers_local_vllm_coder",
workspace/policy/llm_policy.json:286:        "provider": "local_vllm_coder"
workspace/policy/llm_policy.json:300:          "local_vllm_coder",
```

### Existing health/diagnostic hooks

```bash
$ rg -n "provider_diag|system_health_monitor|openclaw health|check_gateway_pairing_health" scripts workspace/scripts -S
scripts/system2/provider_diag.js:96:  if (env.PROVIDER_DIAG_NO_PROBES === '1') {
scripts/system2/provider_diag.js:204:  process.stderr.write(`provider_diag_failed: ${err.message}\\n`);
workspace/scripts/cron_with_gateway_preflight.sh:38:GUARD="${ROOT}/workspace/scripts/check_gateway_pairing_health.sh"
```

### Service/unit layout

```bash
$ find . -maxdepth 4 -type f \( -name '*vllm*service' -o -name '*coder*service' -o -name '*vllm*timer' -o -name '*canary*timer' -o -name '*canary*service' \) | sort
./workspace/local_exec/systemd/vllm-local-exec.service
```

## Recon findings summary

1. This `origin/main` snapshot includes policy-level coder lane config (`local_vllm_coder` on `:8002`) but lacks runtime launcher/service assets for coder lane.
2. No existing replay inspector/hashes-only replay harness files are present in this baseline.
3. Pairing preflight currently exists as shell guard (`workspace/scripts/check_gateway_pairing_health.sh`), not `pairing_preflight.py`.
4. Provider diagnostics currently probe only local vLLM (`:8001`) and do not report coder lane degradation reasons.
5. No existing shared event envelope helper/schema across Python and Node for gate/health events.

## Phase 1 — Canary runner (manual CLI + timer-ready)

### Implemented

- Added `scripts/dali_canary_runner.py` (stdlib only).
- Checks performed each run:
  1. provider diagnostics via `node scripts/system2/provider_diag.js` (parses stable `key=value` markers)
  2. replay log writability (`OPENCLAW_REPLAY_LOG_PATH` or `~/.local/share/openclaw/replay/replay.jsonl`)
  3. pairing canary via `workspace/scripts/check_gateway_pairing_health.sh`
- Emits one stable status line:
  - `CANARY status=<OK|DEGRADED|FAIL> coder=<UP|DOWN|DEGRADED> replay=<WRITABLE|NOACCESS> pairing=<OK|UNHEALTHY> ts=<ISO8601>`
- Exit codes:
  - `0` OK
  - `10` DEGRADED
  - `20` FAIL
- Appends same line to runtime log path:
  - `OPENCLAW_CANARY_LOG_PATH` or `~/.local/share/openclaw/canary/canary.log`
- Emits a golden envelope event to runtime envelope log (`OPENCLAW_EVENT_ENVELOPE_LOG_PATH` fallback path).

### Tests added

- `tests_unittest/test_dali_canary_runner.py`
  - line format regex stability
  - forbidden field absence in line
  - exit code mapping and mocked status paths

## Phase 1.3 — Opt-in user systemd service + timer

Added:
- `workspace/systemd/openclaw-canary.service`
- `workspace/systemd/openclaw-canary.timer`

Design:
- user-level, opt-in only, disabled by default.
- cadence: every 30 minutes (`OnUnitActiveSec=30min`).

Operator enable commands (not executed in this tranche):

```bash
systemctl --user daemon-reload
systemctl --user enable --now openclaw-canary.timer
```

## Phase 2 — VRAM/contention guard for coder lane

### Implemented

- Added `scripts/vram_guard.py` (stdlib only).
- Queries `nvidia-smi --query-gpu=memory.total,memory.used --format=csv,noheader,nounits`.
- Computes max free VRAM across GPUs and compares to:
  - `VLLM_CODER_MIN_FREE_VRAM_MB` (default `7000`).
- Missing `nvidia-smi` behavior:
  - blocked by default
  - allowed only if `VLLM_CODER_ALLOW_NO_NVIDIA_SMI=true`
- Machine-readable JSON verdict with fields:
  - `ok`, `reason`, `message`, `threshold_mb`, `gpu_count`, `max_free_vram_mb`
- Added `scripts/vllm_launch_coder.sh` startup wrapper:
  - runs VRAM guard before starting vLLM
  - on block: exits non-zero and logs
    - `VRAM_GUARD_BLOCKED: reason=... details=...`
- Added `workspace/systemd/openclaw-vllm-coder.service` (user-level) using wrapper script.

### Diagnostics surfacing

Updated `scripts/system2/provider_diag.js`:
- probes coder endpoint (`OPENCLAW_VLLM_CODER_BASE_URL` default `http://127.0.0.1:8002/v1/models`)
- emits stable markers:
  - `coder_status=<UP|DOWN|DEGRADED>`
  - `coder_degraded_reason=<...>`
- if coder down, inspects coder log tail for `VRAM_GUARD_BLOCKED` reason (best effort)
- emits replay writability markers and canary recommendations.

## Phase 3 — Golden event envelope schema alignment (python + node)

### Implemented

- Added spec doc:
  - `workspace/governance/EVENT_ENVELOPE_SCHEMA.md`
- Added Python helper:
  - `workspace/scripts/event_envelope.py`
- Added Node helper:
  - `scripts/system2/event_envelope.js`

Envelope keys/types aligned across runtimes:
- `schema`, `ts`, `event`, `severity`, `component`, `corr_id`, `details`

Forbidden payload keys stripped recursively:
- `prompt`, `text`, `body`, `document_body`, `messages`, `content`, `raw_content`, `raw`

Wired emissions in this tranche:
- Python: `scripts/dali_canary_runner.py`, `scripts/vram_guard.py`
- Node: `scripts/system2/provider_diag.js`

### Tests added/updated

- `tests_unittest/test_event_envelope.py`
- `tests/event_envelope_schema.test.js`
- updated `tests/provider_diag_format.test.js` for new stable markers

## Phase 4 — Verification

### Python tests

```bash
$ python3 -m unittest -v tests_unittest.test_dali_canary_runner tests_unittest.test_vram_guard tests_unittest.test_event_envelope
...
Ran 12 tests in 0.003s
OK
```

### Node tests

```bash
$ node tests/provider_diag_format.test.js && node tests/event_envelope_schema.test.js && node tests/model_routing_no_oauth.test.js
PASS provider_diag includes grep-friendly providers_summary section
provider_diag_format tests complete
PASS node event envelope has required keys and strips forbidden fields
event_envelope_schema tests complete
PASS model routing no oauth/codex regression gate
```

### Manual dry-runs

```bash
$ python3 scripts/dali_canary_runner.py || true
CANARY status=FAIL coder=DOWN replay=NOACCESS pairing=UNHEALTHY ts=2026-02-23T00:43:34Z
```

```bash
$ node scripts/system2/provider_diag.js || true
# (abbrev)
coder_status=DOWN
coder_degraded_reason=UNKNOWN
replay_log_writable=false
replay_log_reason=EACCES
event_envelope_schema=openclaw.event_envelope.v1
...
```

```bash
$ python3 scripts/vram_guard.py || true
{"ok": false, "reason": "NVIDIA_SMI_ERROR", "message": "Failed to initialize NVML: Unknown Error", "threshold_mb": 7000, "gpu_count": 0, "max_free_vram_mb": null}
```

## Rollback

### Git rollback (preserve history)

```bash
git log --oneline origin/main..HEAD
git revert <newest_sha>..<oldest_sha>
```

### Branch/worktree discard (if not merged)

```bash
git checkout main
git branch -D codex/harden/dali-canary-timer-vram-guard-envelope-20260223
git worktree remove /tmp/wt_canary_timer_vram_env_20260223
```

### Runtime artifacts cleanup

```bash
rm -f ~/.local/share/openclaw/canary/canary.log
rm -f ~/.local/share/openclaw/events/gate_health.jsonl
rm -f ~/.local/share/openclaw/replay/replay.jsonl
rm -f ~/.local/state/openclaw/vllm-coder.log
```

### Timer rollback (if enabled on host)

```bash
systemctl --user disable --now openclaw-canary.timer
systemctl --user daemon-reload
```

## Residual uncertainties

1. User/system permissions in this environment prevented writing to `~/.local/share/openclaw/...` (`EACCES`), so replay/canary/envelope runtime append was exercised in failure-safe mode.
2. `nvidia-smi` returned NVML init error in this environment; VRAM guard behavior validated via unit tests and manual output, but live GPU state remains host-dependent.
3. Coder degraded reason detection relies on coder log tail containing `VRAM_GUARD_BLOCKED` markers; if logs are rotated externally, reason may resolve to `UNKNOWN`.

## Phase 4 Re-Verification (post-commit)

```bash
$ python3 -m unittest -v tests_unittest.test_dali_canary_runner tests_unittest.test_vram_guard tests_unittest.test_event_envelope
...
Ran 12 tests in 0.003s
OK
```

```bash
$ node tests/provider_diag_format.test.js && node tests/event_envelope_schema.test.js && node tests/model_routing_no_oauth.test.js
PASS provider_diag includes grep-friendly providers_summary section
provider_diag_format tests complete
PASS node event envelope has required keys and strips forbidden fields
event_envelope_schema tests complete
PASS model routing no oauth/codex regression gate
```

```bash
$ python3 scripts/dali_canary_runner.py || true
CANARY status=FAIL coder=DOWN replay=NOACCESS pairing=UNHEALTHY ts=2026-02-23T00:44:52Z
```

```bash
$ node scripts/system2/provider_diag.js || true
# (abbrev)
coder_status=DOWN
coder_degraded_reason=UNKNOWN
replay_log_writable=false
replay_log_reason=EACCES
event_envelope_schema=openclaw.event_envelope.v1
event_envelope_write_ok=false
event_envelope_write_reason=EACCES
```

```bash
$ python3 scripts/vram_guard.py || true
{"ok": false, "reason": "NVIDIA_SMI_ERROR", "message": "Failed to initialize NVML: Unknown Error", "threshold_mb": 7000, "gpu_count": 0, "max_free_vram_mb": null}
```
