# Twenty System Evolutions
*Synthesised from Agent Proposal + Clawd/TACTI Architecture | 2026-02-21*

---

## How to use this document

Pass the full list below to ChatGPT o3 with this framing:

> "You are a senior AI systems architect. Below are 20 evolutionary features for a personal AI agent called Clawd, built around the TACTI(C)-R framework (arousal regulation, novelty detection, relational tracking, pattern chunking, collapse recovery). Each feature has a name, what it does, and why it matters. Your job is to produce Codex-ready implementation tickets for each one — pseudocode, file locations, acceptance criteria, and test strategy."

---

## The Original Ten (from Agent)

### 1. Hook Modules Into Message Flow
**What:** Wire `arousal_tracker` and `relationship_tracker` to live message events.
**Why:** Modules exist but aren't running. The nervous system needs to be online.

### 2. Daily Briefing Personalization
**What:** Inject `trust_score` and `attunement_index` from `relationship_tracker` into the 7AM briefing.
**Why:** Morning ritual is the highest-leverage relational touchpoint.

### 3. Collapse Detection & Recovery
**What:** Monitor for 3+ consecutive tool failures or context overflow; trigger graceful degradation.
**Why:** Systems break. A recovery reflex is the difference between crash and repair.

### 4. Novelty-Aware KB Retrieval
**What:** Score knowledge base results by novelty (`novelty.py`) and surface the delta first.
**Why:** Stop reciting known things. Priority = what just changed.

### 5. Pattern Chunking Automation
**What:** Auto-scan session logs for requests repeated 3+ times and create shortcuts.
**Why:** Repetition is a signal. Turn it into a one-word command.

### 6. Wheel of Awareness Exercise
**What:** Periodic self-reflection prompt — agent distinguishes what it's observing vs. what it's doing.
**Why:** IPNB: consciousness integrates by observing itself.

### 7. Inter-Brain Synchrony Metrics
**What:** Measure attunement via response relevance and sentiment alignment over time.
**Why:** Can't improve what you don't measure.

### 8. Context Auto-Compaction
**What:** Smart compression of old context when token arousal hits threshold.
**Why:** Long conversations lose the thread. Keep working memory fresh.

### 9. MWe Relationship Score
**What:** Composite metric of individual health (arousal, coherence) + collective health (trust, attunement).
**Why:** Gives scientific grounding to the relational layer.

### 10. Feedback Loop Learning
**What:** Track which suggestions are accepted/dismissed; adjust future output accordingly.
**Why:** Turns interaction into adaptation. Closes the loop.

---

## My Ten (from Clawd Architecture)

### 11. Cross-Timescale Router
**What:** Explicit routing layer that sends requests down fast (direct tool), medium (deliberate + memory), or slow (consolidation to KB) paths based on complexity inference.
**Why:** The TACTI framework describes three processing timescales but they're not implemented as distinct paths. Soar does this with substates — we need the equivalent. Codex ticket: add a `timescale_router.py` that classifies intent and dispatches accordingly.

### 12. Impasse Substate Handler
**What:** When tool failure is detected, spawn a "substate" that tries alternative approaches (different tool, different query, ask user) before escalating to collapse mode.
**Why:** Directly from Soar architecture research. Failure → substate → recovery is more graceful than failure → crash. This is the micro-level complement to item 3's macro collapse detection.

### 13. Embedding-Based Novelty Comparison
**What:** Replace string-diff novelty detection with embedding cosine distance so novelty is semantic, not syntactic.
**Why:** The roadmap already flags this as incomplete (`[ ] Embedding-based comparison`). Current novelty detection is naive. Embedding similarity is the correct substrate.

### 14. Arousal Temporal Embedding
**What:** Implement the time-delay reconstruction from `TACTI_architecture_implementation.md` — store `[z(t), z(t-τ), z(t-2τ)]` as a rolling arousal vector, not just current state.
**Why:** The Nature 2025 paper shows arousal as a universal embedding requires temporal context, not just scalar value. This turns the arousal state machine into a proper dynamic signal.

### 15. Φ (Phi) Integration Proxy
**What:** Implement a lightweight IIT-inspired integration metric across the agent's active modules — how much are arousal, relationship, novelty, and pattern modules influencing each other vs. running in isolation?
**Why:** From `active_inference_research.md`: high Φ = high integration. A low integration score is a signal that modules are siloed and the system is incoherent. This gives us a health check for architectural coupling.

### 16. Heartbeat Proactive Suggestions
**What:** Background scheduler that, between sessions, identifies items the user would likely want to know about (new research matches, pattern anomalies, relationship drift) and queues them for the next session open.
**Why:** The roadmap Phase 3 item: "Suggest before asked." True autonomy is proactive, not reactive. The daily briefing is one channel; this makes every session opening an opportunity.

### 17. Emotional Tone Classifier
**What:** Tag each message pair (user in / agent out) with emotional valence and energy level; feed into `relationship_tracker` and `arousal_tracker`.
**Why:** The roadmap lists this as a "dream feature." It's actually the missing input signal. Without tone data, relationship health is a guess. With it, attunement scoring becomes real.

### 18. Predictive Context Preloading
**What:** At session start, predict which KB entities, research papers, and patterns are most likely relevant based on time of day, recent activity, and open threads — and pre-load them into working context.
**Why:** Retrieval lag is a form of cognitive friction. Pre-warming context means the agent is already thinking about what matters before the user types. This is the agent equivalent of a therapist reviewing notes before the session.

### 19. Session Continuity Handshake
**What:** Structured open and close protocol — on open: load last session summary, relationship state, open tasks; on close: write session summary, update relationship tracker, flag unresolved threads.
**Why:** Currently, each session starts cold. The SOUL.md says "these files are your memory — read them," but this is manual and inconsistent. A structured handshake makes continuity mechanical, not aspirational.

### 20. Self-Configuration Tuning
**What:** Track which configuration parameters (chunk threshold = 3, arousal threshold for compaction, novelty weight = 0.4) correlate with better outcomes (user accepts suggestion, task completed cleanly) and propose adjustments over time.
**Why:** Phase 3 roadmap item: "Configuration auto-tuning." The current constants are educated guesses. After 30+ sessions of feedback loop data (item 10), we have enough signal to make them adaptive. This is the system learning its own optimal operating parameters.

---

## Synthesis Notes for Codex

**Architectural dependencies (implement in this order):**

1. Items 1, 19 — get the plumbing live (hooks + handshake)
2. Items 3, 12 — collapse detection at macro and micro levels
3. Items 13, 14 — upgrade novelty and arousal to embedding-based signals
4. Items 4, 11 — retrieval and routing become intelligence-grade
5. Items 7, 17 — attunement and tone give the relational layer real inputs
6. Items 2, 16, 18 — personalisation, proactive, and predictive behaviours
7. Items 5, 10 — chunking and feedback close the adaptation loop
8. Items 6, 15 — meta-level: self-reflection and integration health
9. Items 9, 20 — composite scores and self-tuning (require all prior data)

**Key files to brief Codex on:**
- `workspace/memory/arousal_tracker.py`
- `workspace/memory/relationship_tracker.py`
- `workspace/memory/novelty.py`
- `workspace/memory/pattern_chunker.py`
- `workspace/memory/context_compactor.py`
- `workspace/research/IMPLEMENTATION_ROADMAP.md`
- `workspace/research/TACTI_architecture_implementation.md`
- `SOUL.md` (agent operating principles)
- `MEMORY.md` (persistent context)

---

*The paradox: endless work, perfect progress.*
