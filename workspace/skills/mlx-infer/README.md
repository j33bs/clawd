# mlx-infer

Local inference skill backed by `mlx-lm` through a Node wrapper that spawns Python.

## Prerequisites
- `python3`
- `node`
- `mlx-lm` installed in the Python environment used by `python3`:
  - `pip install mlx-lm`

## Config
Optional JSON config via `OPENCLAW_SKILL_CONFIG` or `--config`:

```json
{
  "model_path": "./models",
  "default_model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
  "max_concurrent": 1
}
```

## Example tool calls
```bash
node {baseDir}/dist/cli.js --prompt "Summarize this patch" --max_tokens 200
node {baseDir}/dist/cli.js --prompt "Classify this task" --temperature 0.1
```

## Known limitations
- Token count may be estimated when tokenizer token usage is unavailable.
- Initial model load can dominate latency for cold starts.
