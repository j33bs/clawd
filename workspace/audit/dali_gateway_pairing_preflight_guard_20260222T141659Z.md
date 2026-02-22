# Dali Gateway Pairing Preflight Guard Audit

- UTC: 20260222T141659Z
- Branch: codex/chore/dali-gateway-pairing-preflight-20260223
- HEAD: ea2a2044966624d6e818998b36ac1b6e4f4b846e
- Objective: add preflight guard to detect pending pairing/repair and fail fast before sub-agent/gateway churn.
- Constraints: minimal diff, reversible, evidence-first, no unrelated changes, no secrets printed.
- Acceptance criteria: guard exits 0 on healthy; exits non-zero with remediation when pending pairing/repair exists.

## Phase 1 — Wiring point discovery
```text
$ ls -la workspace/scripts | sed -n "1,200p"
total 572
drwxrwxr-x  4 jeebs jeebs  4096 Feb 22 21:03 .
drwxrwxr-x 31 jeebs jeebs  4096 Feb 22 21:03 ..
-rw-rw-r--  1 jeebs jeebs   473 Feb 22 21:03 approve_integrity_baseline.sh
-rwxrwxr-x  1 jeebs jeebs  6108 Feb 22 21:03 audit_commit_hook.py
-rwxrwxr-x  1 jeebs jeebs 16344 Feb 22 21:03 automation_status.py
-rwxrwxr-x  1 jeebs jeebs  1027 Feb 22 21:03 await_mouse_idle.py
-rwxrwxr-x  1 jeebs jeebs   798 Feb 22 21:03 calendar.sh
-rw-rw-r--  1 jeebs jeebs  9222 Feb 22 21:03 compare_token_burn.py
-rwxrwxr-x  1 jeebs jeebs  2962 Feb 22 21:03 consciousness_timer.py
-rw-rw-r--  1 jeebs jeebs  2177 Feb 22 21:03 daily_brief_generator.py
-rw-rw-r--  1 jeebs jeebs  7153 Feb 22 21:03 diagnose_openclaw_status_hang.py
-rwxrwxr-x  1 jeebs jeebs  1700 Feb 22 21:03 dream_consolidation.py
-rwxrwxr-x  1 jeebs jeebs   558 Feb 22 21:03 dream_consolidation.sh
-rwxrwxr-x  1 jeebs jeebs  9173 Feb 22 21:03 ensure_cron_jobs.py
-rwxrwxr-x  1 jeebs jeebs  2495 Feb 22 21:03 epistemic.py
-rwxrwxr-x  1 jeebs jeebs  1883 Feb 22 21:03 external_memory_demo.py
-rw-rw-r--  1 jeebs jeebs  1409 Feb 22 21:03 extract_decisions.py
-rwxrwxr-x  1 jeebs jeebs   876 Feb 22 21:03 failure_archaeology.py
drwxrwxr-x  2 jeebs jeebs  4096 Feb 22 21:03 hooks
-rwxrwxr-x  1 jeebs jeebs   816 Feb 22 21:03 install-hooks.sh
-rwxrwxr-x  1 jeebs jeebs   626 Feb 22 21:03 install_git_hooks.sh
-rw-rw-r--  1 jeebs jeebs   172 Feb 22 21:03 intent_failure_report.sh
-rw-rw-r--  1 jeebs jeebs 11533 Feb 22 21:03 intent_failure_scan.py
drwxrwxr-x  2 jeebs jeebs  4096 Feb 22 21:03 itc
-rwxrwxr-x  1 jeebs jeebs  1681 Feb 22 21:03 kb_daily_brief.py
-rw-rw-r--  1 jeebs jeebs  8125 Feb 22 21:03 message_handler.py
-rw-rw-r--  1 jeebs jeebs  7714 Feb 22 21:03 message_load_balancer.py
-rwxrwxr-x  1 jeebs jeebs  1846 Feb 22 21:03 metacognitive_loop.py
-rwxrwxr-x  1 jeebs jeebs  1891 Feb 22 21:03 mouse_monitor.py
-rw-rw-r--  1 jeebs jeebs 10164 Feb 22 21:03 narrative_distill.py
-rwxrwxr-x  1 jeebs jeebs  8134 Feb 22 21:03 nightly_build.sh
-rwxrwxr-x  1 jeebs jeebs  9099 Feb 22 21:03 openclaw_autoupdate.sh
-rwxrwxr-x  1 jeebs jeebs   907 Feb 22 21:03 phenomenal_binding.py
-rw-rw-r--  1 jeebs jeebs 69540 Feb 22 21:03 policy_router.py
-rw-rw-r--  1 jeebs jeebs 31503 Feb 22 21:03 preflight_check.py
-rw-rw-r--  1 jeebs jeebs  3371 Feb 22 21:03 proprioception.py
-rw-rw-r--  1 jeebs jeebs  2013 Feb 22 21:03 quarantine_artifacts.py
-rw-rw-r--  1 jeebs jeebs 10848 Feb 22 21:03 regression.sh
-rwxrwxr-x  1 jeebs jeebs   100 Feb 22 21:03 regression_core.sh
-rwxrwxr-x  1 jeebs jeebs   100 Feb 22 21:03 regression_paid.sh
-rw-rw-r--  1 jeebs jeebs 14877 Feb 22 21:03 report_token_burn.py
-rw-rw-r--  1 jeebs jeebs  2980 Feb 22 21:03 run_narrative_distill.py
-rwxrwxr-x  1 jeebs jeebs  7691 Feb 22 21:03 run_novel10_fixture.py
-rw-rw-r--  1 jeebs jeebs  3241 Feb 22 21:03 safe_error_surface.js
-rw-rw-r--  1 jeebs jeebs  3923 Feb 22 21:03 safe_error_surface.py
-rwxrwxr-x  1 jeebs jeebs   758 Feb 22 21:03 semantic_immune_approve.py
-rwxrwxr-x  1 jeebs jeebs  1720 Feb 22 21:03 smart_calendar.sh
-rwxrwxr-x  1 jeebs jeebs   891 Feb 22 21:03 sync_heartbeat.sh
-rwxrwxr-x  1 jeebs jeebs  5407 Feb 22 21:03 system_health_monitor.py
-rw-rw-r--  1 jeebs jeebs 35628 Feb 22 21:03 team_chat.py
-rw-rw-r--  1 jeebs jeebs 13995 Feb 22 21:03 team_chat_adapters.py
-rwxrwxr-x  1 jeebs jeebs   436 Feb 22 21:03 temporal_beacon_update.py
-rw-rw-r--  1 jeebs jeebs  1887 Feb 22 21:03 test_intent_failure_taxonomy.py
-rw-rw-r--  1 jeebs jeebs  4770 Feb 22 21:03 verify.sh
-rw-rw-r--  1 jeebs jeebs  1099 Feb 22 21:03 verify_allowlist.py
-rw-rw-r--  1 jeebs jeebs   622 Feb 22 21:03 verify_coding_ladder.sh
-rwxrwxr-x  1 jeebs jeebs  1101 Feb 22 21:03 verify_dream_consolidation.sh
-rw-rw-r--  1 jeebs jeebs  8632 Feb 22 21:03 verify_goal_identity_invariants.py
-rw-rw-r--  1 jeebs jeebs   200 Feb 22 21:03 verify_intent_failure_scan.sh
-rw-rw-r--  1 jeebs jeebs  3717 Feb 22 21:03 verify_llm_policy.sh
-rwxrwxr-x  1 jeebs jeebs  1622 Feb 22 21:03 verify_nightly_health_config.sh
-rw-rw-r--  1 jeebs jeebs  5863 Feb 22 21:03 verify_policy_provider_aliases.py
-rw-rw-r--  1 jeebs jeebs 18174 Feb 22 21:03 verify_policy_router.sh
-rw-rw-r--  1 jeebs jeebs   201 Feb 22 21:03 verify_preflight.sh
-rwxrwxr-x  1 jeebs jeebs  1835 Feb 22 21:03 verify_runtime_autoupdate.sh
-rw-rw-r--  1 jeebs jeebs  1869 Feb 22 21:03 verify_security_config.sh
-rwxrwxr-x  1 jeebs jeebs  2337 Feb 22 21:03 verify_tacti_cr_events.py
-rwxrwxr-x  1 jeebs jeebs   241 Feb 22 21:03 verify_tacti_cr_events.sh
-rwxrwxr-x  1 jeebs jeebs  2227 Feb 22 21:03 verify_tacti_cr_novel10_fixture.py
-rwxrwxr-x  1 jeebs jeebs   846 Feb 22 21:03 verify_tacti_cr_novel10_fixture.sh
-rwxrwxr-x  1 jeebs jeebs  1946 Feb 22 21:03 verify_tacti_cr_novel_10.sh
-rwxrwxr-x  1 jeebs jeebs  2064 Feb 22 21:03 verify_tacti_system.sh
-rwxrwxr-x  1 jeebs jeebs  1685 Feb 22 21:03 verify_team_chat.sh
-rwxrwxr-x  1 jeebs jeebs   169 Feb 22 21:03 verify_teamchat_witness.sh
-rw-rw-r--  1 jeebs jeebs   495 Feb 22 21:03 verify_token_burn_tools.sh
-rw-rw-r--  1 jeebs jeebs  3770 Feb 22 21:03 witness_ledger.py

$ rg -n "subagent|spawn|run_multi_agent|gateway|sessions_|pairing|devices list|openclaw status|openclaw health" workspace/scripts workspace/**.js workspace/**.ts || true
workspace/scripts/message_handler.py:5:Integrates message_load_balancer with OpenClaw gateway for:
workspace/scripts/message_handler.py:30:    def __init__(self, gateway_url: str, token: str):
workspace/scripts/message_handler.py:31:        self.gateway_url = gateway_url
workspace/scripts/message_handler.py:42:                    f"{self.gateway_url}/api/status",
workspace/scripts/message_handler.py:128:async def send_telegram_reply(chat_id: str, message_id: str, text: str, gateway_url: str, token: str):
workspace/scripts/message_handler.py:142:            f"{gateway_url}/api/tool/message",
workspace/scripts/message_handler.py:149:async def spawn_chatgpt_subagent(task: str, context: dict, gateway_url: str, token: str):
workspace/scripts/message_handler.py:150:    """Spawn a ChatGPT subagent to handle a message.
workspace/scripts/message_handler.py:152:    Uses OpenClaw's sessions_spawn internally.
workspace/scripts/message_handler.py:166:            f"{gateway_url}/api/agents/spawn",
workspace/scripts/message_handler.py:195:        # Spawn ChatGPT subagent
workspace/scripts/message_handler.py:196:        result = await spawn_chatgpt_subagent(
workspace/scripts/message_handler.py:199:            gateway_url=GATEWAY_URL,
workspace/scripts/message_handler.py:205:        # Use MiniMax (normal flow) - would integrate with gateway here
workspace/scripts/message_handler.py:214:            gateway_url=GATEWAY_URL,
workspace/scripts/diagnose_openclaw_status_hang.py:3:Diagnose why `openclaw status` hangs using timeboxed, read-only checks.
workspace/scripts/diagnose_openclaw_status_hang.py:69:    status = by_cmd.get("openclaw status")
workspace/scripts/diagnose_openclaw_status_hang.py:70:    deep = by_cmd.get("openclaw status --deep")
workspace/scripts/diagnose_openclaw_status_hang.py:71:    js = by_cmd.get("openclaw status --json")
workspace/scripts/diagnose_openclaw_status_hang.py:74:        notes.append("Both `openclaw status` and `openclaw status --deep` timed out. Likely CLI/daemon wait, lock contention, or backend hang.")
workspace/scripts/diagnose_openclaw_status_hang.py:80:            notes.append("`openclaw status --json` appears unsupported in this CLI version.")
workspace/scripts/diagnose_openclaw_status_hang.py:87:    parser = argparse.ArgumentParser(description="Diagnose openclaw status hangs")
workspace/scripts/diagnose_openclaw_status_hang.py:140:            "command": "strace openclaw status",
workspace/scripts/safe_error_surface.js:50:  errorCode = 'gateway_error',
workspace/scripts/safe_error_surface.js:62:    log_ref: logRef || 'check local gateway logs with request_id',
workspace/scripts/safe_error_surface.js:70:    error_code: String(envelope.error_code || 'gateway_error'),
workspace/scripts/intent_failure_scan.py:87:            "Retry `openclaw status` without --deep if it hangs",
workspace/scripts/verify_policy_router.sh:332:            "subagentProvider": "local_vllm_assistant",
workspace/scripts/verify_policy_router.sh:372:        subagent_sel = router.select_model(
workspace/scripts/verify_policy_router.sh:374:            {"input_text": "use chatgpt", "is_subagent": True, "agent_class": "subagent"},
workspace/scripts/verify_policy_router.sh:376:        assert subagent_sel["provider"] == "local_vllm_assistant", subagent_sel
workspace/scripts/verify_policy_router.sh:377:        assert subagent_sel["model"] == "vllm/local-assistant", subagent_sel
workspace/scripts/safe_error_surface.py:2:"""Safe error surface + redaction helpers for gateway adapters."""
workspace/scripts/safe_error_surface.py:68:    error_code: str = "gateway_error",
workspace/scripts/safe_error_surface.py:80:        "log_ref": log_ref or "check local gateway logs with request_id",
workspace/scripts/safe_error_surface.py:88:        "error_code": str(envelope.get("error_code", "gateway_error")),
workspace/scripts/verify_runtime_autoupdate.sh:43:if grep -q "executed:gateway_install:openclaw gateway install --force" "$log_file"; then
workspace/scripts/verify_runtime_autoupdate.sh:44:  echo "error: dry-run executed gateway install" >&2
workspace/scripts/preflight_check.py:34:PAIRING = BASE_DIR / "credentials" / "telegram-pairing.json"
workspace/scripts/preflight_check.py:788:    if tg.get("dmPolicy") == "pairing":
workspace/scripts/preflight_check.py:789:        pairing = load_json(PAIRING) or {}
workspace/scripts/preflight_check.py:790:        if not pairing.get("requests") and not allowlist:
workspace/scripts/preflight_check.py:792:                "Telegram pairing is required but no paired users exist",
workspace/scripts/policy_router.py:219:            "subagentProvider": "local_vllm_assistant",
workspace/scripts/policy_router.py:725:def _is_subagent_context(context):
workspace/scripts/policy_router.py:728:    if context.get("subagent") or context.get("is_subagent"):
workspace/scripts/policy_router.py:732:        if value in {"subagent", "worker", "tool", "tool_agent", "child_agent"}:
workspace/scripts/policy_router.py:1117:        apply_to_subagents = bool(cfg.get("explicitApplyToSubagents", False))
workspace/scripts/policy_router.py:1118:        subagent = _is_subagent_context(context_metadata)
workspace/scripts/policy_router.py:1120:        if not subagent or apply_to_subagents:
workspace/scripts/policy_router.py:1130:        if subagent:
workspace/scripts/policy_router.py:1131:            provider = cfg.get("subagentProvider")
workspace/scripts/policy_router.py:1134:                    "trigger": "subagent_default",
workspace/scripts/policy_router.py:1135:                    "matched": "subagent=true",
workspace/scripts/policy_router.py:1137:                    "reason": "subagent primary uses local provider",
workspace/scripts/policy_router.py:1157:                provider = mechanical_provider or code_provider or cfg.get("subagentProvider")
workspace/scripts/policy_router.py:1163:                    "reason": "mechanical/execution class prefers local vLLM subagent",
workspace/scripts/team_chat.py:412:    sessions_file = base_dir / "sessions" / f"{session_id}.jsonl"
workspace/scripts/team_chat.py:480:                sessions_file,
workspace/scripts/team_chat.py:533:            sessions_file,
workspace/scripts/team_chat.py:549:            sessions_file,
workspace/scripts/team_chat.py:561:        sessions_file,
workspace/scripts/team_chat.py:579:                sessions_file,
workspace/scripts/team_chat.py:589:                sessions_file,
workspace/scripts/team_chat.py:607:                sessions_file,
workspace/scripts/team_chat.py:642:                    sessions_file,
workspace/scripts/team_chat.py:659:                sessions_file,
workspace/scripts/team_chat.py:674:            sessions_file,
workspace/scripts/team_chat.py:687:                sessions_file,
workspace/scripts/team_chat.py:703:                sessions_file,
workspace/scripts/team_chat.py:714:            sessions_file,
workspace/scripts/team_chat.py:727:                    sessions_file,
workspace/scripts/team_chat.py:756:                sessions_file,
workspace/scripts/team_chat.py:772:                sessions_file,
workspace/scripts/team_chat.py:824:            sessions_file,
workspace/scripts/team_chat.py:860:                sessions_file,
workspace/scripts/team_chat.py:871:        sessions_file,
workspace/scripts/team_chat.py:885:            "session_jsonl": str(sessions_file),
workspace/scripts/team_chat.py:915:def run_multi_agent(
workspace/scripts/verify_goal_identity_invariants.py:122:        "child_process.spawn(",
workspace/scripts/system_health_monitor.py:84:def check_gateway() -> dict:
workspace/scripts/system_health_monitor.py:85:    rc, out, err = run_cmd(["openclaw", "gateway", "status"], timeout=10)
workspace/scripts/system_health_monitor.py:172:        "openclaw_gateway": check_gateway(),
workspace/scripts/openclaw_autoupdate.sh:96:exact_gateway_pids() {
workspace/scripts/openclaw_autoupdate.sh:108:    if [[ "$base" == "openclaw-gateway" ]]; then
workspace/scripts/openclaw_autoupdate.sh:113:    if [[ "$base" == "openclaw" ]] && [[ "$cmd" =~ (^|[[:space:]])gateway([[:space:]]|$) ]]; then
workspace/scripts/openclaw_autoupdate.sh:117:  done < <(pgrep -af 'openclaw-gateway|openclaw.*gateway' || true)
workspace/scripts/openclaw_autoupdate.sh:120:quiesce_gateway() {
workspace/scripts/openclaw_autoupdate.sh:123:    log_action "planned:quiesce:systemctl --user stop openclaw-gateway.service (or pid_fallback)"
workspace/scripts/openclaw_autoupdate.sh:129:    stop_out="$(systemctl --user stop openclaw-gateway.service 2>&1 || true)"
workspace/scripts/openclaw_autoupdate.sh:132:      log_action "systemctl --user stop openclaw-gateway.service"
workspace/scripts/openclaw_autoupdate.sh:136:    log_action "systemctl --user stop openclaw-gateway.service (output: ${stop_out//$'\n'/ })"
workspace/scripts/openclaw_autoupdate.sh:143:      done < <(exact_gateway_pids | sort -u)
workspace/scripts/openclaw_autoupdate.sh:149:        log_action "pid_fallback: no exact openclaw gateway pid found"
workspace/scripts/openclaw_autoupdate.sh:159:  log_action "systemctl missing; gateway stop skipped"
workspace/scripts/openclaw_autoupdate.sh:162:restart_gateway() {
workspace/scripts/openclaw_autoupdate.sh:164:    log_action "planned:restart:systemctl --user start openclaw-gateway.service (if systemctl path)"
workspace/scripts/openclaw_autoupdate.sh:169:    run_cmd "restart" systemctl --user start openclaw-gateway.service
workspace/scripts/openclaw_autoupdate.sh:173:  echo "OpenClaw gateway not auto-started; start it manually for this environment."
workspace/scripts/openclaw_autoupdate.sh:262:quiesce_gateway
workspace/scripts/openclaw_autoupdate.sh:294:  if openclaw gateway --help >/dev/null 2>&1; then
workspace/scripts/openclaw_autoupdate.sh:295:    run_cmd "gateway_install" openclaw gateway install --force
workspace/scripts/openclaw_autoupdate.sh:298:      log_action "planned:gateway_install:skip_unavailable"
workspace/scripts/openclaw_autoupdate.sh:300:      log_action "gateway_install: openclaw present but gateway install unavailable"
workspace/scripts/openclaw_autoupdate.sh:305:    log_action "planned:gateway_install:skip_openclaw_missing"
workspace/scripts/openclaw_autoupdate.sh:307:    log_action "gateway_install: openclaw command missing"
workspace/scripts/openclaw_autoupdate.sh:311:restart_gateway
workspace/scripts/message_load_balancer.py:6:automatically falls back to spawning a ChatGPT subagent to handle overflow.
workspace/scripts/message_load_balancer.py:172:def spawn_chatgpt_subagent(task: str, context: dict = None) -> dict:
workspace/scripts/message_load_balancer.py:174:    Spawn a ChatGPT subagent to handle overflow.
workspace/scripts/message_load_balancer.py:176:    This uses OpenClaw's sessions_spawn internally. In production,
workspace/scripts/message_load_balancer.py:179:    Returns spawn result with session_key.
workspace/scripts/message_load_balancer.py:184:        "action": "spawn",

$ rg -n "openclaw.*gateway|gateway.*--port|systemctl --user.*openclaw-gateway" workspace/scripts workspace/governance .github/workflows || true
workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md:43:  - `pgrep -f '^openclaw-gateway$'`
workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md:45:  - verify with `pgrep -af '^openclaw-gateway$'`
workspace/scripts/system_health_monitor.py:85:    rc, out, err = run_cmd(["openclaw", "gateway", "status"], timeout=10)
workspace/scripts/system_health_monitor.py:172:        "openclaw_gateway": check_gateway(),
workspace/scripts/openclaw_autoupdate.sh:108:    if [[ "$base" == "openclaw-gateway" ]]; then
workspace/scripts/openclaw_autoupdate.sh:113:    if [[ "$base" == "openclaw" ]] && [[ "$cmd" =~ (^|[[:space:]])gateway([[:space:]]|$) ]]; then
workspace/scripts/openclaw_autoupdate.sh:117:  done < <(pgrep -af 'openclaw-gateway|openclaw.*gateway' || true)
workspace/scripts/openclaw_autoupdate.sh:123:    log_action "planned:quiesce:systemctl --user stop openclaw-gateway.service (or pid_fallback)"
workspace/scripts/openclaw_autoupdate.sh:129:    stop_out="$(systemctl --user stop openclaw-gateway.service 2>&1 || true)"
workspace/scripts/openclaw_autoupdate.sh:132:      log_action "systemctl --user stop openclaw-gateway.service"
workspace/scripts/openclaw_autoupdate.sh:136:    log_action "systemctl --user stop openclaw-gateway.service (output: ${stop_out//$'\n'/ })"
workspace/scripts/openclaw_autoupdate.sh:149:        log_action "pid_fallback: no exact openclaw gateway pid found"
workspace/scripts/openclaw_autoupdate.sh:164:    log_action "planned:restart:systemctl --user start openclaw-gateway.service (if systemctl path)"
workspace/scripts/openclaw_autoupdate.sh:169:    run_cmd "restart" systemctl --user start openclaw-gateway.service
workspace/scripts/openclaw_autoupdate.sh:294:  if openclaw gateway --help >/dev/null 2>&1; then
workspace/scripts/openclaw_autoupdate.sh:295:    run_cmd "gateway_install" openclaw gateway install --force
workspace/scripts/openclaw_autoupdate.sh:300:      log_action "gateway_install: openclaw present but gateway install unavailable"
workspace/scripts/verify_runtime_autoupdate.sh:43:if grep -q "executed:gateway_install:openclaw gateway install --force" "$log_file"; then
```

