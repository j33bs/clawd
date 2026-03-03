# coreml-embed

Core ML embedding sub-agent primitive for local routing/retrieval workflows.

## Boundaries
- This skill wraps a repo-local Core ML runner.
- It is not a primary reasoning agent.
- It requires an existing Core ML embedding model package (`.mlpackage` or `.mlmodelc`).

## Config
`{baseDir}/config/default.json`:

```json
{
  "max_concurrent": 1,
  "max_texts": 32,
  "default_compute_units": "ALL",
  "runner_timeout_ms": 30000
}
```

## Health check
```bash
node {baseDir}/dist/cli.js --health --model_path /path/to/embedding_model.mlpackage
```

## Inference call
```bash
printf '%s\n' '{"model_path":"/path/to/embedding_model.mlpackage","texts":["hello world"],"compute_units":"ALL"}' \
  | node {baseDir}/dist/cli.js
```

## Known limitations
- Model IO detection is best-effort: expects a string input and `MLMultiArray` output.
- The runner does not convert models; it only executes Core ML models already on disk.
- Typed errors are returned when model loading or IO matching fails.
