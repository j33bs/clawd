# task-triage

Classifies a task into `LOCAL`, `REMOTE`, or `HUMAN` with a multi-stage prepass:

- Stage 0: deterministic prefilter (regex/size/metadata)
- Stage 1: optional sentinel handoff input (`local_sentinel_result`)
- Stage 2: deterministic evidence bundle selector (`topk_stub`)

This skill does decisioning and audit only. It does **not** call remote APIs.

## Config
- `config/decision_rules.json` stores all routing thresholds, prefilter rules, sentinel threshold, and evidence selector parameters.
- `config/classifier_prompt.md` is used by the agent when calling `mlx-infer`.

## Budgets
- Task/context caps are enforced via `config.prefilter.max_task_chars` and `config.prefilter.max_context_chars`.
- Excerpts are deterministically truncated by these caps and optional `sentinel.max_excerpt_chars`.
- Truncation emits `TRUNCATED` flags in output.

## Example calls

Process with default prefilter + evidence bundle:
```bash
printf '%s\n' '{"task":"Design governance hardening","context":"repo policy update"}' \
  | node {baseDir}/dist/cli.js
```

Process with caller-supplied sentinel signal:
```bash
printf '%s\n' '{"task":"Investigate architecture", "context":"large context", "local_sentinel_result":{"tier_suggestion":"REMOTE","confidence":0.82,"rationale":"multi-service impact","labels":["ARCH"]}}' \
  | node {baseDir}/dist/cli.js
```

Drop trivial input:
```bash
printf '%s\n' '{"task":"ping","context":""}' | node {baseDir}/dist/cli.js
```

## Output
```json
{
  "action": "PROCESS",
  "tier": "REMOTE",
  "confidence": 0.82,
  "rationale": "...",
  "flags": [],
  "evidence_bundle": {
    "kind": "topk_stub",
    "top_k": 5,
    "selected": [{"id":"chunk-0","start":0,"end":120,"score":3}],
    "notes": "deterministic token-overlap selector"
  }
}
```

For dropped items, output uses `action: "DROP"` and omits `tier`.
When OpenAI mediation is implicated, output includes `request_for_chatgpt` for human handoff.
