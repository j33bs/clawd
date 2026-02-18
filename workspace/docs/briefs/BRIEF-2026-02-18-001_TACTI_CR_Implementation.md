# Brief: TACTI(C)-R Technical Implementation

## Metadata
- **ID**: BRIEF-2026-02-18-001
- **Category**: B (Security + Capability)
- **Author**: C_Lawd (via Heath)
- **Date**: 2026-02-18
- **Branch**: `feat/tacti-cr-technical-implementation`

---

## Summary

Implement the TACTI(C)-R framework as technical modules that can be integrated into OpenClaw. TACTI(C)-R = Temporality, Arousal, Cross-Timescale, Collapse, Repairable. Based on research corpus of 22 papers bridging human cognitive architecture with AI systems.

---

## Motivation

The research phase (22 papers) established the theoretical foundation. Now we need to implement these principles as practical code modules that can:
- Monitor and modulate agent arousal state
- Maintain episodic temporal memory
- Enable cross-timescale processing (fast/slow thinking)
- Detect and prevent collapse states
- Implement self-healing repair mechanisms

This transforms TACTI(C)-R from theory into operational capability.

---

## Risk Assessment

### Reversibility
- [x] Easy - Modular implementation, can be disabled via config
- [ ] Moderate
- [ ] Hard

### Blast Radius
New modules in `workspace/tacti_cr/` - isolated from core OpenClaw

| File | Change Type |
|------|-------------|
| `workspace/tacti_cr/` | CREATE |
| `workspace/tacti_cr/arousal.py` | CREATE |
| `workspace/tacti_cr/temporal.py` | CREATE |
| `workspace/tacti_cr/collapse.py` | CREATE |
| `workspace/tacti_cr/repair.py` | CREATE |
| `workspace/tacti_cr/__init__.py` | CREATE |
| `workspace/tacti_cr/config.py` | CREATE |
| `tests/tacti_cr/` | CREATE |

### Security Impact
- [x] None - Internal monitoring/optimization modules
- [ ] Low
- [ ] Medium
- [ ] High

---

## Implementation Plan

### Phase 1: Core Module Architecture

**1.1 Define Module Structure**
```
workspace/tacti_cr/
├── __init__.py          # Module exports
├── config.py            # Configuration schema
├── arousal.py           # Arousal detection and modulation
├── temporal.py          # Temporal memory with decay
├── collapse.py          # Collapse detection/prevention
├── repair.py            # Self-healing mechanisms
└── tests/
    ├── test_arousal.py
    ├── test_temporal.py
    ├── test_collapse.py
    └── test_repair.py
```

**1.2 Configuration Schema** (`config.py`)
- Arousal thresholds (low/medium/high)
- Temporal memory decay rates
- Collapse detection parameters
- Repair strategies

### Phase 2: Module Implementations

**2.1 Arousal Module** (`arousal.py`)
- Detect task complexity (input length, reasoning requirements)
- Modulate compute allocation based on arousal state
- Return recommended model tier (fast/local vs slow/premium)
- Interface: `detect_arousal(task_input) -> ArousalState`
- Interface: `get_compute_allocation(arousal_state) -> ComputePlan`

**2.2 Temporal Memory Module** (`temporal.py`)
- Store episodic memories with timestamps
- Implement time-decay (forget old context)
- Support retrieval by recency and relevance
- Interface: `store(episode)` / `retrieve(query)` / `prune_expired()`

**2.3 Collapse Detection Module** (`collapse.py`)
- Monitor for failure patterns (repeated errors, timeout, model drift)
- Detect "tunnel vision" (narrowed attention)
- Alert when approaching collapse threshold
- Interface: `check_health() -> HealthState` / `detect_collapse_precursors() -> List[Warning]`

**2.4 Repair Module** (`repair.py`)
- Implement recovery strategies (retry, fallback, reset)
- Track error patterns for learning
- Support graceful degradation
- Interface: `repair(error) -> RepairAction` / `can_recover(error) -> bool`

### Phase 3: Integration Points

**3.1 Model Routing Integration**
- Wire arousal module into `core/model_call.js`
- Arousal-based tier selection: high arousal → premium model, low → local

**3.2 Memory Integration**
- Add temporal memory to `memory_tool.py`
- Query temporal store for context-aware responses

**3.3 Health Monitoring**
- Hook collapse detector into gateway health checks
- Enable repair triggers on error conditions

---

## Technical Specifications

### Arousal State
```python
class ArousalState(Enum):
    LOW      # Simple task, minimal compute needed
    MEDIUM   # Moderate complexity
    HIGH     # Complex reasoning required
    
@dataclass
class ComputePlan:
    model_tier: str          # "fast" | "medium" | "premium"
    timeout_multiplier: float # Increase for complex tasks
    context_budget: int      # Token allocation
```

### Temporal Memory Entry
```python
@dataclass
class TemporalEntry:
    timestamp: datetime
    content: str
    importance: float         # 0-1
    decay_rate: float        # How fast this decays
    
def retrieve(query: str, limit: int = 5) -> List[TemporalEntry]:
    """Retrieve relevant memories, considering recency and relevance."""
```

### Health State
```python
@dataclass
class HealthState:
    status: str              # "healthy" | "degraded" | "collapse"
    confidence: float
    warnings: List[str]
    recommended_actions: List[str]
```

---

## Regression Scope

### Automated Validation
- [ ] Must pass: `python -m pytest workspace/tacti_cr/tests/`
- [ ] Must pass: Existing model routing tests still work
- [ ] Must pass: Memory operations still functional

### Manual Checks
- [ ] Arousal detection responds to input complexity
- [ ] Temporal memory stores and retrieves correctly
- [ ] Collapse detection triggers on failure patterns
- [ ] Repair mechanisms execute on errors

---

## Admission Checklist

- [x] Brief complete with all sections filled
- [ ] Branch created with correct prefix
- [ ] Implementation follows existing patterns
- [ ] Regression validation passed
- [ ] No secrets in diff
- [ ] Category/branch aligned
- [ ] Governance log entry prepared (for Category A/B)
- [ ] Rollback plan tested (for Category A/B)

---

## Notes

- Research corpus in `workspace/research/` (22 papers)
- Introduction paper: `workspace/research/TACTI_CR_Introduction_Paper.docx`
- Principles align with PRINCIPLES.md in governance/
- Start with arousal module (most immediately useful for routing)

---

*Template version: 1.0*
