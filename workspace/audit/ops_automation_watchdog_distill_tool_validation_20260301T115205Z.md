# Ops automation: watchdog + memory distillation + tooling health validation

Timestamp (UTC): 20260301T115205Z
Branch: codex/ops/watchdog-distill-tooling-health-20260301T115205Z

## Changes
- External watchdog:
  - workspace/scripts/agent_watchdog.sh
  - workspace/systemd/openclaw-agent-watchdog.service
  - workspace/systemd/openclaw-agent-watchdog.timer
  - workspace/scripts/install_agent_watchdog.sh

- Automated memory distillation (cron):
  - workspace/scripts/memory_distill_cron.py
  - workspace/scripts/cron_memory_distill.sh
  - workspace/scripts/install_ops_cron_jobs.sh

- Continuous tool validation (skills/tooling_health):
  - SKILL.md
  - tool_validation_targets.json
  - validate_tools_daily.py
  - run_daily_tool_validation.sh
  - Runtime artifacts:
    - workspace/state_runtime/tool_validation/tool_error.log
    - workspace/state_runtime/tool_validation/offline_tools.json
    - workspace/state_runtime/tool_validation/tool_routing_overrides.json
    - workspace/state_runtime/tool_validation/heartbeat_notice.md

- Heartbeat integration:
  - workspace/governance/HEARTBEAT.md
  - HEARTBEAT.md

## Validation
- Unit tests:
  - python3 -m unittest -v tests_unittest.test_memory_distill_cron tests_unittest.test_validate_tools_daily

## Observed offline tools (at time of validation)
- coder_vllm.models
- mcp.qmd.http
- ain.phi

## Notes / follow-ups
- Consider converging cron → systemd timers for operational uniformity.
- Consider watchdog as long-running service with Restart=always (timer as optional kick).
