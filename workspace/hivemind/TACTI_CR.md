# TACTI(C)-R System Synthesis (HiveMind Integration)

## Integration Map
- `workspace/hivemind/hivemind/peer_graph.py`: Murmuration local peer topology and interaction updates.
- `workspace/hivemind/hivemind/reservoir.py`: Echo-state reservoir + deterministic readout hints.
- `workspace/hivemind/hivemind/physarum_router.py`: Conductance/path exploration and pruning.
- `workspace/hivemind/hivemind/trails.py`: External trail memory with decay, reinforcement, and similarity query.
- `workspace/hivemind/hivemind/dynamics_pipeline.py`: Composition layer for Tasks 1-4.
- `scripts/memory_tool.py`: Optional Task 1-4 runtime hook for memory query consult-order/path bias.
- `workspace/hivemind/hivemind/active_inference.py`: Preference priors + prediction-error updates.
- `workspace/scripts/policy_router.py`: Optional Task 5 response-pipeline hook (pre-predict, post-update).

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
2. Computes `consult_order` + candidate paths for the current query.
3. Biases memory result order by consult order.
4. Logs `dynamics_query_plan` to HiveMind ingest log.
5. Updates pipeline state with proxy outcome and persists snapshot.

### Task 5 (response pipeline)
When `ENABLE_ACTIVE_INFERENCE=1`, `PolicyRouter.execute_with_escalation`:
1. Predicts preference parameters before provider routing.
2. Injects prediction into `context_metadata["active_inference"]`.
3. Updates preference priors after each outcome (success/failure proxy + optional explicit feedback in `context_metadata.feedback`).
4. Persists model state at `workspace/hivemind/data/active_inference_state.json`.

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

