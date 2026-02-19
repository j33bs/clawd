# QMD + HiveMind Integration Plan

## Executive Summary

**QMD** (by Tobi Lütke/Shopify) and **HiveMind** serve overlapping but distinct purposes. This document outlines a cohesive integration strategy.

---

## System Comparison

| Capability | QMD | HiveMind | Winner |
|------------|-----|----------|--------|
| **Search** | BM25 + Vector + LLM reranking | Keyword only (no vectors) | QMD |
| **Local Embeddings** | ✅ GGUF models (Metal) | ⚠️ Ollama required | QMD |
| **Agent Scope** | ❌ No | ✅ `main`/`shared`/`codex` | HiveMind |
| **Redaction** | ❌ No | ✅ Mandatory pre-embed | HiveMind |
| **Contradiction Detection** | ❌ No | ✅ Phase 3 | HiveMind |
| **TTL/Expiry** | ❌ No | ✅ Knowledge Units | HiveMind |
| **MCP Server** | ✅ Built-in | ❌ Manual exec | QMD |
| **Context Trees** | ✅ Yes | ❌ No | QMD |
| **Query Expansion** | ✅ LLM-based | ❌ No | QMD |

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER QUERY                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  QMD (Primary Search Layer)                                 │
│  - BM25 keyword search                                      │
│  - Vector semantic search (Metal GPU)                      │
│  - LLM reranking + query expansion                         │
│  - Fast, production-ready                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (if scope-relevant)
┌─────────────────────────────────────────────────────────────┐
│  HiveMind (Intelligence Layer)                              │
│  - Agent scope filtering (main/shared/codex)               │
│  - Redaction enforcement                                    │
│  - Contradiction detection                                  │
│  - TTL expiry management                                    │
│  - Cross-agent digest generation                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Integration Steps

### Phase 1: Wire QMD for Workspace Search (Priority: HIGH)

```bash
# Add workspace as QMD collection
cd /Users/heathyeager/clawd
npx @tobilu/qmd collection add . --name clawd

# Add context for better results
npx @tobilu/qmd context add qmd://clawd "OpenClaw agent workspace with routing, memory, and governance"

# Create vector embeddings
npx @tobilu/qmd embed

# Test search
npx @tobilu/qmd query "Ollama config"
```

### Phase 2: MCP Server for Agent Access (Priority: HIGH)

```bash
# Start QMD MCP server (HTTP mode for shared access)
npx @tobilu/qmd mcp --http --daemon

# Verify
curl http://localhost:8181/health
```

### Phase 3: HiveMind as Intelligence Overlay (Priority: MEDIUM)

Keep HiveMind for:
- Agent scope filtering
- Redaction enforcement  
- Long-term memory with TTL
- Contradiction detection
- Cross-agent digests

Update HiveMind to use QMD for embeddings:
- Instead of calling Ollama directly
- Call `qmd embed` for vector creation

### Phase 4: Unified CLI (Priority: LOW)

Create wrapper that queries both:
```bash
# Pseudocode
function memory-query($query, $agent) {
  # 1. QMD search (fast, semantic)
  qmd_results = qmd query "$query" --json
  
  # 2. HiveMind scope filter
  filtered = filter_by_scope(qmd_results, $agent)
  
  # 3. Return combined results
  return merge(qmd_results, filtered)
}
```

---

## Commands to Run

### Jeebs: Execute these

```bash
# 1. Index the workspace
cd /Users/heathyeager/clawd
npx @tobilu/qmd collection add . --name clawd
npx @tobilu/qmd context add qmd://clawd "OpenClaw agent workspace - routing, memory, governance, hivemind, skills, configs"
npx @tobilu/qmd embed

# 2. Start MCP daemon  
npx @tobilu/qmd mcp --http --daemon

# 3. Test search
npx @tobilu/qmd query "model routing" -n 5
```

### OpenClaw Config (Optional)

If we want native QMD integration in OpenClaw:
```json
{
  "memory": {
    "backend": "qmd"
  }
}
```

But we can also just query via exec when needed.

---

## What HiveMind Does Better (Keep)

1. **Agent scope filtering** - QMD has no concept of agent identity
2. **Redaction** - Critical for security; QMD indexes everything
3. **TTL/Expiry** - QMD has no time-based cleanup
4. **Contradiction detection** - Unique to HiveMind Phase 3

## What QMD Does Better (Adopt)

1. **Search quality** - BM25 + vectors + reranking is superior
2. **Performance** - Local GGUF models, Metal GPU acceleration
3. **Production-ready** - Active development, MCP built-in
4. **Context trees** - QMD's context feature helps LLM selection

---

## Recommended Workflow

1. **Every query** → QMD for fast workspace search
2. **Scope-relevant** → HiveMind for agent-specific filtering
3. **Periodic** → HiveMind scan-contradictions + digest
4. **On ingestion** → HiveMind redaction → QMD embed

---

## Timeline

- **Day 1**: Index workspace with QMD, start MCP daemon
- **Day 2**: Update agent to query QMD automatically
- **Day 3**: Wire HiveMind contradiction scanning
- **Ongoing**: Refine context trees, monitor performance

---

## Status: WAITING ON USER

Need Jeebs to run the Phase 1 commands to index the workspace.
