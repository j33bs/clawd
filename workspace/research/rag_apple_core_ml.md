# RAG + Apple Core ML Research Notes

*Initial research — 2026-02-23*

---

## The Goal

Implement RAG (Retrieval-Augmented Generation) using Apple Core ML for on-device, private inference.

- Data stays local (privacy)
- Uses Apple Silicon (fast, efficient)
- Works offline

---

## Key Technologies

### Core ML
- Apple's on-device ML framework
- Runs .mlmodel files on iPhone/Mac
- Optimized for Apple Silicon (Neural Engine)

### sentence-transformers (via Core ML)
- Models like `all-MiniLM-L6-v2` convert text → embeddings
- Can be converted to Core ML format

### Local Vector Databases
- **Chroma** — Python-native, easy to use
- **llama.cpp** — Can run locally with GGUF models
- **FAISS** — Facebook's fast similarity search
- **Annoy** — Approximate Nearest Neighbors

---

## Approaches

### Approach 1: Full Apple Core ML Stack
1. Convert transformer model → Core ML (using `coremltools`)
2. Run inference locally on Apple Silicon
3. Store embeddings in local vector DB
4. Retrieve → inject into LLM context

### Approach 2: Hybrid (More Practical)
1. Use existing Mac-native embedding models (via Python)
2. Local vector DB (Chroma/FAISS)
3. LLM runs via Ollama (local) or external API
4. RAG prompt assembled locally

### Approach 3: On-Device iOS
1. Core ML model on iPhone
2. Local SQLite for vectors (or Chroma)
3. Small LLM via Apple's on-device models
4. Fully offline iPhone AI assistant

---

## Useful Libraries

```python
# Embedding models that work on Mac
from sentence_transformers import SentenceTransformer

# Convert to Core ML
import coremltools as ct

# Local vector DB
import chromadb

# Or for iOS
from CoreML import MLPackedWordEmbedding
```

---

## Models to Consider

| Model | Size | Quality | Core ML? |
|-------|------|---------|----------|
| all-MiniLM-L6-v2 | 80MB | Good | Yes (convert) |
| all-mpnet-base-v2 | 420MB | Great | Yes (convert) |
| sentence-t5-base | 300MB | Best | Possible |
| Apple Neural Hash | N/A | For iOS | Native |

---

## CBP (Assuming "Conversational Best Practices" / Custom)

For RAG protocols, apply CBP principles:
- **Chunking**: Split documents into meaningful units (paragraphs, sections)
- **Context window**: Fit retrieved chunks + query into LLM context
- **Ranking**: Re-rank retrieved results by relevance
- **Freshness**: Keep vector DB updated when source docs change

---

## Research Queue Topics

- [x] RAG + Apple Core ML on-device
- [ ] Core ML model conversion pipeline
- [ ] Local vector DB on Apple Silicon
- [ ] Privacy-preserving RAG
- [ ] Integration with this workspace (QMD replacement?)

---

*To be continued...*
