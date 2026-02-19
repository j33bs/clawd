# TACTI(C)-R System Synthesis (HiveMind Integration)

## Integration Map
- `workspace/hivemind/hivemind/peer_graph.py`: Murmuration local peer topology and interaction updates.
- `workspace/hivemind/hivemind/reservoir.py`: Echo-state reservoir + deterministic readout hints.
- `workspace/hivemind/hivemind/physarum_router.py`: Conductance/path exploration and pruning.
- `workspace/hivemind/hivemind/trails.py`: External trail memory with decay, reinforcement, and similarity query.
- `workspace/hivemind/hivemind/dynamics_pipeline.py`: Composition layer for Tasks 1-4.
- `workspace/hivemind/hivemind/integrations/main_flow_hook.py`: Main-flow adapter (flag checks, agent-id resolution, routing enhancement, outcome updates).
- `scripts/memory_tool.py`: Optional Task 1-4 runtime hook for memory query consult-order/path bias.
- `workspace/hivemind/hivemind/active_inference.py`: Preference priors + prediction-error updates.
- `workspace/scripts/policy_router.py`: Real response routing hook site (`PolicyRouter.execute_with_escalation`) for Tasks 1-4 + Task 5.

## Feature Flags
All modules are optional and off by default.

- `ENABLE_MURMURATION=1`
- `ENABLE_RESERVOIR=1`
- `ENABLE_PHYSARUM_ROUTER=1`
- `ENABLE_TRAIL_MEMORY=1`
- `ENABLE_ACTIVE_INFERENCE=1`

## Module APIs
### Task 1: Murmuration
- `PeerGraph.init(agent_ids, k, seed)`
- `PeerGraph.peers(agent_id) -> list[str]`
- `PeerGraph.observe_interaction(src, dst, signal)`
- `PeerGraph.tick(dt)`
- `PeerGraph.snapshot() / PeerGraph.load(payload)`

### Task 2: Reservoir
- `Reservoir.init(dim, leak, spectral_scale, seed)`
- `Reservoir.step(input_features, agent_features, adjacency_features) -> state`
- `Reservoir.readout(state) -> dict`
- `Reservoir.reset(session_id=None)`
- `Reservoir.snapshot() / Reservoir.load(payload)`

### Task 3: Physarum
- `PhysarumRouter.propose_paths(src_agent, target_intent, peer_graph, n_paths) -> list[list[str]]`
- `PhysarumRouter.update(path, reward_signal)`
- `PhysarumRouter.prune(min_k, max_k)`
- `PhysarumRouter.snapshot() / PhysarumRouter.load(payload)`

### Task 4: External Trails
- `TrailStore.add(trail) -> trail_id`
- `TrailStore.query(text_or_embedding, k, now=None) -> list[dict]`
- `TrailStore.decay(now=None) -> dict`
- `TrailStore.reinforce(trail_id, delta) -> bool`
- `TrailStore.snapshot() / TrailStore.load(payload)`

### Task 5: Active Inference
- `PreferenceModel.predict(context) -> (preference_params, confidence)`
- `PreferenceModel.update(feedback, observed_outcome) -> dict`
- `PredictionError.compute(predicted, observed) -> float`
- `PreferenceModel.snapshot() / PreferenceModel.load(payload)`
- `PreferenceModel.save_path(path) / PreferenceModel.load_path(path)`

## Integration Behavior
### Tasks 1-4 (HiveMind memory query path)
When any of the first four flags is enabled, `scripts/memory_tool.py query`:
1. Loads `TactiDynamicsPipeline` state from `workspace/hivemind/data/tacti_dynamics_snapshot.json` if present.
2. Resolves agent IDs from runtime candidates and canonical manifests (not hardcoded IDs).
3. Computes `consult_order` + candidate paths for the current query.
4. Biases memory result order by consult order.
5. Logs `dynamics_query_plan` to HiveMind ingest log.
6. Updates pipeline state with proxy outcome and persists snapshot.

### Tasks 1-4 (main response routing path)
When any of `ENABLE_MURMURATION/ENABLE_RESERVOIR/ENABLE_PHYSARUM_ROUTER/ENABLE_TRAIL_MEMORY` is enabled, `PolicyRouter.execute_with_escalation`:
1. Calls `hivemind.integrations.main_flow_hook.tacti_enhance_plan(context, order)` before provider selection.
2. Uses TACTI ordering hints as assistive reordering only (fail-open: original order on empty/error).
3. Emits `tacti_routing_plan` and `tacti_routing_outcome` events in the existing router JSONL event log.
4. Calls `tacti_record_outcome(...)` after attempt success/failure so PeerGraph/Physarum/Trails can update.

### Task 5 (response pipeline)
When `ENABLE_ACTIVE_INFERENCE=1`, `PolicyRouter.execute_with_escalation`:
1. Predicts preference parameters before provider routing.
2. Injects prediction into `context_metadata["active_inference"]`.
3. Updates preference priors after each outcome (success/failure proxy + optional explicit feedback in `context_metadata.feedback`).
4. Persists model state at `workspace/hivemind/data/active_inference_state.json`.

## Agent ID Resolution
`resolve_agent_ids()` in `workspace/hivemind/hivemind/integrations/main_flow_hook.py` resolves in this order:
1. Runtime orchestration catalog used by current flow (candidate order + policy routing/providers).
2. Canonical repo manifests (`agents/*/agent/models.json`, `workspace/policy/llm_policy.json` providers).
3. Empty list (TACTI disabled fail-open for that call) if no deterministic source is available.

## Enablement on C_Lawd
Shell session:
```bash
export ENABLE_MURMURATION=1
export ENABLE_RESERVOIR=1
export ENABLE_PHYSARUM_ROUTER=1
export ENABLE_TRAIL_MEMORY=1
export ENABLE_ACTIVE_INFERENCE=1
```

Persistent profile example:
```bash
cat > ~/.openclaw/env.d/tacti.flags.env <<'EOF'
ENABLE_MURMURATION=1
ENABLE_RESERVOIR=1
ENABLE_PHYSARUM_ROUTER=1
ENABLE_TRAIL_MEMORY=1
ENABLE_ACTIVE_INFERENCE=1
EOF
```

Failure mode:
- If agent ID resolution returns empty/insufficient IDs, the hook returns original order and routing proceeds unchanged.

## Deterministic Verification
- Script: `workspace/scripts/verify_tacti_system.sh`
- Unit tests:
  - `tests_unittest/test_hivemind_peer_graph.py`
  - `tests_unittest/test_hivemind_reservoir.py`
  - `tests_unittest/test_hivemind_physarum_router.py`
  - `tests_unittest/test_hivemind_trails.py`
  - `tests_unittest/test_hivemind_dynamics_pipeline.py`
  - `tests_unittest/test_hivemind_active_inference.py`
  - `tests_unittest/test_policy_router_active_inference_hook.py`

## Known Limitations
- `memory_tool.py` integration currently uses proxy rewards from query score; explicit user feedback plumbing can be expanded.
- Physarum path proposal depth is intentionally shallow for deterministic offline behavior.
- Trail embeddings use deterministic hash vectors when offline embeddings are unavailable.
- Active inference observed-outcome metrics in `policy_router.py` are lightweight proxies, not full behavioral telemetry.
