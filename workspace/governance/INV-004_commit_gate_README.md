# INV-004 Commit Gate Tooling

Use `workspace/tools/commit_gate.py` to execute INV-004 gate checks with append-only evidence.

## Run

```bash
python3 workspace/tools/commit_gate.py inv004 \
  --run-id dryrun-001 \
  --mode dry \
  --theta 0.15 \
  --embedder sentence-transformers/all-MiniLM-L6-v2 \
  --inputs workspace/artifacts/inv004/dry_run \
  --isolation-verified true \
  --isolation-evidence "separate sessions, no cross-paste before meet"
```

Set `--mode enforce` to make gate failure block progression via non-zero exit (`2`).

## PASS Criteria

A run is PASS only if all are true:

1. `min(dist(joint,dali), dist(joint,clawd)) >= theta`
2. Joint output includes `[JOINT: c_lawd + dali]`
3. Isolation evidence note is provided
4. In `enforce` mode, `--isolation-verified true`

Each run writes:

- Artifacts: `workspace/artifacts/inv004/<run-id>/`
- Audit note: `workspace/audit/inv004_<run-id>_<timestamp>.md`
