# MLX Integration Audit Report
## Scalable Matrix Extensions for Local AI on Apple Silicon

*Date: 2026-02-21*
*Auditor: C_Lawd (Autonomous)*

---

## Executive Summary

This report audits the current system architecture to identify necessary components for integrating MLX (Apple's machine learning framework) as a local inference and fine-tuning platform. The goal is to leverage Apple Silicon's Neural Engine for local model inference, reducing API costs and enabling parallel processing.

**Key Finding:** The system already has local inference infrastructure (Ollama) but lacks deep integration with Apple Silicon's ML capabilities. MLX-LM is now installed and ready.

---

## 1. Current Architecture

### 1.1 Model Providers

| Provider | Status | Endpoint | Models |
|----------|--------|----------|--------|
| `minimax-portal` | Active | api.minimax.io | M2.1, M2.5 |
| `qwen-portal` | Active | portal.qwen.ai | Coder, Vision |
| `ollama` | Running | 127.0.0.1:11434 | qwen2.5:0.5b, qwen2.5-coder:7b |
| `groq` | Configured | api.groq.com | Llama 3.3 70B |

### 1.2 Current Routing

Primary model: `minimax-portal/MiniMax-M2.5`
Fallback chain includes Ollama as last resort.

### 1.3 System Components

```
User Message → Telegram → OpenClaw Gateway → Model Router → Provider
                                           ↓
                                    [TACTI Modules]
                                          ↓
                    Novelty | Relationship | Arousal | Pattern
```

---

## 2. Available ML Resources

### 2.1 Apple Silicon Hardware

- **Chip:** Apple Silicon (arm64)
- **Neural Engine:** Available (dedicated ML accelerator)
- **Unified Memory:** 24GB RAM (shared CPU/GPU)
- **GPU:** Integrated Apple GPU

### 2.2 Installed ML Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| MLX | 0.30.5 | Core array library |
| MLX-LM | 0.30.7 | LLM inference & LoRA |
| Transformers | 5.2.0 | HuggingFace compat |

### 2.3 MLX-LM Capabilities

- **generate:** Text generation from prompts
- **lora:** Fine-tune models with LoRA adapters
- **server:** Run as API server
- **chat:** Interactive chat
- **fuse:** Merge adapters

---

## 3. Integration Requirements

### 3.1 Files to Modify

| File | Purpose | Modification |
|------|---------|--------------|
| `~/.openclaw/openclaw.json` | Model config | Add MLX provider |
| `workspace/tacti_cr/config.py` | TACTI config | Add MLX routing rules |
| (New) `workspace/mlx_provider.py` | MLX wrapper | Create inference client |
| (New) `workspace/local_router.py` | Smart routing | Route simple queries to local |

### 3.2 New Components Needed

1. **MLX Model Provider** - Wrap mlx_lm for OpenClaw compatibility
2. **Local Routing Logic** - Decide when to use local vs remote
3. **LoRA Training Pipeline** - Fine-tune adapters for TACTI tasks
4. **Model Management** - Download/cache MLX models

---

## 4. Proposed Architecture

### 4.1 Three-Tier Model System

```
Tier 1 (Fast/Local):  MLX + Ollama  →  Simple queries, confirmations
Tier 2 (Smart/Remote): MiniMax M2.5  →  Complex reasoning, creative
Tier 3 (Specialized): LoRA Adapters →  TACTI-specific tasks
```

### 4.2 Routing Rules

| Query Type | Route | Rationale |
|------------|-------|-----------|
| Simple factual | MLX | Fast, free |
| Confirmation | MLX | Fast, free |
| Code review | Ollama (7B) | Local coder |
| Complex reasoning | MiniMax | Best reasoning |
| TACTI task | MiniMax + LoRA | Specialized |
| Background processing | MLX | Non-blocking |

### 4.3 Parallel Processing

- Main agent handles user conversation
- MLX processes in background:
  - Pattern detection
  - Relationship health checks
  - Novelty scoring
  - Memory consolidation

---

## 5. Implementation Phases

### Phase 1: Local Inference (Week 1)
- [ ] Add MLX provider to openclaw.json
- [ ] Create mlx_provider.py wrapper
- [ ] Test basic inference
- [ ] Add simple routing rules

### Phase 2: Smart Routing (Week 2)
- [ ] Implement complexity classifier
- [ ] Add routing logic to message handler
- [ ] Configure fallback chain
- [ ] Test latency improvements

### Phase 3: LoRA Fine-tuning (Week 3)
- [ ] Create training dataset (TACTI interactions)
- [ ] Fine-tune adapter for relationship detection
- [ ] Fine-tune adapter for arousal detection
- [ ] Integrate into pipeline

### Phase 4: Parallel Processing (Week 4)
- [ ] Background MLX workers
- [ ] Memory consolidation
- [ ] Pattern detection automation

---

## 6. Files for Analysis

The following files are packaged for analysis:

### Configuration Files
- `~/.openclaw/openclaw.json` - Current model config
- `docs/system1/ROUTING_POLICY.md` - Routing rules

### TACTI Modules
- `workspace/tacti_cr/config.py` - TACTI configuration
- `workspace/tacti_cr/arousal.py` - Arousal detection
- `workspace/tacti_cr/collapse.py` - Collapse detection

### Research & Integration
- `workspace/research/TACTI_framework_integration.md` - TACTI docs
- `workspace/TEN_HIGH_LEVERAGE.md` - Implementation priorities
- `MEMORY.md` - System memory

### ML Libraries (Reference)
- `workspace/venv/lib/python*/site-packages/mlx/` (not included)

---

## 7. Recommendations

1. **Start Simple:** Add MLX as a simple provider first, then build routing
2. **LoRA Priority:** Fine-tuning is the biggest win - enables TACTI-specific intelligence
3. **Parallelism:** Use MLX for background tasks while main agent responds
4. **Monitor:** Track latency improvements and cost savings

---

## 8. Next Steps

1. Analyze packaged files for integration points
2. Design MLX provider interface
3. Define routing decision tree
4. Plan LoRA training data collection

---

*This report was generated autonomously. The system is ready for implementation.*
