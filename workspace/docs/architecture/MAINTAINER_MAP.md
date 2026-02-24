# Maintainer Map (clawd)

## 1) High-level mental model
- Control plane:
  - Primary anchor: `workspace/scripts/policy_router.py`.
  - Holds routing/governance decisions: intent routing, provider ordering, budget/circuit checks, escalation, and event logging.
- Execution plane:
  - Node inference stack under `core/system2/inference/` and runtime gateway paths.
  - Actual model calls execute here (local vLLM and cloud/provider adapters).
- Data/evidence plane:
  - JSON/JSONL artifacts in `itc/`, `workspace/state/`, `workspace/artifacts/`, and `workspace/audit/`.
  - Router and pipeline behavior is evidenced via append-only logs/artifacts.

Governance lives in `workspace/scripts/policy_router.py`; inference execution primarily lives in `core/system2/inference/` and runtime gateway code.

## 2) Subsystem map

### Policy router (Python)
- Entry points:
  - `PolicyRouter.execute_with_escalation(...)`
  - `PolicyRouter.explain_route(...)`
- Core files/modules:
  - `workspace/scripts/policy_router.py`
  - `workspace/policy/llm_policy.json`
- Responsibilities:
  - Intent-aware provider order resolution.
  - Budget and circuit-breaker enforcement.
  - Escalation/fallback behavior and provider dispatch wrappers.
  - Router event emission (`router_skip`, `router_success`, `router_fail`, etc.).
- Key artifacts:
  - `itc/llm_budget.json`
  - `itc/llm_circuit.json`
  - `itc/llm_router_events.jsonl`
  - `workspace/state/tacti_cr/events.jsonl`
- Interaction with policy router:
  - This subsystem is the policy router.

### System2 inference (Node)
- Entry points:
  - `routeRequest(...)` in `core/system2/inference/router.js`
  - provider dispatch in `core/system2/inference/provider_adapter.js`
- Core files/modules:
  - `core/system2/inference/router.js`
  - `core/system2/inference/provider_adapter.js`
  - `core/system2/inference/catalog.js`
  - `core/system2/inference/local_vllm_provider.js`
  - `core/system2/inference/gpu_guard.js`
  - `core/system2/inference/concurrency_tuner.js`
- Responsibilities:
  - Provider/model candidate scoring and selection.
  - Runtime deflection (GPU pressure guard).
  - Provider-specific payload shaping and outbound execution.
- Key artifacts:
  - Mostly runtime logs; consumes external artifacts/signals rather than owning many durable files.
- Interaction with policy router:
  - Parallel routing path in Node; policy concepts align with Python router but are not a single unified module.

### vLLM integration
- Entry points:
  - `LocalVllmProvider.generateChat(...)`
  - `LocalVllmProvider.generateStream(...)`
  - startup script `scripts/vllm_launch_optimal.sh`
- Core files/modules:
  - `core/system2/inference/local_vllm_provider.js`
  - `scripts/vllm_launch_optimal.sh`
  - `scripts/tune_concurrency.js`
  - `scripts/vllm_prefix_warmup.js`
  - `workspace/scripts/vllm_metrics_sink.py`
- Responsibilities:
  - Local vLLM request execution and stream handling.
  - Startup-time tuning (`--max-num-seqs`) and optional warmup.
  - Metrics extraction for routing feedback.
- Key artifacts:
  - `workspace/state/vllm_metrics.json`
- Interaction with policy router:
  - `policy_router.py` consumes `read_metrics_artifact()` from `workspace/scripts/vllm_metrics_sink.py` for gating/prioritization.

### ITC pipeline
- Entry points:
  - `workspace/itc_pipeline/telegram_reader_telethon.py`
  - `workspace/itc_pipeline/ingestion_boundary.py` (`ingest_message`)
- Core files/modules:
  - `workspace/itc_pipeline/ingestion_boundary.py`
  - `workspace/itc_pipeline/allowlist.py`
  - `workspace/itc/ingest/interfaces.py`
  - `workspace/itc/api.py`
  - `workspace/itc/schema/itc_signal.v1.json`
- Responsibilities:
  - Ingest Telegram/raw messages, apply allowlist + dedupe.
  - Route ITC classification via policy router.
  - Validate and persist normalized ITC signal artifacts.
- Key artifacts:
  - ITC raw/normalized/event outputs under `workspace/artifacts/itc/`
  - dedupe/queue state under `telegram/` and related runtime paths.
- Interaction with policy router:
  - `_forward_to_pipeline(...)` calls `PolicyRouter.execute_with_escalation("itc_classify", ...)`.

### TACTI-CR
- Entry points:
  - Runtime controls in `workspace/scripts/policy_router.py` (`_tacti_runtime_controls`, `tacti_enhance_plan` use)
- Core files/modules:
  - `workspace/tacti_cr/*`
  - `workspace/hivemind/hivemind/integrations/main_flow_hook.py`
- Responsibilities:
  - Arousal/valence style control signals.
  - Optional token-pressure and ordering bias influences.
  - Event emission for explainability.
- Key artifacts:
  - `workspace/state/tacti_cr/events.jsonl`
  - `workspace/state/active_inference_state.json`
