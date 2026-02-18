# TACTI(C)-R Modules

TACTI(C)-R implementation modules for C_Lawd and System-2.

## Modules

- `arousal.py`
  - `detect_arousal(task_input)`
  - `get_compute_allocation(arousal_state)`
  - `recommend_tier(task_input)`
- `temporal.py`
  - `TemporalMemory.store(...)`
  - `TemporalMemory.retrieve(..., include_hivemind=True)`
  - `TemporalMemory.prune_expired(...)`
- `collapse.py`
  - `CollapseDetector.record_event(...)`
  - `CollapseDetector.detect_collapse_precursors()`
  - `CollapseDetector.check_health()`
- `repair.py`
  - `RepairEngine.can_recover(error)`
  - `RepairEngine.repair(error)`
- `cross_timescale.py`
  - `CrossTimescaleController.reflex_layer(...)`
  - `CrossTimescaleController.deliberative_layer(...)`
  - `CrossTimescaleController.meta_controller(...)`
  - `CrossTimescaleController.process(...)`
- `hivemind_bridge.py`
  - `hivemind_query(topic, agent)`
  - `hivemind_store(entry)`

## Usage

```python
from tacti_cr.arousal import detect_arousal, get_compute_allocation

state = detect_arousal("debug routing regression with strict gates")
plan = get_compute_allocation(state)
print(state.level.value, plan.model_tier)
```

```python
from tacti_cr.temporal import TemporalMemory

memory = TemporalMemory(agent_scope="main", sync_hivemind=True)
memory.store("Resolved fallback timeout with bounded backoff", importance=0.8)
rows = memory.retrieve("fallback timeout", include_hivemind=True, limit=5)
```

```python
from tacti_cr.collapse import CollapseDetector
from tacti_cr.repair import RepairEngine

detector = CollapseDetector(agent_scope="main", use_hivemind=True)
detector.record_event("all models failed timeout")
health = detector.check_health()

repair = RepairEngine()
action = repair.repair("timeout connecting to provider")
print(health.status, action.action)
```

## Test Coverage

Unit/integration tests in `tests_unittest/`:

- `test_tacti_cr_arousal.py`
- `test_tacti_cr_temporal.py`
- `test_tacti_cr_collapse.py`
- `test_tacti_cr_repair.py`
- `test_tacti_cr_cross_timescale.py`
- `test_tacti_cr_hivemind_bridge.py`
- `test_tacti_cr_integration.py`

Run all TACTI(C)-R tests:

```bash
python3 -m unittest discover -s tests_unittest -p 'test_tacti_cr*.py' -v
```
