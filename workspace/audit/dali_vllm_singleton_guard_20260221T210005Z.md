# Dali vLLM Singleton Guard Audit

- Audit file: workspace/audit/dali_vllm_singleton_guard_20260221T210005Z.md
- Start (UTC): 2026-02-21T21:00:05Z

## Context
Previous fix (commit 12b7bc8) kept system  as owner of port 8001 and disabled user .

```bash
date -u
```

```text
Sat Feb 21 21:00:05 UTC 2026
```

```bash
uname -a
```

```text
Linux jeebs-Z490-AORUS-MASTER 6.17.0-14-generic #14~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Thu Jan 15 15:52:10 UTC 2 x86_64 x86_64 x86_64 GNU/Linux
```

```bash
git rev-parse HEAD
```

```text
12b7bc82165f77f22fe8c9236066f0f630bde15f
```

## Audit Note
During file creation, shell backtick expansion produced harmless stderr in terminal; this note supersedes the header text and preserves append-only behavior.

## Corrected Context Statement
Previous fix (commit `12b7bc8`) kept system `vllm-assistant.service` as owner of port 8001 and disabled user `openclaw-vllm.service`.

## Phase 1 Reversion Guard Recon

```bash
set -euo pipefail
date -u

# Confirm current enablement/health
systemctl is-enabled vllm-assistant.service || true
systemctl status vllm-assistant.service --no-pager || true

systemctl --user is-enabled openclaw-vllm.service || true
systemctl --user status openclaw-vllm.service --no-pager || true

# Search likely enablement points (installers/maintenance scripts)
grep -RIn --color=never -E 'openclaw-vllm\.service|systemctl --user.*enable.*vllm|enable.*openclaw-vllm|daemon-reload|systemctl --user.*(start|restart).*vllm' ~/bin ~/.local/bin ~/.config/systemd ~/.config/autostart workspace workspace/scripts .github 2>/dev/null || true
```

```text
Sat Feb 21 21:00:31 UTC 2026
enabled
● vllm-assistant.service - vLLM OpenAI Server (assistant)
     Loaded: loaded (/etc/systemd/system/vllm-assistant.service; enabled; preset: enabled)
     Active: active (running) since Sun 2026-02-22 06:35:31 AEST; 25min ago
   Main PID: 3285 (vllm)
      Tasks: 161 (limit: 38169)
     Memory: 2.2G (peak: 2.2G)
        CPU: 47.605s
     CGroup: /system.slice/vllm-assistant.service
             ├─3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
             ├─3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─3361 VLLM::EngineCore

Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/embeddings, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v2/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pooling, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Started server process [3285]
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Waiting for application startup.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Application startup complete.
disabled
○ openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; disabled; preset: enabled)
     Active: inactive (dead)

Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER python3.12[16233]: (APIServer pid=16233)     raise RuntimeError(
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER python3.12[16233]: (APIServer pid=16233) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.465s CPU time.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 76.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-vllm.service - OpenClaw local vLLM server...
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-vllm.service - OpenClaw local vLLM server.
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 2.731s CPU time, 306.8M memory peak, 0B memory swap peak.
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:357:- `systemctl --user daemon-reload`
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:386:2. `systemctl --user daemon-reload`
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:476:- `systemctl --user daemon-reload`
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:541:- `systemctl --user daemon-reload`
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:614:systemctl --user daemon-reload
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:681:systemctl --user daemon-reload
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:754:systemctl --user daemon-reload
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:825:systemctl --user daemon-reload
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:903:systemctl --user daemon-reload
workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md:959:systemctl --user daemon-reload
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:713:  openclaw-vllm.service                                            loaded    active   running OpenClaw local vLLM server
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1122:systemctl --user status openclaw-vllm.service --no-pager || true
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1123:systemctl --user cat openclaw-vllm.service 2>/dev/null || true
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1124:journalctl --user -u openclaw-vllm.service -n 200 --no-pager || true
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1128:systemctl --user is-enabled openclaw-vllm.service || true
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1386:● openclaw-vllm.service - OpenClaw local vLLM server
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1387:     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1393:     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm.service
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1396:Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.502s CPU time.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1397:Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 65.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1398:Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1399:# /home/jeebs/.config/systemd/user/openclaw-vllm.service
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1481:Feb 22 06:52:32 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1482:Feb 22 06:52:32 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1483:Feb 22 06:52:32 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.534s CPU time.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1484:Feb 22 06:52:37 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 64.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1485:Feb 22 06:52:37 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1610:Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1611:Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1612:Feb 22 06:52:49 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.502s CPU time.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1613:Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 65.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1614:Feb 22 06:52:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1620:14790 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' PHASE23='/tmp/dali_phase2b_cmd.sh' cat > "$PHASE23" <<'EOF' # Focused vLLM launcher attribution systemctl status vllm-assistant.service --no-pager || true systemctl cat vllm-assistant.service 2>/dev/null || true journalctl -u vllm-assistant.service -n 200 --no-pager || true  systemctl --user status openclaw-vllm.service --no-pager || true systemctl --user cat openclaw-vllm.service 2>/dev/null || true journalctl --user -u openclaw-vllm.service -n 200 --no-pager || true  # Check enablement state for both units systemctl is-enabled vllm-assistant.service || true systemctl --user is-enabled openclaw-vllm.service || true  # show explicit PIDs for current listeners and related services ss -ltnp | grep -E '(:8001)\b' || true pgrep -af 'vllm serve|openai.api_server|local-assistant' || true EOF  {   echo '## Phase 2b Focused vLLM Launcher Attribution'   echo   echo '```bash'   cat "$PHASE23"   echo '```'   echo   echo '```text' } >> "$AUDIT"  bash "$PHASE23" >> "$AUDIT" 2>&1 || true  {   echo '```'   echo } >> "$AUDIT"  echo done
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1625:- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1658:systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1662:● openclaw-vllm.service - OpenClaw local vLLM server
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1663:     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; enabled; preset: enabled)
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1669:     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-vllm.service
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1672:Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.465s CPU time.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1673:Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 76.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1674:Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1678:systemctl --user disable --now openclaw-vllm.service
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1682:Removed "/home/jeebs/.config/systemd/user/default.target.wants/openclaw-vllm.service".
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1686:systemctl --user mask openclaw-vllm.service
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1690:Failed to mask unit: File /home/jeebs/.config/systemd/user/openclaw-vllm.service already exists.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1694:systemctl --user is-enabled openclaw-vllm.service || true
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1710:systemctl --user reset-failed openclaw-vllm.service || true
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1714:Failed to reset failed state of unit openclaw-vllm.service: Unit openclaw-vllm.service not loaded.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1718:systemctl --user status openclaw-vllm.service --no-pager || true
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1722:○ openclaw-vllm.service - OpenClaw local vLLM server
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1723:     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; disabled; preset: enabled)
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1728:Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1729:Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1730:Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.465s CPU time.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1731:Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 76.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1732:Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1733:Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-vllm.service - OpenClaw local vLLM server...
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1734:Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-vllm.service - OpenClaw local vLLM server.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1735:Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 2.731s CPU time, 306.8M memory peak, 0B memory swap peak.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1752:16396 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' append_cmd() {   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  {   echo '## Phase 5 Fix Applied (Singleton Enforcement)'   echo   echo '- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.'   echo '- Rationale: listener ownership is stable on system unit PID; user unit is in restart-loop with repeated failures while targeting same model/port.'   echo } >> "$AUDIT"  append_cmd 'systemctl status vllm-assistant.service --no-pager | sed -n "1,80p"' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"' append_cmd 'systemctl --user disable --now openclaw-vllm.service' append_cmd 'systemctl --user mask openclaw-vllm.service' append_cmd 'systemctl --user is-enabled openclaw-vllm.service || true' append_cmd 'systemctl is-enabled vllm-assistant.service || true' append_cmd 'systemctl --user reset-failed openclaw-vllm.service || true' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # Phase 6 gateway evidence search {   echo '## Phase 6 Gateway Error Evidence'   echo } >> "$AUDIT" append_cmd 'journalctl --user -u openclaw-gateway.service --since "2026-02-21 20:30:00" --until "2026-02-21 20:50:00" --no-pager || true' append_cmd 'grep -RIn --color=never -E "tg-mlws9pj6-002|Gateway logs contain details" ~/.local/state/openclaw 2>/dev/null || true'  # Phase 7 verification per acceptance criteria {   echo '## Phase 7 Verification'   echo } >> "$AUDIT" append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm|openai.api_server|api_server" || true' append_cmd 'bash -lc "~/bin/python-env-audit.sh" || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'systemctl --user restart openclaw-gateway.service' append_cmd 'sleep 2; systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,80p"' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # extra: ensure no timer mentions openclaw-vllm append_cmd 'systemctl --user list-timers --all | grep -i -E "openclaw|vllm|llm|audit" || true'  echo done
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1790:16396 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' append_cmd() {   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  {   echo '## Phase 5 Fix Applied (Singleton Enforcement)'   echo   echo '- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.'   echo '- Rationale: listener ownership is stable on system unit PID; user unit is in restart-loop with repeated failures while targeting same model/port.'   echo } >> "$AUDIT"  append_cmd 'systemctl status vllm-assistant.service --no-pager | sed -n "1,80p"' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"' append_cmd 'systemctl --user disable --now openclaw-vllm.service' append_cmd 'systemctl --user mask openclaw-vllm.service' append_cmd 'systemctl --user is-enabled openclaw-vllm.service || true' append_cmd 'systemctl is-enabled vllm-assistant.service || true' append_cmd 'systemctl --user reset-failed openclaw-vllm.service || true' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # Phase 6 gateway evidence search {   echo '## Phase 6 Gateway Error Evidence'   echo } >> "$AUDIT" append_cmd 'journalctl --user -u openclaw-gateway.service --since "2026-02-21 20:30:00" --until "2026-02-21 20:50:00" --no-pager || true' append_cmd 'grep -RIn --color=never -E "tg-mlws9pj6-002|Gateway logs contain details" ~/.local/state/openclaw 2>/dev/null || true'  # Phase 7 verification per acceptance criteria {   echo '## Phase 7 Verification'   echo } >> "$AUDIT" append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm|openai.api_server|api_server" || true' append_cmd 'bash -lc "~/bin/python-env-audit.sh" || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'systemctl --user restart openclaw-gateway.service' append_cmd 'sleep 2; systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,80p"' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # extra: ensure no timer mentions openclaw-vllm append_cmd 'systemctl --user list-timers --all | grep -i -E "openclaw|vllm|llm|audit" || true'  echo done
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1852:16396 /bin/bash -c set -euo pipefail AUDIT='workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md' append_cmd() {   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  {   echo '## Phase 5 Fix Applied (Singleton Enforcement)'   echo   echo '- Decision: keep system unit `vllm-assistant.service` as owner of `:8001`; disable competing user unit `openclaw-vllm.service`.'   echo '- Rationale: listener ownership is stable on system unit PID; user unit is in restart-loop with repeated failures while targeting same model/port.'   echo } >> "$AUDIT"  append_cmd 'systemctl status vllm-assistant.service --no-pager | sed -n "1,80p"' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager | sed -n "1,120p"' append_cmd 'systemctl --user disable --now openclaw-vllm.service' append_cmd 'systemctl --user mask openclaw-vllm.service' append_cmd 'systemctl --user is-enabled openclaw-vllm.service || true' append_cmd 'systemctl is-enabled vllm-assistant.service || true' append_cmd 'systemctl --user reset-failed openclaw-vllm.service || true' append_cmd 'systemctl --user status openclaw-vllm.service --no-pager || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # Phase 6 gateway evidence search {   echo '## Phase 6 Gateway Error Evidence'   echo } >> "$AUDIT" append_cmd 'journalctl --user -u openclaw-gateway.service --since "2026-02-21 20:30:00" --until "2026-02-21 20:50:00" --no-pager || true' append_cmd 'grep -RIn --color=never -E "tg-mlws9pj6-002|Gateway logs contain details" ~/.local/state/openclaw 2>/dev/null || true'  # Phase 7 verification per acceptance criteria {   echo '## Phase 7 Verification'   echo } >> "$AUDIT" append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm|openai.api_server|api_server" || true' append_cmd 'bash -lc "~/bin/python-env-audit.sh" || true' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'systemctl --user restart openclaw-gateway.service' append_cmd 'sleep 2; systemctl --user status openclaw-gateway.service --no-pager | sed -n "1,80p"' append_cmd 'ss -ltnp | grep -E "(:8001)\\b" || true' append_cmd 'pgrep -af "vllm serve|openai.api_server|local-assistant" || true'  # extra: ensure no timer mentions openclaw-vllm append_cmd 'systemctl --user list-timers --all | grep -i -E "openclaw|vllm|llm|audit" || true'  echo done
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1868:  - User unit `openclaw-vllm.service` (was enabled with `Restart=always`) repeatedly attempted the same `local-assistant` on `:8001` and failed/restarted.
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1877:  - Disabled/stopped: `openclaw-vllm.service` (user).
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1890:   - `systemctl --user unmask openclaw-vllm.service || true`
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1891:   - `systemctl --user enable --now openclaw-vllm.service`
workspace/audit/dali_vllm_duplicate_audit_20260221T204411Z.md:1894:   - `systemctl --user enable --now openclaw-vllm.service`
```

