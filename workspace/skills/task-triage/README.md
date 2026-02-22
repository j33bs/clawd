# task-triage

Classifies a task into `LOCAL`, `REMOTE`, or `HUMAN`.

This skill does decisioning and audit only. It does **not** call remote APIs.

## Stage Pipeline
- Stage 0/1 output handling is consumed from caller input (`task`, `context`, local suggestion signals).
- Stage 2 evidence bundling is config-driven:
  - preferred strategy: `coreml_embed`
  - deterministic fallback: `keyword_stub`
- Output always includes `action` (`PROCESS` or `DROP`). Current default behavior is `PROCESS`.

## Config
- `config/decision_rules.json` stores thresholds/signals/overrides.
- `config/classifier_prompt.md` is used by the agent when calling `mlx-infer`.
- Evidence selector settings are under `decision_rules.json.evidence`.
  - `evidence.coreml.model_path` must be set to enable Core ML embedding selection.
  - If Core ML is unavailable or health check fails, selector falls back to keyword stub.
  - Context is truncated deterministically using `max_context_chars_for_evidence`.

## Example flow
1. Ask `mlx-infer` to classify using `config/classifier_prompt.md`.
2. Feed the local suggestion into this skill:

```bash
printf '%s\n' '{"task":"Design governance hardening","context":"repo policy update","local":{"tier_suggestion":"REMOTE","confidence":0.62,"rationale":"complex architecture"}}' \
  | node {baseDir}/dist/cli.js
```

## Output
```json
{
  "action": "PROCESS",
  "tier": "REMOTE",
  "confidence": 0.62,
  "rationale": "...",
  "evidence_bundle": {
    "kind": "keyword_stub",
    "top_k": 5,
    "selected": [],
    "notes": "keyword overlap fallback selector",
    "stats": {
      "chunks_total": 0,
      "chunks_used": 0,
      "truncated": false,
      "latency_ms": 0,
      "strategy_attempts": []
    }
  }
}
```

When OpenAI mediation is implicated, output includes `request_for_chatgpt` for human handoff.
