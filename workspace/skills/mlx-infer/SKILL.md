---
name: mlx-infer
description: Local MLX inference via mlx-lm
metadata:
  openclaw:
    requires:
      bins: ["python3", "node"]
    os: ["darwin"]
---

Use this skill for local inference only.

## Invocation
Run via exec:

```bash
node {baseDir}/dist/cli.js --prompt "..." --model "..." --max_tokens 200 --temperature 0.1
```

Input contract:
```json
{ "prompt": "...", "model": "...", "max_tokens": 200, "temperature": 0.1 }
```

Output contract:
```json
{ "completion": "...", "latency_ms": 123, "tokens_used": 456 }
```

Schemas:
- `{baseDir}/schemas/input.schema.json`
- `{baseDir}/schemas/output.schema.json`

Notes:
- This skill never calls OpenAI APIs.
- Python worker handles MLX execution and returns strict JSON.
