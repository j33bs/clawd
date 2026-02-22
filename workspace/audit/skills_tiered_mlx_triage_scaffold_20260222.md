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
