# Local Assistant (Qwen3.5-27B)

## Status
- **Model:** Qwen_Qwen3.5-27B-Q4_K_M.gguf
- **Runtime:** llama.cpp-vulkan
- **Port:** 8001
- **Alias:** local-assistant
- **VRAM:** ~16.5GB (Q4 quantization on 24GB RTX 3090)

## Files

### `task_router.py`
Routes tasks to local model based on capability levels:
- Level 1: Basic Q&A, echo, summarize, classify
- Level 2: Code review, docs, refactor
- Level 3: Complex reasoning, agentic tasks

### `learning_pipeline.py`
Collects interaction samples for future fine-tuning:
- Saves c_lawd responses as training data
- Daily JSONL files in `learning_data/`

## Usage

```bash
# Check status
python3 workspace/local_assistant/task_router.py status

# Test model
python3 workspace/local_assistant/task_router.py test

# Route a task
python3 workspace/local_assistant/task_router.py "Explain what a closure is in JavaScript"
```

## Chain Integration

The local model is wired into OpenClaw via:
- Provider: `vllm` at `http://127.0.0.1:8001/v1`
- Model ID: `local-assistant`
- In fallback chain after: minimax-m2.1 → gpt-mini → grok-fast → local-assistant

## Next Steps

1. Expand capability levels as model demonstrates competence
2. Build training dataset via `learning_pipeline.py`
3. Set up LoRA fine-tuning when samples > 1000
4. Graduate to heavier tasks as confidence grows
