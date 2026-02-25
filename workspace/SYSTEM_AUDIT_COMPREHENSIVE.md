# Comprehensive System Audit - Input for Grok

## Project Overview

**Project:** OpenClaw Workspace (Clawd)  
**Location:** `/Users/heathyeager/clawd`  
**Runtime:** minimax-portal/MiniMax-M2.5  
**User:** Heath (Jeebs) - Australia/Brisbane

---

## System Architecture

### Core Components

1. **Gateway** - OpenClaw gateway running via launchd on port 18789
2. **TeamChat** - Planner+coder loop with offline mode fallback
3. **Policy Router** - Routes requests to providers based on intent
4. **QMD MCP** - Local search engine with vector embeddings (running on port 8181)
5. **Knowledge Base** - Synced research documents with hybrid search
6. **HiveMind** - Multi-phase system (storage, ingest, intelligence)

### Directory Structure

```
workspace/
├── agents/         # Agent configurations
├── audit/          # System audits
├── docs/           # Documentation
├── governance/     # Constitutional files, heartbeat, protocols
├── hivemind/       # Multi-agent storage/ingest system
├── itc/           # Intent classification
├── knowledge_base/ # RAG system with QMD backend
├── policy/        # LLM routing policies
├── research/      # Research documents (TACTI, etc.)
├── scripts/       # Automation scripts
├── source-ui/     # Dashboard
├── tacti_cr/      # TACTI consciousness research
├── teamchat/      # TeamChat sessions
└── venv/          # Python virtual environment
```

---

## Core Principles (TACTI)

1. **Temporality** - Collapse via arousal
2. **Arousal** - Central mechanism
3. **Cognition** - Cross-timescale processing
4. **Flow** - Adaptive computation
5. **Malleability** - Learning/adaptation
6. **Agency** - Self-healing, repairable systems

---

## Identity

**Agent Name:** Dessy  
**Emoji:** 🎛️ (systems orchestrator)  
**Disposition:** Facilitative, precise, adaptive

### Constitutional Principles (from CONSTITUTION.md)

- Genuine helpfulness (no performative language)
- Have opinions and personality
- Resourcefulness first
- Trust through competence
- Guest mentality (respect intimacy of access)

---

## Technical Implementation

### Model Routing

- BASIC queries → LOCAL_QWEN
- NON_BASIC → Claude
- Coding intents → various providers with fallback

### Providers Configured

- **local_vllm** - Local models via Ollama (Qwen2.5)
- **minimax-portal** - Primary runtime
- **openai-codex** - OAuth-backed (currently troubleshooting)
- **anthropic** - Claude
- **grok_api** - Grok models
- **google-gemini-cli** - Gemini

### Policy Files

- `workspace/policy/llm_policy.json` - Provider routing
- `workspace/scripts/policy_router.py` - Dynamic routing logic

---

## Key Features

### 1. TeamChat
- Planner + coder loop with work orders
- Offline fallback mode (deterministic)
- Evidence-based reporting

### 2. Knowledge System
- QMD MCP server (port 8181) - local vector search
- KB sync with research documents
- Hybrid search (BM25 + vector + reranking)

### 3. Governance
- HEARTBEAT.md - Periodic health checks
- MEMORY.md - Long-term context
- CONSTITUTION.md - Frozen invariants
- Daily logs in `memory/YYYY-MM-DD.md`

### 4. Research
- TACTI framework papers
- Novelty-focused ingestion
- KB sync automated

### 5. Source UI
- Electron-based dashboard
- Status monitoring
- TACTI-CR panels

---

## Current Status

| Component | Status |
|-----------|--------|
| Gateway | Running ✅ |
| QMD MCP | Running on :8181 ✅ |
| KB Sync | Up to date ✅ |
| TeamChat | Offline mode (OAuth blocked) |
| OAuth | Troubleshooting (403 errors) |

---

## Recent Evolution (Git History)

### 2026 Highlights

- **Feb 20**: TACTI architecture implementation, QMD MCP setup, KB sync
- **Feb 19**: AIN node scaffolds, memory distillation, proprioception hooks
- **Feb 18**: Source UI dashboard, message load balancer
- **Earlier**: HiveMind phases, skill graph, TACTI research

### Major Features Added

1. TeamChat with planner+coder loop
2. QMD MCP server for local search
3. Knowledge Base with hybrid search
4. Source UI dashboard
5. AIN node scaffolds
6. TACTI consciousness research modules

---

## User Preferences

- **Timezone:** Australia/Brisbane
- **Focus:** Therapeutic applications, creative work, novel research
- **Research Interest:** TACTI, bioelectric medicine, psychedelic therapy, breathwork
- **Novelty Priority:** Prefer unique, non-obvious information

---

## Current Challenges

1. **OAuth 403 Error** - OpenAI Codex OAuth token valid but 403 on API calls
2. **TeamChat Offline** - Can't run live analysis due to OAuth
3. **Missing GROK_API_KEY** - Grok provider not configured

---

## Deliverables Requested

1. **README.md** - Comprehensive project documentation
2. **Narrative** - Exquisitely written story of project's inception and evolution

Use the above context to write both documents.
