# Post-merge Live Alignment Verification

- ts_utc: 20260227T012822Z
- branch: main
- head: b70d7c2b121f4e0c48621c42c528c8c68497ccab
- recorded_stash_ref: stash@{0}: On main: wip: postmerge drift quarantine (HEARTBEAT + workspace/profile) 20260227T012736Z

## Commands and Outputs

```bash
git checkout main
Your branch is up to date with 'origin/main'.

git pull --ff-only origin main
Already up to date.

tools/check_launchagent_points_to_repo.sh
PASS: launchagent points to repo wrapper (/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh)

tools/assert_machine_surface.sh http://127.0.0.1:18789
PASS /health: status=200 content-type=application/json; charset=utf-8
PASS /ready: status=503 content-type=application/json; charset=utf-8
PASS /diag/runtime: status=200 content-type=application/json; charset=utf-8
PASS /api/does-not-exist: status=404 content-type=application/json; charset=utf-8
PASS /diag/does-not-exist: status=404 content-type=application/json; charset=utf-8
machine surface assertion passed for http://127.0.0.1:18789

curl -sf -H "Authorization: Bearer <redacted>" http://127.0.0.1:18789/diag/runtime
{"ok":true,"diag":{"uptime_ms":15014899,"event_loop_lag_ms":42,"event_loop_lag_max_ms":1055952,"event_loop_samples":11234,"event_loop_last_sample_ts":"2026-02-27T01:28:26.938Z","event_loop_last_sample_age_ms":743,"event_loop_stall_after_ms":5000,"event_loop_stalled":false,"inflight_global":1,"inflight_identities":1,"runtime":{"build":{"repo_sha":"761549d","repo_branch":"codex/fix/c_lawd-telemetry-unresponsive-telegram-ui-20260226","entrypoint":"/Users/heathyeager/clawd/scripts/system2_http_edge.js"}}},"build":{"repo_sha":"761549d","repo_branch":"codex/fix/c_lawd-telemetry-unresponsive-telegram-ui-20260226","entrypoint":"/Users/heathyeager/clawd/scripts/system2_http_edge.js"},"timestamp_utc":"2026-02-27T01:28:27.681Z"}

```
