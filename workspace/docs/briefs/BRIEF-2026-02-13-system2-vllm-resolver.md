# Brief: System-2 vLLM Resolver Provenance (PR #19)

- PR URL: https://github.com/j33bs/clawd/pull/19
- Main HEAD (short): bdd84d5
- Main HEAD (full): bdd84d5c3f66bc261c912d1264b6b6064e3d6795

## What Changed
- Added System-2 vLLM config resolver + unit tests + smoke script.
- Strict gating: System-2 config is consulted only when `options.system2 === true`.
- Added deterministic regression guard proving System-1 ignores `SYSTEM2_VLLM_*` unless `options.system2 === true`.

## Verification Evidence
- Local: `npm test` passed on main at bdd84d5.
- CI checks on PR #19: `ci` and `node-test` succeeded.

## Invariant
SYSTEM2_VLLM_* must not influence behavior unless options.system2 === true (enforced by unit test).