```bash
set -euo pipefail
# Focused search excluding prior audit documents
rg -n --hidden -S   'openclaw-vllm\.service|systemctl --user.*enable.*vllm|enable.*openclaw-vllm|systemctl --user.*(start|restart).*vllm'   ~/bin ~/.local/bin ~/.config/systemd ~/.config/autostart workspace scripts .github   -g '!workspace/audit/**' -g '!workspace/artifacts/**' -g '!.git/**' || true
```

```text
rg: /home/jeebs/.config/autostart: No such file or directory (os error 2)
```

## Phase 1 Decision
If no executable installer/maintenance path is found that enables `openclaw-vllm.service`, no code patch is warranted; preserve minimal-diff by shipping audit-only evidence.

## Phase 2 Causality Check (tg-mlws9pj6-002)

```bash
set -euo pipefail
date -u

# Snapshot services and restart counters (if present)
systemctl status vllm-assistant.service --no-pager || true
systemctl --user status openclaw-gateway.service --no-pager || true
systemctl --user status openclaw-vllm.service --no-pager || true

# Confirm port 8001 owner + vLLM process stability
ss -ltnp | grep -E '(:8001)\b' || true
pgrep -af 'vllm|openai\.api_server|api_server' || true

# Gateway logs (recent window)
journalctl --user -u openclaw-gateway.service -n 300 --no-pager || true

# vLLM logs for stability
journalctl -u vllm-assistant.service -n 300 --no-pager || true
```

