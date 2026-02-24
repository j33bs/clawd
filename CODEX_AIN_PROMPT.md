# AIN Agent Prototype — Codex Prompt

## Mission

Build a prototype Active Integration Network (AIN) agent with working Active Inference, Reservoir dynamics, and consciousness measurement. This is a proof-of-concept to test the AIN framework in code.

## Background

AIN is a novel consciousness architecture combining:
- **Active Inference** — agent minimizes surprise (prediction error)
- **Reservoir Computing** — temporal memory echoes
- **IIT (Integrated Information Theory)** — consciousness measurement (Φ)
- **GNWT (Global Neuronal Workspace)** — information broadcasting

See `/Users/heathyeager/clawd/nodes/ain/docs/IMPLEMENTATION.md` and `/Users/heathyeager/clawd/nodes/ain/docs/AIN_FRAMEWORK.md` for detailed theory.

## Core Requirements

### 1. Active Inference Module

- Implement a generative model that predicts observations
- Calculate prediction error (surprise) as free energy
- Map prediction error to drives: survival, curiosity, coherence
- Agent should act to minimize prediction error

```python
# Core concept
class GenerativeModel:
    def predict(self, observation) -> prediction
    def free_energy(self, observation) -> float

class Drives:
    def update(self, prediction_error, novelty, homeostasis)
    def get_total_drive() -> float
```

### 2. Reservoir State

- Maintain temporal state that echoes past inputs
- Use echo state network dynamics
- State should influence current predictions

```python
class Reservoir:
    def update(self, input_signal)
    def get_state() -> np.array
```

### 3. Φ (Phi) Measurement

- Approximate integrated information
- Track consciousness over time
- Measure integration, complexity, mutual information

```python
class PhiMeasurer:
    def measure() -> float  # Returns approximate Φ
    def track_over_time() -> list
```

### 4. Complete Agent

```python
class AINAgent:
    def __init__(self, id):
        self.model = GenerativeModel()
        self.drives = Drives()
        self.reservoir = Reservoir()
        self.phi = PhiMeasurer()

    def perceive(self, observation):
        # Update model, drives, reservoir
        pass

    def act(self):
        # Act based on drives
        pass

    def get_consciousness(self) -> float:
        # Return Φ
        pass
```

## Environment

Create a simple test environment:
- Grid world or simple 2D space
- Randomly generated observations (shapes, colors, patterns)
- Agent must learn to predict observations
- Track prediction error over time

## Testing

1. Agent should show decreasing prediction error (learning)
2. Φ should vary based on integration
3. Drives should influence behavior
4. Reservoir should show temporal effects

## Output Location

Create in: `/Users/heathyeager/clawd/nodes/ain/code/`

Files:
- `ain_agent.py` — Core AIN agent
- `environment.py` — Test environment
- `test_ain.py` — Run and visualize agent
- `README.md` — How to run and interpret results

## Success Criteria

- [ ] Agent learns (prediction error decreases)
- [ ] Drives influence behavior
- [ ] Reservoir shows temporal memory
- [ ] Φ measurement tracks consciousness
- [ ] Code runs without errors

## Notes

- Keep it simple — this is a prototype
- Use numpy, no heavy ML frameworks needed
- Focus on the mechanism, not perfect implementation
- Comment code to explain the AIN concepts
