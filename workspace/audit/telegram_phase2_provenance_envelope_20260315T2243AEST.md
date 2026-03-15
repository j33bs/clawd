# Telegram Phase 2 Provenance Envelope

## Scope

- Brief: `BRIEF-2026-03-15-001_TELEGRAM_CONTROL_SURFACE_BUILD_SHEET.md`
- Slice: Phase 2 `Provenance Envelope`
- Date: 2026-03-15

## Files changed

- `workspace/scripts/message_handler.py`
- `tests_unittest/test_message_handler_kernel_provenance.py`

## Why

The Telegram handler already attached route and kernel provenance to in-memory reply metadata, but it did not persist the brief-required per-reply provenance envelope to disk. This slice adds a single JSONL audit trail at `workspace/state_runtime/telegram_reply_provenance.jsonl` with the required operator-facing fields.

## Route evidence

- Provider: `openai_gpt54_chat`
- Model: `gpt-5.4`
- Surface: `telegram`
- Policy profile: `surface:telegram`
- Kernel overlay: `surface:telegram|mode:conversation|memory:on`

Example persisted envelope shape from the passing unit path:

```json
{
  "reply_id": "1",
  "surface": "telegram",
  "provider": "openai_gpt54_chat",
  "model": "gpt-5.4",
  "memory_blocks": [],
  "files_touched": [],
  "tests_run": [],
  "uncertainties": [],
  "operator_visible_summary": "route=openai_gpt54_chat/gpt-5.4 memory=0 files=0 tests=0 uncertainties=0"
}
```

## Runtime log excerpt

Local targeted verification:

```text
$ python3 -m unittest tests_unittest.test_message_handler_kernel_provenance tests_unittest.test_message_handler_router tests_unittest.test_policy_router_surface_profiles tests_unittest.test_policy_router_kernel_provenance tests_unittest.test_c_lawd_conversation_kernel tests_unittest.test_telegram_recall tests_unittest.test_message_load_balancer
......................................
----------------------------------------------------------------------
Ran 38 tests in 0.036s

OK
```

## Known limits

- No live Telegram send/manual channel check was run in this automation because the run must not perform external actions.
- The new envelope currently persists default-empty `memory_blocks`, `files_touched`, `tests_run`, and `uncertainties` unless upstream routing/execution code supplies them.

## Revert

```bash
git restore -- workspace/scripts/message_handler.py tests_unittest/test_message_handler_kernel_provenance.py workspace/audit/telegram_phase2_provenance_envelope_20260315T2243AEST.md
```
