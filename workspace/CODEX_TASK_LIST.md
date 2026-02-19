# Codex Tasks: Imaginative Computation

## Theme: Building systems inspired by Active Inference, Slime Mold, Reservoir Computing, and Murmuration

---

### Task 1: Implement Expected Free Energy (EFE) Calculator
**File:** `workspace/tacti_cr/efe_calculator.py`

Implement a function that calculates Expected Free Energy for agent actions:
- Pragmatic value (task reward)
- Epistemic value (information gain)
- Combine with configurable curiosity coefficient

---

### Task 2: Create Slime Mold Network Optimizer
**File:** `workspace/tacti_cr/slime_optimizer.py`

Implement Physarum-inspired network routing:
- Oscillator-based path selection
- Automatic pruning of inefficient routes
- Feedback-driven rewiring

---

### Task 3: Build Reservoir Computing Core
**File:** `workspace/tacti_cr/reservoir_core.py`

Create a software reservoir:
- Input injection mechanism
- Reservoir dynamics (echo state)
- Readout layer for prediction/classification

---

### Task 4: Implement Murmuration Agent Dynamics
**File:** `workspace/tacti_cr/murmuration_agent.py`

Agent coordination inspired by starling flocks:
- Local neighbor tracking (7 nearest)
- Scale-free correlation implementation
- Emergent collective behavior

---

### Task 5: External Memory System (Slime Trail)
**File:** `workspace/tacti_cr/external_memory.py`

Inspired by Physarum's externalized memory:
- Write memories to environment (file/directory)
- Read path history from external traces
- Implement "confusion" when trail is overwritten

---

### Task 6: Active Inference Agent Template
**File:** `workspace/tacti_cr/active_inference_agent.py`

Full agent implementing AIF principles:
- Generative world model (can use LLM)
- Belief updating on prediction error
- Active inference for action selection

---

### Task 7: Multi-Timescale Dynamics Engine
**File:** `workspace/tacti_cr/multiscale_engine.py`

Implement cross-timescale processing:
- Fast dynamics (immediate reactions)
- Slow dynamics (memory/consolidation)
- Coupling between timescales

---

### Task 8: Curiosity-Driven Exploration Module
**File:** `workspace/tacti_cr/curiosity.py`

Implement epistemic drive:
- Information gain measurement
- Uncertainty quantification
- Exploration/exploitation balance

---

### Task 9: Self-Healing Agent Network
**File:** `workspace/tacti_cr/self_healing.py`

Inspired by repairable systems:
- Detect failed agents/components
- Reroute around failures
- Regenerate capabilities

---

### Task 10: Integration Test Suite
**File:** `workspace/tests/test_imaginative_computation.py`

Test all 9 modules together:
- EFE drives action selection
- Slime optimizer routes resources
- Reservoir processes temporal data
- Murmuration coordinates agents
- External memory persists

---

## Notes

- All modules should be independent but composable
- Use type hints and docstrings
- Include usage examples in each file
- Aim for clean, readable code over optimization
