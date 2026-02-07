# Change Admission Gate - Sub-Agent Chain (2026-02-07)

## Design Brief
- Add token-budgeted chain orchestration with trace logging and rule-based routing.
- Keep changes localized to chain modules, tests, CLI, and docs.

## Evidence Pack
- Chain budgeting utilities and trace logging implemented under `core/chain/`.
- Rule-based router with tests for intent routing.
- Chain runner smoke test validates step progression + trace writes.

## Rollback Plan
- Remove `core/chain/` modules and `scripts/run_chain.js`.
- Revert `package.json` and test additions.

## Budget Envelope
- Default token ceiling 6k; per-step ceiling 2k.
- Aggressive pruning of scratch and rolling summaries on budget enforcement.

## Expected ROI
- Deterministic, auditable chain orchestration with bounded token usage.
- Improved traceability for debugging and governance.

## Kill-Switch
- Set `CHAIN_TOKEN_CEILING` low to force aborts.
- Disable chain invocation by not calling `run_chain.js`.

## Post-Mortem
- Review `logs/chain_runs/chain_trace.jsonl` for step outcomes and budgets.
- Adjust router rules and ceilings if repeated aborts occur.
