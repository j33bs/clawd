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

## Runtime Drift Note (2026-02-27T01:48:39Z)

- stop_condition: worktree became dirty during local-gates run
- drift_file: workspace/state/tacti_cr/events.jsonl
- drift_patch_tmp: /tmp/drift_events_jsonl_20260227T014839Z.patch
- cause: Drift produced by OPENCLAW_LOCAL_GATES=1 tools/run_checks.sh runtime writer.
- action: captured diff to /tmp, restored runtime artifact, and quiesced writers for remainder (OPENCLAW_QUIESCE=1).

## Drift Recovery Verification (2026-02-27T01:49:15Z)

```bash
OPENCLAW_QUIESCE=1 node --check scripts/system2_http_edge.js

OPENCLAW_QUIESCE=1 node --test tests/no_html_on_machine_routes.test.js
✔ machine surface never serves html and unknown machine paths are JSON 404 (43.108417ms)
ℹ tests 1
ℹ suites 0
ℹ pass 1
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 266.583958

OPENCLAW_QUIESCE=1 tools/reliability_tripwire.sh http://127.0.0.1:18789
PASS /health: status=200 content-type=application/json; charset=utf-8
PASS /ready: status=503 content-type=application/json; charset=utf-8
PASS /diag/runtime: status=200 content-type=application/json; charset=utf-8
PASS /api/does-not-exist: status=404 content-type=application/json; charset=utf-8
PASS /diag/does-not-exist: status=404 content-type=application/json; charset=utf-8
reliability tripwire passed for http://127.0.0.1:18789

OPENCLAW_QUIESCE=1 tools/check_launchagent_points_to_repo.sh
PASS: launchagent points to repo wrapper (/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh)
```
