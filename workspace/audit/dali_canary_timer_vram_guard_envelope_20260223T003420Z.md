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
\n## Coder Lane DOWN Diagnosis - 2026-02-23T04:57:16Z
### Phase 0.1 - Unit identity and install source
$ systemctl --user cat openclaw-vllm-coder.service --no-pager
\n## Coder Lane DOWN Diagnosis - 2026-02-23T04:58:08Z
### Phase 0.1 - Unit identity and install source
$ systemctl --user cat openclaw-vllm-coder.service --no-pager
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
$ systemctl --user show -p FragmentPath,DropInPaths,ExecStart,WorkingDirectory,EnvironmentFile openclaw-vllm-coder.service || true
WorkingDirectory=
FragmentPath=
DropInPaths=
$ systemctl --user list-unit-files | grep -E 'openclaw-vllm-coder|openclaw-vllm' || true
openclaw-vllm.service                                                             enabled   enabled
### Phase 0.2 - Launch script path checks
$ ls -la /tmp/wt_merge_main/scripts/vllm_launch_coder.sh
-rwxrwxr-x 1 jeebs jeebs 1876 Feb 23 13:29 /tmp/wt_merge_main/scripts/vllm_launch_coder.sh
$ ls -la /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh || true
-rw-rw-r-- 1 jeebs jeebs 1094 Feb 23 06:27 /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh
$ head -n 40 /tmp/wt_merge_main/scripts/vllm_launch_coder.sh
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VLLM_PYTHON="${VLLM_PYTHON:-python3}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_CODER_PORT:-8002}"
MODEL="${OPENCLAW_VLLM_CODER_MODEL:-${VLLM_CODER_MODEL:-local-coder}}"
VLLM_MAX_MODEL_LEN="${VLLM_CODER_MAX_MODEL_LEN:-16384}"
VLLM_SWAP_SPACE="${VLLM_CODER_SWAP_SPACE:-0}"
CODER_LOG_PATH="${OPENCLAW_VLLM_CODER_LOG_PATH:-$HOME/.local/state/openclaw/vllm-coder.log}"

mkdir -p "$(dirname "$CODER_LOG_PATH")"

set +e
VRAM_JSON="$($VLLM_PYTHON "$ROOT_DIR/scripts/vram_guard.py" --json 2>&1)"
VRAM_RC=$?
set -e
if [[ $VRAM_RC -ne 0 ]]; then
  PARSED="$($VLLM_PYTHON - <<'PY' "$VRAM_JSON" "${VLLM_CODER_MIN_FREE_VRAM_MB:-7000}"
import json, sys
raw = sys.argv[1] if len(sys.argv) > 1 else '{}'
threshold = sys.argv[2] if len(sys.argv) > 2 else '7000'
try:
    obj = json.loads(raw)
except Exception:
    obj = {}
reason = str(obj.get('reason') or 'UNKNOWN')
free_mb = obj.get('max_free_vram_mb')
if free_mb is None:
    free_mb = "na"
print(f"{reason}|{free_mb}|{threshold}")
PY
)"
  REASON="${PARSED%%|*}"
  REST="${PARSED#*|}"
  FREE_MB="${REST%%|*}"
  MIN_FREE_MB="${REST##*|}"
### Phase 1 - Recent logs (expanded window)
$ journalctl --user -u openclaw-vllm-coder.service -n 300 --no-pager || true
-- No entries --
$ journalctl --user -u openclaw-vllm-coder.service -n 300 --no-pager | egrep -n "VLLM_CODER_START_BLOCKED|VRAM_GUARD|Traceback|Error|failed|No such file|Address already in use|CUDA|NVML|OOM|Killed" || true
### Phase 2 - Controlled restart + immediate logs
$ systemctl --user restart openclaw-vllm-coder.service || true
$ sleep 2
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
$ journalctl --user -u openclaw-vllm-coder.service -n 120 --no-pager || true
-- No entries --
### Phase 3 - Source unit presence check (no code changes)
$ ls -la workspace/systemd/openclaw-vllm-coder.service
-rw-rw-r-- 1 jeebs jeebs 487 Feb 23 12:33 workspace/systemd/openclaw-vllm-coder.service
$ sed -n '1,120p' workspace/systemd/openclaw-vllm-coder.service
[Unit]
Description=OpenClaw local vLLM coder lane (:8002)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/src/clawd
Environment=VLLM_CODER_PORT=8002
Environment=VLLM_CODER_MIN_FREE_VRAM_MB=7000
ExecStart=%h/src/clawd/scripts/vllm_launch_coder.sh
Restart=on-failure
RestartSec=5
StandardOutput=append:%h/.local/state/openclaw/vllm-coder.log
StandardError=append:%h/.local/state/openclaw/vllm-coder.log

[Install]
WantedBy=default.target
\n## 1-hour coder lane operational pass - 2026-02-23T06:48:07Z
### STEP 1 - baseline + stop thrash
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: activating (auto-restart) (Result: exit-code) since Mon 2026-02-23 16:48:04 AEST; 2s ago
    Process: 367057 ExecStart=/home/jeebs/src/clawd/scripts/vllm_launch_coder.sh (code=exited, status=203/EXEC)
   Main PID: 367057 (code=exited, status=203/EXEC)
        CPU: 312us
$ systemctl --user show -p FragmentPath,ExecStart,MainPID,NRestarts,Result,ExecMainStatus openclaw-vllm-coder.service || true
MainPID=0
Result=exit-code
NRestarts=925
ExecMainStatus=203
ExecStart={ path=/home/jeebs/src/clawd/scripts/vllm_launch_coder.sh ; argv[]=/home/jeebs/src/clawd/scripts/vllm_launch_coder.sh ; ignore_errors=no ; start_time=[Mon 2026-02-23 16:48:04 AEST] ; stop_time=[Mon 2026-02-23 16:48:04 AEST] ; pid=367057 ; code=exited ; status=203 }
FragmentPath=/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service
$ systemctl --user cat openclaw-vllm-coder.service --no-pager || true
# /home/jeebs/.config/systemd/user/openclaw-vllm-coder.service
[Unit]
Description=OpenClaw local vLLM coder lane (:8002)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/src/clawd
Environment=VLLM_CODER_PORT=8002
Environment=VLLM_CODER_MIN_FREE_VRAM_MB=7000
ExecStart=%h/src/clawd/scripts/vllm_launch_coder.sh
Restart=on-failure
RestartSec=5
StandardOutput=append:%h/.local/state/openclaw/vllm-coder.log
StandardError=append:%h/.local/state/openclaw/vllm-coder.log

[Install]
WantedBy=default.target
$ systemctl --user stop openclaw-vllm-coder.service || true
$ systemctl --user reset-failed openclaw-vllm-coder.service || true
### STEP 2 - ExecStart target validity
$ ls -la /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh || true
-rw-rw-r-- 1 jeebs jeebs 1094 Feb 23 06:27 /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh
$ ls -la ~/src/clawd/scripts/vllm_launch_coder.sh
-rw-rw-r-- 1 jeebs jeebs 1094 Feb 23 06:27 /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh
$ head -n 3 ~/src/clawd/scripts/vllm_launch_coder.sh
#!/usr/bin/env bash
set -euo pipefail

$ chmod +x ~/src/clawd/scripts/vllm_launch_coder.sh
$ command -v bash
/usr/bin/bash
$ file ~/src/clawd/scripts/vllm_launch_coder.sh
/home/jeebs/src/clawd/scripts/vllm_launch_coder.sh: Bourne-Again shell script, ASCII text executable
CRLF_CHECK:no_crlf_detected
$ ls -la ~/src/clawd/scripts/vllm_launch_coder.sh
-rwxrwxr-x 1 jeebs jeebs 1094 Feb 23 06:27 /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh
### STEP 3 - unit source/path validation
$ systemctl --user show -p FragmentPath openclaw-vllm-coder.service
FragmentPath=/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service
$ readlink -f ~/.config/systemd/user/openclaw-vllm-coder.service || true
/tmp/wt_merge_main/workspace/systemd/openclaw-vllm-coder.service
UNIT_PATH_CHECK:already_expected_fragment_path
$ systemctl --user daemon-reload
### STEP 4 - start coder lane + immediate logs
$ systemctl --user enable --now openclaw-vllm-coder.service || true
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 16:50:41 AEST; 3ms ago
   Main PID: 368626 (vllm)
      Tasks: 1 (limit: 38169)
     Memory: 960.0K (peak: 1.4M)
        CPU: 2ms
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             └─368626 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning

