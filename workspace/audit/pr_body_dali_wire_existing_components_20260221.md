### Summary
Implements **thin glue only** (no new abstraction layers) to wire together ten partially-built subsystems across OpenClaw (Dali).

### Implemented wiring (10/10)
1. vLLM metrics → policy router (queue depth gating, KV cache token halving; fail-open)
2. ITC ingestion boundary → router classify → schema validate → FileDropAdapter.persist
3. Local vLLM streaming consumer (generateStream proxy; blocking path unchanged)
4. Concurrency tuner → vLLM launch (`--max-num-seqs` from tuner; fail-open)
5. GPU guard → System2 router candidate deflection (fail-open)
6. TACTI main-flow hook → token cap + provider bias (fail-open)
7. Reservoir readout → provider reordering (urgency/risk_off; reorder only; fail-open)
8. ITC sentiment → intent-aware routing tilt (fail-open)
9. Prefix warmup → post-health hook (fail-open)
10. Source UI SSE → `/events` streaming router_tick + gpu_tick

### Tests / verification
Python:
- python3 -m unittest tests_unittest.test_policy_router_tacti_main_flow
- python3 -m unittest tests_unittest.test_policy_router_glue_integrations
- python3 -m unittest tests_unittest.test_itc_ingestion_boundary_forwarding
- python3 -m unittest tests_unittest.test_source_ui_sse

Node:
- node tests/providers/local_vllm_provider.test.js
- node tests/router_gpu_guard.test.js

Shell:
- bash -n scripts/vllm_launch_optimal.sh

All PASS. Evidence appended to:
- workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md

### Scope control
- All gating is **fail-open** to preserve baseline behavior when artifacts/subsystems are absent.
- Required modules are tracked (concurrency_tuner, gpu_guard, vllm_metrics_sink).
- Runtime artifacts and local docs remain explicitly excluded.
