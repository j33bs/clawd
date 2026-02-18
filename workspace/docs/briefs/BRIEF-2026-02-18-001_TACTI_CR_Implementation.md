# Brief: TACTI(C)-R Technical Implementation

## Metadata
- **ID**: BRIEF-2026-02-18-001
- **Category**: B (Security + Capability)
- **Author**: C_Lawd (via Heath)
- **Date**: 2026-02-18
- **Branch**: `feat/tacti-cr-technical-implementation`
- **Paper**: `workspace/research/TACTI_CR_Introduction_Paper.docx` (v2.0 - rewritten)

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
- Explicit budgets: token, tool, wall-clock, cost
- Risk tiers that scale permitted actions
- Entropy-based triggers ("uncertainty spikes" increase deliberation)
- De-escalation triggers ("stuck loops" reduce exploration)
- Interface: `detect_arousal(task_input) -> ArousalState`
- Interface: `get_compute_allocation(arousal_state) -> ComputePlan`

**2.2 Temporal Memory Module** (`temporal.py`)
- Store episodic memories with timestamps
- Event schema: who/what/why/outcome
- Time-aware storage: episode IDs, temporal edges
- Retrieval policies: recency × relevance × provenance
- "Future buffer" structures: plans/commitments with explicit expiry
- Support retrieval by recency and relevance
- Interface: `store(episode)` / `retrieve(query)` / `prune_expired()`

**2.3 Cross-Timescale Module** (`cross_timescale.py`)
- NEW: Hierarchical controller with three layers
- Reflex policies: linting, validation, guardrails (fast)
- Deliberative planner: search, synthesis, counterfactual (slow)
- Monitor/meta-controller: budget, risk, drift
- Inter-layer contracts: what state may be read/written, at what cadence
- Interface: `execute_reflex(action)` / `deliberate(goal)` / `govern()`

**2.4 Collapse Detection Module** (`collapse.py`)
- Monitor for failure patterns (repeated errors, timeout, model drift)
- Detect "tunnel vision" (narrowed attention)
- Provenance-aware memory: source attribution and trust scores
- Drift monitors: performance and distribution shift
- Circuit breakers: stop conditions on repeated failures
- Sandbox and least-privilege tool access
- Alert when approaching collapse threshold
- NEW: **C-Mode (Collapse Regime)** - deliberate capability contraction:
  - Reduce autonomy, shorten planning horizons
  - Restrict tools, request human confirmation
  - Only reversible after repair tests pass
- Interface: `check_health() -> HealthState` / `detect_collapse_precursors() -> List[Warning]` / `enter_c_mode()` / `exit_c_mode()`

**2.5 Repair Module** (`repair.py`)
- Implement recovery strategies (retry, fallback, reset)
- Incident objects: structured failure reports
- Automated reproduction harnesses
- Rollback and safe-mode operation
- Patch pipelines: policy updates, prompt/program changes
- Postmortem learning: update detectors and runbooks
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

## C-Mode (Collapse Regime) - NEW

TACTI(C)-R introduces an optional deliberate collapse mode:

When the monitor detects:
- (a) Uncertainty is high
- (b) Repeated tool failures occur
- (c) Safety constraints are at risk

The agent enters **C-mode**:
- Reduce autonomy
- Shorten planning horizons
- Restrict tools
- Request human confirmation or additional data

**Exit condition**: Only after repair tests pass

This transforms collapse from accident to design feature.

---

## Technical Specifications

### Arousal State (from paper v2.0)
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
    risk_tier: str          # "safe" | "cautious" | "restricted"
    entropy_trigger: float   # Threshold for uncertainty spike
```

### Temporal Memory Entry (from paper v2.0)
```python
@dataclass
class TemporalEntry:
    timestamp: datetime
    who: str                # Agent/user ID
    what: str               # Action/observation
    why: str                # Rationale
    outcome: str            # Result
    episode_id: str         # Session/episode identifier
    importance: float       # 0-1
    decay_rate: float       # How fast this decays
    
def retrieve(query: str, limit: int = 5, 
            recency_weight: float = 0.3,
            relevance_weight: float = 0.7) -> List[TemporalEntry]:
    """Retrieve relevant memories, considering recency and relevance."""
```

### Cross-Timescale Layers (NEW)
```python
class ReflexLayer:
    """Fast: linting, validation, guardrails"""
    def execute(self, action) -> ActionResult
    
class DeliberativeLayer:
    """Slow: search, synthesis, counterfactual"""
    def plan(self, goal) -> Plan
    
class MetaController:
    """Govern: budget, risk, drift, C-mode transitions"""
    def govern(self) -> GovernanceDecision
```

### Health State
```python
@dataclass
class HealthState:
    status: str              # "healthy" | "degraded" | "collapse"
    confidence: float
    warnings: List[str]
    recommended_actions: List[str]
    c_mode_active: bool      # NEW: C-mode flag
```

### Collapse Precursors (from paper v2.0)
```python
# Leading indicators (measure before failure):
- error_rate_acceleration: float  # Is error rate speeding up?
- entropy_spikes: List[datetime] # Unusual uncertainty bursts
- near_miss_count: int          # Repeated near-failures
- tool_failure_streak: int      # Consecutive tool errors
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
