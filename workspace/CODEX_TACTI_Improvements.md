# Codex Tasks: TACTI(C)-R Research-Backed Improvements

## Context
The unified framework research (Active Inference, Slime Mold, Reservoir Computing, Murmuration) reveals several high-impact improvements not yet implemented in HiveMind.

---

### Task 1: Prediction Error Tracking & Model Updating
**File:** `workspace/hivemind/hivemind/prediction_error.py`

Implement Active Inference properly:
- Each agent maintains beliefs about user preferences
- Compute prediction error after each response (did we predict correctly?)
- Update beliefs using Bayesian update or simple reinforcement
- Expose `belief_strength` and `surprise` metrics

**Research basis:** Free Energy Principle — systems minimize surprise

---

### Task 2: Multi-Timescale Dynamics Engine
**File:** `workspace/hivemind/hivemind/multiscale_engine.py`

Implement fast + slow dynamics coupling:
- **Fast timescale:** Immediate reactions (< 100ms)
- **Slow timescale:** Memory consolidation, belief updates (> minutes)
- Coupling mechanism: slow dynamics influence fast decisions
- Configurable time constants per agent

**Research basis:** Murmuration — birds react instantly but flock patterns evolve slowly

---

### Task 3: Self-Healing Agent Network
**File:** `workspace/hivemind/hivemind/self_healing.py`

Detect and recover from failures:
- Heartbeat mechanism to detect stale agents
- Automatic rerouting around failed nodes
- Quarantine & recovery protocol for struggling agents
- Regenerate connections over time

**Research basis:** Biological immune system, repairable systems theory

---

### Task 4: Curiosity-Driven Exploration
**File:** `workspace/hivemind/hivemind/curiosity_module.py`

Implement epistemic drive:
- Measure information gain per interaction
- Track uncertainty (entropy) in beliefs
- Curiosity-weighted exploration vs exploitation
- Configurable curiosity coefficient

**Research basis:** Active Inference's epistemic value — curiosity about what we don't know

---

### Task 5: Generative World Model
**File:** `workspace/hivemind/hivemind/generative_model.py`

Full Active Inference agent internal model:
- Model "generates" predictions about user needs
- Compare predictions to actual outcomes
- Update model based on prediction error
- Can use LLM as the generative model backend

**Research basis:** The brain has internal models that generate predictions (Friston)

---

### Task 6: Hebbian Connection Weighting
**File:** `workspace/hivemind/hivemind/hebbian_learning.py`

Implement "neurons that fire together, wire together":
- Strengthen agent connections after successful collaborations
- Weaken connections after failures
- Learning rate configurable per agent
- Persist connection weights to disk

**Research basis:** Slime mold strengthens efficient paths, neurons strengthen synaptic connections

---

### Task 7: Oscillator Synchronization
**File:** `workspace/hivemind/hivemind/oscillator_sync.py`

Add phase synchronization between agents:
- Each agent has an "oscillator" (attention cycle)
- Agents sync their cycles with successful partners
- Synchronized agents respond faster to shared context
- Kuramoto model or simple phase locking

**Research basis:** Fireflies sync, neurons sync, slime mold oscillations enable network learning

---

### Task 8: Resource/Energy Budgeting
**File:** `workspace/hivemind/hivemind/energy_budget.py`

Implement computational economy:
- Each agent has limited "energy" per time window
- High-confidence responses cost less energy
- Agents can request energy from peers (cooperative)
- Budget pressure forces efficient routing

**Research basis:** Biological organisms have finite metabolic energy; efficiency matters

---

### Task 9: Belief Propagation Algorithm
**File:** `workspace/hivemind/hivemind/belief_propagation.py`

Implement proper message passing:
- Agents send belief updates to neighbors
- Loopy belief propagation for approximate inference
- Convergence detection
- Visualize belief flow

**Research basis:** Sum-product algorithm, loopy LDPC codes, cavity method (Mézard, Parisi)

---

### Task 10: Homeostatic Regulation
**File:** `workspace/hivemind/hivemind/homeostasis.py`

Agents maintain internal stability:
- Monitor deviation from "set point" (baseline performance)
- If stressed (high error rate), reduce load
- If underutilized, take on more tasks
- Temperature metaphor: "agent temperature" rises with load

**Research basis:** All living systems maintain homeostasis; stress response in biology

---

## Priority Recommendation

**Tier 1 (Foundation):**
- Task 1 — Prediction Error Tracking (core to Active Inference)
- Task 6 — Hebbian Learning (makes routing adaptive)
- Task 3 — Self-Healing (production reliability)

**Tier 2 (Intelligence):**
- Task 4 — Curiosity (better exploration)
- Task 5 — Generative Model (deeper inference)
- Task 2 — Multi-Timescale (realistic dynamics)

**Tier 3 (Polish):**
- Task 7 — Oscillator Sync (emergent coordination)
- Task 8 — Energy Budgeting (efficiency)
- Task 9 — Belief Propagation (advanced inference)
- Task 10 — Homeostasis (self-regulation)

---

## Integration Note
All new modules should integrate with `TactiDynamicsPipeline`. Add feature flags:
```bash
ENABLE_PREDICTION_ERROR=1
ENABLE_HEBBIAN_LEARNING=1
ENABLE_CURIOSITY=1
ENABLE_SELF_HEALING=1
ENABLE_MULTISCALE=1
ENABLE_ENERGY_BUDGET=1
```
