# Dali Ultra Stabilization Report

Timestamp (UTC): 2026-02-27
Repo: /home/jeebs/src/clawd

## Summary
Stabilization loop executed with `OPENCLAW_QUIESCE=1`.

Validated:
- skip-worktree allowlist guard passes
- `node --test` passes (60/60)
- `python3 -m unittest -v` passes (276 tests, 0 failures)
- runtime rebuild succeeds twice
- dashboard launches deterministically twice (`--no-open`)
- 5x status/health/curl loop succeeds on host execution context

## Fixes Applied
1. Operational gateway bind normalization (host config)
- `openclaw config set gateway.bind auto`
- then refined to:
  - `openclaw config set gateway.bind custom`
  - `openclaw config set gateway.customBindHost 127.0.0.1`
- Rationale: avoid non-deterministic loopback host resolution failures in this environment.
- Backup path created by OpenClaw CLI: `~/.openclaw/openclaw.json.bak`

2. No source architecture changes were introduced in this run.

## Evidence Pointers
- Tick snapshots:
  - `workspace/audit/stabilization_tick_20260227T095611Z.md`
  - `workspace/audit/stabilization_tick_20260227T101131Z.md`
- Node test log: `/tmp/dali_stabilize_node_20260227T095627Z.log`
- Python test log: `/tmp/dali_stabilize_py_20260227T095627Z.log`
- Double rebuild + validation log: `/tmp/dali_stabilize_verify_20260227T101106Z.log`
- Dashboard deterministic launches:
  - `/tmp/dali_dashboard_post1_20260227T101140Z.log`
  - `/tmp/dali_dashboard_post2_20260227T101140Z.log`
- Host-context health loop (5/5 pass):
  - `/tmp/dali_health_loop_final_escalated_20260227T101304Z.log`

## Provider Determinism Note
- Probe A (local_vllm, isolated env): success.
- Probe B (normal shell): deterministic success.
- Probe C (`anthropic`, `openclaw --version`): deterministic success in this environment; this command path does not serve as a reliable missing-key gate assertion when key material/config is present.

## Remaining Risks
- Sandbox execution context can produce false-negative gateway bind/health failures (EPERM/loopback resolution anomalies) not reproduced in host-context runs.
- `openclaw status` reports security warning(s) for non-loopback Control UI origin policy/rate-limit posture when gateway bind is non-default.

## Rollback Guidance
1. Restore OpenClaw user config:
- `cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json`

2. Rebuild runtime (repo-local):
- `bash workspace/scripts/rebuild_runtime_openclaw.sh`

3. Revert stabilization audit commit:
- `git revert <commit_sha>`

## Commits Created During This Run
- `audit(stabilization): dali stable baseline` (this baseline commit)
