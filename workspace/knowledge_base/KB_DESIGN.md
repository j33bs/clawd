# Knowledge Base System - Architecture Design

## Vision
A local-first, agentic knowledge base that combines:
- **QMD** for fast search (BM25 + vectors + reranking)
- **HiveMind** for scoped, redacted memory with TTL
- **Knowledge Graph** for entity relationships and decision trails
- **Agentic RAG** for self-improving retrieval

## Current State
- QMD: Indexed 120 files, 278 vectors ✅
- HiveMind: Query, store, contradictions, digests ✅
- MCP: Running on port 8181 ✅

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER QUERY                                    │
│              "What decisions did we make about X?"               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  AGENTIC RAG ORCHESTRATOR                                        │
│  1. Analyze query intent                                         │
│  2. Decide retrieval strategy (search / graph / memory)          │
│  3. Execute multi-step retrieval                                 │
│  4. Self-critique and refine                                     │
│  5. Format response with citations                               │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  QMD Search      │  │  Knowledge Graph │  │  HiveMind        │
│  - BM25 keyword  │  │  - Entities      │  │  - Scope filter │
│  - Vector sim    │  │  - Relations     │  │  - Redaction    │
│  - Reranking     │  │  - Decision path │  │  - TTL expiry   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Components to Build

### 1. Knowledge Graph Store
- Entity extraction from documents
- Relationship mapping (depends_on, caused_by, related_to)
- Decision trail tracking

### 2. Agentic RAG Engine
- Query intent classification
- Retrieval strategy selection
- Result synthesis with citations
- Self-critique loop

### 3. Unified CLI
- Single entry point for all KB operations
- `kb query <question>` - ask anything
- `kb add <content>` - add to knowledge base
- `kb graph` - visualize relationships
- `kb stats` - show KB health

## Implementation

### Phase 1: QMD + HiveMind (COMPLETED)
- QMD indexes workspace ✅
- HiveMind stores scoped memories ✅
- Agent auto-queries both ✅

### Phase 2: Knowledge Graph (IN PROGRESS)
- [ ] Create entity extraction from QMD results
- [ ] Build relationship store
- [ ] Track decision provenance

### Phase 3: Agentic RAG (PENDING)
- [ ] Intent classification
- [ ] Multi-step retrieval
- [ ] Self-critique loop

### Phase 4: Unified CLI (PENDING)
- [ ] Single `kb` command
- [ ] Natural language queries

## File Structure
```
workspace/
├── knowledge-base/
│   ├── kb.py                 # Main CLI
│   ├── graph/
│   │   ├── entities.py       # Entity extraction
│   │   ├── relations.py      # Relationship mapping
│   │   └── store.py          # Graph database
│   ├── agentic/
│   │   ├── intent.py         # Query classification
│   │   ├── retrieve.py       # Multi-step retrieval
│   │   └── synthesize.py     # Result generation
│   └── data/
│       └── graph.jsonl       # Knowledge graph storage
```

## Usage

```bash
# Ask a question (Agentic RAG)
python -m kb query "What do we know about Ollama routing?"

# Add a decision
python -m kb add --type decision --content "Use QMD for workspace search"

# View graph
python -m kb graph --entity Ollama

# Stats
python -m kb stats
```

## Integration with Existing Systems

- **QMD**: Used for initial document retrieval
- **HiveMind**: Used for agent-specific memory
- **Git commits**: Used for decision provenance
- **MCP**: Exposes kb query to agents

## Success Metrics
- Query latency < 500ms
- Citation accuracy > 90%
- Entity recall > 80%
- Scope enforcement 100%
