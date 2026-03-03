# Dali vLLM Port 8001 Canonical Ownership

- date_utc: 2026-02-26T08:37:04Z
- branch: codex/fix/dali-audit-hardening-mcp-client-20260226
- sha: 679055d1ccc5436a2c3b830d10d97a8beda20b1b

## Why
Ensure `openclaw-vllm.service` is the canonical owner of `:8001`, reclaim stray OpenClaw/vLLM holders automatically, and refuse unknown holders without killing them.

## Behavior Matrix
- Port free: `VLLM_PORT_OK` -> service starts.
- Stray vLLM/OpenClaw holder: `VLLM_PORT_RECLAIM` -> kill holder -> `VLLM_PORT_RECLAIMED` -> service starts.
- Unknown holder: `VLLM_PORT_HELD_UNKNOWN` -> exit 42 -> service refuses to start.

## Files Changed
- scripts/ensure_port_free.sh
- scripts/vllm_launch_assistant.sh
- workspace/systemd/openclaw-vllm.service

## Verification Commands
```bash
cp workspace/systemd/openclaw-vllm.service ~/.config/systemd/user/openclaw-vllm.service
systemctl --user daemon-reload
systemctl --user reset-failed openclaw-vllm.service

# Reclaim case
systemctl --user stop openclaw-vllm.service
nohup bash -lc 'exec -a vllm-stray python3 -m http.server 8001 >/tmp/vllm_stray_8001.log 2>&1' &
systemctl --user restart openclaw-vllm.service
curl -sf http://127.0.0.1:8001/health

# Unknown-holder case
systemctl --user stop openclaw-vllm.service
nohup bash -lc 'exec -a unknown-holder python3 -m http.server 8001 >/tmp/unknown_holder_8001.log 2>&1' &
systemctl --user restart openclaw-vllm.service
journalctl --user -t openclaw-vllm-port-guard --since '-3 min' --no-pager

# Normal case
systemctl --user restart openclaw-vllm.service
curl -sf http://127.0.0.1:8001/health
```

## Reclaim Case Output
```text
CASE=reclaim TS=20260226T081249Z
STRAY_PID=421841
6:LISTEN 0      5            0.0.0.0:8001       0.0.0.0:*    users:(("python3",pid=421841,fd=3))       
HEALTH_OK=1
● openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: active (running) since Thu 2026-02-26 18:12:51 AEST; 33s ago
    Process: 421851 ExecStartPre=/home/jeebs/src/clawd/scripts/ensure_port_free.sh 8001 (code=exited, status=0/SUCCESS)
   Main PID: 421876 (python3.12)
      Tasks: 161 (limit: 38151)
     Memory: 2.2G (peak: 2.2G)
        CPU: 40.360s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm.service
             ├─421876 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.85 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─421964 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─421965 VLLM::EngineCore

Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER systemd[1669]: Starting openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001)...
Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[421866]: VLLM_PORT_RECLAIM port=8001 pid=421841 cmd="vllm-stray -m http.server 8001"
Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[421874]: VLLM_PORT_RECLAIMED port=8001
Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER systemd[1669]: Started openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001).
Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[421889]: VLLM_PORT_OK port=8001
--- JOURNAL (unit) ---
7:Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER systemd[1669]: Started openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001).
--- JOURNAL (port-guard tag) ---
1:Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[421866]: VLLM_PORT_RECLAIM port=8001 pid=421841 cmd="vllm-stray -m http.server 8001"
2:Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[421874]: VLLM_PORT_RECLAIMED port=8001
3:Feb 26 18:12:51 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[421889]: VLLM_PORT_OK port=8001
```

## Unknown Holder Output
```text
CASE=unknown-holder TS=20260226T082748Z
HOLDER_PID=422992
6:LISTEN 0      5            0.0.0.0:8001       0.0.0.0:*    users:(("python3",pid=422992,fd=3))       
RESTART_EC=1
● openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: activating (auto-restart) (Result: exit-code) since Thu 2026-02-26 18:27:49 AEST; 1s ago
    Process: 423000 ExecStartPre=/home/jeebs/src/clawd/scripts/ensure_port_free.sh 8001 (code=exited, status=42)
        CPU: 25ms
--- JOURNAL (unit) ---
5:Feb 26 18:27:49 jeebs-Z490-AORUS-MASTER systemd[1669]: openclaw-vllm.service: Control process exited, code=exited, status=42/n/a
7:Feb 26 18:27:49 jeebs-Z490-AORUS-MASTER systemd[1669]: Failed to start openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001).
--- JOURNAL (port-guard tag) ---
1:Feb 26 18:27:49 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[423015]: VLLM_PORT_HELD_UNKNOWN port=8001 pid=422992 cmd="unknown-holder -m http.server 8001"
HOLDER_STILL_ALIVE=1
6:LISTEN 0      5            0.0.0.0:8001       0.0.0.0:*    users:(("python3",pid=422992,fd=3))       
```

## Normal Start Output
```text
CASE=normal-start TS=20260226T083542Z
PRECHECK_PORT_8001_OCCUPIED=1
HEALTH_OK=1
● openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
     Active: active (running) since Thu 2026-02-26 18:35:43 AEST; 32s ago
    Process: 424505 ExecStartPre=/home/jeebs/src/clawd/scripts/ensure_port_free.sh 8001 (code=exited, status=0/SUCCESS)
   Main PID: 424513 (python3.12)
      Tasks: 161 (limit: 38151)
     Memory: 2.2G (peak: 2.2G)
        CPU: 39.743s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm.service
             ├─424513 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.85 --max-model-len 16384 --max-num-seqs 8 --enable-auto-tool-choice --tool-call-parser hermes --uvicorn-log-level warning
             ├─424600 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─424601 VLLM::EngineCore

Feb 26 18:35:43 jeebs-Z490-AORUS-MASTER systemd[1669]: Starting openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001)...
Feb 26 18:35:43 jeebs-Z490-AORUS-MASTER systemd[1669]: Started openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001).
--- JOURNAL (unit) ---
5:Feb 26 18:35:43 jeebs-Z490-AORUS-MASTER systemd[1669]: Started openclaw-vllm.service - OpenClaw local vLLM assistant lane (:8001).
--- JOURNAL (port-guard tag) ---
1:Feb 26 18:35:43 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[424511]: VLLM_PORT_OK port=8001
2:Feb 26 18:35:43 jeebs-Z490-AORUS-MASTER openclaw-vllm-port-guard[424526]: VLLM_PORT_OK port=8001
```

## Follow-Up: Status Hint For Unknown Port Holder (2026-02-26)
- Change: `openclaw status --verbose` now emits a targeted hint when vLLM health is down and `:8001` is held by an unknown process.
- Hint text:
  `HINT: vLLM blocked — port 8001 held by unknown process (pid=<pid>, cmd="<cmd>"). Stop it or free :8001, then restart openclaw-vllm.service.`
- Scope:
  - No change to status exit code policy.
  - No hint for `vllm_like`, `free`, or `probe_failed` probe results.

### Follow-Up Verification Commands
```bash
npm run typecheck:hardening
npm run test:hardening
npm run runtime:rebuild
```

### Follow-Up Verification Output (Summary)
```text
typecheck:hardening => PASS
test:hardening => PASS (11/11, includes status_hint.test.mjs)
runtime:rebuild => PASS
```
