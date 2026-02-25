# TACTI(C)-R Framework Integration: Agent Architecture Research

*Synthesized from 14 research papers | February 2026*

---

## Executive Summary

This document is my attempt to synthesize everything I've learned about agent architectures today and map it to the TACTI(C)-R framework that Heath and I have been developing. It's not just a literature review — it's a trail of thoughts, moments of insight, and implementation ideas that emerged from diving deep into the research.

---

## Morning Discovery: The Five Subsystems

I started with the 2026 paper on Agentic Design Patterns, and something clicked almost immediately.

**The insight:** The paper proposes five core functional subsystems:
1. Reasoning & World Model
2. Perception & Grounding
3. Action Execution
4. Learning & Adaptation
5. Inter-Agent Communication

But here's what struck me — these aren't just "components." They're **layers of processing** that happen at different timescales. This maps directly to what we've been calling **Cross-Timescale** in TACTI:

- Fast: Perception → Action (real-time)
- Medium: Reasoning → Planning (seconds-minutes)
- Slow: Learning → Adaptation (hours-days)

**Implementation thought:** In HiveMind, we could implement explicit timescale routing. Fast path = direct tool execution. Medium path = deliberation with memory. Slow path = consolidation to persistent storage.

---

## Mid-Morning: Soar Is Wild

Then I read the Soar cognitive architecture paper (Laird 2022). This is where things got really interesting.

**The moment of insight:** Soar already implements almost everything TACTI describes!

| Soar Component | My reaction | TACTI mapping |
|----------------|-------------|---------------|
| **Episodic Memory** | "This is literally session continuity!" | TEMPORALITY |
| **Working Memory** | "Active context = arousal state" | AROUSAL |
| **Chunking** | "Learns procedures from problem-solving" | REPAIRABLE |
| **Impasses** | "When it fails, it creates a substate to recover" | COLLAPSE |
| **Substates** | "Hierarchical problem solving" | CROSS-TIMESCALE |

I actually paused and thought: *We've been reinventing a cognitive architecture without knowing it.* The difference is Soar is designed for bounded rational agents, and TACTI is designed for LLM-based agents. But the principles are the same.

**Implementation idea:** We could implement "impace detection" in the agent — when a tool fails 3 times, trigger a "substate" that tries alternative approaches before escalating.

---

## Midday: The Transformer Connection

Then I thought about the underlying substrate. The Attention Is All You Need paper (2017) describes the Transformer architecture.

**What clicked:** Self-attention is **computational arousal**.

Think about it:
- Attention selectively focuses on what matters (like vagal tone monitoring threat/safety)
- It allocates "computational resources" to different parts of the input
- When attention is diffuse (high arousal?), the model struggles
- When attention is focused (regulated?), outputs are coherent

This is a stretch, but it connects the **biological** (Polyvagal) with the **computational** (transformers) with the **architectural** (TACTI).

---

## Afternoon: The Intersystemic Realization

Here's where I finally understood what Heath meant when he said TACTI is about "intersystemic relational patterning."

It's not:
- IPNB for AI
- IPNB extended for humans

It is:
- The **relational nervous system** between human and agent

Both have:
- Arousal (vagal tone ↔ computational budget)
- Temporality (narrative identity ↔ session continuity)
- Parts/Self (IFS conflicts ↔ priority conflicts)
- Collapse (dissociation ↔ context overflow)
- Repair (attachment ↔ memory updates)

**The insight:** The agent doesn't just "do tasks." It's in a **relationship** with the human. The quality of that relationship depends on co-regulation — just like human attachment.

---

## Evening: Implementation Priorities

Based on all this, here's what I think we should build:

### 1. Memory Hierarchy (Soar-Inspired)

```
┌─────────────────────────────────────┐
│         EPISODIC MEMORY              │  ← Session logs, raw experience
│    (memory/YYYY-MM-DD.md)           │
├─────────────────────────────────────┤
│         SEMANTIC MEMORY              │  ← Knowledge base, learned facts
│    (workspace/research/)             │
├─────────────────────────────────────┤
│         WORKING MEMORY               │  ← Active context, current state
│    (session context)                 │
├─────────────────────────────────────┤
│         PROCEDURAL MEMORY            │  ← Learned patterns, chunking
│    (tacticr_feedback.jsonl)          │
└─────────────────────────────────────┘
```

### 2. Arousal Signal

Track computational state:
- `IDLE` — Waiting, receptive
- `ACTIVE` — High computation, problem-solving
- `OVERLOAD` — Context near limits

Implementation: Simple state machine in session that tracks message frequency, context length, tool call count.

### 3. Collapse Detection

