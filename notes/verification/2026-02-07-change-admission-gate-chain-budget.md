# Change Admission Gate - Chain Budget + Trace (2026-02-07)

## Design Brief
- Introduce token budgeting utilities and append-only chain trace logging.
- Keep changes localized to chain utilities and minimal supporting tests.

## Evidence Pack
- `core/chain/chain_budget.js` and `core/chain/chain_trace.js` added.
- Budget test covers pinning and deterministic output.

## Rollback Plan
- Remove chain budget/trace modules and associated test files.

## Budget Envelope
- Default token ceiling 6k, step ceiling 2k.
- Trace rotation capped to max entries.

## Expected ROI
- Deterministic budget enforcement and auditable step traces.

## Kill-Switch
- Lower `CHAIN_TOKEN_CEILING` to force early aborts.

## Post-Mortem
- Review trace logs under `logs/chain_runs/` for budget behavior.
