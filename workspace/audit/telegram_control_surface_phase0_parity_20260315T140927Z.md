# Telegram Control Surface Phase 0 Parity Audit

- Timestamp: `2026-03-15T14:09:27Z`
- Branch: `codex/telegram-control-surface-phase1`
- Baseline commit: `a90d13656d0ef664221ed5512f8e58d073019f87`

## Files Changed

- `workspace/runtime_hardening/src/telegram_runtime_parity.mjs`
- `workspace/runtime_hardening/tests/telegram_runtime_parity.test.mjs`

## Route Evidence

- Repo policy Telegram profile expects `openai_gpt54_chat` (`gpt-5.4`) as the first conversation/default chat lane.
- Repo policy Telegram profile also references `local_vllm_assistant`, `minimax_m25`, and `minimax_m25_lightning`.
- Local runtime registry satisfies `local_vllm_assistant` and `MiniMax-M2.5` parity by model exposure.
- Local runtime registry does not expose any `gpt-5.4` model and does not expose `MiniMax-M2.5-Lightning`.

## Runtime Verifier Excerpt

```json
{
  "surface": "telegram",
  "policy_profile": "surface:telegram",
  "status": "mismatch",
  "mismatches": [
    {
      "provider": "openai_gpt54_chat",
      "required_models": ["gpt-5.4"],
      "status": "missing_provider"
    },
    {
      "provider": "minimax_m25_lightning",
      "required_models": ["minimax-portal/MiniMax-M2.5-Lightning"],
      "status": "missing_provider"
    }
  ]
}
```

## Commands Run

- `node --test workspace/runtime_hardening/tests/telegram_runtime_parity.test.mjs` -> pass
- `python3 -m unittest tests_unittest.test_policy_router_surface_profiles tests_unittest.test_message_handler_router tests_unittest.test_message_handler_kernel_provenance` -> pass
- `node workspace/runtime_hardening/src/telegram_runtime_parity.mjs /Users/heathyeager/clawd` -> exit 1 with explicit parity mismatch report

## Revert

```bash
git restore -- workspace/runtime_hardening/src/telegram_runtime_parity.mjs workspace/runtime_hardening/tests/telegram_runtime_parity.test.mjs workspace/audit/telegram_control_surface_phase0_parity_20260315T140927Z.md
```
