# Tooling Health Skill

Purpose:
- Validate local endpoints and MCP-adjacent services daily.
- Record failures with stack traces.
- Mark failing tools as temporarily offline.
- Emit a heartbeat notice for operator visibility.

Entrypoints:
- `python3 skills/tooling_health/validate_tools_daily.py --repo-root <repo>`
- `bash skills/tooling_health/run_daily_tool_validation.sh`

Configuration:
- `skills/tooling_health/tool_validation_targets.json`

Artifacts:
- `workspace/state_runtime/tool_validation/offline_tools.json`
- `workspace/state_runtime/tool_validation/tool_routing_overrides.json`
- `workspace/state_runtime/tool_validation/tool_error.log`
- `workspace/state_runtime/tool_validation/heartbeat_notice.md`
