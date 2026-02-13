# System-1 vLLM (Local Inference)

## Prerequisites

* vLLM requires Linux + CUDA GPU (compute capability >= 7.0).
* On Windows, run vLLM via Docker Desktop (WSL2 backend) or inside WSL2.

## Start / Stop

Docker Compose (recommended if available):

```powershell
# Required: set a model id/path
$env:VLLM_MODEL = "<your-model>"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\vllm_start.ps1 -Port 8000
```

Stop:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\vllm_stop.ps1
```

## Health Check

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\vllm_health.ps1 -Port 8000
```

Exit codes:

* `0` OK
* `2` Not healthy (no listener or unexpected response)
* `1` Script error

## GPU Memory + Context Sizing Knobs

When using Docker Compose, set:

* `VLLM_GPU_MEMORY_UTILIZATION` (default `0.90`)
* `VLLM_MAX_MODEL_LEN` (default `8192`)

Start with a conservative context length and increase only after confirming stability.

## OpenClaw Integration (Local-First)

This repo uses a wrapper runner to keep tracked intent catalogs stable and route discovery into an untracked observed cache:

* `scripts/run_gateway_intent_observed.ps1`

This runner sets:

* `ENABLE_LOCAL_VLLM=1` (unless `-DisableLocalVllm` is passed)
* `OPENCLAW_VLLM_BASE_URL=http://127.0.0.1:8000/v1` (unless already set)

## Rollback

* Stop vLLM: `scripts/vllm_stop.ps1`
* Run gateway without vLLM env:
  * pass `-DisableLocalVllm` to `scripts/run_gateway_intent_observed.ps1`
* Revert policy changes in `workspace/policy/llm_policy.json` if needed.
