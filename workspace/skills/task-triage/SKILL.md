---
name: task-triage
description: Classify tasks into LOCAL, REMOTE, or HUMAN
metadata:
  openclaw:
    requires:
      bins: ["node"]
---

Use this skill to convert local model suggestions into final triage decisions.

## Agent procedure
1. Read `{baseDir}/config/classifier_prompt.md`.
2. Call `mlx-infer` via tool surface (do not import internals) with:
   - prompt rendered from template with task/context
   - low temperature (e.g. `0.1`)
   - small max tokens (e.g. `300`)
3. Pipe result into:

```bash
node {baseDir}/dist/cli.js
```

Input JSON:
```json
{ "task": "...", "context": "...", "local": { "tier_suggestion": "LOCAL", "confidence": 0.8, "rationale": "..." } }
```

Output JSON:
```json
{ "tier": "LOCAL|REMOTE|HUMAN", "confidence": 0.8, "rationale": "...", "request_for_chatgpt": { "task": "...", "context": "...", "why": "...", "expected_output": "..." } }
```

Schemas:
- `{baseDir}/schemas/input.schema.json`
- `{baseDir}/schemas/output.schema.json`
