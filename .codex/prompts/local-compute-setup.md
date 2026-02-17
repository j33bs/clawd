# /local-compute-setup

Configure and validate System-1 local compute routing (`local_vllm` first, `minimax-portal` fallback) for this repository.

## What to do

1. Ensure `env.d/system1-routing.env` exists with these keys:
- `ENABLE_LOCAL_VLLM`
- `OPENCLAW_VLLM_BASE_URL`
- `FREECOMPUTE_PROVIDER_ALLOWLIST`
- `OPENCLAW_MINIMAX_PORTAL_API_KEY` (placeholder only)

2. Source profile for the current shell and print only non-secret variable names and safe values.

3. Run readiness checks:
- Docker daemon reachable: `docker info`
- GPU visible: `nvidia-smi -L`
- vLLM endpoint reachable: `curl -fsS "$OPENCLAW_VLLM_BASE_URL/models"`

4. Validate routing contract from repo code:
- Use a Node one-liner with `ProviderRegistry` and print:
  - loaded adapters
  - `reg.explain(...)` output for `taskClass=code`

5. Run evidence commands:
- `npm run system2:experiment -- --out .tmp/system1_local_compute_setup --fail-on log_signature_counts.auth_error --no-prompt`
- `npm run system2:snapshot -- --out .tmp/system1_local_compute_snapshot`

6. Finish with:
- readiness result summary
- missing prerequisites (if any)
- exact next command for the operator

## Fallback behavior

If Docker is not running:
- Report: "Docker is not reachable; start Docker and rerun /local-compute-setup."
- Skip vLLM container-specific assumptions.

If NVIDIA GPU is not visible:
- Report: "No NVIDIA GPU detected; local vLLM may be unavailable."
- Continue with MiniMax fallback validation only.

If vLLM endpoint is unreachable:
- Report: "vLLM endpoint not reachable at OPENCLAW_VLLM_BASE_URL."
- Continue by validating `minimax-portal` eligibility and routing explanation.

If `OPENCLAW_MINIMAX_PORTAL_API_KEY` is unset:
- Report: "MiniMax fallback is fail-closed until OPENCLAW_MINIMAX_PORTAL_API_KEY is set."
- Do not request or print the secret value.

## Guardrails

- Never print secret values.
- Never write secret values to tracked files.
- Keep output evidence-first with command results.
