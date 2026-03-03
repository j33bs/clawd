# Dali Local Exec Model Menu (RTX-3090 24GB)

This menu is for the local execution plane. It is governed by CBP constraints:
- bounded budgets per job
- deny-by-default tools
- deterministic offline fallback when model plane is unavailable

## Coordinator / Router

1) `qwen2.5-7b-instruct` (preferred baseline)
- Role: coordinator, decomposition, strict JSON planning
- Why: reliable instruction following, practical fit on 24GB with long uptime
- vLLM notes:
  - `--served-model-name coordinator-qwen25-7b`
  - `--max-model-len 8192`
  - `--gpu-memory-utilization 0.85`
  - tool parser: `hermes` (if model formatting supports it)

2) `llama-3.1-8b-instruct`
- Role: backup coordinator / high-level summaries
- Why: robust generic assistant behavior
- vLLM notes:
  - `--served-model-name coordinator-llama31-8b`
  - `--max-model-len 8192`
  - tool parser: `llama3_json`

## Specialists

1) `qwen2.5-coder-7b-instruct`
- Role: coder (patch synthesis, refactors)
- vLLM notes:
  - `--served-model-name coder-qwen25-7b`
  - `--max-model-len 8192`
  - tool parser: `hermes`

2) `qwen2.5-14b-instruct-awq` (optional heavy)
- Role: verifier, difficult code review, test triage
- Fit note: may fit with constrained context/kv cache; validate at runtime
- vLLM notes:
  - `--served-model-name verifier-qwen25-14b-awq`
  - `--quantization awq`
  - `--max-model-len 4096-8192` (tune by VRAM pressure)

3) `llama-3.1-8b-instruct`
- Role: doc_compactor (evidence summarization)
- vLLM notes:
  - `--served-model-name doc-llama31-8b`
  - `--max-model-len 8192`

## Optional reasoning-heavy model (conditional)

- `qwen2.5-32b-instruct` (quantized / offloaded only)
- Marked optional: may exceed practical 24GB envelope depending on quantization and context length.

## Common runtime guardrails

- Bind loopback only (`127.0.0.1`)
- Set explicit API port
- `parallel_tool_calls=false`
- deterministic budgets from local_exec job schema
- disable network tools by default in local-exec worker
