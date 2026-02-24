# Research Wanderer -> OPEN_QUESTIONS Evidence (20260223T005754Z)

## Commands
- python3 workspace/scripts/research_wanderer.py --input /tmp/research_wanderer_sample.json --run-id rw-demo --dry-run --json
- python3 workspace/scripts/research_wanderer.py --input /tmp/research_wanderer_sample.json --run-id rw-demo --json
- sed -n '1,160p' workspace/OPEN_QUESTIONS.md

## Outputs
```text
{
  "append_preview": "\n## Research Wanderer Session 2026-02-23T00:56:33Z (run_id=rw-demo, commit=fc904b4)\n1. How does reservoir confidence influence long-horizon routing? [significance=0.920]\n2. What token [REDACTED_TOKEN] appears in logs? [significance=0.880]\n",
  "commit_sha": "fc904b4",
  "run_id": "rw-demo",
  "selected_count": 2,
  "status": "dry_run",
  "target_path": "workspace/OPEN_QUESTIONS.md",
  "threshold": 0.8
}
---
{
  "append_preview": "\n## Research Wanderer Session 2026-02-23T00:56:33Z (run_id=rw-demo, commit=fc904b4)\n1. How does reservoir confidence influence long-horizon routing? [significance=0.920]\n2. What token [REDACTED_TOKEN] appears in logs? [significance=0.880]\n",
  "commit_sha": "fc904b4",
  "run_id": "rw-demo",
  "selected_count": 2,
  "status": "appended",
  "target_path": "workspace/OPEN_QUESTIONS.md",
  "threshold": 0.8
}
--- OPEN_QUESTIONS.md ---
# Open Questions

This document is append-only. Additions only; no edits to prior content.

## Research Wanderer Session 2026-02-23T00:56:33Z (run_id=rw-demo, commit=fc904b4)
1. How does reservoir confidence influence long-horizon routing? [significance=0.920]
2. What token [REDACTED_TOKEN] appears in logs? [significance=0.880]
```
