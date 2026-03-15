# Telegram Control Surface Brief Rollup

- Brief: `BRIEF-2026-03-15-001_TELEGRAM_CONTROL_SURFACE_BUILD_SHEET.md`
- Timestamp: `2026-03-16 03:07:37 AEST`
- Branch: `codex/telegram-control-surface-phase1`
- Baseline at run start: `789fbb3bc1b357a4e9737898b54eaec77d6e8f53`

## Status

- Phase 0 `Runtime Parity Gate`: repo-side verifier and plugin guard are implemented, but live parity is still blocked by local runtime drift in `~/.openclaw/openclaw.json`.
- Phase 1 `Alignment Compiler`: implemented via shared c_lawd surface kernel assembly and covered by unit tests.
- Phase 2 `Provenance Envelope`: implemented in the Telegram handler and persisted to JSONL.
- Phase 3 `Memory Parliament`: implemented for governed Telegram fact proposal/admission/query with chat scope, contradiction state, and explicit global-scope gating.
- Phase 4 `Router Consolidation`: implemented by retiring legacy load balancer routing authority so it remains advisory-only.
- Phase 5 `Higher-Agency Telegram Features`: deferred by brief rule until Phases 0-4 fully pass, including live runtime parity.

## Commit Evidence

- `4e5edbe` Clarify surface identity and fix load balancer deadlock
- `d9ddc7b` Add governed Telegram memory admission gates
- `09013b3` Add telegram reply provenance envelope
- `a90d136` Retire legacy load balancer authority
- `2fc3859` Add Telegram runtime parity verifier
- `8986c73` Test telegram surface capability routing parity
- `789fbb3` Add telegram runtime plugin parity guard

## Verification

- `python3 -m unittest tests_unittest.test_c_lawd_conversation_kernel tests_unittest.test_policy_router_surface_profiles tests_unittest.test_policy_router_kernel_provenance tests_unittest.test_message_handler_router tests_unittest.test_message_handler_kernel_provenance tests_unittest.test_telegram_recall tests_unittest.test_user_memory_db tests_unittest.test_message_load_balancer`
  - Result: `Ran 49 tests in 0.142s` / `OK`
- `node --test tests/openclaw_surface_router_plugin.test.js workspace/runtime_hardening/tests/telegram_runtime_parity.test.mjs`
  - Result: `9` tests passed, `0` failed
- `node workspace/runtime_hardening/src/telegram_runtime_parity.mjs /Users/heathyeager/clawd`
  - Result: exit `1` with live mismatch report

## Live Runtime Blockers

- Missing enabled plugin: `openclaw_surface_router_plugin`
- Missing runtime provider/model lane for `openai_gpt54_chat` / `gpt-5.4`
- Missing runtime provider/model lane for `minimax_m25_lightning` / `MiniMax-M2.5-Lightning`

These blockers are outside the scoped repo change set for this run because they live in local runtime state under `~/.openclaw/`.

## Revert

```bash
git restore -- workspace/audit/telegram_control_surface_brief_rollup_20260316T0307AEST.md
```