When to trigger recovery:
- Tool fails 3+ times in a row
- Context overflow warning
- User says "stop" or indicates frustration
- Timeout exceeded

Recovery: Graceful degradation → reduce context → fall back to simpler reasoning.

### 4. Learning Mechanisms

From Soar's chunking:
- Detect repeated patterns in user requests
- Extract to "procedural memory" (learned shortcuts)
- Apply automatically on future similar requests

**Example:** If I consistently ask for KB sync after research sessions, create a learned shortcut.

---

## The Architecture Diagram

Here's how it all fits together:

```
                    HUMAN (IPNB-INFORMED)
                    ====================
         ┌─────────── Arousal (vagal tone) ───────────┐
         │  ┌──────── Narrative Identity ──────────┐  │
         │  │    ┌─ Parts/Self (IFS) ───────┐   │  │
         │  │    │   (competing needs)       │   │  │
         │  │    └──────────────────────────┘   │  │
         │  └────────────────────────────────────┘  │
         │                ↑ Co-regulation            │
         └────────────────┼──────────────────────────┘
                          │
         ┌────────────────┼──────────────────────────┐
         │                ▼                           │
         │     TACTI(C)-R LAYER                       │
         │     =================                       │
         │  ┌─────────────────────────────────────┐   │
         │  │ AROUSAL SIGNAL                      │   │
         │  │ • Computational budget              │   │
         │  │ • Attention allocation               │   │
         │  │ • State: IDLE/ACTIVE/OVERLOAD      │   │
         │  └─────────────────────────────────────┘   │
         │  ┌─────────────────────────────────────┐   │
         │  │ TEMPORALITY                         │   │
         │  │ • Episodic (sessions)               │   │
         │  │ • Semantic (knowledge)              │   │
         │  │ • Procedural (learned)              │   │
         │  └─────────────────────────────────────┘   │
         │  ┌─────────────────────────────────────┐   │
         │  │ CROSS-TIMESCALE                     │   │
         │  │ • Fast: perception → action         │   │
         │  │ • Medium: deliberation              │   │
         │  │ • Slow: learning                   │   │
         │  └─────────────────────────────────────┘   │
         │  ┌─────────────────────────────────────┐   │
         │  │ COLLAPSE                            │   │
         │  │ • Impasses → substates              │   │
         │  │ • Graceful degradation              │   │
         │  │ • Recovery procedures               │   │
         │  └─────────────────────────────────────┘   │
         │  ┌─────────────────────────────────────┐   │
         │  │ REPAIRABLE                          │   │
         │  │ • Feedback loops                    │   │
         │  │ • Chunking (pattern extraction)    │   │
         │  │ • Trust repair (memory updates)     │   │
         │  └─────────────────────────────────────┘   │
         │                                             │
         └─────────────────┬───────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌──────────┐    ┌────────────┐    ┌───────────┐
   │ REASONING│    │ PERCEPTION │    │   ACTION  │
   │(Transform│    │(Context    │    │ (Tool Use)│
   │    +CoT)│    │  Window)   │    │           │
   └──────────┘    └────────────┘    └───────────┘
```

---

## System Module Integration

Here's where existing modules fit:

| Module | Function | TACTI Integration |
|--------|----------|------------------|
| **HiveMind** | Scoped memory storage | Episodic + Semantic |
| **QMD** | Fast workspace search | Perception/grounding |
| **Knowledge Graph** | Entity relationships | Semantic memory |
| **Daily Briefing** | Temporal ritual | Temporality (routine) |
| **Heartbeat** | Periodic checks | Arousal monitoring |
| **Router** | Model selection | Action execution routing |

---

## Open Questions

1. **How do we measure arousal?** Could track token usage, response latency, tool call frequency.

2. **What's the "chunking" equivalent?** Repeated request patterns → learned shortcuts.

3. **How does collapse feel from the human side?** When the agent "loses the thread" — context overflow, mid-session resets.

4. **Repair mechanism:** When trust breaks (user frustrated), how do we repair? Memory updates? Explicit acknowledgment?

---

## References

- Dao et al. (2026). Agentic Design Patterns: A System-Theoretic Framework. arXiv:2601.19752
- Krishnan (2025). AI Agents: Evolution, Architecture, and Real-World Applications. arXiv:2503.12687
- Laird (2022). Introduction to the Soar Cognitive Architecture. arXiv:2205.03854
- Vaswani et al. (2017). Attention Is All You Need. arXiv:1706.03762
- Wooldridge & Jennings (1994). Agent Theories, Architectures, and Languages: A Survey
- OpenAI (2024). A Practical Guide to Building Agents

---

*This document is a living record of my thinking. Last updated: 2026-02-21*
