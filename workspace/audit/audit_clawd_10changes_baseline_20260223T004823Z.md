# Baseline Evidence (20260223T004823Z)

## Commands
- git status --porcelain -uall
- git rev-parse HEAD
- git branch --show-current
- node -v
- python3 -V
- node --test workspace/skills/**/tests/*.test.js

## Outputs
```text
?? workspace/audit/audit_clawd_10changes_baseline_20260223T004823Z.md
2e02e515c150318ca1a775132c2fed822c0b136c
codex/feat/audit-clawd-10changes-20260223
v25.6.0
Python 3.14.3
```
{"ts":"2026-02-23T00:49:04.086Z","level":"info","skill":"coreml-embed","event":"runner_invocation","stage":"inference","text_count":1}
{"ts":"2026-02-23T00:49:04.098Z","level":"info","skill":"coreml-embed","event":"runner_invocation","stage":"inference","text_count":1}
{"ts":"2026-02-23T00:49:04.099Z","level":"info","skill":"coreml-embed","event":"runner_invocation","stage":"inference","text_count":1}
{"ts":"2026-02-23T00:49:04.099Z","level":"info","skill":"coreml-embed","event":"runner_invocation","stage":"health","model_path":"/tmp/model.mlpackage"}
✔ enforces max_texts budget (1.513917ms)
✔ returns embeddings on successful runner output (11.522709ms)
✔ surfaces runner typed error (0.556875ms)
✔ maps runner timeout to RUNNER_TIMEOUT (0.482292ms)
✔ health mode passes runner health response through (0.53175ms)
✔ removes stale pid files for dead processes before counting (61.437875ms)
✔ removes pid file when ttl is exceeded (1.367709ms)
✔ live pid file contributes to concurrency limit (72.753708ms)
✔ maps python error types to node-level types (3.975167ms)
✔ buildPythonArgs includes required and optional args (2.431208ms)
✔ resolvePythonExecutable prefers OPENCLAW_MLX_INFER_PYTHON and falls back to python3 (0.370708ms)
✔ preflight nonzero exit returns MLX_DEVICE_UNAVAILABLE (84.9775ms)
✔ preflight timeout returns MLX_DEVICE_UNAVAILABLE (72.541125ms)
✔ preflight ok proceeds to generation path (64.502792ms)
✔ dry-run patch check passes on valid patch (240.789166ms)
✔ dry-run patch check reports failed step on invalid patch (155.259542ms)
✔ validation fails when required fields are missing (1.498ms)
✔ validation fails invalid operation (0.472875ms)
✔ validation rejects path traversal (0.123542ms)
✔ high-confidence LOCAL remains LOCAL (1.619042ms)
✔ low confidence escalates to REMOTE (0.104417ms)
✔ very low confidence escalates to HUMAN (0.0715ms)
✔ force_human signal triggers HUMAN (0.061792ms)
✔ openai keyword triggers HUMAN plus request_for_chatgpt (0.101125ms)
✔ MLX_DEVICE_UNAVAILABLE escalates using configured error_escalations rule (0.132584ms)
✔ evidence selector prefers coreml strategy when embeddings succeed (1.485667ms)
✔ falls back to keyword stub when coreml model_path is not configured (0.348458ms)
✔ falls back to keyword stub when coreml embed reports MODEL_NOT_FOUND (0.1435ms)
✔ falls back to keyword stub when coreml embed times out (0.137417ms)
✔ keyword fallback chunking is deterministic (0.872083ms)
ℹ tests 30
ℹ suites 0
ℹ pass 30
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 523.056333
