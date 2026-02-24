# Agent Skills for Context Engineering

**Source:** [GitHub - muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)
**Author:** Muratcan Koylan (@koylanai)
**Added:** 2026-02-23

## Overview

A "Meta-Agent" knowledge base: a collection of skills written in markdown that teach an agent *how* to do context engineering, manage memory, and architect multi-agent systems.

Instead of just offering tools, it provides **conceptual knowledge** that an agent can read to improve its own performance in these domains.

## Key Concepts

**Context Engineering** is defined as the holistic curation of all information that enters the model's limited attention budget (system prompts, tools, history, etc.) to maximize signal and minimize degradation.

### Skill Categories

1.  **Foundational Skills**
    *   `context-fundamentals`: Anatomy of context.
    *   `context-degradation`: "Lost-in-the-middle", poisoning, distraction.
    *   `context-compression`: Summarization and compression strategies.

2.  **Architectural Skills**
    *   `multi-agent-patterns`: Orchestrator, P2P, Hierarchical.
    *   `memory-systems`: Short/Long-term, Graph memory.
    *   `tool-design`: Building effective tools.
    *   `filesystem-context`: Using files for dynamic context/offloading.
    *   `hosted-agents`: Background coding agents, sandboxed VMs.

3.  **Operational Skills**
    *   `context-optimization`: Compaction, caching.
    *   `evaluation` & `advanced-evaluation`: LLM-as-a-Judge, rubrics.

4.  **Cognitive Architecture**
    *   `bdi-mental-states`: BDI (Beliefs-Desires-Intentions) ontology patterns.

## Design Philosophy

*   **Progressive Disclosure:** Agents load only skill names/descriptions first. Full content loads only when activated.
*   **Platform Agnosticism:** Principles work across Claude Code, Cursor, etc.

## Usage Strategy

*   **For Claude Code:** Can be installed via `/plugin marketplace add ...`
*   **For Custom Agents (us):** Copy `SKILL.md` content into the agent's context (e.g., via `read` tool) when tackling specific architectural or optimization tasks.

## Relevance to TACTI

This repo offers concrete patterns for:
*   **Memory Systems**: Could inform our `memory/` architecture.
*   **Cognitive Architecture**: The `bdi-mental-states` skill might offer a structured way to track internal state alongside our TACTI arousal/vitality metrics.
*   **Multi-Agent Patterns**: Relevant for the C_Lawd / Dali / Claude / ChatGPT coordination.
