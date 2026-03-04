# Emergent Coordination in Multi-Agent LLM Systems

**Source:** arXiv 2510.05174 — Christoph Riedl et al.

**TL;DR:** Multi-agent LLM systems can be steered from "mere aggregates" to "higher-order collectives" via prompt design. Integration emerges.

---

## Core Question

When are multi-agent LLM systems merely a collection of individual agents versus an integrated collective with higher-order structure?

---

## Method

Information-theoretic framework using **partial information decomposition of time-delayed mutual information (TDMI)** to measure:
- Whether dynamical emergence is present
- Where it's localized
- Whether cross-agent synergy is performance-relevant or spurious temporal coupling

**The task:** Simple guessing game with NO direct agent communication — only minimal group-level feedback.

---

## Three Prompt Conditions

### 1. Control (basic prompt)
- Strong temporal synergy
- Little coordinated alignment across agents
- → Agents act as **aggregate**

### 2. Persona assignment
- Stable identity-linked differentiation emerges
- → Each agent develops consistent "character"

### 3. Persona + "think about what other agents might do"
- Identity-linked differentiation + goal-directed complementarity
- → Agents become **higher-order collective**

---

## Key Findings

1. **Prompt design steers emergence** — From aggregate to collective via prompting alone
2. **Synergy is measurable** — Information decomposition captures integration
3. **No attribution of human-like cognition needed** — Patterns mirror collective intelligence without claiming agents "think"
4. **Robust across measures and estimators** — Not explained by coordination-free baselines

---

## Relevance to TACTI

| TACTI Concept | Emergent Coordination Finding |
|---------------|------------------------------|
| **Integration** | Synergy emerges via prompt design — integration can be *steered* |
| **Cross-timescale** | TDMI captures time-delayed mutual information — cross-agent temporal dynamics |
| **Higher-order structure** | Demonstrates higher-order collective properties without explicit programming |
| **Prompt as lever** | Prompt design = architectural choice = integration outcome |
| **Complementarity** | "Think about others" produces goal-directed complementarity — alignment + differentiation |

---

## Tensions & Questions

1. **Is this "real" emergence or sophisticated pattern-matching?** — No explicit communication, yet coordination emerges. Is this integration or just good prediction?

2. **Synergy vs. coupling** — They distinguish spurious temporal coupling from performance-relevant synergy. How does this map to TACTI's Φ measurement?

3. **Prompt = architecture** — If prompts can induce integration, is a prompt just a lightweight architecture? What does this mean for TACTI's claims about structural integration?

4. **The alignment-complementarity trade-off** — Effective performance requires both shared objectives (alignment) AND complementary contributions. This mirrors TACTI's cross-timescale integration: different agents = different timescales = complementarity.

---

## Quote

> "Without attributing human-like cognition to the agents, the patterns of interaction we observe mirror well-established principles of collective intelligence in human groups: effective performance requires both alignment on shared objectives and complementary contributions across members."

---

## Next Steps

- [ ] Map TDMI synergy metrics to TACTI Φ measurement
- [ ] Test similar prompts in HiveMind/Dali
- [ ] Explore whether "think about what other agents might do" could activate cross-agent integration in this system
- [ ] Consider: if prompts induce integration, what does TACTI predict about which prompts work?
