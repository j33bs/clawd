# coreml_embed_runner

Repo-local Swift CLI for Core ML embedding inference.

## Contract
- Reads JSON request from stdin for inference mode.
- Writes one JSON response to stdout.
- Typed failures are emitted as `{ "ok": false, "error": { ... } }`.

## Build
```bash
bash workspace/runners/coreml_embed_runner/build.sh
```

## Run
```bash
printf '%s\n' '{"model_path":"/path/to/model.mlpackage","texts":["hello"],"max_text_chars":4000,"compute_units":"ALL"}' \
  | bash workspace/runners/coreml_embed_runner/run.sh --json
```

## Health
```bash
bash workspace/runners/coreml_embed_runner/run.sh --health --model_path /path/to/model.mlpackage
```

## Limitations
- Requires a Core ML model that accepts string input and emits `MLMultiArray` embeddings.
- Model conversion/packaging is out of scope; this runner only executes existing Core ML models.
