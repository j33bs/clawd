# C_Lawd Wander + Inquiry Loops Audit (2026-02-23)

## Baseline
- Branch: `codex/feat/clawd-wander-inquiry-loops-20260223`
- Base SHA: `45253fab1b7954bc5c4b175e2d1936ecb2fb82e9`
- Node: `v25.6.0`
- Python: `Python 3.14.3`

### Pre-flight commands and outcomes
- `ps aux | egrep -i "openclaw|gateway|wander|worker|vllm|node|python" | head -n 50`
  - Outcome: process snapshot captured; no service stop/restart executed in this run.
- `git status --porcelain -uall`
  - Outcome: clean.
- `git rev-parse HEAD`
  - Outcome: `45253fab1b7954bc5c4b175e2d1936ecb2fb82e9`.
- `node -v && python3 -V`
  - Outcome: `v25.6.0`, `Python 3.14.3`.
- `git checkout -b codex/feat/clawd-wander-inquiry-loops-20260223`
  - Outcome: branch created.

## Recon map (actual insertion points)
- INV-005 / inquiry momentum:
  - `rg -n "INV-005|inquiry_momentum|inquiry momentum" -S` returned no code implementation.
  - Existing wander script: `workspace/scripts/research_wanderer.py`.
- Wander runner / scheduler:
  - No dedicated wander cron entry found in current `workspace/automation/cron_jobs.json`.
  - Current candidate runner path: `workspace/scripts/research_wanderer.py`.
- Trail store and metadata path:
  - `workspace/hivemind/hivemind/trails.py`
  - `workspace/hivemind/hivemind/dynamics_pipeline.py`
  - default JSONL path: `workspace/hivemind/data/trails.jsonl`.
- observe_outcome signature:
  - `workspace/hivemind/hivemind/dynamics_pipeline.py` (`def observe_outcome(...)`).
- Reservoir mode producer/consumer paths:
  - Producer: `workspace/hivemind/hivemind/reservoir.py` (`response_plan.mode` in readout).
  - Planner: `workspace/hivemind/hivemind/dynamics_pipeline.py`.
  - Integration wrapper: `workspace/hivemind/hivemind/integrations/main_flow_hook.py`.
- Identity/source docs discovered:
  - `SOUL.md`, `workspace/SOUL.md`, `workspace/governance/SOUL.md`
  - `IDENTITY.md`, `workspace/IDENTITY.md`, `workspace/governance/IDENTITY.md`, `nodes/*/IDENTITY.md`
  - `workspace/OPEN_QUESTIONS.md`

## Mode
- CBP-governed Execution Mode (no exploratory/adversarial switch needed so far).

## Item 1 — Live inquiry_momentum logging during wander sessions
Intent:
- Add deterministic inquiry momentum scoring and append-only per-session wander logging.

Touched files:
- `workspace/hivemind/hivemind/inquiry_momentum.py`
- `workspace/scripts/research_wanderer.py`
- `tests_unittest/test_research_wanderer_logging.py`

Implementation notes:
- Added INV-005-compatible lightweight instrument function: `compute_inquiry_momentum(...)`.
- Wired `research_wanderer.py` to append JSONL session records to `workspace/memory/wander_log.jsonl` (configurable with `--wander-log-path`).
- Required keys emitted per run: `timestamp`, `session_id`, `trigger`, `inquiry_momentum_score`, `threshold`, `exceeded`, `duration_ms`, `trails_written_count`, `errors`.
- Logging failure is non-fatal and emitted as structured stderr warning.

Verification:
- `python3 -m unittest tests_unittest.test_research_wanderer_logging -v`
  - PASS (2 tests)
- `python3 workspace/scripts/research_wanderer.py --input /tmp/wander_item1_sample.json --open-questions-path /tmp/wander_item1_open_questions.md --wander-log-path /tmp/wander_item1_log.jsonl --run-id item1-demo --session-id item1-session --trigger cron --dry-run --json`
  - PASS, produced inquiry momentum summary.
- Parsed log keys from `/tmp/wander_item1_log.jsonl`:
  - `['duration_ms','errors','exceeded','inquiry_momentum_score','run_id','session_id','threshold','timestamp','trails_written_count','trigger']`

Rollback:
- `git revert <item1_commit_sha>`

## Item 2 — observe_outcome() wiring for wander completions
Intent:
- Call `observe_outcome()` automatically for successful wander sessions that wrote trails, with per-session dedupe.

Touched files:
- `workspace/scripts/research_wanderer.py`
- `tests_unittest/test_research_wanderer_observe_outcome.py`

Implementation notes:
- Added trail write path to wander session (`--trail-path`) and observed-outcomes dedupe ledger (`--observed-outcomes-path`).
- Added `observe_wander_outcome(...)` helper:
  - Calls `TactiDynamicsPipeline.observe_outcome(...)` only when `trails_written_count > 0` and run has no fatal errors.
  - Idempotent by `session_id` using append-only JSONL ledger.
- Dedupe reason reported as `duplicate_session` when retried with same `session_id`.

Verification:
- `python3 -m unittest tests_unittest.test_research_wanderer_observe_outcome tests_unittest.test_research_wanderer_logging tests_unittest.test_research_wanderer_open_questions_pipeline -v`
  - PASS (4 tests)
- Manual deterministic run:
  - First run: `observe_outcome.called=true`, `trails_written_count=1`.
  - Second run same `session_id`: `observe_outcome.called=false`, reason `duplicate_session`.

Rollback:
- `git revert <item2_commit_sha>`
