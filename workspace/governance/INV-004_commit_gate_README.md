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
3. In `enforce` mode, `--isolation-verified true`
4. In `enforce` mode, `--isolation-evidence` is non-empty
5. Embedder loads offline when required

Each run writes:

- Artifacts: `workspace/artifacts/inv004/<run-id>/`
- Audit note: `workspace/audit/inv004_<run-id>_<timestamp>.md`

## Calibration

Compute baseline distance buckets with the same embedder used by gating:

```bash
python3 workspace/tools/commit_gate.py inv004-calibrate \
  --inputs workspace/artifacts/inv004/dry_run \
  --embedder sentence-transformers/all-MiniLM-L6-v2 \
  --out workspace/artifacts/inv004/calibration/run-001/baseline.json \
  --require-offline-model true
```

`baseline.json` includes:

- `within_agent_rewrite_dist` (deterministic rewrite proxy)
- `trivial_concat_dist` (naive dali+clawd concatenation)
- `true_joint_dist` (if `joint_output.md` exists)
- `p50/p90/p95/p99` stats for each bucket
- `recommended_theta = p95(within_agent_rewrite_dist)`

## Offline Model Requirement

- `enforce` mode always requires offline-local model availability (`HF_HUB_OFFLINE=1`, `local_files_only=True`).
- If the model is unavailable offline, the gate FAILs with a clear "offline model not available" reason.
- `dry` mode can also require offline via `--require-offline-model true`; failures still write audit evidence.

## Sanitization (Anti-Goodhart)

Before embedding, input text is sanitized to strip governance tags and status strings:

- `[EXEC:*]`, `[JOINT:*]`
- Leading `[UPPER:...]` tokens
- `EXPERIMENT PENDING`, `GOVERNANCE RULE CANDIDATE`, `PHILOSOPHICAL ONLY`

Rationale: this prevents novelty scoring from being gamed by tag tokens instead of semantic content.

Audit notes record:

- `embedding_input_sanitized: true`
- `sanitizer_rules_version`
- runtime identity (`python`, `platform`, `sentence-transformers`, `transformers`, `torch`, embedder id)
