# Proposal E — Abstract machine-specific paths

timestamp_utc: 20260227T053243Z
Intent: Portability across nodes (dali/c_lawd).
Scope: HEARTBEAT.md, scripts/run_openclaw_gateway_repo.sh, tools/check_launchagent_points_to_repo.sh.
Safety: OPENCLAW_HOME-aware defaults preserve existing behavior without hardcoded machine paths.
Verification: no hardcoded repo root path remains in touched files; shell syntax checks pass.