Feb 23 16:50:41 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ journalctl --user -u openclaw-vllm-coder.service -n 200 --no-pager || true
Feb 23 16:43:47 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:43:47 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:43:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 877.
Feb 23 16:43:52 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:43:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:43:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:43:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 878.
Feb 23 16:43:58 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:43:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:43:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 879.
Feb 23 16:44:03 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:08 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 880.
Feb 23 16:44:08 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:08 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:08 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 881.
Feb 23 16:44:13 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:19 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 882.
Feb 23 16:44:19 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:19 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:19 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 883.
Feb 23 16:44:24 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 884.
Feb 23 16:44:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:34 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 885.
Feb 23 16:44:34 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:34 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:34 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 886.
Feb 23 16:44:40 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 887.
Feb 23 16:44:45 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:50 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 888.
Feb 23 16:44:50 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:50 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:50 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:44:55 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 889.
Feb 23 16:44:55 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:44:55 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:44:55 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:00 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 890.
Feb 23 16:45:00 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:00 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:00 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:06 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 891.
Feb 23 16:45:06 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:06 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:06 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:11 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 892.
Feb 23 16:45:11 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:11 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:11 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:16 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 893.
Feb 23 16:45:16 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:16 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:16 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:21 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 894.
Feb 23 16:45:21 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:21 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:21 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 895.
Feb 23 16:45:27 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 896.
Feb 23 16:45:32 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:37 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 897.
Feb 23 16:45:37 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:37 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:37 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 898.
Feb 23 16:45:42 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 899.
Feb 23 16:45:48 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 900.
Feb 23 16:45:53 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:45:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 901.
Feb 23 16:45:58 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:45:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:45:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 902.
Feb 23 16:46:03 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 903.
Feb 23 16:46:09 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:14 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 904.
Feb 23 16:46:14 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:14 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:14 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:19 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 905.
Feb 23 16:46:19 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:19 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:19 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 906.
Feb 23 16:46:24 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 907.
Feb 23 16:46:30 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 908.
Feb 23 16:46:35 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 909.
Feb 23 16:46:40 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 910.
Feb 23 16:46:45 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:51 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 911.
Feb 23 16:46:51 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:51 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:51 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:46:56 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 912.
Feb 23 16:46:56 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:46:56 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:46:56 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:01 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 913.
Feb 23 16:47:01 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:01 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:01 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:06 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 914.
Feb 23 16:47:06 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:06 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:06 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:12 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 915.
Feb 23 16:47:12 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:12 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:12 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:17 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 916.
Feb 23 16:47:17 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:17 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:17 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:22 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 917.
Feb 23 16:47:22 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:22 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:22 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 918.
Feb 23 16:47:27 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:33 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 919.
Feb 23 16:47:33 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:33 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:33 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:38 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 920.
Feb 23 16:47:38 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:38 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:38 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:43 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 921.
Feb 23 16:47:43 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:43 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:43 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 922.
Feb 23 16:47:48 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:54 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 923.
Feb 23 16:47:54 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:54 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:54 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:47:59 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 924.
Feb 23 16:47:59 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:47:59 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:47:59 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:48:04 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 925.
Feb 23 16:48:04 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:48:04 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=203/EXEC
Feb 23 16:48:04 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:48:07 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopped openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:50:41 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ journalctl --user -u openclaw-vllm-coder.service -n 200 --no-pager | egrep -n "VLLM_CODER_START_BLOCKED|Address already in use|No such file|permission denied|CUDA|NVML|OOM|Killed|Traceback|Error|failed" || true
### STEP 5 - endpoint + diagnostics verification
$ curl -sf http://127.0.0.1:8002/health && echo "VLLM_CODER_OK" || echo "VLLM_CODER_DOWN"
VLLM_CODER_DOWN
$ node /tmp/wt_merge_main/scripts/system2/provider_diag.js || true
=== System-2 Provider Diagnostics (safe) ===
freecompute_enabled=false
freecompute_env_keys_seen=(none)
secrets_bridge_enabled=false

local_vllm_endpoint_present=false
local_vllm_models_fetch_ok=false
local_vllm_models_count=0
local_vllm_generation_probe_ok=false
local_vllm_generation_probe_reason=unknown
coder_vllm_endpoint=http://127.0.0.1:8002/v1/models
coder_vllm_endpoint_present=false
coder_vllm_models_fetch_ok=false
coder_vllm_models_count=0
coder_status=DOWN
coder_degraded_reason=UNAVAILABLE
coder_degraded_note=journal_unavailable
replay_log_path=/home/jeebs/.local/share/openclaw/replay/replay.jsonl
replay_log_writable=false
replay_log_reason=EACCES
event_envelope_schema=openclaw.event_envelope.v1

event_envelope_log_path=/home/jeebs/.local/share/openclaw/events/gate_health.jsonl
event_envelope_write_ok=false
event_envelope_write_reason=EACCES

canary_recommendations:
- run: python3 scripts/dali_canary_runner.py
- optional timer: systemctl --user enable --now openclaw-canary.timer
- if coder DEGRADED with VRAM_LOW, reduce load or raise VLLM_CODER_MIN_FREE_VRAM_MB policy

providers:
- gemini: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GEMINI_API_KEY
- groq: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GROQ_API_KEY
- local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed auth_env_keys=OPENCLAW_VLLM_API_KEY
- minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_MINIMAX_PORTAL_API_KEY
- openrouter: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_OPENROUTER_API_KEY
- qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_QWEN_API_KEY

providers_summary:
gemini: configured=no enabled=yes eligible=no reason=missing_api_key
groq: configured=no enabled=yes eligible=no reason=missing_api_key
local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed
minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key
openrouter: configured=no enabled=yes eligible=no reason=missing_api_key
qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key
$ python3 /tmp/wt_merge_main/scripts/dali_canary_runner.py || true
CANARY status=FAIL coder=DOWN replay=NOACCESS pairing=UNHEALTHY ts=2026-02-23T06:50:49Z
### STEP 5b - host-level recheck after warm-up
$ sleep 20
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 16:58:27 AEST; 5s ago
   Main PID: 376429 (vllm)
      Tasks: 64 (limit: 38169)
     Memory: 874.7M (peak: 874.7M)
        CPU: 9.657s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             ├─376429 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─376543 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─376544 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=35, pipe_handle=37)" --multiprocessing-fork