## Phase 1b — Discovery rerun (corrected globbing)
```text
$ rg -n "subagent|spawn|run_multi_agent|gateway|sessions_|pairing|devices list|openclaw status|openclaw health" workspace -g "*.js" -g "*.ts" -g "*.py" || true
workspace/scripts/system_health_monitor.py:84:def check_gateway() -> dict:
workspace/scripts/system_health_monitor.py:85:    rc, out, err = run_cmd(["openclaw", "gateway", "status"], timeout=10)
workspace/scripts/system_health_monitor.py:172:        "openclaw_gateway": check_gateway(),
workspace/scripts/message_load_balancer.py:6:automatically falls back to spawning a ChatGPT subagent to handle overflow.
workspace/scripts/message_load_balancer.py:172:def spawn_chatgpt_subagent(task: str, context: dict = None) -> dict:
workspace/scripts/message_load_balancer.py:174:    Spawn a ChatGPT subagent to handle overflow.
workspace/scripts/message_load_balancer.py:176:    This uses OpenClaw's sessions_spawn internally. In production,
workspace/scripts/message_load_balancer.py:179:    Returns spawn result with session_key.
workspace/scripts/message_load_balancer.py:184:        "action": "spawn",
workspace/scripts/preflight_check.py:34:PAIRING = BASE_DIR / "credentials" / "telegram-pairing.json"
workspace/scripts/preflight_check.py:788:    if tg.get("dmPolicy") == "pairing":
workspace/scripts/preflight_check.py:789:        pairing = load_json(PAIRING) or {}
workspace/scripts/preflight_check.py:790:        if not pairing.get("requests") and not allowlist:
workspace/scripts/preflight_check.py:792:                "Telegram pairing is required but no paired users exist",
workspace/scripts/message_handler.py:5:Integrates message_load_balancer with OpenClaw gateway for:
workspace/scripts/message_handler.py:30:    def __init__(self, gateway_url: str, token: str):
workspace/scripts/message_handler.py:31:        self.gateway_url = gateway_url
workspace/scripts/message_handler.py:42:                    f"{self.gateway_url}/api/status",
workspace/scripts/message_handler.py:128:async def send_telegram_reply(chat_id: str, message_id: str, text: str, gateway_url: str, token: str):
workspace/scripts/message_handler.py:142:            f"{gateway_url}/api/tool/message",
workspace/scripts/message_handler.py:149:async def spawn_chatgpt_subagent(task: str, context: dict, gateway_url: str, token: str):
workspace/scripts/message_handler.py:150:    """Spawn a ChatGPT subagent to handle a message.
workspace/scripts/message_handler.py:152:    Uses OpenClaw's sessions_spawn internally.
workspace/scripts/message_handler.py:166:            f"{gateway_url}/api/agents/spawn",
workspace/scripts/message_handler.py:195:        # Spawn ChatGPT subagent
workspace/scripts/message_handler.py:196:        result = await spawn_chatgpt_subagent(
workspace/scripts/message_handler.py:199:            gateway_url=GATEWAY_URL,
workspace/scripts/message_handler.py:205:        # Use MiniMax (normal flow) - would integrate with gateway here
workspace/scripts/message_handler.py:214:            gateway_url=GATEWAY_URL,
workspace/scripts/team_chat.py:412:    sessions_file = base_dir / "sessions" / f"{session_id}.jsonl"
workspace/scripts/team_chat.py:480:                sessions_file,
workspace/scripts/team_chat.py:533:            sessions_file,
workspace/scripts/team_chat.py:549:            sessions_file,
workspace/scripts/team_chat.py:561:        sessions_file,
workspace/scripts/team_chat.py:579:                sessions_file,
workspace/scripts/team_chat.py:589:                sessions_file,
workspace/scripts/team_chat.py:607:                sessions_file,
workspace/scripts/team_chat.py:642:                    sessions_file,
workspace/scripts/team_chat.py:659:                sessions_file,
workspace/scripts/team_chat.py:674:            sessions_file,
workspace/scripts/team_chat.py:687:                sessions_file,
workspace/scripts/team_chat.py:703:                sessions_file,
workspace/scripts/team_chat.py:714:            sessions_file,
workspace/scripts/team_chat.py:727:                    sessions_file,
workspace/scripts/team_chat.py:756:                sessions_file,
workspace/scripts/team_chat.py:772:                sessions_file,
workspace/scripts/team_chat.py:824:            sessions_file,
workspace/scripts/team_chat.py:860:                sessions_file,
workspace/scripts/team_chat.py:871:        sessions_file,
workspace/scripts/team_chat.py:885:            "session_jsonl": str(sessions_file),
workspace/scripts/team_chat.py:915:def run_multi_agent(
workspace/scripts/verify_goal_identity_invariants.py:122:        "child_process.spawn(",
workspace/scripts/policy_router.py:219:            "subagentProvider": "local_vllm_assistant",
workspace/scripts/policy_router.py:725:def _is_subagent_context(context):
workspace/scripts/policy_router.py:728:    if context.get("subagent") or context.get("is_subagent"):
workspace/scripts/policy_router.py:732:        if value in {"subagent", "worker", "tool", "tool_agent", "child_agent"}:
workspace/scripts/policy_router.py:1117:        apply_to_subagents = bool(cfg.get("explicitApplyToSubagents", False))
workspace/scripts/policy_router.py:1118:        subagent = _is_subagent_context(context_metadata)
workspace/scripts/policy_router.py:1120:        if not subagent or apply_to_subagents:
workspace/scripts/policy_router.py:1130:        if subagent:
workspace/scripts/policy_router.py:1131:            provider = cfg.get("subagentProvider")
workspace/scripts/policy_router.py:1134:                    "trigger": "subagent_default",
workspace/scripts/policy_router.py:1135:                    "matched": "subagent=true",
workspace/scripts/policy_router.py:1137:                    "reason": "subagent primary uses local provider",
workspace/scripts/policy_router.py:1157:                provider = mechanical_provider or code_provider or cfg.get("subagentProvider")
workspace/scripts/policy_router.py:1163:                    "reason": "mechanical/execution class prefers local vLLM subagent",
workspace/skills/mlx-infer/dist/cli.js:4:const { spawn, spawnSync } = require("node:child_process");
workspace/skills/mlx-infer/dist/cli.js:68:  const check = spawnSync(resolvePythonExecutable(), ["--version"], { encoding: "utf8" });
workspace/skills/mlx-infer/dist/cli.js:75:  const check = spawnSync(resolvePythonExecutable(), ["-c", "import mlx_lm"], { encoding: "utf8" });
workspace/skills/mlx-infer/dist/cli.js:181:function spawnPython(args, timeoutMs) {
workspace/skills/mlx-infer/dist/cli.js:183:    const proc = spawn(resolvePythonExecutable(), args, { stdio: ["ignore", "pipe", "pipe"] });
workspace/skills/mlx-infer/dist/cli.js:200:  const usedSpawn = deps.spawnPython || spawnPython;
workspace/scripts/intent_failure_scan.py:87:            "Retry `openclaw status` without --deep if it hangs",
workspace/scripts/diagnose_openclaw_status_hang.py:3:Diagnose why `openclaw status` hangs using timeboxed, read-only checks.
workspace/scripts/diagnose_openclaw_status_hang.py:69:    status = by_cmd.get("openclaw status")
workspace/scripts/diagnose_openclaw_status_hang.py:70:    deep = by_cmd.get("openclaw status --deep")
workspace/scripts/diagnose_openclaw_status_hang.py:71:    js = by_cmd.get("openclaw status --json")
workspace/scripts/diagnose_openclaw_status_hang.py:74:        notes.append("Both `openclaw status` and `openclaw status --deep` timed out. Likely CLI/daemon wait, lock contention, or backend hang.")
workspace/scripts/diagnose_openclaw_status_hang.py:80:            notes.append("`openclaw status --json` appears unsupported in this CLI version.")
workspace/scripts/diagnose_openclaw_status_hang.py:87:    parser = argparse.ArgumentParser(description="Diagnose openclaw status hangs")
workspace/scripts/diagnose_openclaw_status_hang.py:140:            "command": "strace openclaw status",
workspace/scripts/safe_error_surface.js:50:  errorCode = 'gateway_error',
workspace/scripts/safe_error_surface.js:62:    log_ref: logRef || 'check local gateway logs with request_id',
workspace/scripts/safe_error_surface.js:70:    error_code: String(envelope.error_code || 'gateway_error'),
workspace/scripts/safe_error_surface.py:2:"""Safe error surface + redaction helpers for gateway adapters."""
workspace/scripts/safe_error_surface.py:68:    error_code: str = "gateway_error",
workspace/scripts/safe_error_surface.py:80:        "log_ref": log_ref or "check local gateway logs with request_id",
workspace/scripts/safe_error_surface.py:88:        "error_code": str(envelope.get("error_code", "gateway_error")),
workspace/source-ui/static/js/components.js:138:            gateway: '🌐',
workspace/source-ui/main.js:3:const { spawn } = require('child_process');
workspace/source-ui/main.js:14:    backendProcess = spawn('python3', [BACKEND_SCRIPT, '--port', '18990'], {
workspace/skills/mlx-infer/src/cli.ts:3:import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from "node:child_process";
workspace/skills/mlx-infer/src/cli.ts:32:  spawnPython?: (args: string[], timeoutMs: number) => Promise<SpawnResult>;
workspace/skills/mlx-infer/src/cli.ts:104:  const check = spawnSync(resolvePythonExecutable(), ["--version"], { encoding: "utf8" });
workspace/skills/mlx-infer/src/cli.ts:111:  const check = spawnSync(resolvePythonExecutable(), ["-c", "import mlx_lm"], { encoding: "utf8" });
workspace/skills/mlx-infer/src/cli.ts:215:function spawnPython(args: string[], timeoutMs: number): Promise<SpawnResult> {
workspace/skills/mlx-infer/src/cli.ts:217:    const proc: ChildProcessWithoutNullStreams = spawn(resolvePythonExecutable(), args, { stdio: ["ignore", "pipe", "pipe"] });
workspace/skills/mlx-infer/src/cli.ts:238:  const usedSpawn = deps.spawnPython || spawnPython;
workspace/source-ui/js/components.js:138:            gateway: '🌐',
workspace/source-ui/static/js/store.js:41:            gatewayStatus: 'connecting',
workspace/source-ui/static/js/store.js:229:            { id: 'gateway', name: 'Gateway', status: 'healthy', details: 'Running on port 18789' },
workspace/source-ui/js/app.js:628:        'Are you sure you want to restart the gateway? This will briefly interrupt all connections.',
workspace/source-ui/js/app.js:630:            Toast.info('Restarting gateway...');
workspace/source-ui/js/app.js:635:                Toast.error('Failed to restart gateway');
workspace/source-ui/js/app.js:661:    const gateway = $('#gateway-status');
workspace/source-ui/js/app.js:662:    const text = $('#gateway-status-text');
workspace/source-ui/js/app.js:664:    if (gateway && text) {
workspace/source-ui/js/app.js:666:        gateway.classList.add('connected');
workspace/source-ui/js/app.js:667:        gateway.classList.remove('error');
workspace/source-ui/js/store.js:41:            gatewayStatus: 'connecting',
workspace/source-ui/js/store.js:229:            { id: 'gateway', name: 'Gateway', status: 'healthy', details: 'Running on port 18789' },
workspace/source-ui/static/js/app.js:629:        'Are you sure you want to restart the gateway? This will briefly interrupt all connections.',
workspace/source-ui/static/js/app.js:631:            Toast.info('Restarting gateway...');
workspace/source-ui/static/js/app.js:636:                Toast.error('Failed to restart gateway');
workspace/source-ui/static/js/app.js:662:    const gateway = $('#gateway-status');
workspace/source-ui/static/js/app.js:663:    const text = $('#gateway-status-text');
workspace/source-ui/static/js/app.js:665:    if (gateway && text) {
workspace/source-ui/static/js/app.js:667:        gateway.classList.add('connected');
workspace/source-ui/static/js/app.js:668:        gateway.classList.remove('error');
workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js:7:const { spawn } = require("node:child_process");
workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js:26:  const dead = spawn(process.execPath, ["-e", "process.exit(0)"], { stdio: "ignore" });
workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js:66:  const live = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { stdio: "ignore" });
workspace/skills/mlx-infer/tests/mlx_infer_concurrency_stale_pid_cleanup.test.js:79:  const probe = spawn(process.execPath, ["-e", probeCode], { stdio: ["ignore", "pipe", "pipe"] });
workspace/source-ui/js/api.js:14:        // Try to detect the gateway URL from the current location
workspace/source-ui/js/api.js:126:        return this.request('/api/gateway/restart', { method: 'POST' });
workspace/source-ui/js/api.js:150:// Mock API for demo (when gateway is not available)
workspace/source-ui/js/api.js:159:            gateway: {
workspace/source-ui/static/js/api.js:14:        // Try to detect the gateway URL from the current location
workspace/source-ui/static/js/api.js:126:        return this.request('/api/gateway/restart', { method: 'POST' });
workspace/source-ui/static/js/api.js:150:// Mock API for demo (when gateway is not available)
workspace/source-ui/static/js/api.js:159:            gateway: {
workspace/source-ui/app.py:43:    gateway_url: str = "http://127.0.0.1:18789"
workspace/source-ui/app.py:44:    gateway_token: Optional[str] = None
workspace/source-ui/app.py:51:        gateway_token = args.token or os.environ.get('OPENCLAW_TOKEN')
workspace/source-ui/app.py:60:            gateway_url=args.gateway or os.environ.get('GATEWAY_URL', 'http://127.0.0.1:18789'),
workspace/source-ui/app.py:61:            gateway_token=gateway_token,
workspace/source-ui/app.py:83:        self.gateway_connected: bool = False
workspace/source-ui/app.py:95:            'gateway_connected': self.gateway_connected,
workspace/source-ui/app.py:140:            {'id': 'gateway', 'name': 'Gateway', 'status': 'healthy', 'details': 'Running on port 18789'},
workspace/source-ui/app.py:232:        elif parsed.path == '/api/gateway/restart':
workspace/source-ui/app.py:233:            self.restart_gateway()
workspace/source-ui/app.py:333:        self.state.gateway_connected = False  # Would check real gateway
workspace/source-ui/app.py:341:    def restart_gateway(self):
workspace/source-ui/app.py:342:        """Restart gateway."""
workspace/source-ui/app.py:422:    parser.add_argument('--gateway', '-g', help='Gateway URL')
workspace/teamchat/witness_verify.py:73:    sessions_dir = Path(repo_root) / "workspace" / "state_runtime" / "teamchat" / "sessions"
workspace/teamchat/witness_verify.py:74:    candidates = [p for p in sessions_dir.glob("*.jsonl") if p.is_file()]
workspace/teamchat/witness_verify.py:76:        raise FileNotFoundError(f"no session files found under {sessions_dir}")
workspace/teamchat/witness_verify.py:138:    sessions_dir = session_path.parent
workspace/teamchat/witness_verify.py:156:        if not (sessions_dir / f"{ref_session_id}.jsonl").exists():
workspace/skills/scaffold-apply/dist/cli.js:5:const { spawnSync } = require("node:child_process");
workspace/skills/scaffold-apply/dist/cli.js:34:  const proc = spawnSync("git", ["-C", targetDir, ...args], { encoding: "utf8" });
workspace/skills/scaffold-apply/src/cli.ts:4:import { spawnSync } from "node:child_process";
workspace/skills/scaffold-apply/src/cli.ts:42:  const proc = spawnSync("git", ["-C", targetDir, ...args], { encoding: "utf8" });
workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js:7:const { spawnSync } = require("node:child_process");
workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js:10:  const out = spawnSync(cmd, args, { cwd, encoding: "utf8" });
workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js:46:  const proc = spawnSync("node", [cli], {
workspace/skills/scaffold-apply/tests/dry_run_patch_check.test.js:72:  const proc = spawnSync("node", [cli], {

$ rg -n "openclaw.*gateway|gateway.*--port|systemctl --user.*openclaw-gateway" workspace/scripts workspace/governance .github/workflows || true
workspace/scripts/system_health_monitor.py:85:    rc, out, err = run_cmd(["openclaw", "gateway", "status"], timeout=10)
workspace/scripts/system_health_monitor.py:172:        "openclaw_gateway": check_gateway(),
workspace/scripts/openclaw_autoupdate.sh:108:    if [[ "$base" == "openclaw-gateway" ]]; then
workspace/scripts/openclaw_autoupdate.sh:113:    if [[ "$base" == "openclaw" ]] && [[ "$cmd" =~ (^|[[:space:]])gateway([[:space:]]|$) ]]; then
workspace/scripts/openclaw_autoupdate.sh:117:  done < <(pgrep -af 'openclaw-gateway|openclaw.*gateway' || true)
workspace/scripts/openclaw_autoupdate.sh:123:    log_action "planned:quiesce:systemctl --user stop openclaw-gateway.service (or pid_fallback)"
workspace/scripts/openclaw_autoupdate.sh:129:    stop_out="$(systemctl --user stop openclaw-gateway.service 2>&1 || true)"
workspace/scripts/openclaw_autoupdate.sh:132:      log_action "systemctl --user stop openclaw-gateway.service"
workspace/scripts/openclaw_autoupdate.sh:136:    log_action "systemctl --user stop openclaw-gateway.service (output: ${stop_out//$'\n'/ })"
workspace/scripts/openclaw_autoupdate.sh:149:        log_action "pid_fallback: no exact openclaw gateway pid found"
workspace/scripts/openclaw_autoupdate.sh:164:    log_action "planned:restart:systemctl --user start openclaw-gateway.service (if systemctl path)"
workspace/scripts/openclaw_autoupdate.sh:169:    run_cmd "restart" systemctl --user start openclaw-gateway.service
workspace/scripts/openclaw_autoupdate.sh:294:  if openclaw gateway --help >/dev/null 2>&1; then
workspace/scripts/openclaw_autoupdate.sh:295:    run_cmd "gateway_install" openclaw gateway install --force
workspace/scripts/openclaw_autoupdate.sh:300:      log_action "gateway_install: openclaw present but gateway install unavailable"
workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md:43:  - `pgrep -f '^openclaw-gateway$'`
workspace/governance/SECURITY_GOVERNANCE_CONTRACT.md:45:  - verify with `pgrep -af '^openclaw-gateway$'`
workspace/scripts/verify_runtime_autoupdate.sh:43:if grep -q "executed:gateway_install:openclaw gateway install --force" "$log_file"; then
```
Decision: no safe single pre-subagent chokepoint identified in repo-managed scripts with guaranteed use across all spawn paths.
Rationale: observed gateway controls span runtime/systemd/user contexts; wiring into one script risks partial coverage and unintended behavior changes.
Action: implement guard as standalone ops preflight script only (no wiring).

