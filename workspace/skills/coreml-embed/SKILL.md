---
name: coreml-embed
description: Local Core ML embedding primitive via repo-local Swift runner
metadata:
  openclaw:
    requires:
      bins: ["node", "bash", "swift"]
    os: ["darwin"]
---

Use this skill for bounded local embedding generation only.

## Invocation
Health:
```bash
node {baseDir}/dist/cli.js --health --model_path /path/to/model.mlpackage
```

Inference:
```bash
printf '%s\n' '{"model_path":"/path/to/model.mlpackage","texts":["example"]}' | node {baseDir}/dist/cli.js
```

Input contract:
```json
{
  "model_path": "string",
  "texts": ["string"],
  "max_text_chars": 4000,
  "compute_units": "ALL|CPU_ONLY|CPU_AND_GPU|CPU_AND_NE",
  "dry_run": false
}
```

Output contract:
```json
{
  "model_path": "string",
  "dims": 768,
  "embeddings": [[0.1, 0.2]],
  "latency_ms": 123
}
```

Schemas:
- `{baseDir}/schemas/input.schema.json`
- `{baseDir}/schemas/output.schema.json`