```text
Sat Feb 21 21:02:20 UTC 2026
● vllm-assistant.service - vLLM OpenAI Server (assistant)
     Loaded: loaded (/etc/systemd/system/vllm-assistant.service; enabled; preset: enabled)
     Active: active (running) since Sun 2026-02-22 06:35:31 AEST; 26min ago
   Main PID: 3285 (vllm)
      Tasks: 161 (limit: 38169)
     Memory: 2.2G (peak: 2.2G)
        CPU: 48.283s
     CGroup: /system.slice/vllm-assistant.service
             ├─3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
             ├─3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c "from multiprocessing.resource_tracker import main;main(34)"
             └─3361 VLLM::EngineCore

Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/embeddings, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v2/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pooling, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Started server process [3285]
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Waiting for application startup.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Application startup complete.
● openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-gateway.service; enabled; preset: enabled)
    Drop-In: /home/jeebs/.config/systemd/user/openclaw-gateway.service.d
             └─10-provider-lock.conf, override.conf
     Active: active (running) since Sun 2026-02-22 06:56:23 AEST; 5min ago
   Main PID: 16591 (openclaw-gatewa)
      Tasks: 31 (limit: 38169)
     Memory: 307.1M (peak: 381.1M)
        CPU: 4.177s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-gateway.service
             └─16591 openclaw-gateway

Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.849Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.885Z [heartbeat] started
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.889Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.890Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.891Z [gateway] listening on ws://127.0.0.1:18789 (PID 16591)
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.892Z [gateway] listening on ws://[::1]:18789
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.893Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.912Z [browser/service] Browser control service ready (profiles=2)
Feb 22 06:56:27 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:27.378Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 06:56:27 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:27.381Z [telegram] autoSelectFamily=true (default-node22)
○ openclaw-vllm.service - OpenClaw local vLLM server
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-vllm.service; disabled; preset: enabled)
     Active: inactive (dead)

Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER python3.12[16233]: (APIServer pid=16233)     raise RuntimeError(
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER python3.12[16233]: (APIServer pid=16233) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Main process exited, code=exited, status=1/FAILURE
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Failed with result 'exit-code'.
Feb 22 06:55:47 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 16.465s CPU time.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Scheduled restart job, restart counter is at 76.
Feb 22 06:55:53 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-vllm.service - OpenClaw local vLLM server.
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-vllm.service - OpenClaw local vLLM server...
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-vllm.service - OpenClaw local vLLM server.
Feb 22 06:55:54 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-vllm.service: Consumed 2.731s CPU time, 306.8M memory peak, 0B memory swap peak.
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))            
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
17583 /bin/bash -c set -euo pipefail cd /home/jeebs/src/clawd AUDIT='workspace/audit/dali_vllm_singleton_guard_20260221T210005Z.md' append_cmd(){   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  append_cmd "set -euo pipefail # Focused search excluding prior audit documents rg -n --hidden -S \   'openclaw-vllm\\.service|systemctl --user.*enable.*vllm|enable.*openclaw-vllm|systemctl --user.*(start|restart).*vllm' \   ~/bin ~/.local/bin ~/.config/systemd ~/.config/autostart workspace scripts .github \   -g '!workspace/audit/**' -g '!workspace/artifacts/**' -g '!.git/**' || true"  cat >> "$AUDIT" <<'EOF' ## Phase 1 Decision If no executable installer/maintenance path is found that enables `openclaw-vllm.service`, no code patch is warranted; preserve minimal-diff by shipping audit-only evidence.  EOF  {   echo '## Phase 2 Causality Check (tg-mlws9pj6-002)'   echo } >> "$AUDIT" append_cmd "set -euo pipefail date -u  # Snapshot services and restart counters (if present) systemctl status vllm-assistant.service --no-pager || true systemctl --user status openclaw-gateway.service --no-pager || true systemctl --user status openclaw-vllm.service --no-pager || true  # Confirm port 8001 owner + vLLM process stability ss -ltnp | grep -E '(:8001)\\b' || true pgrep -af 'vllm|openai\\.api_server|api_server' || true  # Gateway logs (recent window) journalctl --user -u openclaw-gateway.service -n 300 --no-pager || true  # vLLM logs for stability journalctl -u vllm-assistant.service -n 300 --no-pager || true"  cat >> "$AUDIT" <<'EOF' ## Phase 2 Interpretation Rubric - If `tg-mlws9pj6-002` stops occurring after duplicate launcher disable and vLLM is stable, restart-loop is a likely proximal contributor. - If telegram timeout signatures persist while vLLM remains stable/singleton, treat as independent gateway/telegram latency path.  EOF  {   echo '## Phase 3 Verification (No Relapse)'   echo } >> "$AUDIT" append_cmd "set -euo pipefail date -u  # Re-run observational audit script bash -lc '~/bin/python-env-audit.sh' || true  # Restart gateway (user) and confirm singleton remains systemctl --user restart openclaw-gateway.service sleep 2 ss -ltnp | grep -E '(:8001)\\b' || true pgrep -af 'vllm|openai\\.api_server|api_server' || true  # Confirm the user vLLM service remains disabled systemctl --user is-enabled openclaw-vllm.service || true"  echo done
17602 bash -lc set -euo pipefail date -u  # Snapshot services and restart counters (if present) systemctl status vllm-assistant.service --no-pager || true systemctl --user status openclaw-gateway.service --no-pager || true systemctl --user status openclaw-vllm.service --no-pager || true  # Confirm port 8001 owner + vLLM process stability ss -ltnp | grep -E '(:8001)\b' || true pgrep -af 'vllm|openai\.api_server|api_server' || true  # Gateway logs (recent window) journalctl --user -u openclaw-gateway.service -n 300 --no-pager || true  # vLLM logs for stability journalctl -u vllm-assistant.service -n 300 --no-pager || true
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 108.
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:                                    ^^^
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]: SyntaxError: missing ) after argument list
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER node[484970]: Node.js v22.22.0
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:27 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 109.
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:                                    ^^^
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]: SyntaxError: missing ) after argument list
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER node[485027]: Node.js v22.22.0
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:33 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:01:38 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 110.
Feb 21 20:01:38 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:                                    ^^^
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]: SyntaxError: missing ) after argument list
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER node[485113]: Node.js v22.22.0
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:39 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 111.
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:                                    ^^^
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]: SyntaxError: missing ) after argument list
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER node[485165]: Node.js v22.22.0
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:44 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:01:49 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 112.
Feb 21 20:01:49 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:                                    ^^^
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]: SyntaxError: missing ) after argument list
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER node[485223]: Node.js v22.22.0
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:50 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:01:55 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 113.
Feb 21 20:01:55 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:                                    ^^^
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]: SyntaxError: missing ) after argument list
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER node[485291]: Node.js v22.22.0
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:01:56 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 114.
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:                                    ^^^
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]: SyntaxError: missing ) after argument list
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER node[485322]: Node.js v22.22.0
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:02:01 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:06 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 115.
Feb 21 20:02:06 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:                                    ^^^
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]: SyntaxError: missing ) after argument list
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER node[485400]: Node.js v22.22.0
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:02:07 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Scheduled restart job, restart counter is at 116.
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]: file:///home/jeebs/src/clawd/.runtime/openclaw/dist/reply-B4B0jUCM.js:35318
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:         return `'${s.replace(/'/g, "'"'"'")}'`;
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:                                    ^^^
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]: SyntaxError: missing ) after argument list
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at compileSourceTextModule (node:internal/modules/esm/utils:346:16)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at ModuleLoader.moduleStrategy (node:internal/modules/esm/translators:107:18)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at #translate (node:internal/modules/esm/loader:546:20)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at afterLoad (node:internal/modules/esm/loader:596:29)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at ModuleLoader.loadAndTranslate (node:internal/modules/esm/loader:601:12)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at #createModuleJob (node:internal/modules/esm/loader:624:36)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at #getJobFromResolveResult (node:internal/modules/esm/loader:343:34)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]:     at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:311:41)
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER node[485471]: Node.js v22.22.0
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Main process exited, code=exited, status=1/FAILURE
Feb 21 20:02:12 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Failed with result 'exit-code'.
Feb 21 20:02:15 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:15 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:02:17 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:17.105Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.046Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.084Z [heartbeat] started
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.087Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.089Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.090Z [gateway] listening on ws://127.0.0.1:18789 (PID 485512)
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.090Z [gateway] listening on ws://[::1]:18789
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.092Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-21.log
Feb 21 20:02:18 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:18.112Z [browser/service] Browser control service ready (profiles=2)
Feb 21 20:02:20 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:20.451Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 21 20:02:20 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:20.456Z [telegram] autoSelectFamily=true (default-node22)
Feb 21 20:02:25 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:25.606Z [ws] webchat connected conn=4ca35bcb-dbe8-4ba6-9af2-9c04bf8a464b remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:02:25 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:02:25.627Z [ws] webchat connected conn=a797f1a7-4557-4880-b82f-805242da58bd remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.631Z [gateway] signal SIGTERM received
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.632Z [gateway] received SIGTERM; shutting down
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.645Z [gmail-watcher] gmail watcher stopped
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.902Z [ws] webchat disconnected code=1012 reason=service restart conn=a797f1a7-4557-4880-b82f-805242da58bd
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER node[485512]: 2026-02-21T10:07:42.903Z [ws] webchat disconnected code=1012 reason=service restart conn=4ca35bcb-dbe8-4ba6-9af2-9c04bf8a464b
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Consumed 6.081s CPU time, 411.5M memory peak, 0B memory swap peak.
Feb 21 20:07:42 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:07:44 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:44.347Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.262Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.300Z [heartbeat] started
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.303Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.305Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.306Z [gateway] listening on ws://127.0.0.1:18789 (PID 489125)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.307Z [gateway] listening on ws://[::1]:18789
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.308Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-21.log
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.328Z [browser/service] Browser control service ready (profiles=2)
Feb 21 20:07:45 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:45.789Z [ws] webchat connected conn=6445579a-5856-47b8-aee6-b3ab0fe0e1e9 remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:07:46 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:46.824Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 21 20:07:46 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:46.827Z [telegram] autoSelectFamily=true (default-node22)
Feb 21 20:07:47 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:07:47.240Z [ws] webchat connected conn=56e404e4-67b2-48a6-a3b7-130c74314e17 remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.451Z [gateway] signal SIGTERM received
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.451Z [gateway] received SIGTERM; shutting down
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.466Z [gmail-watcher] gmail watcher stopped
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.715Z [ws] webchat disconnected code=1012 reason=service restart conn=56e404e4-67b2-48a6-a3b7-130c74314e17
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER node[489125]: 2026-02-21T10:09:21.716Z [ws] webchat disconnected code=1012 reason=service restart conn=6445579a-5856-47b8-aee6-b3ab0fe0e1e9
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Consumed 4.664s CPU time, 194.7M memory peak, 0B memory swap peak.
Feb 21 20:09:21 jeebs-Z490-AORUS-MASTER systemd[1668]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 21 20:09:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:23.144Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.051Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.088Z [heartbeat] started
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.091Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.093Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.094Z [gateway] listening on ws://127.0.0.1:18789 (PID 490423)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.095Z [gateway] listening on ws://[::1]:18789
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.096Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-21.log
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.115Z [browser/service] Browser control service ready (profiles=2)
Feb 21 20:09:24 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:24.260Z [ws] webchat connected conn=7e80d68c-9d22-4309-b324-7cee4a1bdfac remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 20:09:25 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:25.573Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 21 20:09:25 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:25.576Z [telegram] autoSelectFamily=true (default-node22)
Feb 21 20:09:25 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T10:09:25.984Z [ws] webchat connected conn=c09aba15-357c-47bc-a9b0-83f17759c473 remote=127.0.0.1 client=openclaw-control-ui webchat vdev
Feb 21 22:05:18 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:05:18.220+10:00 [tools] read failed: ENOENT: no such file or directory, access '/home/jeebs/.openclaw/workspace/docs/index.md'
Feb 21 22:06:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:06:23.177Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=137s queueDepth=1
Feb 21 22:12:57 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:12:57.513+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:13:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:13:53.180Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=127s queueDepth=1
Feb 21 22:17:56 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:17:56.358+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:18:05 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:18:05.584+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:18:21 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T22:18:21.755+10:00 [tools] edit failed: Could not find the exact text in /home/jeebs/.openclaw/workspace/docs/multi-tier-agents-research.md. The old text must match exactly including all whitespace and newlines.
Feb 21 22:23:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:23:53.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=150s queueDepth=1
Feb 21 22:24:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:24:23.185Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=180s queueDepth=1
Feb 21 22:24:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:24:53.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=210s queueDepth=1
Feb 21 22:25:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:25:23.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=240s queueDepth=1
Feb 21 22:25:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:25:53.184Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=270s queueDepth=1
Feb 21 22:26:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:26:23.185Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=300s queueDepth=1
Feb 21 22:26:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:26:53.187Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=330s queueDepth=1
Feb 21 22:59:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T12:59:53.193Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=133s queueDepth=1
Feb 21 23:00:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:00:23.194Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=163s queueDepth=1
Feb 21 23:00:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:00:53.194Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=193s queueDepth=1
Feb 21 23:01:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:01:23.195Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=223s queueDepth=1
Feb 21 23:06:01 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T23:06:01.388+10:00 [tools] read failed: ENOENT: no such file or directory, access '/home/jeebs/.openclaw/workspace/memory/2026-02-21.md'
Feb 21 23:07:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:07:23.196Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=150s queueDepth=1
Feb 21 23:07:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:07:53.196Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=180s queueDepth=1
Feb 21 23:08:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:08:23.197Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=210s queueDepth=1
Feb 21 23:08:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:08:53.197Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=240s queueDepth=1
Feb 21 23:38:10 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T23:38:10.483+10:00 typing TTL reached (2m); stopping typing indicator
Feb 21 23:38:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:38:23.206Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=131s queueDepth=1
Feb 21 23:38:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:38:53.205Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=161s queueDepth=1
Feb 21 23:39:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:39:23.205Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=191s queueDepth=1
Feb 21 23:39:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:39:53.206Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=221s queueDepth=1
Feb 21 23:40:23 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:40:23.206Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=251s queueDepth=1
Feb 21 23:40:53 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T13:40:53.207Z [diagnostic] stuck session: sessionId=main sessionKey=agent:main:main state=processing age=281s queueDepth=1
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.344Z [ws] webchat disconnected code=1006 reason=n/a conn=7e80d68c-9d22-4309-b324-7cee4a1bdfac
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.346Z [ws] webchat disconnected code=1006 reason=n/a conn=c09aba15-357c-47bc-a9b0-83f17759c473
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.498Z [gateway] signal SIGTERM received
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.499Z [gateway] received SIGTERM; shutting down
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER node[490423]: 2026-02-21T14:53:22.514Z [gmail-watcher] gmail watcher stopped
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1668]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1668]: openclaw-gateway.service: Consumed 47.769s CPU time, 203.3M memory peak, 0B memory swap peak.
-- Boot 45b35623d291431fa703c9232d2ea952 --
Feb 22 06:34:42 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 06:34:44 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:44.429Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.494Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.543Z [heartbeat] started
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.545Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.547Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.548Z [gateway] listening on ws://127.0.0.1:18789 (PID 1682)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.549Z [gateway] listening on ws://[::1]:18789
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.550Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.576Z [browser/service] Browser control service ready (profiles=2)
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:34:58.873Z [gateway] update available (latest): v2026.2.21-2 (current v2026.2.19-2). Run: openclaw update
Feb 22 06:35:00 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:00.932Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 06:35:00 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:00.935Z [telegram] autoSelectFamily=true (default-node22)
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:53.302Z [gateway] security audit: device access upgrade requested reason=scope-upgrade device=d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301 ip=unknown-ip auth=token roleFrom=operator roleTo=operator scopesFrom=operator.admin,operator.approvals,operator.pairing scopesTo=operator.write client=gateway-client conn=5a8ca0b7-af47-456a-aa00-ee86228cb94f
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-22T06:35:53.305+10:00 gateway connect failed: Error: pairing required
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-22T06:35:53.308+10:00 Subagent completion direct announce failed for run b1a26796-f74b-4f78-92b0-25416e1e5ec9:78ca328f-460e-404d-8d10-2c48e2712048: gateway closed (1008): pairing required
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Gateway target: ws://127.0.0.1:18789
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Source: local loopback
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Config: /home/jeebs/.openclaw/openclaw.json
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: Bind: loopback
Feb 22 06:35:53 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:35:53.316Z [ws] closed before connect conn=5a8ca0b7-af47-456a-aa00-ee86228cb94f remote=127.0.0.1 fwd=n/a origin=n/a host=127.0.0.1:18789 ua=n/a code=1008 reason=pairing required
Feb 22 06:38:15 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:38:15.886Z [telegram] telegram_handler_finally chatId=8159253715 messageId=516
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:39:38.190Z [telegram] telegram_handler_finally chatId=8159253715 messageId=518
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_handler_failed","correlation_id":"tg-mlws8eku-001","update_id":518,"stage":"pipeline","err_class":"Error","err_message":"telegram handler timed out after 25000ms"}
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_deadletter_write_failed","error":"TypeError: fs$1.mkdirSync is not a function"}
Feb 22 06:39:38 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:39:38.194Z [telegram] handler failed (correlation_id=tg-mlws8eku-001, stage=pipeline): telegram handler timed out after 25000ms
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:39.042Z [telegram] telegram_handler_finally chatId=8159253715 messageId=521
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_handler_failed","correlation_id":"tg-mlws9pj6-002","update_id":521,"stage":"pipeline","err_class":"Error","err_message":"telegram handler timed out after 25000ms"}
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: {"event":"telegram_deadletter_write_failed","error":"TypeError: fs$1.mkdirSync is not a function"}
Feb 22 06:40:39 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:39.045Z [telegram] handler failed (correlation_id=tg-mlws9pj6-002, stage=pipeline): telegram handler timed out after 25000ms
Feb 22 06:40:40 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:40.452Z [telegram] telegram_handler_finally chatId=8159253715 messageId=522
Feb 22 06:40:51 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:40:51.796Z [telegram] telegram_handler_finally chatId=8159253715 messageId=524
Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopping openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2)...
Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:56:23.230Z [gateway] signal SIGTERM received
Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:56:23.230Z [gateway] received SIGTERM; shutting down
Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER node[1682]: 2026-02-21T20:56:23.249Z [gmail-watcher] gmail watcher stopped
Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER systemd[1643]: Stopped openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER systemd[1643]: openclaw-gateway.service: Consumed 41.493s CPU time, 1.8G memory peak, 0B memory swap peak.
Feb 22 06:56:23 jeebs-Z490-AORUS-MASTER systemd[1643]: Started openclaw-gateway.service - OpenClaw Gateway (v2026.2.19-2).
Feb 22 06:56:24 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:24.960Z [gateway] [plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.849Z [canvas] host mounted at http://127.0.0.1:18789/__openclaw__/canvas/ (root /home/jeebs/.openclaw/canvas)
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.885Z [heartbeat] started
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.889Z [health-monitor] started (interval: 300s, grace: 60s)
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.890Z [gateway] agent model: minimax-portal/MiniMax-M2.5
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.891Z [gateway] listening on ws://127.0.0.1:18789 (PID 16591)
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.892Z [gateway] listening on ws://[::1]:18789
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.893Z [gateway] log file: /tmp/openclaw/openclaw-2026-02-22.log
Feb 22 06:56:25 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:25.912Z [browser/service] Browser control service ready (profiles=2)
Feb 22 06:56:27 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:27.378Z [telegram] [default] starting provider (@jeebsdalibot)
Feb 22 06:56:27 jeebs-Z490-AORUS-MASTER node[16591]: 2026-02-21T20:56:27.381Z [telegram] autoSelectFamily=true (default-node22)
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     return self._validate_input(request, input_ids, input_text)
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/engine/serving.py", line 1074, in _validate_input
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     raise VLLMValidationError(
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323] vllm.exceptions.VLLMValidationError: This model's maximum context length is 16384 tokens. However, your request has 19069 input tokens. Please reduce the length of the input messages. (parameter=input_tokens, value=19069)
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:42876 - "POST /v1/chat/completions HTTP/1.1" 400 Bad Request
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) WARNING 02-21 16:58:46 [protocol.py:53] The following fields were present in the request but ignored: {'store'}
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323] Error in preprocessing prompt inputs
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323] Traceback (most recent call last):
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/chat_completion/serving.py", line 301, in render_chat_request
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     conversation, engine_prompts = await self._preprocess_chat(
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/engine/serving.py", line 1219, in _preprocess_chat
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     engine_prompt = await self._tokenize_prompt_input_async(
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/engine/serving.py", line 1106, in _tokenize_prompt_input_async
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     async for result in self._tokenize_prompt_inputs_async(
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/engine/serving.py", line 1127, in _tokenize_prompt_inputs_async
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     yield await self._normalize_prompt_text_to_input(
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/engine/serving.py", line 987, in _normalize_prompt_text_to_input
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     return self._validate_input(request, input_ids, input_text)
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/engine/serving.py", line 1084, in _validate_input
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323]     raise VLLMValidationError(
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) ERROR 02-21 16:58:46 [serving.py:323] vllm.exceptions.VLLMValidationError: 'max_tokens' or 'max_completion_tokens' is too large: 16000. This model's maximum context length is 16384 tokens and your request has 602 input tokens (16000 > 16384 - 602). (parameter=max_tokens, value=16000)
Feb 21 16:58:46 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:42874 - "POST /v1/chat/completions HTTP/1.1" 400 Bad Request
Feb 21 19:39:45 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:43184 - "GET /v1/models HTTP/1.1" 200 OK
Feb 21 19:45:05 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:60478 - "POST /v1/completions HTTP/1.1" 200 OK
Feb 21 19:45:07 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 19:45:07 [loggers.py:257] Engine 000: Avg prompt throughput: 100.0 tokens/s, Avg generation throughput: 1.6 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 8.7%
Feb 21 19:45:17 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 19:45:17 [loggers.py:257] Engine 000: Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 0.0 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 8.7%
Feb 21 21:13:44 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:44124 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:13:47 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:13:47 [loggers.py:257] Engine 000: Avg prompt throughput: 6.2 tokens/s, Avg generation throughput: 5.5 tokens/s, Running: 1 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.1%, Prefix cache hit rate: 10.3%
Feb 21 21:13:50 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:57838 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:13:55 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:54778 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:13:57 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:13:57 [loggers.py:257] Engine 000: Avg prompt throughput: 3.1 tokens/s, Avg generation throughput: 6.0 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 11.0%
Feb 21 21:14:07 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:14:07 [loggers.py:257] Engine 000: Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 0.0 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 11.0%
Feb 21 21:14:16 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:53106 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:14:17 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:14:17 [loggers.py:257] Engine 000: Avg prompt throughput: 6.2 tokens/s, Avg generation throughput: 4.5 tokens/s, Running: 1 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.1%, Prefix cache hit rate: 12.4%
Feb 21 21:14:21 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:53120 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:14:27 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:55622 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:14:27 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:14:27 [loggers.py:257] Engine 000: Avg prompt throughput: 3.1 tokens/s, Avg generation throughput: 7.1 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 13.0%
Feb 21 21:14:37 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:14:37 [loggers.py:257] Engine 000: Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 0.0 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 13.0%
Feb 21 21:15:17 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:15:17 [loggers.py:257] Engine 000: Avg prompt throughput: 3.1 tokens/s, Avg generation throughput: 0.4 tokens/s, Running: 1 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.1%, Prefix cache hit rate: 13.7%
Feb 21 21:15:26 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:56410 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:15:27 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:15:27 [loggers.py:257] Engine 000: Avg prompt throughput: 3.1 tokens/s, Avg generation throughput: 7.5 tokens/s, Running: 1 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.1%, Prefix cache hit rate: 14.3%
Feb 21 21:15:32 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:33136 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:15:37 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:15:37 [loggers.py:257] Engine 000: Avg prompt throughput: 3.1 tokens/s, Avg generation throughput: 7.4 tokens/s, Running: 1 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.1%, Prefix cache hit rate: 14.9%
Feb 21 21:15:40 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:53444 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:15:47 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:15:47 [loggers.py:257] Engine 000: Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 2.0 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 14.9%
Feb 21 21:15:57 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:15:57 [loggers.py:257] Engine 000: Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 0.0 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 14.9%
Feb 21 21:17:44 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:55362 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:17:47 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:17:47 [loggers.py:257] Engine 000: Avg prompt throughput: 6.2 tokens/s, Avg generation throughput: 6.1 tokens/s, Running: 1 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.1%, Prefix cache hit rate: 16.0%
Feb 21 21:17:50 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:46952 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:17:56 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:46960 - "POST /v1/chat/completions HTTP/1.1" 200 OK
Feb 21 21:17:57 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:17:57 [loggers.py:257] Engine 000: Avg prompt throughput: 3.1 tokens/s, Avg generation throughput: 6.2 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 16.6%
Feb 21 21:18:07 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-21 21:18:07 [loggers.py:257] Engine 000: Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 0.0 tokens/s, Running: 0 reqs, Waiting: 0 reqs, GPU KV cache usage: 0.0%, Prefix cache hit rate: 16.6%
Feb 21 22:05:39 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     127.0.0.1:42676 - "GET /v1/models HTTP/1.1" 200 OK
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1]: Stopping vllm-assistant.service - vLLM OpenAI Server (assistant)...
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO 02-22 00:53:22 [launcher.py:110] Shutting down FastAPI HTTP server.
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     Shutting down
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     Waiting for application shutdown.
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER env[3210]: (APIServer pid=3210) INFO:     Application shutdown complete.
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Deactivated successfully.
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1]: Stopped vllm-assistant.service - vLLM OpenAI Server (assistant).
Feb 22 00:53:22 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Consumed 11min 44.105s CPU time.
-- Boot 45b35623d291431fa703c9232d2ea952 --
Feb 22 06:34:42 jeebs-Z490-AORUS-MASTER systemd[1]: Started vllm-assistant.service - vLLM OpenAI Server (assistant).
Feb 22 06:34:46 jeebs-Z490-AORUS-MASTER env[1633]: /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/transformers/utils/hub.py:110: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.
Feb 22 06:34:46 jeebs-Z490-AORUS-MASTER env[1633]:   warnings.warn(
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [utils.py:325]
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [utils.py:325]        █     █     █▄   ▄█
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [utils.py:325]  ▄▄ ▄█ █     █     █ ▀▄▀ █  version 0.15.1
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [utils.py:325]   █▄█▀ █     █     █     █  model   /opt/models/qwen2_5_14b_instruct_awq
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [utils.py:325]    ▀▀  ▀▀▀▀▀ ▀▀▀▀▀ ▀     ▀
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [utils.py:325]
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [utils.py:261] non-default args: {'model_tag': '/opt/models/qwen2_5_14b_instruct_awq', 'api_server_count': 1, 'host': '127.0.0.1', 'port': 8001, 'model': '/opt/models/qwen2_5_14b_instruct_awq', 'max_model_len': 16384, 'quantization': 'awq', 'served_model_name': ['local-assistant'], 'max_num_seqs': 8}
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [model.py:541] Resolved architecture: Qwen2ForCausalLM
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [model.py:1561] Using max model len 16384
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [awq_marlin.py:166] Detected that the model can run with awq_marlin, however you specified quantization=awq explicitly, so forcing awq. Use quantization=awq_marlin for faster inference
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [scheduler.py:226] Chunked prefill is enabled with max_num_batched_tokens=2048.
Feb 22 06:34:50 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) INFO 02-22 06:34:50 [vllm.py:624] Asynchronous scheduling is enabled.
Feb 22 06:34:52 jeebs-Z490-AORUS-MASTER env[2827]: /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/transformers/utils/hub.py:110: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.
Feb 22 06:34:52 jeebs-Z490-AORUS-MASTER env[2827]:   warnings.warn(
Feb 22 06:34:55 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:34:55 [core.py:96] Initializing a V1 LLM engine (v0.15.1) with config: model='/opt/models/qwen2_5_14b_instruct_awq', speculative_config=None, tokenizer='/opt/models/qwen2_5_14b_instruct_awq', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=16384, download_dir=None, load_format=auto, tensor_parallel_size=1, pipeline_parallel_size=1, data_parallel_size=1, disable_custom_all_reduce=False, quantization=awq, enforce_eager=False, enable_return_routed_experts=False, kv_cache_dtype=auto, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False, enable_mfu_metrics=False, enable_mm_processor_stats=False, enable_logging_iteration_details=False), seed=0, served_model_name=local-assistant, enable_prefix_caching=True, enable_chunked_prefill=True, pooler_config=None, compilation_config={'level': None, 'mode': <CompilationMode.VLLM_COMPILE: 3>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['none'], 'splitting_ops': ['vllm::unified_attention', 'vllm::unified_attention_with_output', 'vllm::unified_mla_attention', 'vllm::unified_mla_attention_with_output', 'vllm::mamba_mixer2', 'vllm::mamba_mixer', 'vllm::short_conv', 'vllm::linear_attention', 'vllm::plamo2_mamba_mixer', 'vllm::gdn_attention_core', 'vllm::kda_attention', 'vllm::sparse_attn_indexer', 'vllm::rocm_aiter_sparse_attn_indexer', 'vllm::unified_kv_cache_update'], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_split_points': [2048], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE: (2, 1)>, 'cudagraph_num_of_warmups': 1, 'cudagraph_capture_sizes': [1, 2, 4, 8, 16], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': False, 'fuse_act_quant': False, 'fuse_attn_quant': False, 'eliminate_noops': True, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 16, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': True}, 'local_cache_dir': None, 'static_all_moe_layers': []}
Feb 22 06:34:55 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:34:55 [parallel_state.py:1212] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://[2001:8003:63ce:4a00:c765:1888:516e:f8fe]:56515 backend=nccl
Feb 22 06:34:55 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:34:55 [parallel_state.py:1423] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank N/A
Feb 22 06:34:56 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:34:56 [gpu_model_runner.py:4033] Starting to load model /opt/models/qwen2_5_14b_instruct_awq...
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/tvm_ffi/_optional_torch_c_dlpack.py:174: UserWarning: Failed to JIT torch c dlpack extension, EnvTensorAllocator will not be enabled.
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) We recommend installing via `pip install torch-c-dlpack-ext`
Feb 22 06:34:58 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   warnings.warn(
Feb 22 06:34:59 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:34:59 [cuda.py:364] Using FLASH_ATTN attention backend out of potential backends: ('FLASH_ATTN', 'FLASHINFER', 'TRITON_ATTN', 'FLEX_ATTENTION')
Feb 22 06:34:59 jeebs-Z490-AORUS-MASTER env[2827]: [103B blob data]
Feb 22 06:35:01 jeebs-Z490-AORUS-MASTER env[2827]: [111B blob data]
Feb 22 06:35:06 jeebs-Z490-AORUS-MASTER env[2827]: [111B blob data]
Feb 22 06:35:10 jeebs-Z490-AORUS-MASTER env[2827]: [111B blob data]
Feb 22 06:35:10 jeebs-Z490-AORUS-MASTER env[2827]: [111B blob data]
Feb 22 06:35:10 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)
Feb 22 06:35:10 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:10 [default_loader.py:291] Loading weights took 11.13 seconds
Feb 22 06:35:10 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:10 [gpu_model_runner.py:4130] Model loading took 9.38 GiB memory and 14.168070 seconds
Feb 22 06:35:18 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:18 [backends.py:812] Using cache directory: /home/jeebs/.cache/vllm/torch_compile_cache/2e488e759d/rank_0_0/backbone for vLLM's torch.compile
Feb 22 06:35:18 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:18 [backends.py:872] Dynamo bytecode transform time: 7.37 s
Feb 22 06:35:26 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:26 [backends.py:267] Directly load the compiled graph(s) for compile range (1, 2048) from the cache, took 1.908 s
Feb 22 06:35:26 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:26 [monitor.py:34] torch.compile takes 9.27 s in total
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) INFO 02-22 06:35:27 [gpu_worker.py:356] Available KV cache memory: 1.87 GiB
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946] EngineCore failed to start.
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946] Traceback (most recent call last):
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     super().__init__(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 112, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     num_gpu_blocks, num_cpu_blocks, kv_cache_config = self._initialize_kv_caches(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]                                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 253, in _initialize_kv_caches
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     kv_cache_configs = get_kv_cache_configs(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]                        ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 1516, in get_kv_cache_configs
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     _check_enough_kv_cache_memory(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 634, in _check_enough_kv_cache_memory
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946]     raise ValueError(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ERROR 02-22 06:35:27 [core.py:946] ValueError: To serve at least one request with the models's max seq len (16384), (3.0 GiB KV cache is needed, which is larger than the available KV cache memory (1.87 GiB). Based on the available memory, the estimated maximum model length is 10224. Try increasing `gpu_memory_utilization` or decreasing `max_model_len` when initializing the engine. See https://docs.vllm.ai/en/latest/configuration/conserving_memory/ for more details.
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) Process EngineCore_DP0:
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) Traceback (most recent call last):
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/usr/lib/python3.12/multiprocessing/process.py", line 314, in _bootstrap
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     self.run()
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/usr/lib/python3.12/multiprocessing/process.py", line 108, in run
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     self._target(*self._args, **self._kwargs)
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 950, in run_engine_core
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     raise e
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 937, in run_engine_core
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 691, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     super().__init__(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 112, in __init__
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     num_gpu_blocks, num_cpu_blocks, kv_cache_config = self._initialize_kv_caches(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)                                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core.py", line 253, in _initialize_kv_caches
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     kv_cache_configs = get_kv_cache_configs(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)                        ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 1516, in get_kv_cache_configs
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     _check_enough_kv_cache_memory(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/core/kv_cache_utils.py", line 634, in _check_enough_kv_cache_memory
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827)     raise ValueError(
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: (EngineCore_DP0 pid=2827) ValueError: To serve at least one request with the models's max seq len (16384), (3.0 GiB KV cache is needed, which is larger than the available KV cache memory (1.87 GiB). Based on the available memory, the estimated maximum model length is 10224. Try increasing `gpu_memory_utilization` or decreasing `max_model_len` when initializing the engine. See https://docs.vllm.ai/en/latest/configuration/conserving_memory/ for more details.
Feb 22 06:35:27 jeebs-Z490-AORUS-MASTER env[2827]: [rank0]:[W222 06:35:27.321548260 ProcessGroupNCCL.cpp:1524] Warning: WARNING: destroy_process_group() was not called before program exit, which can leak resources. For more info, please see https://pytorch.org/docs/stable/distributed.html#shutdown (function operator())
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) Traceback (most recent call last):
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/bin/vllm", line 6, in <module>
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     sys.exit(main())
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)              ^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/main.py", line 73, in main
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     args.dispatch_function(args)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/cli/serve.py", line 111, in cmd
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     uvloop.run(run_server(args))
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 96, in run
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return __asyncio.run(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return runner.run(main)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return self._loop.run_until_complete(task)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/uvloop/__init__.py", line 48, in wrapper
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return await main
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 919, in run_server
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     await run_server_worker(listen_address, sock, args, **uvicorn_kwargs)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 938, in run_server_worker
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     async with build_async_engine_client(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return await anext(self.gen)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 147, in build_async_engine_client
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     async with build_async_engine_client_from_engine_args(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/contextlib.py", line 210, in __aenter__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return await anext(self.gen)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/entrypoints/openai/api_server.py", line 188, in build_async_engine_client_from_engine_args
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     async_llm = AsyncLLM.from_vllm_config(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)                 ^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 228, in from_vllm_config
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return cls(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/async_llm.py", line 155, in __init__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     self.engine_core = EngineCoreClient.make_async_mp_client(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 122, in make_async_mp_client
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     return AsyncMPClient(*client_args)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 819, in __init__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     super().__init__(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/core_client.py", line 479, in __init__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     with launch_core_engines(vllm_config, executor_class, log_stats) as (
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/usr/lib/python3.12/contextlib.py", line 144, in __exit__
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     next(self.gen)
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 933, in launch_core_engines
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     wait_for_engine_startup(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)   File "/home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/vllm/v1/engine/utils.py", line 992, in wait_for_engine_startup
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633)     raise RuntimeError(
Feb 22 06:35:28 jeebs-Z490-AORUS-MASTER env[1633]: (APIServer pid=1633) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
Feb 22 06:35:29 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Main process exited, code=exited, status=1/FAILURE
Feb 22 06:35:29 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Failed with result 'exit-code'.
Feb 22 06:35:29 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Consumed 38.244s CPU time.
Feb 22 06:35:31 jeebs-Z490-AORUS-MASTER systemd[1]: vllm-assistant.service: Scheduled restart job, restart counter is at 1.
Feb 22 06:35:31 jeebs-Z490-AORUS-MASTER systemd[1]: Started vllm-assistant.service - vLLM OpenAI Server (assistant).
Feb 22 06:35:32 jeebs-Z490-AORUS-MASTER env[3285]: /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/transformers/utils/hub.py:110: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.
Feb 22 06:35:32 jeebs-Z490-AORUS-MASTER env[3285]:   warnings.warn(
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]        █     █     █▄   ▄█
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]  ▄▄ ▄█ █     █     █ ▀▄▀ █  version 0.15.1
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]   █▄█▀ █     █     █     █  model   /opt/models/qwen2_5_14b_instruct_awq
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]    ▀▀  ▀▀▀▀▀ ▀▀▀▀▀ ▀     ▀
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:325]
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [utils.py:261] non-default args: {'model_tag': '/opt/models/qwen2_5_14b_instruct_awq', 'api_server_count': 1, 'host': '127.0.0.1', 'port': 8001, 'model': '/opt/models/qwen2_5_14b_instruct_awq', 'max_model_len': 16384, 'quantization': 'awq', 'served_model_name': ['local-assistant'], 'max_num_seqs': 8}
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [model.py:541] Resolved architecture: Qwen2ForCausalLM
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [model.py:1561] Using max model len 16384
Feb 22 06:35:35 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:35 [awq_marlin.py:166] Detected that the model can run with awq_marlin, however you specified quantization=awq explicitly, so forcing awq. Use quantization=awq_marlin for faster inference
Feb 22 06:35:36 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:36 [scheduler.py:226] Chunked prefill is enabled with max_num_batched_tokens=2048.
Feb 22 06:35:36 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:35:36 [vllm.py:624] Asynchronous scheduling is enabled.
Feb 22 06:35:38 jeebs-Z490-AORUS-MASTER env[3361]: /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/transformers/utils/hub.py:110: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.
Feb 22 06:35:38 jeebs-Z490-AORUS-MASTER env[3361]:   warnings.warn(
Feb 22 06:35:40 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:40 [core.py:96] Initializing a V1 LLM engine (v0.15.1) with config: model='/opt/models/qwen2_5_14b_instruct_awq', speculative_config=None, tokenizer='/opt/models/qwen2_5_14b_instruct_awq', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=16384, download_dir=None, load_format=auto, tensor_parallel_size=1, pipeline_parallel_size=1, data_parallel_size=1, disable_custom_all_reduce=False, quantization=awq, enforce_eager=False, enable_return_routed_experts=False, kv_cache_dtype=auto, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False, enable_mfu_metrics=False, enable_mm_processor_stats=False, enable_logging_iteration_details=False), seed=0, served_model_name=local-assistant, enable_prefix_caching=True, enable_chunked_prefill=True, pooler_config=None, compilation_config={'level': None, 'mode': <CompilationMode.VLLM_COMPILE: 3>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['none'], 'splitting_ops': ['vllm::unified_attention', 'vllm::unified_attention_with_output', 'vllm::unified_mla_attention', 'vllm::unified_mla_attention_with_output', 'vllm::mamba_mixer2', 'vllm::mamba_mixer', 'vllm::short_conv', 'vllm::linear_attention', 'vllm::plamo2_mamba_mixer', 'vllm::gdn_attention_core', 'vllm::kda_attention', 'vllm::sparse_attn_indexer', 'vllm::rocm_aiter_sparse_attn_indexer', 'vllm::unified_kv_cache_update'], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_split_points': [2048], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE: (2, 1)>, 'cudagraph_num_of_warmups': 1, 'cudagraph_capture_sizes': [1, 2, 4, 8, 16], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': False, 'fuse_act_quant': False, 'fuse_attn_quant': False, 'eliminate_noops': True, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 16, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False, 'assume_32_bit_indexing': True}, 'local_cache_dir': None, 'static_all_moe_layers': []}
Feb 22 06:35:40 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:40 [parallel_state.py:1212] world_size=1 rank=0 local_rank=0 distributed_init_method=tcp://192.168.0.162:49255 backend=nccl
Feb 22 06:35:41 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:41 [parallel_state.py:1423] rank 0 in world size 1 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank N/A
Feb 22 06:35:41 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:41 [gpu_model_runner.py:4033] Starting to load model /opt/models/qwen2_5_14b_instruct_awq...
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) /home/jeebs/src/clawd/.venv-vllm/lib/python3.12/site-packages/tvm_ffi/_optional_torch_c_dlpack.py:174: UserWarning: Failed to JIT torch c dlpack extension, EnvTensorAllocator will not be enabled.
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) We recommend installing via `pip install torch-c-dlpack-ext`
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361)   warnings.warn(
Feb 22 06:35:42 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:42 [cuda.py:364] Using FLASH_ATTN attention backend out of potential backends: ('FLASH_ATTN', 'FLASHINFER', 'TRITON_ATTN', 'FLEX_ATTENTION')
Feb 22 06:35:43 jeebs-Z490-AORUS-MASTER env[3361]: [103B blob data]
Feb 22 06:35:43 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: [111B blob data]
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361)
Feb 22 06:35:44 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:44 [default_loader.py:291] Loading weights took 1.74 seconds
Feb 22 06:35:45 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:45 [gpu_model_runner.py:4130] Model loading took 9.38 GiB memory and 3.424887 seconds
Feb 22 06:35:52 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:52 [backends.py:812] Using cache directory: /home/jeebs/.cache/vllm/torch_compile_cache/2e488e759d/rank_0_0/backbone for vLLM's torch.compile
Feb 22 06:35:52 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:52 [backends.py:872] Dynamo bytecode transform time: 7.05 s
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [backends.py:267] Directly load the compiled graph(s) for compile range (1, 2048) from the cache, took 1.047 s
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [monitor.py:34] torch.compile takes 8.10 s in total
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [gpu_worker.py:356] Available KV cache memory: 11.33 GiB
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [kv_cache_utils.py:1307] GPU KV cache size: 61,872 tokens
Feb 22 06:35:59 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:35:59 [kv_cache_utils.py:1312] Maximum concurrency for 16,384 tokens per request: 3.78x
Feb 22 06:36:00 jeebs-Z490-AORUS-MASTER env[3361]: [819B blob data]
Feb 22 06:36:01 jeebs-Z490-AORUS-MASTER env[3361]: [594B blob data]
Feb 22 06:36:01 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:36:01 [gpu_model_runner.py:5063] Graph capturing finished in 2 secs, took 0.43 GiB
Feb 22 06:36:01 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:36:01 [core.py:272] init engine (profile, create kv cache, warmup model) took 16.62 seconds
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3361]: (EngineCore_DP0 pid=3361) INFO 02-22 06:36:02 [vllm.py:624] Asynchronous scheduling is enabled.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [api_server.py:665] Supported tasks: ['generate']
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) WARNING 02-22 06:36:02 [model.py:1371] Default vLLM sampling parameters have been overridden by the model's `generation_config.json`: `{'repetition_penalty': 1.05, 'temperature': 0.7, 'top_k': 20, 'top_p': 0.8}`. If this is not intended, please relaunch vLLM instance with `--generation-config vllm`.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [serving.py:177] Warming up chat template processing...
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [hf.py:310] Detected the chat template content format to be 'string'. You can set `--chat-template-content-format` to override this.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [serving.py:212] Chat template warmup completed in 178.6ms
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [api_server.py:946] Starting vLLM API server 0 on http://127.0.0.1:8001
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:38] Available routes are:
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /openapi.json, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /docs, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /docs/oauth2-redirect, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /redoc, Methods: HEAD, GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /scale_elastic_ep, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /is_scaling_elastic_ep, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /tokenize, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /detokenize, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /inference/v1/generate, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pause, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /resume, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /is_paused, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /metrics, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /health, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/chat/completions, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/chat/completions/render, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/responses, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/responses/{response_id}, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/responses/{response_id}/cancel, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/audio/transcriptions, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/audio/translations, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/completions, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/completions/render, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/messages, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/models, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /load, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /version, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /ping, Methods: GET
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /ping, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /invocations, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /classify, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/embeddings, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/score, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v1/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /v2/rerank, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO 02-22 06:36:02 [launcher.py:46] Route: /pooling, Methods: POST
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Started server process [3285]
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Waiting for application startup.
Feb 22 06:36:02 jeebs-Z490-AORUS-MASTER env[3285]: (APIServer pid=3285) INFO:     Application startup complete.
```

## Phase 2 Interpretation Rubric
- If `tg-mlws9pj6-002` stops occurring after duplicate launcher disable and vLLM is stable, restart-loop is a likely proximal contributor.
- If telegram timeout signatures persist while vLLM remains stable/singleton, treat as independent gateway/telegram latency path.

## Phase 3 Verification (No Relapse)

```bash
set -euo pipefail
date -u