## Phase 4 - Verification + evidence

```
$ workspace/scripts/check_gateway_pairing_health.sh
INFO: recent scope-upgrade/pairing-required log lines were found; ensure devices list remains pending-free.
OK: no pending pairing/repair detected.
(exit_code=0)

$ openclaw devices list --json | head -n 200
{
  "pending": [],
  "paired": [
    {
      "deviceId": "d59e8530ab5264cdd8fc054743aa677883e0705f191cc4d5f6c3bd5fc07bf301",
      "publicKey": "cciOUMewwV-1Z5hvEFMxwnZ8zo7iMXeu5jMH0GA6jD4",
      "platform": "linux",
      "clientId": "cli",
      "clientMode": "cli",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing",
        "operator.read"
      ],
      "createdAtMs": 1771311120916,
      "approvedAtMs": 1771768620670,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing",
            "operator.read"
          ],
          "createdAtMs": 1771311120916,
          "rotatedAtMs": 1771768956600,
          "lastUsedAtMs": 1771484248970
        }
      ]
    },
    {
      "deviceId": "cf4e0b24aeaa879608c15454f8e4976f8ec648c656b06960e41d14618d0b378b",
      "publicKey": "3-6dDf3MCikaZqcnkEpnHd_A2oBwzHTPo_xpsVk_z2k",
      "platform": "Linux x86_64",
      "clientId": "openclaw-control-ui",
      "clientMode": "webchat",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing"
      ],
      "createdAtMs": 1771441549064,
      "approvedAtMs": 1771441549064,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing"
          ],
          "createdAtMs": 1771441549064,
          "lastUsedAtMs": 1771502457549
        }
      ]
    },
    {
      "deviceId": "b3f91ba144ed6ecc1a0140facd0a2c35cac0ba0812951d9e03edc1a59bda89a3",
      "publicKey": "cl6ukD4V4vug0PxZF2HYp9sKon7pcXhHaic_2O4afts",
      "platform": "Linux x86_64",
      "clientId": "openclaw-control-ui",
      "clientMode": "webchat",
      "role": "operator",
      "roles": [
        "operator"
      ],
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing"
      ],
      "createdAtMs": 1771359006652,
      "approvedAtMs": 1771359006652,
      "tokens": [
        {
          "role": "operator",
          "scopes": [
            "operator.admin",
            "operator.approvals",
            "operator.pairing"
          ],
          "createdAtMs": 1771359006652,
          "lastUsedAtMs": 1771668565977
        }
      ]
    }
  ]
}

$ openclaw status || true
[plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
OpenClaw status

Overview
┌─────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Item            │ Value                                                                                             │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Dashboard       │ http://127.0.0.1:18789/                                                                           │
│ OS              │ linux 6.17.0-14-generic (x64) · node 22.22.0                                                      │
│ Tailscale       │ off                                                                                               │
│ Channel         │ stable (default)                                                                                  │
│ Update          │ available · pnpm · npm update 2026.2.21-2                                                         │
│ Gateway         │ local · ws://127.0.0.1:18789 (local loopback) · reachable 10ms · auth token · jeebs-Z490-AORUS-   │
│                 │ MASTER (192.168.0.162) app unknown linux 6.17.0-14-generic                                        │
│ Gateway service │ systemd installed · enabled · running (pid 104765, state active)                                  │
│ Node service    │ systemd not installed                                                                             │
│ Agents          │ 1 · 1 bootstrapping · sessions 9 · default main active 40m ago                                    │
│ Memory          │ 0 files · 0 chunks · sources memory · plugin memory-core · vector unknown · fts ready · cache on  │
│                 │ (0)                                                                                               │
│ Probes          │ skipped (use --deep)                                                                              │
│ Events          │ none                                                                                              │
│ Heartbeat       │ 30m (main)                                                                                        │
│ Sessions        │ 9 active · default MiniMax-M2.5 (200k ctx) · ~/.openclaw/agents/main/sessions/sessions.json       │
└─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

Security audit
Summary: 0 critical · 1 warn · 1 info
  WARN Reverse proxy headers are not trusted
    gateway.bind is loopback and gateway.trustedProxies is empty. If you expose the Control UI through a reverse proxy, configure trusted proxies so local-client c…
    Fix: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
Full report: openclaw security audit
Deep probe: openclaw security audit --deep

Channels
┌──────────┬─────────┬────────┬───────────────────────────────────────────────────────────────────────────────────────┐
│ Channel  │ Enabled │ State  │ Detail                                                                                │
├──────────┼─────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────┤
│ Telegram │ ON      │ OK     │ token config (8517…TcJk · len 46) · accounts 1/1                                      │
└──────────┴─────────┴────────┴───────────────────────────────────────────────────────────────────────────────────────┘

Sessions
┌───────────────────────────────────────────────────────────────┬────────┬─────────┬──────────────┬───────────────────┐
│ Key                                                           │ Kind   │ Age     │ Model        │ Tokens            │
├───────────────────────────────────────────────────────────────┼────────┼─────────┼──────────────┼───────────────────┤
│ agent:main:main                                               │ direct │ 40m ago │ MiniMax-M2.5 │ 83k/200k (41%)    │
│ agent:main:cron:3d7aa458-12a9-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ unknown/200k (?%) │
│ agent:main:cron:3d7aa458-12a9-4…                              │ direct │ 15h ago │ MiniMax-M2.5 │ unknown/200k (?%) │
│ agent:main:cron:500367aa-d5c7-4…                              │ direct │ 16h ago │ MiniMax-M2.5 │ 9.9k/200k (5%)    │
│ agent:main:cron:500367aa-d5c7-4…                              │ direct │ 16h ago │ MiniMax-M2.5 │ 9.9k/200k (5%)    │
│ agent:main:cron:32bfc7b3-4ea1-4…                              │ direct │ 16h ago │ MiniMax-M2.5 │ 9.4k/200k (5%)    │
│ agent:main:cron:32bfc7b3-4ea1-4…                              │ direct │ 16h ago │ MiniMax-M2.5 │ 9.4k/200k (5%)    │
│ agent:main:cron:b1a26796-f74b-4…                              │ direct │ 18h ago │ MiniMax-M2.5 │ 11k/200k (6%)     │
│ agent:main:cron:b1a26796-f74b-4…                              │ direct │ 18h ago │ MiniMax-M2.5 │ 11k/200k (6%)     │
└───────────────────────────────────────────────────────────────┴────────┴─────────┴──────────────┴───────────────────┘

FAQ: https://docs.openclaw.ai/faq
Troubleshooting: https://docs.openclaw.ai/troubleshooting

Update available (npm 2026.2.21-2). Run: openclaw update

Next steps:
  Need to share?      openclaw status --all
  Need to debug live? openclaw logs --follow
  Need to test channels? openclaw status --deep

$ openclaw health || true
[plugins] plugins.allow is empty; discovered non-bundled plugins may auto-load: openclaw_secrets_plugin (/home/jeebs/src/clawd/scripts/openclaw_secrets_plugin.js). Set plugins.allow to explicit trusted ids.
Telegram: ok (@jeebsdalibot) (2314ms)
Agents: main (default)
Heartbeat interval: 30m (main)
Session store (main): /home/jeebs/.openclaw/agents/main/sessions/sessions.json (9 entries)
- agent:main:main (40m ago)
- agent:main:cron:3d7aa458-12a9-4501-bcb1-6853ec0e6fb0 (874m ago)
- agent:main:cron:3d7aa458-12a9-4501-bcb1-6853ec0e6fb0:run:fc24f385-379e-4b44-bdf9-c7bcfbf4103c (874m ago)
- agent:main:cron:500367aa-d5c7-4f52-9893-f501d6684067 (934m ago)
- agent:main:cron:500367aa-d5c7-4f52-9893-f501d6684067:run:68f73745-88ec-4966-93e2-b5e5c8c72c3a (934m ago)
```

Notes:
- Verification executed outside sandbox because sandboxed openclaw CLI cannot enumerate interfaces (uv_interface_addresses error).
- Guard behavior validated on host context: exits 0 when pending list is empty; prints scope-upgrade info hint when recent logs contain those lines.

### Final guard rerun after deterministic-stderr tweak
```
$ workspace/scripts/check_gateway_pairing_health.sh
INFO: recent scope-upgrade/pairing-required log lines were found; ensure devices list remains pending-free.
OK: no pending pairing/repair detected.
(exit_code=0)
```
