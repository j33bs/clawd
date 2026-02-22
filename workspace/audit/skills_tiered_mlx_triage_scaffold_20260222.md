# Skills Tiered MLX/Triage/Scaffold Audit (2026-02-22)

Append-only implementation evidence for:
- workspace/skills/mlx-infer
- workspace/skills/task-triage
- workspace/skills/scaffold-apply

## Phase 0 Baseline (2026-02-22T04:06:19Z)
```bash
git status --porcelain -uall
?? workspace/audit/skills_tiered_mlx_triage_scaffold_20260222.md

git rev-parse --abbrev-ref HEAD
main

git rev-parse --short HEAD
d58a625
```

## Phase 0 Branch Correction (2026-02-22T04:09:59Z)
```bash
git checkout codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222
git status --porcelain -uall
?? workspace/audit/skills_tiered_mlx_triage_scaffold_20260222.md

git rev-parse --abbrev-ref HEAD
codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222

git rev-parse --short HEAD
d80da3a
```

## Build Strategy Decision
- Repo root does not provide a direct TypeScript build pipeline for workspace skills.
- Implemented fallback: authored runtime-ready JS under dist/ and parallel TS source under src/.
- No external dependencies added; runtime is zero-build.

## Commands Run
```bash
node --test workspace/skills/**/tests/*.test.js
```

## Test Result
- PASS: 12 tests, 0 failures.

## Known Limitations / Follow-ups
- mlx-infer requires python3 + mlx-lm preinstalled; tests use stubs and do not exercise real MLX runtime.
- task-triage relies on external local suggestion JSON; it does not invoke mlx-infer internally by design.
- scaffold-apply does not auto-rollback previously committed steps when a later step fails (intentional).

## Files Added/Changed
- workspace/skills/mlx-infer/
  - README.md, SKILL.md
  - scripts/mlx_infer.py
  - src/{cli.ts,logger.ts}
  - dist/{cli.js,logger.js}
  - schemas/{input.schema.json,output.schema.json}
  - tests/mlx_infer_integration_stub.test.js
- workspace/skills/task-triage/
  - README.md, SKILL.md
  - config/{decision_rules.json,classifier_prompt.md}
  - src/{cli.ts,decision.ts,logger.ts}
  - dist/{cli.js,decision.js,logger.js}
  - schemas/{input.schema.json,output.schema.json}
  - tests/decision_logic.test.js
- workspace/skills/scaffold-apply/
  - README.md, SKILL.md, package.json
  - src/{cli.ts,plan_schema.ts,logger.ts}
  - dist/{cli.js,plan_schema.js,logger.js}
  - schemas/{input.schema.json,output.schema.json}
  - tests/{plan_validation.test.js,dry_run_patch_check.test.js}

## Merge Verification on main (2026-02-22T04:30:10Z)
- BR_REF: origin/codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222
- Merge commit: 8bcbba6
- Test command:     \✔ maps python error types to node-level types (0.737084ms)
✔ buildPythonArgs includes required and optional args (0.823583ms)
✔ dry-run patch check passes on valid patch (184.307333ms)
✔ dry-run patch check reports failed step on invalid patch (148.954333ms)
✔ validation fails when required fields are missing (0.86225ms)
✔ validation fails invalid operation (0.155459ms)
✔ validation rejects path traversal (0.107583ms)
✔ high-confidence LOCAL remains LOCAL (0.846708ms)
✔ low confidence escalates to REMOTE (0.077958ms)
✔ very low confidence escalates to HUMAN (0.066791ms)
✔ force_human signal triggers HUMAN (0.072541ms)
✔ openai keyword triggers HUMAN plus request_for_chatgpt (0.099791ms)
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 424.794583
- Test summary: PASS (12 tests, 0 failures)

## Merge Verification on main (2026-02-22T04:30:25Z)
- BR_REF: origin/codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222
- Merge commit: 8bcbba6
- Test command: ✔ maps python error types to node-level types (0.755583ms)
✔ buildPythonArgs includes required and optional args (0.8165ms)
✔ dry-run patch check passes on valid patch (190.017875ms)
✔ dry-run patch check reports failed step on invalid patch (155.191792ms)
✔ validation fails when required fields are missing (0.848292ms)
✔ validation fails invalid operation (0.146209ms)
✔ validation rejects path traversal (0.103ms)
✔ high-confidence LOCAL remains LOCAL (0.941083ms)
✔ low confidence escalates to REMOTE (0.081167ms)
✔ very low confidence escalates to HUMAN (0.067375ms)
✔ force_human signal triggers HUMAN (0.063083ms)
✔ openai keyword triggers HUMAN plus request_for_chatgpt (0.097834ms)
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 474.158958
- Test summary: PASS (12 tests, 0 failures)

## mlx-infer Concurrency Hardening (2026-02-22T05:08:33Z)
- Rationale: prevent crash-stale PID files in \ from causing false \ failures.
- Change: concurrency guard now removes stale PID files when process is no longer alive and/or file mtime exceeds TTL.
- TTL default: \ ms (10 minutes).
- TTL override env: \.
- Test-only env hook added: no.
- Test commands:
  - \✔ removes stale pid files for dead processes before counting (53.548042ms)
✔ removes pid file when ttl is exceeded (1.082542ms)
✔ live pid file contributes to concurrency limit (62.205459ms)
✔ maps python error types to node-level types (0.756333ms)
✔ buildPythonArgs includes required and optional args (0.808291ms)
ℹ tests 5
ℹ suites 0
ℹ pass 5
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 200.01175 (PASS: 5/5)
  - \✔ removes stale pid files for dead processes before counting (59.787791ms)
✔ removes pid file when ttl is exceeded (1.056666ms)
✔ live pid file contributes to concurrency limit (63.952792ms)
✔ maps python error types to node-level types (0.769333ms)
✔ buildPythonArgs includes required and optional args (0.905541ms)
✔ dry-run patch check passes on valid patch (202.323ms)
✔ dry-run patch check reports failed step on invalid patch (151.098917ms)
✔ validation fails when required fields are missing (0.858ms)
✔ validation fails invalid operation (0.176833ms)
✔ validation rejects path traversal (0.102583ms)
✔ high-confidence LOCAL remains LOCAL (1.449125ms)
✔ low confidence escalates to REMOTE (0.085667ms)
✔ very low confidence escalates to HUMAN (0.071792ms)
✔ force_human signal triggers HUMAN (0.064792ms)
✔ openai keyword triggers HUMAN plus request_for_chatgpt (0.100041ms)
ℹ tests 15
ℹ suites 0
ℹ pass 15
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 447.618791 (PASS: 15/15)
- Rollback: \

## mlx-infer Concurrency Hardening (corrected evidence) (2026-02-22T05:08:50Z)
- Note: previous section had shell interpolation artifacts; this corrected block is authoritative.
- Rationale: prevent crash-stale PID files in .run/mlx-infer/ from causing false CONCURRENCY_LIMIT failures.
- Change: concurrency guard now removes stale PID files when process is no longer alive and/or file mtime exceeds TTL.
- TTL default: 600000 ms (10 minutes).
- TTL override env: OPENCLAW_MLX_INFER_PID_TTL_MS.
- Test-only env hook added: no.
- Test commands and summary:
  - node --test workspace/skills/mlx-infer/tests/*.test.js -> PASS (5 tests, 0 failures)
  - node --test workspace/skills/**/tests/*.test.js -> PASS (15 tests, 0 failures)
- Rollback: git revert <commit_sha>