# Re-run observational audit script
bash -lc '~/bin/python-env-audit.sh' || true

# Restart gateway (user) and confirm singleton remains
systemctl --user restart openclaw-gateway.service
sleep 2
ss -ltnp | grep -E '(:8001)\b' || true
pgrep -af 'vllm|openai\.api_server|api_server' || true

# Confirm the user vLLM service remains disabled
systemctl --user is-enabled openclaw-vllm.service || true
```

```text
Sat Feb 21 21:02:20 UTC 2026
Wrote /home/jeebs/security-audits/python-audit-20260222T070220.txt
LISTEN 0      2048       127.0.0.1:8001       0.0.0.0:*    users:(("vllm",pid=3285,fd=25))           
3285 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 /home/jeebs/src/clawd/.venv-vllm/bin/vllm serve /opt/models/qwen2_5_14b_instruct_awq --served-model-name local-assistant --host 127.0.0.1 --port 8001 --quantization awq --dtype auto --gpu-memory-utilization 0.90 --max-model-len 16384 --max-num-seqs 8
3360 /home/jeebs/src/clawd/.venv-vllm/bin/python3.12 -c from multiprocessing.resource_tracker import main;main(34)
17583 /bin/bash -c set -euo pipefail cd /home/jeebs/src/clawd AUDIT='workspace/audit/dali_vllm_singleton_guard_20260221T210005Z.md' append_cmd(){   local cmd="$1"   {     echo '```bash'     printf '%s\n' "$cmd"     echo '```'     echo     echo '```text'   } >> "$AUDIT"   bash -lc "$cmd" >> "$AUDIT" 2>&1 || true   {     echo '```'     echo   } >> "$AUDIT" }  append_cmd "set -euo pipefail # Focused search excluding prior audit documents rg -n --hidden -S \   'openclaw-vllm\\.service|systemctl --user.*enable.*vllm|enable.*openclaw-vllm|systemctl --user.*(start|restart).*vllm' \   ~/bin ~/.local/bin ~/.config/systemd ~/.config/autostart workspace scripts .github \   -g '!workspace/audit/**' -g '!workspace/artifacts/**' -g '!.git/**' || true"  cat >> "$AUDIT" <<'EOF' ## Phase 1 Decision If no executable installer/maintenance path is found that enables `openclaw-vllm.service`, no code patch is warranted; preserve minimal-diff by shipping audit-only evidence.  EOF  {   echo '## Phase 2 Causality Check (tg-mlws9pj6-002)'   echo } >> "$AUDIT" append_cmd "set -euo pipefail date -u  # Snapshot services and restart counters (if present) systemctl status vllm-assistant.service --no-pager || true systemctl --user status openclaw-gateway.service --no-pager || true systemctl --user status openclaw-vllm.service --no-pager || true  # Confirm port 8001 owner + vLLM process stability ss -ltnp | grep -E '(:8001)\\b' || true pgrep -af 'vllm|openai\\.api_server|api_server' || true  # Gateway logs (recent window) journalctl --user -u openclaw-gateway.service -n 300 --no-pager || true  # vLLM logs for stability journalctl -u vllm-assistant.service -n 300 --no-pager || true"  cat >> "$AUDIT" <<'EOF' ## Phase 2 Interpretation Rubric - If `tg-mlws9pj6-002` stops occurring after duplicate launcher disable and vLLM is stable, restart-loop is a likely proximal contributor. - If telegram timeout signatures persist while vLLM remains stable/singleton, treat as independent gateway/telegram latency path.  EOF  {   echo '## Phase 3 Verification (No Relapse)'   echo } >> "$AUDIT" append_cmd "set -euo pipefail date -u  # Re-run observational audit script bash -lc '~/bin/python-env-audit.sh' || true  # Restart gateway (user) and confirm singleton remains systemctl --user restart openclaw-gateway.service sleep 2 ss -ltnp | grep -E '(:8001)\\b' || true pgrep -af 'vllm|openai\\.api_server|api_server' || true  # Confirm the user vLLM service remains disabled systemctl --user is-enabled openclaw-vllm.service || true"  echo done
17616 bash -lc set -euo pipefail date -u  # Re-run observational audit script bash -lc '~/bin/python-env-audit.sh' || true  # Restart gateway (user) and confirm singleton remains systemctl --user restart openclaw-gateway.service sleep 2 ss -ltnp | grep -E '(:8001)\b' || true pgrep -af 'vllm|openai\.api_server|api_server' || true  # Confirm the user vLLM service remains disabled systemctl --user is-enabled openclaw-vllm.service || true
disabled
```

```bash
date -u; date
journalctl --user -u openclaw-gateway.service --since '2026-02-22 07:00:00' --no-pager | rg -n 'tg-mlws9pj6-002|telegram_handler_failed|timed out after' || true
```

```text
Sat Feb 21 21:03:17 UTC 2026
Sun Feb 22 07:03:17 AEST 2026
```

## Findings Summary
- Re-enable path recon (focused, excluding audit/artifact noise) found **no active installer or maintenance script** in searched paths that enables `openclaw-vllm.service`.
- Current service state remains singleton:
  - `vllm-assistant.service`: enabled/active.
  - `openclaw-vllm.service`: disabled/inactive.
  - Port `127.0.0.1:8001` owned by a single vLLM PID.
- Causality check for `tg-mlws9pj6-002`:
  - The correlation id is present in historical logs at `2026-02-22 06:40:39 AEST`.
  - In this verification window (from `2026-02-22 07:00:00 AEST` onward), no recurrence of `tg-mlws9pj6-002` was observed in captured logs.
  - Interpretation: duplicate-launcher restart-loop is a plausible proximal contributor, but this run does not establish exclusive causality.

## Patch Decision
- **No Phase 1.1 code patch applied** (audit-only): no concrete re-enable mechanism was found in executable scripts under the requested search scope.
- This preserves minimal-diff policy and avoids speculative changes.

## Rollback
1. Revert this audit commit:
   - `git revert <commit_sha>`
2. If intentionally restoring the old duplicate-prone setup:
   - `systemctl --user enable --now openclaw-vllm.service`
3. Keep singleton owner as system service (recommended):
   - `sudo systemctl enable --now vllm-assistant.service`