Feb 23 16:58:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 28.
Feb 23 16:58:27 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ systemctl --user show -p MainPID,SubState,Result,ExecMainStatus,NRestarts openclaw-vllm-coder.service || true
MainPID=376429
Result=success
NRestarts=28
ExecMainStatus=0
SubState=running
$ journalctl --user -u openclaw-vllm-coder.service -n 120 --no-pager || true
Feb 23 16:51:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:51:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:51:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.793s CPU time.
Feb 23 16:52:04 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 5.
Feb 23 16:52:04 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:52:15 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:52:15 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:52:15 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.766s CPU time.
Feb 23 16:52:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 6.
Feb 23 16:52:20 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:52:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:52:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:52:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.565s CPU time.
Feb 23 16:52:37 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 7.
Feb 23 16:52:37 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:52:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:52:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:52:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.631s CPU time.
Feb 23 16:52:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 8.
Feb 23 16:52:53 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:53:05 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:53:05 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:53:05 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.738s CPU time.
Feb 23 16:53:10 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 9.
Feb 23 16:53:10 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:53:21 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:53:21 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:53:21 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.818s CPU time.
Feb 23 16:53:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 10.
Feb 23 16:53:27 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:53:38 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:53:38 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:53:38 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.654s CPU time.
Feb 23 16:53:43 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 11.
Feb 23 16:53:43 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:53:55 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:53:55 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:53:55 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.785s CPU time.
Feb 23 16:54:00 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 12.
Feb 23 16:54:00 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:54:12 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:54:12 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:54:12 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.690s CPU time.
Feb 23 16:54:17 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 13.
Feb 23 16:54:17 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:54:28 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:54:28 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:54:28 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.725s CPU time.
Feb 23 16:54:34 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 14.
Feb 23 16:54:34 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:54:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:54:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:54:45 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.711s CPU time.
Feb 23 16:54:50 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 15.
Feb 23 16:54:50 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:55:02 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:55:02 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:55:02 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.767s CPU time.
Feb 23 16:55:07 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 16.
Feb 23 16:55:07 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:55:18 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:55:18 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:55:18 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.716s CPU time.
Feb 23 16:55:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 17.
Feb 23 16:55:24 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:55:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:55:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:55:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.760s CPU time.
Feb 23 16:55:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 18.
Feb 23 16:55:40 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:55:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:55:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:55:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.806s CPU time.
Feb 23 16:55:57 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 19.
Feb 23 16:55:57 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:56:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:56:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:56:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.755s CPU time.
Feb 23 16:56:14 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 20.
Feb 23 16:56:14 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:56:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:56:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:56:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.868s CPU time.
Feb 23 16:56:31 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 21.
Feb 23 16:56:31 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:56:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:56:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:56:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.664s CPU time.
Feb 23 16:56:47 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 22.
Feb 23 16:56:47 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:56:59 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:56:59 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:56:59 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.662s CPU time.
Feb 23 16:57:04 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 23.
Feb 23 16:57:04 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:57:15 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:57:15 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:57:15 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.623s CPU time.
Feb 23 16:57:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 24.
Feb 23 16:57:20 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:57:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:57:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:57:32 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.769s CPU time.
Feb 23 16:57:37 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 25.
Feb 23 16:57:37 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:57:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:57:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:57:48 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.730s CPU time.
Feb 23 16:57:54 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 26.
Feb 23 16:57:54 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:58:05 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:58:05 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:58:05 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.773s CPU time.
Feb 23 16:58:10 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 27.
Feb 23 16:58:10 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 16:58:22 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 16:58:22 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 16:58:22 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.729s CPU time.
Feb 23 16:58:27 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 28.
Feb 23 16:58:27 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ tail -n 120 ~/.local/state/openclaw/vllm-coder.log || true
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     super().__init__(
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 105, in __init__
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     self.model_executor = executor_class(vllm_config)
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/abstract.py", line 101, in __init__
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     self._init_executor()
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/uniproc_executor.py", line 47, in _init_executor
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     self.driver_worker.init_device()
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/worker_base.py", line 326, in init_device
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     self.worker.init_device()  # type: ignore
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     ^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/gpu_worker.py", line 235, in init_device
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     self.requested_memory = request_memory(init_snapshot, self.cache_config)
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/utils.py", line 260, in request_memory
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946]     raise ValueError(
[0;36m(EngineCore_DP0 pid=376256)[0;0m ERROR 02-23 16:58:20 [core.py:946] ValueError: Free memory on device cuda:0 (0.88/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
[0;36m(EngineCore_DP0 pid=376256)[0;0m Process EngineCore_DP0:
[0;36m(EngineCore_DP0 pid=376256)[0;0m Traceback (most recent call last):
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/usr/lib/python3.12/multiprocessing/process.py", line 314, in _bootstrap
[0;36m(EngineCore_DP0 pid=376256)[0;0m     self.run()
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/usr/lib/python3.12/multiprocessing/process.py", line 108, in run
[0;36m(EngineCore_DP0 pid=376256)[0;0m     self._target(*self._args, **self._kwargs)
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 950, in run_engine_core
[0;36m(EngineCore_DP0 pid=376256)[0;0m     raise e
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
[0;36m(EngineCore_DP0 pid=376256)[0;0m     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
[0;36m(EngineCore_DP0 pid=376256)[0;0m                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
[0;36m(EngineCore_DP0 pid=376256)[0;0m     super().__init__(
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 105, in __init__
[0;36m(EngineCore_DP0 pid=376256)[0;0m     self.model_executor = executor_class(vllm_config)
[0;36m(EngineCore_DP0 pid=376256)[0;0m                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/abstract.py", line 101, in __init__
[0;36m(EngineCore_DP0 pid=376256)[0;0m     self._init_executor()
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/executor/uniproc_executor.py", line 47, in _init_executor
[0;36m(EngineCore_DP0 pid=376256)[0;0m     self.driver_worker.init_device()
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/worker_base.py", line 326, in init_device
[0;36m(EngineCore_DP0 pid=376256)[0;0m     self.worker.init_device()  # type: ignore
[0;36m(EngineCore_DP0 pid=376256)[0;0m     ^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/gpu_worker.py", line 235, in init_device
[0;36m(EngineCore_DP0 pid=376256)[0;0m     self.requested_memory = request_memory(init_snapshot, self.cache_config)
[0;36m(EngineCore_DP0 pid=376256)[0;0m                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(EngineCore_DP0 pid=376256)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/worker/utils.py", line 260, in request_memory
[0;36m(EngineCore_DP0 pid=376256)[0;0m     raise ValueError(
[0;36m(EngineCore_DP0 pid=376256)[0;0m ValueError: Free memory on device cuda:0 (0.88/23.56 GiB) on startup is less than desired GPU memory utilization (0.9, 21.2 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
[rank0]:[W223 16:58:21.076239648 ProcessGroupNCCL.cpp:1524] Warning: WARNING: destroy_process_group() was not called before program exit, which can leak resources. For more info, please see https://pytorch.org/docs/stable/distributed.html#shutdown (function operator())
[0;36m(APIServer pid=376114)[0;0m Traceback (most recent call last):
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/bin/vllm", line 6, in <module>
[0;36m(APIServer pid=376114)[0;0m     sys.exit(main())
[0;36m(APIServer pid=376114)[0;0m              ^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/main.py", line 73, in main
[0;36m(APIServer pid=376114)[0;0m     args.dispatch_function(args)
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/serve.py", line 111, in cmd
[0;36m(APIServer pid=376114)[0;0m     uvloop.run(run_server(args))
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 96, in run
[0;36m(APIServer pid=376114)[0;0m     return __asyncio.run(
[0;36m(APIServer pid=376114)[0;0m            ^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
[0;36m(APIServer pid=376114)[0;0m     return runner.run(main)
[0;36m(APIServer pid=376114)[0;0m            ^^^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
[0;36m(APIServer pid=376114)[0;0m     return self._loop.run_until_complete(task)
[0;36m(APIServer pid=376114)[0;0m            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 48, in wrapper
[0;36m(APIServer pid=376114)[0;0m     return await main
[0;36m(APIServer pid=376114)[0;0m            ^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 919, in run_server
[0;36m(APIServer pid=376114)[0;0m     await run_server_worker(listen_address, sock, args, **uvicorn_kwargs)
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 938, in run_server_worker
[0;36m(APIServer pid=376114)[0;0m     async with build_async_engine_client(
[0;36m(APIServer pid=376114)[0;0m   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
[0;36m(APIServer pid=376114)[0;0m     return await anext(self.gen)
[0;36m(APIServer pid=376114)[0;0m            ^^^^^^^^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 147, in build_async_engine_client
[0;36m(APIServer pid=376114)[0;0m     async with build_async_engine_client_from_engine_args(
[0;36m(APIServer pid=376114)[0;0m   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
[0;36m(APIServer pid=376114)[0;0m     return await anext(self.gen)
[0;36m(APIServer pid=376114)[0;0m            ^^^^^^^^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 188, in build_async_engine_client_from_engine_args
[0;36m(APIServer pid=376114)[0;0m     async_llm = AsyncLLM.from_vllm_config(
[0;36m(APIServer pid=376114)[0;0m                 ^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 228, in from_vllm_config
[0;36m(APIServer pid=376114)[0;0m     return cls(
[0;36m(APIServer pid=376114)[0;0m            ^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 155, in __init__
[0;36m(APIServer pid=376114)[0;0m     self.engine_core = EngineCoreClient.make_async_mp_client(
[0;36m(APIServer pid=376114)[0;0m                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 122, in make_async_mp_client
[0;36m(APIServer pid=376114)[0;0m     return AsyncMPClient(*client_args)
[0;36m(APIServer pid=376114)[0;0m            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 819, in __init__
[0;36m(APIServer pid=376114)[0;0m     super().__init__(
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 479, in __init__
[0;36m(APIServer pid=376114)[0;0m     with launch_core_engines(vllm_config, executor_class, log_stats) as (
[0;36m(APIServer pid=376114)[0;0m   File "/usr/lib/python3.12/contextlib.py", line 144, in __exit__
[0;36m(APIServer pid=376114)[0;0m     next(self.gen)
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 933, in launch_core_engines
[0;36m(APIServer pid=376114)[0;0m     wait_for_engine_startup(
[0;36m(APIServer pid=376114)[0;0m   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 992, in wait_for_engine_startup
[0;36m(APIServer pid=376114)[0;0m     raise RuntimeError(
[0;36m(APIServer pid=376114)[0;0m RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
[vllm-coder] model=/opt/models/qwen2_5_14b_instruct_awq host=127.0.0.1 port=8002 ctx=16384 max_seqs=6
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [utils.py:325] 
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [utils.py:325]        █     █     █▄   ▄█
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [utils.py:325]  ▄▄ ▄█ █     █     █ ▀▄▀ █  version 0.15.1
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [utils.py:325]   █▄█▀ █     █     █     █  model   /opt/models/qwen2_5_14b_instruct_awq
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [utils.py:325]    ▀▀  ▀▀▀▀▀ ▀▀▀▀▀ ▀     ▀
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [utils.py:325] 
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [utils.py:261] non-default args: {'model_tag': '/opt/models/qwen2_5_14b_instruct_awq', 'api_server_count': 1, 'host': '127.0.0.1', 'port': 8002, 'uvicorn_log_level': 'warning', 'enable_auto_tool_choice': True, 'tool_call_parser': 'hermes', 'model': '/opt/models/qwen2_5_14b_instruct_awq', 'max_model_len': 16384, 'quantization': 'awq', 'served_model_name': ['local-coder'], 'max_num_seqs': 6}
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [model.py:541] Resolved architecture: Qwen2ForCausalLM
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [model.py:1561] Using max model len 16384
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [awq_marlin.py:166] Detected that the model can run with awq_marlin, however you specified quantization=awq explicitly, so forcing awq. Use quantization=awq_marlin for faster inference
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [scheduler.py:226] Chunked prefill is enabled with max_num_batched_tokens=2048.
[0;36m(APIServer pid=376429)[0;0m INFO 02-23 16:58:32 [vllm.py:624] Asynchronous scheduling is enabled.
$ curl -sv http://127.0.0.1:8002/health -m 5 || true
### STEP 3/4 minimal remediation - reduce coder GPU utilization
$ rg -n "gpu-memory-utilization|VLLM_CODER_GPU_MEMORY_UTILIZATION" /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh /tmp/wt_merge_main/scripts/vllm_launch_coder.sh
/home/jeebs/src/clawd/scripts/vllm_launch_coder.sh:32:  --gpu-memory-utilization "$GPU_UTIL" \
$ sed -n '1,200p' /home/jeebs/src/clawd/scripts/vllm_launch_coder.sh
#!/usr/bin/env bash
set -euo pipefail

# Dedicated local coder lane for OpenClaw routing.
# Defaults can be overridden with env:
#   VLLM_CODER_MODEL
#   VLLM_CODER_HOST
#   VLLM_CODER_PORT
#   VLLM_CODER_GPU_UTIL
#   VLLM_CODER_CTX_LEN
#   VLLM_CODER_MAX_SEQS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV="${VLLM_CODER_VENV:-$REPO_ROOT/.venv-vllm}"

MODEL="${VLLM_CODER_MODEL:-/opt/models/qwen2_5_14b_instruct_awq}"
HOST="${VLLM_CODER_HOST:-127.0.0.1}"
PORT="${VLLM_CODER_PORT:-8002}"
GPU_UTIL="${VLLM_CODER_GPU_UTIL:-0.90}"
CTX_LEN="${VLLM_CODER_CTX_LEN:-16384}"
MAX_SEQS="${VLLM_CODER_MAX_SEQS:-6}"

echo "[vllm-coder] model=$MODEL host=$HOST port=$PORT ctx=$CTX_LEN max_seqs=$MAX_SEQS"

exec "$VENV/bin/vllm" serve "$MODEL" \
  --served-model-name local-coder \
  --host "$HOST" \
  --port "$PORT" \
  --quantization awq \
  --dtype auto \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-model-len "$CTX_LEN" \
  --max-num-seqs "$MAX_SEQS" \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --uvicorn-log-level warning
### STEP 4.3 classification evidence - GPU/port contention
$ nvidia-smi
Mon Feb 23 17:07:59 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 590.48.01              Driver Version: 590.48.01      CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3090        Off |   00000000:01:00.0  On |                  N/A |
|  0%   35C    P2            119W /  350W |   23309MiB /  24576MiB |      8%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            1796      G   /usr/lib/xorg/Xorg                      308MiB |
|    0   N/A  N/A            2126      G   /usr/bin/gnome-shell                     61MiB |
|    0   N/A  N/A            4656      C   VLLM::EngineCore                      22094MiB |
|    0   N/A  N/A            7089      G   .../7836/usr/lib/firefox/firefox        330MiB |
|    0   N/A  N/A           13535      G   /usr/share/code/code                     67MiB |
|    0   N/A  N/A           16007      G   ...6899/usr/bin/telegram-desktop          4MiB |
|    0   N/A  N/A          385952      C   VLLM::EngineCore                        298MiB |
+-----------------------------------------------------------------------------------------+
$ ss -ltnp | grep ':8002' || true
$ ss -ltnp | grep ':8001' || true
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=4149,fd=25))             
### STEP 4 minimal remediation - free VRAM by pausing assistant lane
$ systemctl --user status openclaw-vllm.service --no-pager -l || true
● openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: activating (auto-restart) (Result: exit-code) since Mon 2026-02-23 17:11:27 AEST; 2s ago
    Process: 389434 ExecStart=/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes (code=exited, status=1/FAILURE)
   Main PID: 389434 (code=exited, status=1/FAILURE)
        CPU: 16.661s
$ systemctl --user stop openclaw-vllm.service || true
$ systemctl --user restart openclaw-vllm-coder.service || true
$ sleep 6
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 17:12:59 AEST; 6s ago
   Main PID: 389828 (vllm)
      Tasks: 64 (limit: 38169)
     Memory: 897.1M (peak: 897.1M)
        CPU: 10.104s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             ├─389828 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─389902 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─389903 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=35, pipe_handle=37)" --multiprocessing-fork

Feb 23 17:12:59 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ ss -ltnp | grep ':8002' || true
$ curl -sf http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN
VLLM_CODER_DOWN
$ nvidia-smi
Mon Feb 23 17:13:05 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 590.48.01              Driver Version: 590.48.01      CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3090        Off |   00000000:01:00.0  On |                  N/A |
|  0%   32C    P8             40W /  350W |   22986MiB /  24576MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            1796      G   /usr/lib/xorg/Xorg                      308MiB |
|    0   N/A  N/A            2126      G   /usr/bin/gnome-shell                     60MiB |
|    0   N/A  N/A            4656      C   VLLM::EngineCore                      22094MiB |
|    0   N/A  N/A            7089      G   .../7836/usr/lib/firefox/firefox        330MiB |
|    0   N/A  N/A           13535      G   /usr/share/code/code                     46MiB |
|    0   N/A  N/A           16007      G   ...6899/usr/bin/telegram-desktop          4MiB |
+-----------------------------------------------------------------------------------------+
### STEP 4.3b - identify conflicting VLLM process
$ systemctl --user status openclaw-vllm.service --no-pager -l || true
○ openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: inactive (dead) (Result: exit-code) since Mon 2026-02-23 17:11:29 AEST; 13min ago
   Duration: 11.368s
    Process: 389434 ExecStart=/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes (code=exited, status=1/FAILURE)
   Main PID: 389434 (code=exited, status=1/FAILURE)
        CPU: 16.661s

Feb 23 17:11:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopped openclaw-vllm.service - OpenClaw local vLLM server.
Feb 23 17:11:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm.service: Consumed 16.661s CPU time.
$ ps -p 4656 -o pid,ppid,user,etime,cmd --forest || true
    PID    PPID USER         ELAPSED CMD
   4656    4149 jeebs       11:35:40 VLLM::EngineCore
$ pgrep -a -f vllm | sed -n '1,120p'
4149 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
4655 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
396557 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
396580 /bin/bash -lc set -euo pipefail cd /tmp/wt_merge_main AUD="workspace/audit/dali_canary_timer_vram_guard_envelope_20260223T003420Z.md" {   echo "### STEP 4.3b - identify conflicting VLLM process";   echo "$ systemctl --user status openclaw-vllm.service --no-pager -l || true";   systemctl --user status openclaw-vllm.service --no-pager -l || true;   echo "$ ps -p 4656 -o pid,ppid,user,etime,cmd --forest || true";   ps -p 4656 -o pid,ppid,user,etime,cmd --forest || true;   echo "$ pgrep -a -f vllm | sed -n '1,120p'";   pgrep -a -f vllm | sed -n '1,120p'; } | tee -a "$AUD"
396584 /bin/bash -lc set -euo pipefail cd /tmp/wt_merge_main AUD="workspace/audit/dali_canary_timer_vram_guard_envelope_20260223T003420Z.md" {   echo "### STEP 4.3b - identify conflicting VLLM process";   echo "$ systemctl --user status openclaw-vllm.service --no-pager -l || true";   systemctl --user status openclaw-vllm.service --no-pager -l || true;   echo "$ ps -p 4656 -o pid,ppid,user,etime,cmd --forest || true";   ps -p 4656 -o pid,ppid,user,etime,cmd --forest || true;   echo "$ pgrep -a -f vllm | sed -n '1,120p'";   pgrep -a -f vllm | sed -n '1,120p'; } | tee -a "$AUD"
### STEP 4 minimal remediation - stop stale assistant process and re-test coder
$ kill 4149 || true
$ sleep 3
$ pgrep -a -f '/vllm serve .*--served-model-name local-assistant|VLLM::EngineCore' || true
400286 VLLM::EngineCore
400352 /bin/bash -lc set -euo pipefail cd /tmp/wt_merge_main AUD="workspace/audit/dali_canary_timer_vram_guard_envelope_20260223T003420Z.md" {   echo "### STEP 4 minimal remediation - stop stale assistant process and re-test coder";   echo "$ kill 4149 || true";   kill 4149 || true;   echo "$ sleep 3";   sleep 3;   echo "$ pgrep -a -f '/vllm serve .*--served-model-name local-assistant|VLLM::EngineCore' || true";   pgrep -a -f '/vllm serve .*--served-model-name local-assistant|VLLM::EngineCore' || true;   echo "$ nvidia-smi";   nvidia-smi;   echo "$ systemctl --user restart openclaw-vllm-coder.service || true";   systemctl --user restart openclaw-vllm-coder.service || true;   echo "$ sleep 8";   sleep 8;   echo "$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true";   systemctl --user status openclaw-vllm-coder.service --no-pager -l || true;   echo "$ ss -ltnp | grep ':8002' || true";   ss -ltnp | grep ':8002' || true;   echo "$ curl -sf http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN";   curl -sf http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN; } | tee -a "$AUD"
400356 /bin/bash -lc set -euo pipefail cd /tmp/wt_merge_main AUD="workspace/audit/dali_canary_timer_vram_guard_envelope_20260223T003420Z.md" {   echo "### STEP 4 minimal remediation - stop stale assistant process and re-test coder";   echo "$ kill 4149 || true";   kill 4149 || true;   echo "$ sleep 3";   sleep 3;   echo "$ pgrep -a -f '/vllm serve .*--served-model-name local-assistant|VLLM::EngineCore' || true";   pgrep -a -f '/vllm serve .*--served-model-name local-assistant|VLLM::EngineCore' || true;   echo "$ nvidia-smi";   nvidia-smi;   echo "$ systemctl --user restart openclaw-vllm-coder.service || true";   systemctl --user restart openclaw-vllm-coder.service || true;   echo "$ sleep 8";   sleep 8;   echo "$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true";   systemctl --user status openclaw-vllm-coder.service --no-pager -l || true;   echo "$ ss -ltnp | grep ':8002' || true";   ss -ltnp | grep ':8002' || true;   echo "$ curl -sf http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN";   curl -sf http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN; } | tee -a "$AUD"
$ nvidia-smi
Mon Feb 23 17:31:59 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 590.48.01              Driver Version: 590.48.01      CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3090        Off |   00000000:01:00.0  On |                  N/A |
|  0%   36C    P2            143W /  350W |    2891MiB /  24576MiB |      2%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            1796      G   /usr/lib/xorg/Xorg                      316MiB |
|    0   N/A  N/A            2126      G   /usr/bin/gnome-shell                     62MiB |
|    0   N/A  N/A            7089      G   .../7836/usr/lib/firefox/firefox        381MiB |
|    0   N/A  N/A           13535      G   /usr/share/code/code                     52MiB |
|    0   N/A  N/A           16007      G   ...6899/usr/bin/telegram-desktop          4MiB |
|    0   N/A  N/A          398017      G   /usr/bin/nautilus                        17MiB |
|    0   N/A  N/A          400286      C   VLLM::EngineCore                       1914MiB |
+-----------------------------------------------------------------------------------------+
$ systemctl --user restart openclaw-vllm-coder.service || true
$ sleep 8
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 17:33:29 AEST; 8s ago
   Main PID: 400834 (vllm)
      Tasks: 65 (limit: 38169)
     Memory: 1.0G (peak: 1.0G)
        CPU: 12.050s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             ├─400834 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─400895 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─400896 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=35, pipe_handle=37)" --multiprocessing-fork

Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ ss -ltnp | grep ':8002' || true
$ curl -sf http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN
VLLM_CODER_DOWN
### STEP 5c - delayed readiness check
$ sleep 30
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 17:33:29 AEST; 16min ago
   Main PID: 400834 (vllm)
      Tasks: 161 (limit: 38169)
     Memory: 2.4G (peak: 2.4G)
        CPU: 51.399s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             ├─400834 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─400895 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─400896 VLLM::EngineCore

Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ systemctl --user show -p MainPID,SubState,Result,ExecMainStatus,NRestarts openclaw-vllm-coder.service || true
MainPID=400834
Result=success
NRestarts=0
ExecMainStatus=0
SubState=running
$ journalctl --user -u openclaw-vllm-coder.service -n 80 --no-pager || true
Feb 23 17:27:56 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:28:07 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:28:07 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:28:07 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.736s CPU time.
Feb 23 17:28:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 56.
Feb 23 17:28:13 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:28:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:28:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:28:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.656s CPU time.
Feb 23 17:28:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 57.
Feb 23 17:28:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:28:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:28:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:28:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.668s CPU time.
Feb 23 17:28:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 58.
Feb 23 17:28:46 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:28:57 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:28:57 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:28:57 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.691s CPU time.
Feb 23 17:29:02 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 59.
Feb 23 17:29:02 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:29:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:29:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:29:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.833s CPU time.
Feb 23 17:29:18 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 60.
Feb 23 17:29:18 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:29:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:29:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:29:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.680s CPU time.
Feb 23 17:29:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 61.
Feb 23 17:29:35 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:29:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:29:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:29:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.669s CPU time.
Feb 23 17:29:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 62.
Feb 23 17:29:52 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.757s CPU time.
Feb 23 17:30:08 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 63.
Feb 23 17:30:08 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.706s CPU time.
Feb 23 17:30:25 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 64.
Feb 23 17:30:25 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:36 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:36 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:36 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.759s CPU time.
Feb 23 17:30:41 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 65.
Feb 23 17:30:41 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.737s CPU time.
Feb 23 17:30:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 66.
Feb 23 17:30:58 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:31:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:31:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.737s CPU time.
Feb 23 17:31:14 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 67.
Feb 23 17:31:14 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:31:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:31:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.669s CPU time.
Feb 23 17:31:31 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 68.
Feb 23 17:31:31 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:31:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:31:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.674s CPU time.
Feb 23 17:31:47 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 69.
Feb 23 17:31:47 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:59 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopping openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)...
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: State 'stop-sigterm' timed out. Killing.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Killing process 400232 (vllm) with signal SIGKILL.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Killing process 400285 (python3.12) with signal SIGKILL.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=killed, status=9/KILL
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'timeout'.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopped openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 19.936s CPU time.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ tail -n 80 ~/.local/state/openclaw/vllm-coder.log || true
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:33:34 [awq_marlin.py:166] Detected that the model can run with awq_marlin, however you specified quantization=awq explicitly, so forcing awq. Use quantization=awq_marlin for faster inference
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:33:34 [scheduler.py:226] Chunked prefill is enabled with max_num_batched_tokens=2048.
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:33:34 [vllm.py:624] Asynchronous scheduling is enabled.
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:39 [core.py:96] Initializing a V1 LLM engine (v0.15.1) with config: model='/opt/models/qwen2_5_14b_instruct_awq', speculative_config=None, tokenizer='/opt/models/qwen2_5_14b_instruct_awq', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=16384, download_dir=None, load_format=auto, tensor_parallel_size=1, pipeline_parallel_size=1, data_parallel_size=1, disable_custom_all_reduce=False, quantization=awq, enforce_eager=False, enable_return_routed_experts=False, kv_cache_dtype=auto, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False, enable_mfu_metrics=False, enable_mm_processor_stats=False, enable_logging_iteration_details=False), seed=0, served_model_name=local-coder, enable_prefix_caching=True, enable_chunked_prefill=True, pooler_config=None, compilation_config={'level': None, 'mode': <CompilationMode.VLLM_COMPILE: 3>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['none'], 'splitting_ops': ['vllm::unified_attention', 'vllm::unified_attention_with_output', 'vllm::unified_mla_attention', 'vllm::unified_mla_attention_with_output', 'vllm::mamba_mixer2', 'vllm::mamba_mixer', 'vllm::short_conv', 'vllm::linear_attention', 'vllm::plamo2_mamba_mixer', 'vllm::gdn_attention_core', 'vllm::kda_attention', 'vllm::sparse_attn_indexer', 'vllm::rocm_aiter_sparse_attn_indexer', 'vllm::unified_kv_cache_update'], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_split_points': [2048], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE: (2, 1)>, 'cudagraph_num_of_warmups': 1, 'cudagraph_capture_sizes': [1, 2, 4, 8], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': False, 'fuse_act_quant': False, 'fuse_attn_quant': False, 'eliminate_noops': True, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 8, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': True}, 'local_cache_dir': None, 'static_all_moe_layers': []}
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:39 [parallel_state.py:1212] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://192.168.0.162:54749 backend=nccl
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:39 [parallel_state.py:1423] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank N/A
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:39 [gpu_model_runner.py:4033] Starting to load model /opt/models/qwen2_5_14b_instruct_awq...
[0;36m(EngineCore_DP0 pid=400896)[0;0m /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/tvm_ffi/_optional_torch_c_dlpack.py:174: UserWarning: Failed to JIT torch c dlpack extension, EnvTensorAllocator will not be enabled.
[0;36m(EngineCore_DP0 pid=400896)[0;0m We recommend installing via `pip install torch-c-dlpack-ext`
[0;36m(EngineCore_DP0 pid=400896)[0;0m   warnings.warn(
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:41 [cuda.py:364] Using FLASH_ATTN attention backend out of potential backends: ('FLASH_ATTN', 'FLASHINFER', 'TRITON_ATTN', 'FLEX_ATTENTION')
[0;36m(EngineCore_DP0 pid=400896)[0;0m Loading safetensors checkpoint shards:   0% Completed | 0/3 [00:00<?, ?it/s]
[0;36m(EngineCore_DP0 pid=400896)[0;0m Loading safetensors checkpoint shards:  33% Completed | 1/3 [00:00<00:00,  3.05it/s]
[0;36m(EngineCore_DP0 pid=400896)[0;0m Loading safetensors checkpoint shards:  67% Completed | 2/3 [00:01<00:00,  1.79it/s]
[0;36m(EngineCore_DP0 pid=400896)[0;0m Loading safetensors checkpoint shards: 100% Completed | 3/3 [00:01<00:00,  1.61it/s]
[0;36m(EngineCore_DP0 pid=400896)[0;0m Loading safetensors checkpoint shards: 100% Completed | 3/3 [00:01<00:00,  1.72it/s]
[0;36m(EngineCore_DP0 pid=400896)[0;0m 
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:43 [default_loader.py:291] Loading weights took 1.76 seconds
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:43 [gpu_model_runner.py:4130] Model loading took 9.38 GiB memory and 3.465704 seconds
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:50 [backends.py:812] Using cache directory: /home/jeebs/.cache/vllm/torch_compile_cache/476e4cf496/rank_0_0/backbone for vLLM's torch.compile
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:50 [backends.py:872] Dynamo bytecode transform time: 7.29 s
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:57 [backends.py:302] Cache the graph of compile range (1, 2048) for later use
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:59 [backends.py:319] Compiling a graph for compile range (1, 2048) takes 2.53 s
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:33:59 [monitor.py:34] torch.compile takes 9.82 s in total
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:34:00 [gpu_worker.py:356] Available KV cache memory: 11.34 GiB
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:34:00 [kv_cache_utils.py:1307] GPU KV cache size: 61,936 tokens
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:34:00 [kv_cache_utils.py:1312] Maximum concurrency for 16,384 tokens per request: 3.78x
[0;36m(EngineCore_DP0 pid=400896)[0;0m Capturing CUDA graphs (mixed prefill-decode, PIECEWISE):   0%|          | 0/4 [00:00<?, ?it/s]Capturing CUDA graphs (mixed prefill-decode, PIECEWISE):  25%|██▌       | 1/4 [00:00<00:00,  5.97it/s]Capturing CUDA graphs (mixed prefill-decode, PIECEWISE):  50%|█████     | 2/4 [00:00<00:00,  6.18it/s]Capturing CUDA graphs (mixed prefill-decode, PIECEWISE):  75%|███████▌  | 3/4 [00:00<00:00,  6.29it/s]Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 100%|██████████| 4/4 [00:00<00:00,  6.35it/s]Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 100%|██████████| 4/4 [00:00<00:00,  6.29it/s]
[0;36m(EngineCore_DP0 pid=400896)[0;0m Capturing CUDA graphs (decode, FULL):   0%|          | 0/3 [00:00<?, ?it/s]Capturing CUDA graphs (decode, FULL):  33%|███▎      | 1/3 [00:00<00:00,  6.14it/s]Capturing CUDA graphs (decode, FULL):  67%|██████▋   | 2/3 [00:00<00:00,  6.38it/s]Capturing CUDA graphs (decode, FULL): 100%|██████████| 3/3 [00:00<00:00,  6.49it/s]Capturing CUDA graphs (decode, FULL): 100%|██████████| 3/3 [00:00<00:00,  6.43it/s]
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:34:01 [gpu_model_runner.py:5063] Graph capturing finished in 1 secs, took 0.41 GiB
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:34:01 [core.py:272] init engine (profile, create kv cache, warmup model) took 18.29 seconds
[0;36m(EngineCore_DP0 pid=400896)[0;0m INFO 02-23 17:34:02 [vllm.py:624] Asynchronous scheduling is enabled.
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [api_server.py:665] Supported tasks: ['generate']
[0;36m(APIServer pid=400834)[0;0m WARNING 02-23 17:34:02 [model.py:1371] Default vLLM sampling parameters have been overridden by the model's `generation_config.json`: `{'repetition_penalty': 1.05, 'temperature': 0.7, 'top_k': 20, 'top_p': 0.8}`. If this is not intended, please relaunch vLLM instance with `--generation-config vllm`.
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [serving.py:273] "auto" tool choice has been enabled.
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [serving.py:273] "auto" tool choice has been enabled.
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [serving.py:177] Warming up chat template processing...
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [hf.py:310] Detected the chat template content format to be 'string'. You can set `--chat-template-content-format` to override this.
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [serving.py:212] Chat template warmup completed in 182.7ms
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [serving.py:273] "auto" tool choice has been enabled.
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [api_server.py:946] Starting vLLM API server 0 on http://127.0.0.1:8002
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:38] Available routes are:
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /openapi.json, Methods: HEAD, GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /docs, Methods: HEAD, GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /docs/oauth2-redirect, Methods: HEAD, GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /redoc, Methods: HEAD, GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /scale_elastic_ep, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /is_scaling_elastic_ep, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /tokenize, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /detokenize, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /inference/v1/generate, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /pause, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /resume, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /is_paused, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /metrics, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /health, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/chat/completions, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/chat/completions/render, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/responses, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/responses/{response_id}, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/responses/{response_id}/cancel, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/audio/transcriptions, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/audio/translations, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/completions, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/completions/render, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/messages, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/models, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /load, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /version, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /ping, Methods: GET
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /ping, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /invocations, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /classify, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/embeddings, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /score, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/score, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /rerank, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v1/rerank, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /v2/rerank, Methods: POST
[0;36m(APIServer pid=400834)[0;0m INFO 02-23 17:34:02 [launcher.py:46] Route: /pooling, Methods: POST
$ ss -ltnp | grep ':8002' || true
LISTEN 0      2048       127.0.0.1:8002       0.0.0.0:*    users:(("vllm",pid=400834,fd=25))           
$ curl -fsS -m 5 http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN
VLLM_CODER_OK
### STEP 5 final diagnostics/canary after remediation
$ node /tmp/wt_merge_main/scripts/system2/provider_diag.js || true
=== System-2 Provider Diagnostics (safe) ===
freecompute_enabled=false
freecompute_env_keys_seen=(none)
secrets_bridge_enabled=false

local_vllm_endpoint_present=false
local_vllm_models_fetch_ok=false
local_vllm_models_count=0
local_vllm_generation_probe_ok=false
local_vllm_generation_probe_reason=unknown
coder_vllm_endpoint=http://127.0.0.1:8002/v1/models
coder_vllm_endpoint_present=false
coder_vllm_models_fetch_ok=false
coder_vllm_models_count=0
coder_status=DOWN
coder_degraded_reason=UNAVAILABLE
coder_degraded_note=journal_unavailable
replay_log_path=/home/jeebs/.local/share/openclaw/replay/replay.jsonl
replay_log_writable=false
replay_log_reason=EACCES
event_envelope_schema=openclaw.event_envelope.v1

event_envelope_log_path=/home/jeebs/.local/share/openclaw/events/gate_health.jsonl
event_envelope_write_ok=false
event_envelope_write_reason=EACCES

canary_recommendations:
- run: python3 scripts/dali_canary_runner.py
- optional timer: systemctl --user enable --now openclaw-canary.timer
- if coder DEGRADED with VRAM_LOW, reduce load or raise VLLM_CODER_MIN_FREE_VRAM_MB policy

providers:
- gemini: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GEMINI_API_KEY
- groq: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GROQ_API_KEY
- local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed auth_env_keys=OPENCLAW_VLLM_API_KEY
- minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_MINIMAX_PORTAL_API_KEY
- openrouter: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_OPENROUTER_API_KEY
- qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_QWEN_API_KEY

providers_summary:
gemini: configured=no enabled=yes eligible=no reason=missing_api_key
groq: configured=no enabled=yes eligible=no reason=missing_api_key
local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed
minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key
openrouter: configured=no enabled=yes eligible=no reason=missing_api_key
qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key
$ python3 /tmp/wt_merge_main/scripts/dali_canary_runner.py || true
CANARY status=FAIL coder=DOWN replay=NOACCESS pairing=UNHEALTHY ts=2026-02-23T07:50:32Z
### STEP 5d - reconcile runtime state
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 17:33:29 AEST; 48min ago
   Main PID: 400834 (vllm)
      Tasks: 161 (limit: 38169)
     Memory: 2.4G (peak: 2.4G)
        CPU: 1min 9.220s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             ├─400834 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─400895 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─400896 VLLM::EngineCore

Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ systemctl --user status openclaw-vllm.service --no-pager -l || true
○ openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: inactive (dead) (Result: exit-code) since Mon 2026-02-23 17:11:29 AEST; 1h 10min ago
   Duration: 11.368s
    Process: 389434 ExecStart=/home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes (code=exited, status=1/FAILURE)
   Main PID: 389434 (code=exited, status=1/FAILURE)
        CPU: 16.661s

Feb 23 17:11:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopped openclaw-vllm.service - OpenClaw local vLLM server.
Feb 23 17:11:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm.service: Consumed 16.661s CPU time.
$ ss -ltnp | grep ':8002' || true
LISTEN 0      2048       127.0.0.1:8002       0.0.0.0:*    users:(("vllm",pid=400834,fd=25))           
$ curl -fsS -m 5 http://127.0.0.1:8002/health && echo VLLM_CODER_OK || echo VLLM_CODER_DOWN
VLLM_CODER_OK
$ nvidia-smi
Mon Feb 23 18:22:00 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 590.48.01              Driver Version: 590.48.01      CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3090        Off |   00000000:01:00.0  On |                  N/A |
|  0%   30C    P8             46W /  350W |   23216MiB /  24576MiB |     43%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            1796      G   /usr/lib/xorg/Xorg                      316MiB |
|    0   N/A  N/A            2126      G   /usr/bin/gnome-shell                     60MiB |
|    0   N/A  N/A            7089      G   .../7836/usr/lib/firefox/firefox        248MiB |
|    0   N/A  N/A           13535      G   /usr/share/code/code                     65MiB |
|    0   N/A  N/A           16007      G   ...6899/usr/bin/telegram-desktop          4MiB |
|    0   N/A  N/A          398017      G   /usr/bin/nautilus                        16MiB |
|    0   N/A  N/A          400896      C   VLLM::EngineCore                      22362MiB |
+-----------------------------------------------------------------------------------------+
### STEP 5e - steady-state diagnostics
$ node /tmp/wt_merge_main/scripts/system2/provider_diag.js || true
=== System-2 Provider Diagnostics (safe) ===
freecompute_enabled=false
freecompute_env_keys_seen=(none)
secrets_bridge_enabled=false

local_vllm_endpoint_present=false
local_vllm_models_fetch_ok=false
local_vllm_models_count=0
local_vllm_generation_probe_ok=false
local_vllm_generation_probe_reason=unknown
coder_vllm_endpoint=http://127.0.0.1:8002/v1/models
coder_vllm_endpoint_present=false
coder_vllm_models_fetch_ok=false
coder_vllm_models_count=0
coder_status=DOWN
coder_degraded_reason=UNAVAILABLE
coder_degraded_note=journal_unavailable
replay_log_path=/home/jeebs/.local/share/openclaw/replay/replay.jsonl
replay_log_writable=false
replay_log_reason=EACCES
event_envelope_schema=openclaw.event_envelope.v1

event_envelope_log_path=/home/jeebs/.local/share/openclaw/events/gate_health.jsonl
event_envelope_write_ok=false
event_envelope_write_reason=EACCES

canary_recommendations:
- run: python3 scripts/dali_canary_runner.py
- optional timer: systemctl --user enable --now openclaw-canary.timer
- if coder DEGRADED with VRAM_LOW, reduce load or raise VLLM_CODER_MIN_FREE_VRAM_MB policy

providers:
- gemini: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GEMINI_API_KEY
- groq: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GROQ_API_KEY
- local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed auth_env_keys=OPENCLAW_VLLM_API_KEY
- minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_MINIMAX_PORTAL_API_KEY
- openrouter: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_OPENROUTER_API_KEY
- qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_QWEN_API_KEY

providers_summary:
gemini: configured=no enabled=yes eligible=no reason=missing_api_key
groq: configured=no enabled=yes eligible=no reason=missing_api_key
local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed
minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key
openrouter: configured=no enabled=yes eligible=no reason=missing_api_key
qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key
$ python3 /tmp/wt_merge_main/scripts/dali_canary_runner.py || true
CANARY status=FAIL coder=DOWN replay=NOACCESS pairing=UNHEALTHY ts=2026-02-23T08:22:10Z
### STEP 5f - host-context diagnostics (escalated)
$ curl -fsS -m 5 http://127.0.0.1:8002/health && echo HOST_CURL_OK || echo HOST_CURL_DOWN
HOST_CURL_OK
$ node /tmp/wt_merge_main/scripts/system2/provider_diag.js || true
=== System-2 Provider Diagnostics (safe) ===
freecompute_enabled=false
freecompute_env_keys_seen=(none)
secrets_bridge_enabled=false

local_vllm_endpoint_present=false
local_vllm_models_fetch_ok=false
local_vllm_models_count=0
local_vllm_generation_probe_ok=false
local_vllm_generation_probe_reason=unknown
coder_vllm_endpoint=http://127.0.0.1:8002/v1/models
coder_vllm_endpoint_present=true
coder_vllm_models_fetch_ok=true
coder_vllm_models_count=1
coder_status=UP
coder_degraded_reason=OK
coder_degraded_note=endpoint_reachable
replay_log_path=/home/jeebs/.local/share/openclaw/replay/replay.jsonl
replay_log_writable=true
replay_log_reason=ok
event_envelope_schema=openclaw.event_envelope.v1

event_envelope_log_path=/home/jeebs/.local/share/openclaw/events/gate_health.jsonl
event_envelope_write_ok=true
event_envelope_write_reason=ok

canary_recommendations:
- run: python3 scripts/dali_canary_runner.py
- optional timer: systemctl --user enable --now openclaw-canary.timer
- if coder DEGRADED with VRAM_LOW, reduce load or raise VLLM_CODER_MIN_FREE_VRAM_MB policy

providers:
- gemini: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GEMINI_API_KEY
- groq: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GROQ_API_KEY
- local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed auth_env_keys=OPENCLAW_VLLM_API_KEY
- minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_MINIMAX_PORTAL_API_KEY
- openrouter: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_OPENROUTER_API_KEY
- qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_QWEN_API_KEY

providers_summary:
gemini: configured=no enabled=yes eligible=no reason=missing_api_key
groq: configured=no enabled=yes eligible=no reason=missing_api_key
local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed
minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key
openrouter: configured=no enabled=yes eligible=no reason=missing_api_key
qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key
$ python3 /tmp/wt_merge_main/scripts/dali_canary_runner.py || true
CANARY status=OK coder=UP replay=WRITABLE pairing=OK ts=2026-02-23T08:22:33Z
### STEP 6 - periodic canary enablement
$ systemctl --user daemon-reload
$ systemctl --user enable --now openclaw-canary.timer
$ systemctl --user status openclaw-canary.timer --no-pager -l
● openclaw-canary.timer - Run OpenClaw Dali Canary every 30 minutes (opt-in)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-canary.timer; enabled; preset: enabled)
     Active: active (waiting) since Mon 2026-02-23 12:53:59 AEST; 5h 29min ago
    Trigger: Mon 2026-02-23 18:24:45 AEST; 54s left
   Triggers: ● openclaw-canary.service

Feb 23 12:53:59 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-canary.timer - Run OpenClaw Dali Canary every 30 minutes (opt-in).
### Final steady-state confirmation
$ systemctl --user is-active openclaw-vllm-coder.service
active
$ curl -fsS -m 5 http://127.0.0.1:8002/health && echo FINAL_CODER_HEALTH_OK
FINAL_CODER_HEALTH_OK
\n## Micro-hardening: exec-bit self-heal + anti-thrash - 2026-02-23T08:42:07Z
$ systemctl --user daemon-reload
$ systemctl --user restart openclaw-vllm-coder.service || true
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 18:42:08 AEST; 3ms ago
   Main PID: 404593 (vllm)
      Tasks: 1 (limit: 38169)
     Memory: 952.0K (peak: 1.5M)
        CPU: 2ms
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             └─404593 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning

Feb 23 18:42:08 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ systemctl --user show -p StartLimitIntervalUSec,StartLimitBurst,NRestarts,Result openclaw-vllm-coder.service || true
Result=success
NRestarts=0
StartLimitIntervalUSec=1min
StartLimitBurst=5
$ journalctl --user -u openclaw-vllm-coder.service -n 80 --no-pager || true
Feb 23 17:28:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 56.
Feb 23 17:28:13 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:28:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:28:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:28:24 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.656s CPU time.
Feb 23 17:28:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 57.
Feb 23 17:28:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:28:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:28:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:28:40 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.668s CPU time.
Feb 23 17:28:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 58.
Feb 23 17:28:46 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:28:57 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:28:57 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:28:57 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.691s CPU time.
Feb 23 17:29:02 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 59.
Feb 23 17:29:02 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:29:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:29:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:29:13 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.833s CPU time.
Feb 23 17:29:18 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 60.
Feb 23 17:29:18 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:29:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:29:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:29:30 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.680s CPU time.
Feb 23 17:29:35 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 61.
Feb 23 17:29:35 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:29:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:29:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:29:46 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.669s CPU time.
Feb 23 17:29:52 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 62.
Feb 23 17:29:52 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:03 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.757s CPU time.
Feb 23 17:30:08 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 63.
Feb 23 17:30:08 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:20 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.706s CPU time.
Feb 23 17:30:25 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 64.
Feb 23 17:30:25 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:36 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:36 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:36 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.759s CPU time.
Feb 23 17:30:41 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 65.
Feb 23 17:30:41 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:30:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:30:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:30:53 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.737s CPU time.
Feb 23 17:30:58 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 66.
Feb 23 17:30:58 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:31:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:31:09 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.737s CPU time.
Feb 23 17:31:14 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 67.
Feb 23 17:31:14 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:31:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:31:26 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.669s CPU time.
Feb 23 17:31:31 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 68.
Feb 23 17:31:31 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=exited, status=1/FAILURE
Feb 23 17:31:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'exit-code'.
Feb 23 17:31:42 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 16.674s CPU time.
Feb 23 17:31:47 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Scheduled restart job, restart counter is at 69.
Feb 23 17:31:47 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:31:59 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopping openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)...
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: State 'stop-sigterm' timed out. Killing.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Killing process 400232 (vllm) with signal SIGKILL.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Killing process 400285 (python3.12) with signal SIGKILL.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Main process exited, code=killed, status=9/KILL
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Failed with result 'timeout'.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopped openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 19.936s CPU time.
Feb 23 17:33:29 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 18:42:07 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopping openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)...
Feb 23 18:42:08 jeebs-Z490-AORUS-MASTER systemd[1648]: Stopped openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
Feb 23 18:42:08 jeebs-Z490-AORUS-MASTER systemd[1648]: openclaw-vllm-coder.service: Consumed 1min 23.011s CPU time, 2.4G memory peak, 0B memory swap peak.
Feb 23 18:42:08 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ curl -fsS -m 5 http://127.0.0.1:8002/health && echo FINAL_CODER_HEALTH_OK || echo FINAL_CODER_HEALTH_DOWN
FINAL_CODER_HEALTH_DOWN
$ node scripts/system2/provider_diag.js || true
=== System-2 Provider Diagnostics (safe) ===
freecompute_enabled=false
freecompute_env_keys_seen=(none)
secrets_bridge_enabled=false

local_vllm_endpoint_present=false
local_vllm_models_fetch_ok=false
local_vllm_models_count=0
local_vllm_generation_probe_ok=false
local_vllm_generation_probe_reason=unknown
coder_vllm_endpoint=http://127.0.0.1:8002/v1/models
coder_vllm_endpoint_present=false
coder_vllm_models_fetch_ok=false
coder_vllm_models_count=0
coder_status=DOWN
coder_degraded_reason=NO_BLOCK_MARKER
coder_degraded_note=journal_no_marker
replay_log_path=/home/jeebs/.local/share/openclaw/replay/replay.jsonl
replay_log_writable=true
replay_log_reason=ok
event_envelope_schema=openclaw.event_envelope.v1

event_envelope_log_path=/home/jeebs/.local/share/openclaw/events/gate_health.jsonl
event_envelope_write_ok=true
event_envelope_write_reason=ok

canary_recommendations:
- run: python3 scripts/dali_canary_runner.py
- optional timer: systemctl --user enable --now openclaw-canary.timer
- if coder DEGRADED with VRAM_LOW, reduce load or raise VLLM_CODER_MIN_FREE_VRAM_MB policy

providers:
- gemini: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GEMINI_API_KEY
- groq: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GROQ_API_KEY
- local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed auth_env_keys=OPENCLAW_VLLM_API_KEY
- minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_MINIMAX_PORTAL_API_KEY
- openrouter: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_OPENROUTER_API_KEY
- qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_QWEN_API_KEY

providers_summary:
gemini: configured=no enabled=yes eligible=no reason=missing_api_key
groq: configured=no enabled=yes eligible=no reason=missing_api_key
local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed
minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key
openrouter: configured=no enabled=yes eligible=no reason=missing_api_key
qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key
$ python3 scripts/dali_canary_runner.py || true
CANARY status=DEGRADED coder=DOWN replay=WRITABLE pairing=OK ts=2026-02-23T08:42:08Z
### Delayed post-restart readiness check
$ sleep 25
$ systemctl --user status openclaw-vllm-coder.service --no-pager -l || true
● openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm-coder.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-02-23 18:42:08 AEST; 2min 51s ago
   Main PID: 404593 (vllm)
      Tasks: 161 (limit: 38169)
     Memory: 2.2G (peak: 2.2G)
        CPU: 41.355s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm-coder.service
             ├─404593 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-coder --host 127.0.0.1 --port 8002 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 6 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─404822 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─404823 VLLM::EngineCore

Feb 23 18:42:08 jeebs-Z490-AORUS-MASTER systemd[1648]: Started openclaw-vllm-coder.service - OpenClaw local vLLM coder lane (:8002).
$ curl -fsS -m 5 http://127.0.0.1:8002/health && echo FINAL_CODER_HEALTH_OK || echo FINAL_CODER_HEALTH_DOWN
FINAL_CODER_HEALTH_OK
### Post-merge final snapshot
$ curl -fsS -m 5 http://127.0.0.1:8002/health && echo FINAL_CODER_HEALTH_OK || echo FINAL_CODER_HEALTH_DOWN
FINAL_CODER_HEALTH_OK
$ node scripts/system2/provider_diag.js || true
=== System-2 Provider Diagnostics (safe) ===
freecompute_enabled=false
freecompute_env_keys_seen=(none)
secrets_bridge_enabled=false

local_vllm_endpoint_present=false
local_vllm_models_fetch_ok=false
local_vllm_models_count=0
local_vllm_generation_probe_ok=false
local_vllm_generation_probe_reason=unknown
coder_vllm_endpoint=http://127.0.0.1:8002/v1/models
coder_vllm_endpoint_present=true
coder_vllm_models_fetch_ok=true
coder_vllm_models_count=1
coder_status=UP
coder_degraded_reason=OK
coder_degraded_note=endpoint_reachable
replay_log_path=/home/jeebs/.local/share/openclaw/replay/replay.jsonl
replay_log_writable=true
replay_log_reason=ok
event_envelope_schema=openclaw.event_envelope.v1

event_envelope_log_path=/home/jeebs/.local/share/openclaw/events/gate_health.jsonl
event_envelope_write_ok=true
event_envelope_write_reason=ok

canary_recommendations:
- run: python3 scripts/dali_canary_runner.py
- optional timer: systemctl --user enable --now openclaw-canary.timer
- if coder DEGRADED with VRAM_LOW, reduce load or raise VLLM_CODER_MIN_FREE_VRAM_MB policy

providers:
- gemini: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GEMINI_API_KEY
- groq: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_GROQ_API_KEY
- local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed auth_env_keys=OPENCLAW_VLLM_API_KEY
- minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_MINIMAX_PORTAL_API_KEY
- openrouter: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_OPENROUTER_API_KEY
- qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key auth_env_keys=OPENCLAW_QWEN_API_KEY

providers_summary:
gemini: configured=no enabled=yes eligible=no reason=missing_api_key
groq: configured=no enabled=yes eligible=no reason=missing_api_key
local_vllm: configured=yes enabled=yes eligible=no reason=generation_probe_failed
minimax-portal: configured=no enabled=yes eligible=no reason=missing_api_key
openrouter: configured=no enabled=yes eligible=no reason=missing_api_key
qwen_alibaba: configured=no enabled=yes eligible=no reason=missing_api_key
$ python3 scripts/dali_canary_runner.py || true
CANARY status=OK coder=UP replay=WRITABLE pairing=OK ts=2026-02-23T08:46:15Z
