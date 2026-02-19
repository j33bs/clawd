# TACTI Main-Flow Wiring Audit

## Summary
- Goal: wire `TactiDynamicsPipeline` into real HiveMind routing flow behind flags, with deterministic agent-id resolution and fail-open behavior.
- Pre SHA: `73a523a`
- Post wiring SHA: `0e7b2b3`

## Integration Map (Discovery)
- Main response routing flow: `workspace/scripts/policy_router.py` -> `PolicyRouter.execute_with_escalation(...)`.
- Existing HiveMind runtime query flow: `scripts/memory_tool.py` -> `cmd_query(...)`.
- Agent/routing catalog sources observed:
  - Runtime policy routing/provider catalog: `workspace/policy/llm_policy.json`
  - Agent manifests: `agents/*/agent/models.json`

## Files Changed
- `workspace/hivemind/hivemind/integrations/main_flow_hook.py`
- `workspace/hivemind/hivemind/integrations/__init__.py`
- `workspace/hivemind/hivemind/flags.py`
- `workspace/scripts/policy_router.py`
- `scripts/memory_tool.py`
- `workspace/hivemind/hivemind/dynamics_pipeline.py`
- `tests_unittest/test_policy_router_tacti_main_flow.py`

## Commands Run
1. `python3 -m unittest tests_unittest/test_policy_router_tacti_main_flow.py tests_unittest/test_policy_router_active_inference_hook.py tests_unittest/test_hivemind_dynamics_pipeline.py`
   - Result: PASS (`Ran 5 tests ... OK`).
2. `npm test`
   - Result: PASS (`Ran 96 tests ... OK`, `OK 35 test group(s)`).
3. `bash workspace/scripts/verify_tacti_system.sh`
   - Result: PASS (`Ran 16 tests ... OK`, artifact generated).

## Behavior Verification
- Flags OFF: router flow unchanged; TACTI hook not invoked.
- Flag ON (`ENABLE_MURMURATION=1`): hook invoked in `PolicyRouter.execute_with_escalation`, emits `tacti_routing_plan` event, and resolves non-empty agent IDs from real catalog/manifests.
- Agent IDs are no longer hardcoded in `memory_tool.py`; they are resolved via canonical runtime/catalog sources.

## Notes
- Routing integration is assistive only (reordering hints); on empty/error the original provider order is preserved.
- No TACTI module internals were refactored; wiring is additive and reversible.
