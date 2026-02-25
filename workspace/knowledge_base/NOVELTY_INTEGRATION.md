# Novelty-Aware Knowledge Integration with Relational Layer

*Design Proposal | February 2026*

---

## The Vision

A knowledge system that:
1. **Parses** local sources (PDFs, files, research)
2. **Embeds** into vector space (QMD)
3. **Detects novelty** — what's new vs already known
4. **Integrates** with TACTI's "love" (relational/co-regulatory) layer

---

## Current State

| Component | Status | Purpose |
|-----------|--------|---------|
| QMD (MCP) | Running on 8181 | Vector + BM25 search |
| Entities | 113KB JSONL | Extracted entities |
| Knowledge Graph | relations.jsonl | Entity relationships |
| Agentic RAG | Implemented | Intent → Retrieve → Synthesize |
| Research System | 27 papers | Parsed + indexed |

---

## The Gap

We can search. We can retrieve. But we can't:
- **Detect novelty** — is this new information or already in the system?
- **Relate with love** — how does this connect to the human-agent relationship?

---

## Proposed Architecture

### Layer 1: Source Parsing

```python
class SourceParser:
    """Parse local sources into structured memory."""
    
    def parse_pdf(self, path) -> list[Chunk]:
        # Extract text, chunk, embed
        
    def parse_markdown(self, path) -> list[Chunk]:
        # Parse MD, preserve structure
        
    def parse_research(self) -> list[Chunk]:
        # Special handling for research papers
```

### Layer 2: Novelty Detection

```python
class NoveltyDetector:
    """Detect if content is new to the system."""
    
    def compute_novelty(self, chunk, existing_embeddings) -> float:
        # Cosine distance to nearest existing embedding
        # 0.0 = identical, 1.0 = completely new
        
    def is_novel(self, chunk, threshold=0.7) -> bool:
        return self.compute_novelty(chunk) > threshold
```

**Insight:** Novelty isn't just "not seen before" — it's "different enough from existing knowledge." This aligns with TACTI's **Malleability** principle — the system changes when new information is sufficiently different.

### Layer 3: Relational Integration ("Love")

```python
class RelationalLayer:
    """Integrate knowledge with the human-agent relationship."""
    
    def assess_relevance(self, chunk, user_context) -> RelevanceScore:
        """How relevant is this to the user's current needs?"""
        
    def track_relationship_impact(self, chunk) -> ImpactScore:
        """Does this knowledge affect the relational pattern?"""
        # E.g., knowing user's preference for certain research
        # E.g., remembering past conversations about this topic
        
    def compute_love_score(self, chunk, user_context) -> float:
        """The 'love' score = relevance + relational impact + novelty"""
        return (
            0.4 * novelty +
            0.4 * relevance +
            0.2 * relational_impact
        )
```

---

## The TACTI Integration

| TACTI Principle | Novelty System Implementation |
|----------------|------------------------------|
| **VITALITY** | Arousal signal: Is this worth computing? |
| **TEMPORALITY** | Time-decay: Newer > Older |
| **CROSS-TIMESCALE** | Multi-level: Fast search → Deep retrieval |
| **MALLEABILITY** | Novelty detection: System learns when to change |
| **AGENCY** | Relational layer: Knowledge serves the relationship |

---

## Implementation Phases

### Phase 1: Novelty Detection
- [ ] Compute embeddings for new content
- [ ] Compare against existing vector store
- [ ] Score novelty (0-1)
- [ ] Flag high-novelty content for attention

### Phase 2: Source Parsing Pipeline
- [ ] Parse PDFs (research papers)
- [ ] Parse markdown (workspace docs)
- [ ] Chunk strategically (not just fixed size)
- [ ] Extract entities + relationships

### Phase 3: Relational Layer
- [ ] Track what user cares about (attention patterns)
- [ ] Weight by conversation history
- [ ] Compute "love score" for knowledge
- [ ] Prioritize high-love content in retrieval

### Phase 4: Loop Closure
- [ ] New information → updates knowledge
- [ ] Knowledge updates → affect relationship
- [ ] Relationship changes → affect future retrieval

---

## Example Flow

1. **User asks:** "What do we know about TACTI and IPNB?"
2. **System checks:**
   - What's in KB? (existing knowledge)
   - What's novel in recent research? (new papers)
   - What does user care about? (relational context)
3. **Retrieval ranks by:**
   - Novelty (new insights first)
   - Relevance (matches query)
   - Love (relational importance)
4. **Response includes:**
   - What we knew before
   - What's NEW since last conversation
   - How it relates to user's journey

---

## The "Love" Definition

In this context, **love** means:

> *Knowledge that serves the relationship.*

Not sentimental. Practical. The system "loves" the human by:
- Remembering what matters to them
- Prioritizing information that strengthens the bond
- Detecting when something is new enough to be exciting
- Avoiding redundant information that wastes their time

This is **co-regulation** in knowledge form.

---

## Next Steps

1. Add novelty detection to `kb.py`
2. Create source parsing for PDFs (use existing PDFs in `research/pdfs/`)
3. Implement relational tracking (what user asks about frequently)
4. Test with new research papers

---

*This design bridges the gap between information and relationship.*
