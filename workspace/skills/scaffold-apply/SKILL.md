---
name: scaffold-apply
description: Apply structured scaffold plans with atomic git commits
metadata:
  openclaw:
    requires:
      bins: ["node", "git"]
---

This skill applies local plan steps to a target git repo.

Run:
```bash
node {baseDir}/dist/cli.js < plan.json
```

Dry-run example input:
```json
{
  "dry_run": true,
  "target_dir": ".",
  "plan": [
    {
      "file": "docs/example.md",
      "operation": "create",
      "content": "# Example\n",
      "rationale": "seed docs"
    }
  ]
}
```

Notes:
- Runs inside specified repo only.
- One commit per successful step.
- Failures stop execution; no rollback of earlier commits.

Schemas:
- `{baseDir}/schemas/input.schema.json`
- `{baseDir}/schemas/output.schema.json`
