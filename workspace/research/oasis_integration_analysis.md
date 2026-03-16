# OASIS Integration Analysis

## What OASIS Provides

**OASIS** (Open Agent Social Interaction Simulations) is a social media simulator from camel-ai:

- **Scale**: Up to 1 million agents
- **Platforms**: Twitter/X, Reddit
- **Actions**: 23 action types (like, comment, follow, post, repost, quote, search, etc.)
- **Features**: Interest-based + hot-score recommendation systems
- **Stars**: 3.2k on GitHub
- **License**: Apache 2.0

## TACTI Current State

The TACTI system tracks:
- **Relationship**: trust_score, attunement_index (per session)
- **Arousal**: token_count, tool_calls, tool_failures
- **Patterns**: conversation shortcuts and patterns
- **Data storage**: JSON files in `workspace/state_runtime/memory/`

## Integration Opportunities

### 1. Relationship Dynamics Simulation (HIGH VALUE)

**What**: Use OASIS to simulate how relationship states propagate through a network.

**How**:
1. Export TACTI relationship data → create OASIS agent profiles
2. Map TACTI's trust_score/attunement → OASIS agent personality traits
3. Inject "events" (like feedback, disagreements) as OASIS posts
4. Observe emergent social dynamics (polarization, healing, withdrawal)

**Why it matters**: TACTI predicts dyadic (one-to-one) relationship health. OASIS could model how that health *spreads* or *decays* in a social context.

### 2. Belief/Opinion Propagation (HIGH VALUE)

**What**: Model how ideas spread through a population.

**How**:
1. Take TACTI insights (from `novelty.py` or research wanderer)
2. Spawn OASIS agents with different "belief profiles"
3. Track how ideas propagate through likes/comments/shares

**Why it matters**: TACTI already tracks novelty and insight — OASIS could test whether an insight would "land" in different populations.

### 3. "What-If" Scenario Testing (MEDIUM)

**What**: Before recommending a response strategy, test it in simulation.

**How**:
1. Current state: trust_score declining
2. Candidate actions: empathize vs. challenge vs. withdraw
3. Run OASIS simulation with each → compare outcomes

**Why it matters**: Could inform *how* to respond, not just *that* something is wrong.

### 4. Mirror Population (FUTURE)

**What**: Create a "shadow population" of agents that mirror the user's social graph.

**How**:
1. Model people the user interacts with (from memory/context)
2. Run parallel simulations
3. Use outcomes to predict real-world dynamics

**Why it matters**: Long-term, but aligns with TACTI's "rehearse the future" ethos.

## Technical Integration Path

### Phase 1: Data Bridge (Quick Win)
```
TACTI state → JSON profiles → OASIS agent profiles
```

### Phase 2: Action Mapping
```
TACTI events → OASIS actions
- "trust_increase" → LIKE_POST, FOLLOW
- "trust_decrease" → MUTE, DISLIKE_POST  
- "arousal_spike" → CREATE_POST (venting)
```

### Phase 3: Feedback Loop
```
OASIS simulation outcomes → TACTI prediction model
```

## Risks & Considerations

- **Complexity**: OASIS requires Python 3.11+, OpenAI API (or compatible)
- **Cost**: LLM calls per agent per action = scales expensively
- **Validation**: Hard to verify simulation matches reality
- **Scope creep**: Could become a research project in itself

## Recommendation

**Start with Phase 1**: Create a simple bridge that exports TACTI session state to OASIS agent profiles. Run a small test (10-20 agents) to see if the dynamics feel meaningful.

This is low-risk, reversible, and gives us data to decide whether deeper integration is worth it.

---

# Other Fruitful Angles

## 1. GraphRAG Upgrade (MiroFish's Knowledge Graph → TACTI KB)

MiroFish uses GraphRAG for entity/relationship extraction from documents. TACTI already has a graph module (`workspace/knowledge_base/graph/`) but it uses simple embedding-based retrieval.

**Opportunity**: Integrate GraphRAG-style extraction to enhance:
- `novelty.py` — better entity tracking beyond simple text similarity
- Knowledge base — richer relationship extraction from ingested PDFs
- Research wanderer — deeper insight from papers

**Effort**: Medium. Requires Python dependencies + understanding their extraction pipeline.

## 2. Agent Memory Systems (Zep → Local)

MiroFish uses Zep Cloud for agent memory management. TACTI has custom JSON-based session memory.

**Opportunity**: Compare architectures:
- Zep: cloud-native, vector search, automatic summarization
- TACTI's current: file-based, manual consolidation

**Actually**: There's already a local fork of MiroFish (`nikmcfly/MiroFish-Offline`) that uses Neo4j + Graphiti instead of Zep. Could study that architecture.

## 3. Multi-Agent Emergence Research

MiroFish spawns thousands of agents → emergent phenomena. TACTI is about dyadic (human-agent) relationship.

**Interesting question**: Could TACTI principles (arousal, trust, attunement) scale to multi-agent populations? What would "collective trust" look like?

**Related**: The `emergent_coordination.md` paper in the research folder (arXiv 2510.05174) — about steering integration in multi-agent LLMs. Very relevant to TACTI's integration claims.

## 4. Prediction/Simulation Output

MiroFish outputs prediction reports. TACTI could benefit from:
- Generating scenario analyses (what if trust drops 20%?)
- Simulating intervention outcomes before applying them
- Visualizing relationship trajectories

---

## Prioritized Next Steps

| Priority | Action | Effort |
|----------|--------|--------|
| 1 | OASIS Phase 1: Export TACTI state → OASIS profiles | Low |
| 2 | Study MiroFish-Offline (Neo4j) architecture for potential KB upgrade | Medium |
| 3 | Read emergent_coordination paper for integration relevance | Low |
| 4 | GraphRAG trial on one PDF | Medium |