- Interaction with policy router:
  - Router reads TACTI signals and applies optional caps/biases (fail-open when unavailable).

### HiveMind / reservoir
- Entry points:
  - `Reservoir.readout(...)` in `workspace/hivemind/hivemind/reservoir.py`
  - `tacti_enhance_plan(...)` in `workspace/hivemind/hivemind/integrations/main_flow_hook.py`
- Core files/modules:
  - `workspace/hivemind/hivemind/reservoir.py`
  - `workspace/hivemind/hivemind/integrations/main_flow_hook.py`
- Responsibilities:
  - Generate routing hints and consult-order style dynamics.
- Key artifacts:
  - `workspace/hivemind/hivemind/data/tacti_dynamics_snapshot.json`
- Interaction with policy router:
  - Router uses readout hints to reorder candidates (urgency/risk_off paths).

### Source UI
- Entry points:
  - HTTP server in `workspace/source-ui/app.py`
  - SSE endpoint: `/events`
- Core files/modules:
  - `workspace/source-ui/app.py`
  - `workspace/source-ui/static/*`
- Responsibilities:
  - Operator-facing APIs and dashboard views.
  - Stream router and GPU/metrics ticks to UI consumers.
- Key artifacts:
  - Reads `itc/llm_router_events.jsonl`
  - Reads `workspace/state/vllm_metrics.json`
- Interaction with policy router:
  - Indirect, read-only via artifacts/events.

### Runtime overlay / rebuild scripts
- Entry points:
  - `workspace/scripts/rebuild_runtime_openclaw.sh`
- Core files/modules:
  - `workspace/scripts/rebuild_runtime_openclaw.sh`
  - `.runtime/openclaw/` (generated/mirrored runtime tree)
  - `.runtime/openclaw-dist/` (generated staging/runtime files)
- Responsibilities:
  - Ensure service runtime uses expected artifact set and runtime patches.
  - Bridge local repo work and live gateway runtime execution context.
- Key artifacts:
  - `.runtime/openclaw/*` and `.runtime/openclaw-dist/*` (runtime artifacts)
- Interaction with policy router:
  - Operational path only; controls which router/provider code is actually active at runtime.

## 3) Call-flow sketch
- Inbound request enters via CLI/gateway/Telegram path:
  - Telegram ingestion path (ITC): `workspace/itc_pipeline/telegram_reader_telethon.py` -> `ingestion_boundary.py`.
  - Gateway runtime provider path: Needs inspection in packaged runtime for exact top-level ingress module.
- Policy routing:
  - `PolicyRouter.execute_with_escalation(...)` computes provider order and applies governance gates.
  - Dynamic influences include policy, budgets, circuit state, metrics/artifacts, ITC signals, TACTI/HiveMind hints.
- Provider selection + outbound execution:
  - Python wrappers (`_call_openai_compatible`, `_call_anthropic`, `_call_ollama`) or Node provider adapters execute request.
  - Local execution path targets vLLM endpoints; cloud path targets provider APIs.
- Artifact/event writes:
  - Router emits events to `itc/llm_router_events.jsonl`.
  - ITC pipeline persists validated raw/normalized artifacts under `workspace/artifacts/itc/`.
  - Audit/evidence is appended under `workspace/audit/`.

## 4) Invariants and design patterns
- Fail-open gates:
  - Missing/stale optional artifacts (metrics/hints/signals) generally do not halt routing.
  - Optional integrations are wrapped with guards and default behavior preserved.
- Fail-closed gates:
  - Payload safety/capability constraints at final dispatch boundaries (tool payload constraints, provider capability restrictions).
- Artifact-first evidence logging:
  - Events and outcomes are captured in JSON/JSONL for traceability and auditability.
- Routing as governance:
  - Router enforces budgets, policy, and escalation semantics, not just target selection.
- Runtime overlay pattern:
  - Service runtime can differ from source tree; rebuild scripts reconcile runtime artifact freshness.

## 5) Where to change what
- Change routing policy/order/intent behavior:
  - `workspace/scripts/policy_router.py`
  - `workspace/policy/llm_policy.json`
- Change provider execution behavior:
  - `core/system2/inference/provider_adapter.js`
  - `core/system2/inference/local_vllm_provider.js`
  - `core/system2/inference/router.js`
- Change budgets/guards:
  - Budget/circuit rules in `workspace/scripts/policy_router.py`
  - GPU deflection in `core/system2/inference/gpu_guard.js`
  - vLLM concurrency and launch guardrails in `core/system2/inference/concurrency_tuner.js`, `scripts/tune_concurrency.js`, `scripts/vllm_launch_optimal.sh`
- Change observability/UI:
  - Router/event emitters in `workspace/scripts/policy_router.py`
  - UI and SSE in `workspace/source-ui/app.py`
  - ITC artifact emission in `workspace/itc/ingest/interfaces.py`
- Change runtime service behavior (live environment coupling):
  - `workspace/scripts/rebuild_runtime_openclaw.sh`
  - systemd user service/override paths: Needs inspection in host environment (not tracked in repo).
