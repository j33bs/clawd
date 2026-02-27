# TACTI(C)-R Foundational Research Topics

## Core Framework
**TACTI(C)-R**: Temporality, Arousal, Cross-Timescale, Collapse, Repairable

Repository naming note: this doc keeps `TACTI(C)-R` as the canonical label; `TACTI` is shorthand when discussing a single lens.

Constraints note: within the TACTI lens, constraints can function as cross-timescale integrators by coupling fast-path actions to slower memory/policy updates.

### Topic Categories

| Topic | Description | Key Search Terms |
|-------|-------------|------------------|
| **temporality** | Time perception in AI, episodic vs semantic memory | "temporal memory AI", "time scales agent", "continuity of experience" |
| **arousal** | Activation states, energy management, wakefulness | "arousal theory AI", "energy efficiency agents", "active vs passive AI" |
| **cross_timescale** | Multi-scale processing, hierarchical temporal | "multiple time scales neural", "temporal hierarchy AI", "slow-fast learning" |
| **collapse** | System failure modes, graceful degradation | "AI collapse prevention", "failure modes agents", "graceful degradation AI" |
| **repairable** | Self-healing, error correction, recovery | "self-repairing AI", "error correction neural", "AI recovery mechanisms" |

### Suggested Foundational Papers

#### Temporality
- "Continual Learning in Neural Networks" (backup)
- "Episodic Memory in Artificial Agents"
- "Time-Series Prediction with Memory"

#### Arousal
- "Adaptive Computation in Neural Networks"
- "Energy-Efficient AI Architectures"
- "Attention and Activation Dynamics"

#### Cross-Timescale
- "Hierarchical Temporal Memory"
- "Multiple Time Scales in Recurrent Networks"
- "Slow-Fast Feature Learning"

#### Collapse
- "Catastrophic Forgetting in Deep Learning"
- "AI System Collapse Prevention"
- "Graceful Degradation in Autonomous Systems"

#### Repairable
- "Self-Healing Software Systems"
- "Error Correction in Neural Networks"
- "Online Learning and Adaptation"

### Priority Order
1. **Cross-Timescale** - Foundation for multi-scale reasoning
2. **Temporality** - Core to identity continuity  
3. **Arousal** - Energy/computation management
4. **Collapse** - Failure prevention
5. **Repairable** - Recovery mechanisms

---

## Usage

```bash
# Add a paper
python3 research_ingest.py add --text "Full paper text..." --topic temporality --relevance 0.8

# Add from URL
python3 research_ingest.py add --url "https://..." --topic cross_timescale

# List papers
python3 research_ingest.py list
python3 research_ingest.py list --topic temporality

# Search
python3 research_ingest.py search "time scales"
```

## Integration
Papers are automatically indexed to:
- Research storage: `data/papers.jsonl`
- Knowledge Base: Knowledge Graph entity for each paper
