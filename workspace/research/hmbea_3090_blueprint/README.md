# HMBEA 3090 Blueprint Integration

## Source
- Downloaded: 2026-03-16
- File: `hmbea_3090_blueprint.zip`
- Location: `workspace/research/hmbea_3090_blueprint/`

## Model Stack (Qwen-based)

| Role | Model | Quant | Notes |
|------|-------|-------|-------|
| Controller | qwen3-14b | Q4_K_M | Primary generalist |
| Coder | devstral-small-2 | Q4_K_M | SWE specialist |
| Critic | phi-4-mini-flash-reasoning | Q4_K_M | Fast triage |
| Embeddings | qwen3-embedding-0.6b | - | Retrieval |
| Reranker | qwen3-reranker-0.6b | - | Context ranking |

## Architecture

```
user task → intake → retrieve → route → execute → validate → gate → finalize
```

## Policies

### Escalation Thresholds
- **Accept**: critic_score >= 0.80, groundedness >= 0.75
- **Retry**: 0.55 <= critic_score < 0.80 (max 1 retry)
- **Escalate**: critic_score < 0.55 or tool errors >= 2

### Approval Required
- file_write, shell_exec, git_commit, web_access

### Security
- Least privilege
- Sandbox for untrusted exec
- Secret redaction in traces

## Integration with HMBEA

This blueprint provides the orchestration layer for:
1. **Role-based routing** - specialist selection
2. **Shadow apprenticeship** - SLM can shadow Codex outputs
3. **Progressive offload** - simple tasks to SLM, hard to FM
4. **3090-compatible** - single GPU, hot-swappable models

## Files

- `configs/model_registry.yaml` - model stack
- `policies/escalation_policy.yaml` - thresholds
- `policies/tool_policy.yaml` - tool permissions
- `src/hmbea/graph.py` - LangGraph orchestration
- `docs/` - audit, governance, benchmarks
