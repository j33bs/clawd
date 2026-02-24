# Agent Memory: Lifecycle Framework

**Source:** GitHub — Shichun-Liu/Agent-Memory-Paper-List ("Memory in the Age of AI Agents: A Survey")
**Added:** 2026-02-23

## Framework: Three-Phase Memory Lifecycle

The survey dissects the operational lifecycle of agent memory into:

1. **Formation** — extraction of relevant information from interactions
2. **Evolution** — consolidation and forgetting (memory strengthening/pruning)
3. **Retrieval** — access strategies for memory lookup

## Conceptual Comparison

The framework distinguishes:
- **Agent Memory** — persistent, goal-directed
- **LLM Memory** — context-window limited
- **RAG** — retrieval-augmented but not truly persistent
- **Context Engineering** — active curation of context window

## Relevance to TACTI

Our existing memory architecture (trails, peer graph, reservoir) could be mapped to this framework:

| Phase | Our Component | Gap? |
|-------|---------------|------|
| Formation | trails.py | ✓ |
| Evolution | reservoir (partially) | Needs sleep-like consolidation |
| Retrieval | peer graph | Could be enhanced |

## Novel Idea: Memory Lifecycle Audit

Apply this three-phase framework to our system. Identify:
- Where Formation works
- Where Evolution is missing/partial
- Where Retrieval could improve

This creates a concrete audit checklist for our memory architecture.

## References
- https://github.com/Shichun-Liu/Agent-Memory-Paper-List
