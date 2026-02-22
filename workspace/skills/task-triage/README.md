# task-triage

Classifies a task into `LOCAL`, `REMOTE`, or `HUMAN`.

This skill does decisioning and audit only. It does **not** call remote APIs.

## Config
- `config/decision_rules.json` stores thresholds/signals/overrides.
- `config/classifier_prompt.md` is used by the agent when calling `mlx-infer`.

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
  "tier": "REMOTE",
  "confidence": 0.62,
  "rationale": "..."
}
```

When OpenAI mediation is implicated, output includes `request_for_chatgpt` for human handoff.
