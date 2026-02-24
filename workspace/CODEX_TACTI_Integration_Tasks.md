# Codex Tasks: TACTI(C)-R Integration & Polish

## Context
The core TACTI(C)-R modules are built in `workspace/hivemind/hivemind/`. Now we need integration, testing, and polish.

---

### Task 1: Integrate TactiDynamicsPipeline into Message Flow
**File:** `workspace/hivemind/hivemind/__init__.py`

Hook `TactiDynamicsPipeline` into the main HiveMind message routing:
- Initialize pipeline with available agent IDs
- Call `plan_consult_order()` before delegating messages
- Call `observe_outcome()` after each agent response

---

### Task 2: Environment Flag Manager
**File:** `workspace/hivemind/hivemind/config.py`

Create a clean config system for feature flags:
- `ENABLE_MURMURATION`, `ENABLE_RESERVOIR`, `ENABLE_PHYSARUM_ROUTER`, `ENABLE_TRAIL_MEMORY`
- Load from env vars with sensible defaults
- Add `debug` mode that logs which components are active

---

### Task 3: Pipeline Persistence
**File:** `workspace/hivemind/hivemind/persistence.py`

Save/load pipeline state to disk:
- `snapshot()` already exists on all modules
- Create `save_pipeline(path)` and `load_pipeline(path)`
- Auto-save on graceful shutdown, restore on startup

---

### Task 4: Integration Test Suite
**File:** `workspace/tests/test_tacti_integration.py`

Test the full pipeline end-to-end:
- Initialize pipeline with mock agents
- Send mock messages through `plan_consult_order`
- Verify routing decisions, trail storage, reservoir state changes

---

### Task 5: Murmuration Visualization
**File:** `workspace/hivemind/hivemind/viz/murmuration.py`

Create an ASCII/terminal visualization:
- Show peer graph as node connections
- Animate state changes
- Display conductance values as line thickness

---

### Task 6: Performance Benchmarking
**File:** `workspace/benchmarks/tacti_benchmark.py`

Measure pipeline performance:
- Latency of `plan_consult_order()`
- Memory usage of reservoir + trails
- Compare with/without each component enabled

---

### Task 7: CLI Commands for Pipeline Control
**File:** `workspace/hivemind/hivemind/cli.py`

Add CLI commands:
- `hivemind pipeline status` — show active flags, state summary
- `hivemind pipeline enable/disable <component>`
- `hivemind pipeline snapshot` — save state
- `hivemind pipeline visualize` — show network

---

### Task 8: Trail Memory Analytics
**File:** `workspace/hivemind/hivemind/analytics.py`

Analyze trail data:
- Most reinforced agents
- Decay rates over time
- Success patterns by agent/path
- Export as simple JSON report

---

### Task 9: Error Handling & Graceful Degradation
**File:** `workspace/hivemind/hivemind/error_handling.py`

Make pipeline robust:
- Catch exceptions in each component
- Fallback to simple routing if physarum fails
- Log errors but don't crash
- Return meaningful error messages

---

### Task 10: Documentation & Examples
**File:** `workspace/hivemind/README_INTEGRATION.md`

Write integration guide:
- How to enable each component
- Example initialization code
- Troubleshooting tips
- Architecture diagram

---

## Priority
1. Task 1 (integration) — makes it actually work
2. Task 2 (config) — makes it usable
3. Task 3 (persistence) — makes it maintainable
4. Task 4 (tests) — makes it reliable

Then 5-10 in any order.
