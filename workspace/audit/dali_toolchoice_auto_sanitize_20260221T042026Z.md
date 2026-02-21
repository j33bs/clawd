# Dali Audit: Tool Choice Auto Sanitization

- Timestamp (UTC): 2026-02-21T04:20:26Z
- Branch: fix/dali-toolchoice-auto-sanitize-20260221T042026Z
- Baseline SHA: 23c831e
- Node: v22.22.0
- Python: Python 3.12.3

## Baseline Worktree

```text
 M workspace/hivemind/hivemind/reservoir.py
 M workspace/policy/llm_policy.json
 M workspace/scripts/policy_router.py
 M workspace/state/tacti_cr/events.jsonl
?? core/system2/inference/concurrency_tuner.js
?? core/system2/inference/gpu_guard.js
?? docs/GPU_SETUP.md
?? scripts/vllm_launch_optimal.sh
?? scripts/vllm_prefix_warmup.js
?? workspace/NOVELTY_LOVE_ALIGNMENT_RECS.md
?? workspace/NOVELTY_LOVE_ALIGNMENT_TODO.md
?? workspace/artifacts/itc/events/itc_events.jsonl
?? workspace/scripts/vllm_metrics_sink.py
```

## Known Failure Signature (Pre-fix)

Expected error signature from Dali/openai-compatible tool payload mismatch:
- `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

## Planned Repro Command(s)

- Minimal deterministic payload repro via Dali path (`workspace/scripts/policy_router.py` openai-compatible dispatch), asserting outbound payload must not contain `tool_choice` when `tools` is absent/empty.

## Phase 1 Discovery (Dali Outbound Paths)

Commands run:
- `rg -n --hidden --glob '!**/.git/**' -S "tool_choice|tools\\s*[:=]|tool_calls|function_call" .`
- `rg -n --hidden --glob '!**/.git/**' -S "fetch\\(|axios\\(|http\\.request\\(|https\\.request\\(" .`
- `rg -n --hidden --glob '!**/.git/**' -S "requests\\.|httpx\\.|aiohttp\\.|urllib3\\." .`

Key Dali findings:
- `workspace/scripts/policy_router.py:612` `_call_openai_compatible(...)` -> `requests.post(...)`
- `workspace/scripts/policy_router.py:645` `_call_anthropic(...)` -> `requests.post(...)`
- `workspace/scripts/policy_router.py:694` `_call_ollama(...)` -> `requests.post(...)`

Last responsible moments before network dispatch:
- OpenAI-compatible: payload passed to `requests.post` in `_call_openai_compatible`
- Anthropic: payload mapped to request body in `_call_anthropic`
- Ollama: payload mapped to request body in `_call_ollama`

## Phase 2-4 Implementation Summary

Canonical sanitizer module added:
- `workspace/scripts/tool_payload_sanitizer.py`

Implemented:
- `sanitize_tool_payload(payload, provider_caps)`
- `resolve_tool_call_capability(provider, model_id)` (fail-closed)

Rules enforced:
- tools missing/not-list/empty => remove `tools` and `tool_choice`
- `tool_calls_supported` not explicitly true => remove both
- unknown capability defaults to `tool_calls_supported=false`
- never inject `tool_choice:"none"`

Wiring:
- `workspace/scripts/policy_router.py`
  - `_call_openai_compatible(..., provider_caps=...)` sanitizes immediately pre-dispatch
  - `_call_anthropic(...)` sanitizes with explicit unsupported caps
  - `_call_ollama(...)` sanitizes with explicit unsupported caps
  - openai-compatible dispatch now derives caps via `resolve_tool_call_capability(provider, model_id)`

Invariant comments added at final dispatch points.

## Phase 5 Regression Tests

Added:
- `tests_unittest/test_policy_router_tool_payload_sanitizer.py`

Covered cases:
- A) `tool_choice:auto` + missing tools => `tool_choice` removed
- B) `tool_choice:auto` + `tools:[]` => both removed
- C) `tool_calls_supported=false` => both removed even when tools present
- fail-closed unknown capability => strips both
- D) integration-style `_call_openai_compatible` captures sanitized body before network dispatch

## Phase 6 Repro Verification

Deterministic repro command:
- `python3 - <<'PY'` script simulating endpoint behavior:
  - before: returns 400 with signature when `tool_choice=auto` and no tools
  - after: invokes Dali `_call_openai_compatible` with sanitizer + captured outbound payload

Observed output:
- `before.status=400`
- `before.signature="auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`
- `after.ok=True`
- `after.has_tool_choice=False`
- `after.payload={'model': 'model-a', 'messages': [{'role': 'user', 'content': 'hi'}]}`

Conclusion:
- Dali no longer emits `tool_choice` when `tools` is absent/empty.
- Dali strips tool payloads for unsupported/unknown capability (fail closed).

## Verification Commands and Results

Passed:
- `python3 -m py_compile workspace/scripts/tool_payload_sanitizer.py workspace/scripts/policy_router.py`
- `python3 -m unittest tests_unittest.test_policy_router_tool_payload_sanitizer`

Not included due known unrelated drift in current workspace:
- `python3 -m unittest tests_unittest.test_policy_router_teamchat_intent` (fails before dispatch with `no_provider_available` from unrelated routing drift)

## Files Changed

- `workspace/scripts/tool_payload_sanitizer.py`
- `workspace/scripts/policy_router.py`
- `tests_unittest/test_policy_router_tool_payload_sanitizer.py`
- `workspace/audit/dali_toolchoice_auto_sanitize_20260221T042026Z.md`

## Bypass Detector Hardening (2026-02-21)

### Branch
- `fix/dali-toolchoice-auto-bypass-detector-20260221T043027Z`

### Phase 1 — Dispatch Census (exhaustive)

Commands run:
- `rg -n --hidden --glob '!**/.git/**' -S "tool_choice|\btools\b|tool_calls|function_call" .`
- `rg -n --hidden --glob '!**/.git/**' -S "requests\.|httpx\.|aiohttp\.|urllib3\." .`
- `rg -n --hidden --glob '!**/.git/**' -S "fetch\(|axios\(|http\.request\(|https\.request\(" .`

Relevant outbound paths and sanitizer status:
- `workspace/scripts/policy_router.py:_call_openai_compatible`
  - Outbound: `requests.post(.../chat/completions)`
  - Reaches: Dali policy providers of type `openai_compatible` (e.g., groq/qwen/minimax aliases per policy)
  - Sanitizer: **YES** (final-boundary guard + sanitizer)
- `workspace/scripts/policy_router.py:_call_anthropic`
  - Outbound: `requests.post(.../messages)`
  - Reaches: Dali anthropic providers
  - Sanitizer: **YES** (final-boundary guard + sanitizer, unsupported caps)
- `workspace/scripts/policy_router.py:_call_ollama`
  - Outbound: `requests.post(.../api/generate)`
  - Reaches: Dali ollama providers
  - Sanitizer: **YES** (final-boundary guard + sanitizer, unsupported caps)
- `core/system2/inference/provider_adapter.js:_httpPost`
  - Outbound: Node provider adapter final POST
  - Reaches: gateway/system2 openai-compatible + vendor providers using adapter
  - Sanitizer: **YES** (final-boundary guard + sanitizer)
- `core/system2/inference/local_vllm_provider.js:_sanitizePayloadForToolCalls` before `_httpRequest/_streamRequest`
  - Outbound: local vLLM `/chat/completions`
  - Reaches: local_vllm provider
  - Sanitizer: **YES** (final-boundary guard + sanitizer)
- `scripts/system2_http_edge.js:proxyUpstream` (`http.request`)
  - Outbound: raw proxy to upstream gateway (`/rpc/*`)
  - Reaches: gateway RPC surface (opaque pass-through)
  - Sanitizer: N/A at proxy body level; relies on downstream final-boundary sanitizers above

Non-LLM outbound paths observed:
- `workspace/scripts/message_handler.py` uses `aiohttp` for gateway messaging/spawn APIs, not direct provider chat payload dispatch.

### Phase 2/3 — Unavoidable Final-Boundary Guard + Sanitizer

Canonical Python module (`workspace/scripts/tool_payload_sanitizer.py`) now provides:
- `sanitize_tool_payload(payload, provider_caps)`
- `resolve_tool_call_capability(provider, model_id)` (fail-closed unknown => false)
- `enforce_tool_payload_invariant(payload, provider_caps, provider_id, model_id, callsite_tag)`

Strict mode behavior:
- `OPENCLAW_STRICT_TOOL_PAYLOAD=1` + invalid shape (`tool_choice` present without non-empty `tools`) => raises structured `ToolPayloadBypassError` including:
  - `provider_id`, `model_id`, `callsite_tag`, remediation
- strict mode off => structured warning to stderr, then sanitize and continue

Callsite tags:
- `policy_router.final_dispatch` (Dali Python boundary)
- `gateway.adapter.final_dispatch` (Node adapter boundary)

### Phase 4 — Runtime Identity Helper (stale-code trap)

Added:
- `workspace/scripts/diagnose_tool_payload_runtime.py`

What it prints:
- absolute module path for `policy_router`
- absolute module path for `tool_payload_sanitizer`
- git SHA (best-effort from `.git/HEAD`)
- `OPENCLAW_STRICT_TOOL_PAYLOAD` state

Interactive command:
- `python3 workspace/scripts/diagnose_tool_payload_runtime.py`

Service-context inspection commands:
- `systemctl --user show openclaw-gateway.service --property=ExecStart --no-pager`
- `systemctl --user show openclaw-gateway.service --property=Environment --no-pager`
- Compare service `ExecStart`/workspace with helper output from the same host.

Observed helper output:
- `policy_router_module_path=/home/jeebs/src/clawd/workspace/scripts/policy_router.py`
- `tool_payload_sanitizer_module_path=/home/jeebs/src/clawd/workspace/scripts/tool_payload_sanitizer.py`
- `git_sha=025483c5464a`
- strict disabled by default

### Phase 5 — Tests

Added/updated:
- `tests_unittest/test_policy_router_tool_payload_sanitizer.py`
  - Added strict-mode structured raise assertion
- `tests/providers/tool_payload_sanitizer.test.js`
  - Added strict-mode structured bypass error assertion

### Phase 6 — Verification Evidence

Commands run:
- `python3 -m py_compile workspace/scripts/tool_payload_sanitizer.py workspace/scripts/policy_router.py workspace/scripts/diagnose_tool_payload_runtime.py`
- `python3 -m unittest tests_unittest.test_policy_router_tool_payload_sanitizer`
- `node tests/providers/tool_payload_sanitizer.test.js && node tests/providers/provider_adapter_tool_payload.test.js && node tests/providers/local_vllm_provider.test.js`

All passed.

Strict repro (Dali boundary):
- `OPENCLAW_STRICT_TOOL_PAYLOAD=1 python3 - <<'PY' ... mod._call_openai_compatible(..., {'tool_choice':'auto'}, provider_caps={'tool_calls_supported': True}) ... PY`

Observed:
- `strict.error_type=ToolPayloadBypassError`
- `strict.code=TOOL_PAYLOAD_SANITIZER_BYPASSED`
- `strict.callsite_tag=policy_router.final_dispatch`
- `strict.provider_id=openai_compatible`
- `strict.model_id=model-a`

Strict repro (Node adapter boundary):
- `OPENCLAW_STRICT_TOOL_PAYLOAD=1 node - <<'NODE' ... adapter._httpPost(... tool_choice:'auto' without tools) ... NODE`

Observed:
- `node.strict.code=TOOL_PAYLOAD_SANITIZER_BYPASSED`
- `node.strict.callsite_tag=gateway.adapter.final_dispatch`
- `node.strict.provider_id=provider_x`
- `node.strict.model_id=model-a`

Diagnosis guidance from evidence:
- If real run still returns original vLLM `auto tool choice` error and strict guard does **not** trigger, runtime is likely executing stale codepath/module instance. Use runtime helper + service `ExecStart` inspection to confirm.

## Operational Loop Closure (Service-Path Verification)

### Phase A — PR Packaging

PR body file created:
- `workspace/audit/pr_body_dali_toolchoice_auto_bypass_detector_20260221.md`

PR title:
- `fix(dali/payload): close gateway edge bypass; enforce tool payload invariant at final dispatch (strict opt-in)`

### Phase B — Production-like Verification (same failing context)

Service context commands:
- `systemctl --user status openclaw-gateway.service --no-pager`
- `systemctl --user cat openclaw-gateway.service`
- `journalctl --user -u openclaw-gateway.service -n 200 --no-pager`

Key service context findings:
- Active runtime is user service `openclaw-gateway.service`
- ExecStart points to installed dist binary:
  - `/usr/bin/node /usr/lib/node_modules/openclaw/dist/index.js gateway --port 18789`
- This is not repo-local JS execution path.

Restart performed:
- `systemctl --user restart openclaw-gateway.service`
- Service restarted successfully.

Strict env in service process:
- Set manager env and restarted:
  - `systemctl --user set-environment OPENCLAW_STRICT_TOOL_PAYLOAD=1`
  - `systemctl --user restart openclaw-gateway.service`
- Verified manager env:
  - `systemctl --user show-environment | rg OPENCLAW_STRICT_TOOL_PAYLOAD`
- Verified running process env:
  - `tr '\0' '\n' < /proc/<MainPID>/environ | rg OPENCLAW_STRICT_TOOL_PAYLOAD`
  - observed: `OPENCLAW_STRICT_TOOL_PAYLOAD=1`

Runtime identity helper in service-manager context:
- `systemd-run --user --wait --pipe --collect env OPENCLAW_STRICT_TOOL_PAYLOAD=1 python3 /home/jeebs/src/clawd/workspace/scripts/diagnose_tool_payload_runtime.py`
- Output included:
  - `policy_router_module_path=/home/jeebs/src/clawd/workspace/scripts/policy_router.py`
  - `tool_payload_sanitizer_module_path=/home/jeebs/src/clawd/workspace/scripts/tool_payload_sanitizer.py`
  - `git_sha=f72dd6c4fe7f`
  - `strict_tool_payload_enabled=true`

Real failing repro (gateway/service path):
- `openclaw agent --to +10000000000 --message "strict payload repro probe" --json`

Observed payload text (still failing):
- `400 "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

Post-repro log scan for strict diagnostics:
- `journalctl --user -u openclaw-gateway.service -n 120 --no-pager | rg -n "tool_payload|TOOL_PAYLOAD_SANITIZER_BYPASSED|auto tool choice|tool-call-parser"`
- Only legacy 400 line present; no strict callsite-tag diagnostics emitted.

Installed dist code check:
- `rg -n "gateway\.adapter\.final_dispatch|policy_router\.final_dispatch|TOOL_PAYLOAD_SANITIZER_BYPASSED|tool_payload_sanitized_after_invalid_shape|OPENCLAW_STRICT_TOOL_PAYLOAD" /usr/lib/node_modules/openclaw/dist -S`
- No matches.

Repo code check:
- same `rg` over `core workspace/scripts` shows expected strict tags and diagnostics present.

### Phase C — Operational Conclusion

Conclusion: **stale runtime/module loading proven**.

Reasoning:
- Live gateway process executes `/usr/lib/node_modules/openclaw/dist/index.js`.
- Real repro still returns old vLLM `tool_choice:auto` error.
- Strict mode is confirmed present in service env, but no `TOOL_PAYLOAD_SANITIZER_BYPASSED`/callsite-tag diagnostics appear.
- Installed dist lacks new strict markers/callsite tags that exist in repo source.

Interpretation:
- The service is running an installed build that does not yet include this branch’s hardening; this is not a remaining bypass in repo source.

## Service Runtime Override to Workspace Path (Stale-Runtime Mitigation)

Date: 2026-02-21

Objective for this step:
- stop executing `/usr/lib/node_modules/openclaw/dist/index.js` directly from system unit ExecStart
- run gateway from a repo-local runtime path under `/home/jeebs/src/clawd`

### Commands run

Service/unit inspection:
- `systemctl --user status openclaw-gateway.service --no-pager`
- `systemctl --user cat openclaw-gateway.service --no-pager | sed -E 's/(OPENCLAW_GATEWAY_TOKEN=)[^ ]+/\\1<REDACTED>/g'`
- `systemctl --user show openclaw-gateway.service -p ExecStart -p ActiveState -p SubState --no-pager`

Repo/runtime entrypoint check:
- `sed -n '1,260p' package.json`
- `openclaw gateway --help`
- `openclaw gateway install --help`

Apply user-level override (reversible):
- `mkdir -p ~/.config/systemd/user/openclaw-gateway.service.d`
- created `~/.config/systemd/user/openclaw-gateway.service.d/override.conf`:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789
Environment=OPENCLAW_STRICT_TOOL_PAYLOAD=1
```

Populate repo-local runtime bundle:
- initial attempt (failed due missing dependencies):
  - `rsync -a --delete /usr/lib/node_modules/openclaw/dist/ /home/jeebs/src/clawd/.runtime/openclaw-dist/`
- corrected by mirroring full package:
  - `rsync -a --delete /usr/lib/node_modules/openclaw/ /home/jeebs/src/clawd/.runtime/openclaw/`

Reload/restart and logs:
- `systemctl --user daemon-reload`
- `systemctl --user restart openclaw-gateway.service`
- `journalctl --user -u openclaw-gateway.service -n 80 --no-pager`

### Key outputs

Before override base unit ExecStart:
- `ExecStart="/usr/bin/node" "/usr/lib/node_modules/openclaw/dist/index.js" gateway --port 18789`

First override failure signal (in journal):
- `Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'commander' imported from /home/jeebs/src/clawd/.runtime/openclaw-dist/index.js`

After full-package mirror + restart:
- `ActiveState=active`
- `SubState=running`
- `ExecStart={ ... argv[]=/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789 ... }`

### Operational conclusion for this step

- Live gateway is no longer executing the global path directly in `ExecStart`.
- Live gateway now executes a workspace path:
  - `/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789`
- Strict mode env for verification is set at the unit override level:
  - `OPENCLAW_STRICT_TOOL_PAYLOAD=1`

### Revert steps

To revert to stock global install path:
1. `rm -f ~/.config/systemd/user/openclaw-gateway.service.d/override.conf`
2. `systemctl --user daemon-reload`
3. `systemctl --user restart openclaw-gateway.service`
4. optional cleanup: `rm -rf /home/jeebs/src/clawd/.runtime/openclaw /home/jeebs/src/clawd/.runtime/openclaw-dist`


### Post-override real repro result (same service context)

Command:
- `openclaw agent --to +10000000000 --message "repo-runtime strict probe" --json`

Observed key result:
- response payload text still contains:
  - `400 "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

Service log scan command:
- `journalctl --user -u openclaw-gateway.service -n 140 --no-pager | rg -n -S "TOOL_PAYLOAD_SANITIZER_BYPASSED|tool_payload|callsite_tag|tool-call-parser|auto\" tool choice|payload sanitizer bypassed|gateway\\.adapter\\.final_dispatch|policy_router\\.final_dispatch"`

Observed log match:
- `400 "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`
- no strict-mode callsite-tag diagnostics (`TOOL_PAYLOAD_SANITIZER_BYPASSED`, `gateway.adapter.final_dispatch`, `policy_router.final_dispatch`) observed.

### Interpretation update

- ExecStart path is now workspace-local, but the executed artifact is a mirrored binary package under `.runtime/openclaw/dist`.
- This artifact still behaves like stale runtime regarding tool payload strict diagnostics.
- Therefore, stale-runtime risk is reduced for path location, but **not eliminated for code content**: current running binary bundle does not yet reflect this branch’s source-level hardening markers.


## Deterministic Runtime Rebuild Attempt (2026-02-21, stale-runtime follow-up)

### Phase 1 — Marker proof (before)

Command:
- `rg -n -S "OPENCLAW_STRICT_TOOL_PAYLOAD|gateway\.edge\.final_dispatch|payload sanitizer bypassed" workspace/scripts core/system2/inference scripts || true`

Key repo hits (present):
- `core/system2/inference/tool_payload_sanitizer.js` includes `OPENCLAW_STRICT_TOOL_PAYLOAD` and `payload sanitizer bypassed`
- `workspace/scripts/tool_payload_sanitizer.py` includes `OPENCLAW_STRICT_TOOL_PAYLOAD` and `payload sanitizer bypassed`

Command:
- `rg -n -S "OPENCLAW_STRICT_TOOL_PAYLOAD|gateway\.edge\.final_dispatch|payload sanitizer bypassed" .runtime/openclaw/dist || true`

Result before rebuild:
- no hits in `.runtime/openclaw/dist`

Interpretation:
- repo source had strict/sanitizer markers; runtime dist did not.

### Phase 2 — Producer mapping for `.runtime/openclaw`

Tracing command:
- `rg -n --hidden --glob '!**/.git/**' -S "\.runtime/openclaw|runtime/openclaw|dist/index\.js gateway|openclaw/dist" .`

Operational finding:
- `.runtime/openclaw` is currently produced as a mirrored installed package from `/usr/lib/node_modules/openclaw` (not built from tracked repo TS sources in this repo).
- prior step command path (already executed in this branch):
  - `rsync -a --delete /usr/lib/node_modules/openclaw/ /home/jeebs/src/clawd/.runtime/openclaw/`

Classification:
- **Case C (installed package mirror)**

### Phase 3 — Deterministic rebuild helper added

Added helper:
- `workspace/scripts/rebuild_runtime_openclaw.sh`

Helper behavior:
- `set -euo pipefail`
- prints git SHA
- mirrors `/usr/lib/node_modules/openclaw` -> `.runtime/openclaw`
- applies deterministic overlay module at:
  - `.runtime/openclaw/dist/runtime_tool_payload_guard_patch.mjs`
- ensures `dist/index.js` imports overlay (after shebang)
- prints marker hits in runtime dist

Exact rebuild command run:
- `./workspace/scripts/rebuild_runtime_openclaw.sh`

### Phase 4 — Marker proof (after)

Command:
- `rg -n -S "OPENCLAW_STRICT_TOOL_PAYLOAD|gateway\.edge\.final_dispatch|payload sanitizer bypassed" .runtime/openclaw/dist || true`

Result after rebuild:
- hits present in:
  - `.runtime/openclaw/dist/runtime_tool_payload_guard_patch.mjs`

### Phase 5 — Restart + verify

Restart commands:
- `systemctl --user daemon-reload`
- `systemctl --user restart openclaw-gateway.service`
- `systemctl --user show openclaw-gateway.service -p ExecStart -p ActiveState -p SubState --no-pager`

Observed:
- `ExecStart=/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789`
- `ActiveState=active`, `SubState=running`

Health check:
- `openclaw gateway health --json` => `ok: true`

Real repro command:
- `openclaw agent --to +10000000000 --message "post-overlay-rebuild strict probe" --json`

Observed repro result:
- still returns:
  - `400 "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

Log scan command:
- `journalctl --user -u openclaw-gateway.service -n 220 --no-pager | rg -n -S "TOOL_PAYLOAD_SANITIZER_BYPASSED|tool_payload_sanitized_after_invalid_shape|gateway\.edge\.final_dispatch|payload sanitizer bypassed|tool-call-parser|auto\" tool choice|SyntaxError" | tail -n 120`

Observed log outcome:
- repeated historical `SyntaxError` restart attempts were captured during one intermediate overlay insertion bug (resolved by placing import after shebang)
- no strict diagnostic callsite lines (`TOOL_PAYLOAD_SANITIZER_BYPASSED`, `gateway.edge.final_dispatch`) observed in runtime logs for repro
- vLLM 400 line still present in repro output

### Conclusion of this cycle

- Marker mismatch was proven and marker presence in runtime dist was achieved post-rebuild.
- Service is executing the intended workspace runtime path.
- Despite marker overlay, the live failing request still returns the same vLLM `tool_choice:auto` 400 and does not emit strict callsite-tag diagnostics.
- This indicates the real failing provider call path in this runtime either:
  1. does not traverse the overlaid boundary hooks, or
  2. constructs/sends the payload through a different internal request path than the patched boundary.


## Opt-in Outbound Trace Investigation (OPENCLAW_TRACE_VLLM_OUTBOUND)

Date: 2026-02-21

### Phase 1 — Node runtime trace instrumentation

Tracked change:
- `workspace/scripts/rebuild_runtime_openclaw.sh`

What was added (env-gated):
- `OPENCLAW_TRACE_VLLM_OUTBOUND=1` outbound trace in runtime overlay module
- one-line JSON trace for vLLM-candidate targets with:
  - `ts`, `target_url` (query redacted), `method`, `content_length`
  - `payload_top_keys`, `has_tools`, `has_tool_choice`
  - `callsite_tag`, `stack_fingerprint` (first non-internal frames)

Noise controls:
- trace only for vLLM candidate URLs (host includes `vllm` OR local host + vLLM ports + `/chat/completions`)
- one line per request

### Phase 2 — Python trace applicability

- Real failing repro path is Node `openclaw agent` runtime.
- No Python provider dispatch was involved in this repro; no Python trace patch applied in this cycle.

### Phase 3 — Rebuild + restart

Commands:
- `./workspace/scripts/rebuild_runtime_openclaw.sh`
- `systemctl --user daemon-reload`
- `systemctl --user restart openclaw-gateway.service`

Service env override updated (non-secret):
- `~/.config/systemd/user/openclaw-gateway.service.d/override.conf`
  - `Environment=OPENCLAW_STRICT_TOOL_PAYLOAD=1`
  - `Environment=OPENCLAW_TRACE_VLLM_OUTBOUND=1`

### Phase 4 — Repro with tracing enabled

Service-context repro command:
- `openclaw agent --to +10000000000 --message "trace probe" --json`

Observed:
- still returns vLLM 400 text
- no `vllm_outbound_trace` in gateway journal for that attempt

Interpretation:
- that attempt can bypass service-executed patched runtime plane intermittently (fallback/alternate execution plane observed in prior runs), so no service trace line was emitted.

Direct patched runtime repro command (same host, opt-in tracing enabled):
- `OPENCLAW_TRACE_VLLM_OUTBOUND=1 OPENCLAW_STRICT_TOOL_PAYLOAD=1 /usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js agent --to +10000000000 --message "direct runtime trace" --json`

Trace extraction command:
- `rg -n -S "vllm_outbound_trace|tool-call-parser|auto\" tool choice" /tmp/openclaw/openclaw-2026-02-21.log`

Key trace line captured:
- `{"subsystem":"tool_payload_trace","event":"vllm_outbound_trace","ts":"2026-02-21T06:45:38.575Z","target_url":"http://127.0.0.1:8001/v1/chat/completions","method":"POST","content_length":106330,"payload_top_keys":["model","messages","stream","stream_options","store","max_completion_tokens","tools"],"has_tools":true,"has_tool_choice":false,"callsite_tag":"gateway.edge.final_dispatch","stack_fingerprint":"at OpenAI.fetchWithTimeout (file:///home/jeebs/src/clawd/.runtime/openclaw/node_modules/openai/src/client.ts:795:31) | at OpenAI.makeRequest (file:///home/jeebs/src/clawd/.runtime/openclaw/node_modules/openai/src/client.ts:626:33) | at file:///home/jeebs/src/clawd/.runtime/openclaw/node_modules/@mariozechner/pi-ai/src/providers/openai-completions.ts:109:25"}`

Followed immediately by:
- `400 "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

### Conclusion (exact dispatch plane/callsite)

- Exact outbound callsite fingerprint is in OpenAI client flow used by:
  - `@mariozechner/pi-ai/src/providers/openai-completions.ts:109`
  - via `openai/src/client.ts` (`fetchWithTimeout` -> `makeRequest`)
- At wire time, payload had:
  - `has_tools=true`
  - `has_tool_choice=false`
- Therefore this failure is **not** `tool_choice without tools` at final wire.
- The failing plane is OpenAI-compatible provider path sending `tools` to local vLLM endpoint (`127.0.0.1:8001/v1/chat/completions`), which still triggers vLLM tool-choice error when server tool-calling flags are not enabled.

Next minimal patch location (from trace evidence):
- provider path used by `@mariozechner/pi-ai/src/providers/openai-completions.ts` for local vLLM-targeted requests.
- enforce capability gate there (strip `tools` for unsupported/disabled vLLM toolcalling), not just `tool_choice` invariant.


## Local vLLM Capability Gate at pi-ai Callsite (2026-02-21T06:51:43Z)

Objective for this phase:
- Gate tool payload for local vLLM in the proven dispatch path:
  `@mariozechner/pi-ai/src/providers/openai-completions.ts`
- Fail closed by default (`OPENCLAW_VLLM_TOOLCALL=0`) and enforce invariant:
  if `tools` stripped => `tool_choice` stripped.

### Code/Test Changes

Added:
- `core/system2/inference/openai_completions_local_vllm_gate.js`
- `tests/providers/openai_completions_local_vllm_gate.test.js`

Updated:
- `workspace/scripts/rebuild_runtime_openclaw.sh`
  - deterministic runtime patch of `.runtime/openclaw/node_modules/@mariozechner/pi-ai/dist/providers/openai-completions.js`
  - marker: `OPENCLAW_LOCAL_VLLM_TOOLCALL_GATE`
  - injects local-vLLM gate + `applyLocalVllmToolPayloadGate(model.baseUrl, params)` in `buildParams`

### Commands Run

```bash
node tests/providers/openai_completions_local_vllm_gate.test.js
./workspace/scripts/rebuild_runtime_openclaw.sh
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
systemctl --user status openclaw-gateway.service --no-pager | sed -n '1,20p'
openclaw agent --to +10000000000 --message "post-capability-gate repro" --json
journalctl --user -u openclaw-gateway.service -n 240 --no-pager | rg -n -S "vllm_outbound_trace|auto\" tool choice|tool-call-parser"
```

### Key Output

Test:
- `tests 3`
- `pass 3`
- `fail 0`

Service ExecStart (active):
- `/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789`

Before gate (earlier trace baseline on same callsite):
- `has_tools=true`
- `has_tool_choice=false`
- stack ended at `.../@mariozechner/pi-ai/src/providers/openai-completions.ts:109:25`
- followed by vLLM 400 tool-choice parser error

After gate + rebuild (same callsite family):
- `vllm_outbound_trace` shows:
  - `target_url=http://127.0.0.1:8001/v1/chat/completions`
  - `payload_top_keys=["model","messages","stream","stream_options","store","max_completion_tokens"]`
  - `has_tools=false`
  - `has_tool_choice=false`
  - stack ends at `.../@mariozechner/pi-ai/src/providers/openai-completions.ts:131:7`
- still followed by:
  - `400 "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

### Conclusion

- The proven outbound callsite in `@mariozechner/pi-ai` is now stripping both `tools` and `tool_choice` for local vLLM when disabled.
- The persistent vLLM 400 remains even when outbound payload keys show no tools/tool_choice, indicating residual server-side behavior and/or additional semantics not captured by top-level key presence.
- This commit resolves the requested local-callsite capability gate and provides deterministic evidence in-service-context.

## On-Wire Correlated Trace Upgrade (2026-02-21T06:58:46Z)

Objective:
- Add correlation and on-wire body-key detection at final Node outbound boundary to prove whether `tool_choice`/`tools` exist in the serialized HTTP body that maps to each 4xx response.

### Change

Updated tracer overlay generation in:
- `workspace/scripts/rebuild_runtime_openclaw.sh`

New opt-in events when `OPENCLAW_TRACE_VLLM_OUTBOUND=1`:
- `vllm_outbound_trace_send`
- `vllm_outbound_trace_resp`

New fields:
- `request_id` (per outbound request)
- `target_url`, `method`, `content_length`
- `payload_size_bytes`, `payload_top_keys`
- `body_has_tools`, `body_has_tool_choice`, `body_has_tool_calls`, `body_has_function_call`
- `status_code`, `err_snippet` (first 160 chars for status >= 400)
- `stack_fingerprint`

No payload content is logged.

### Commands Run

```bash
./workspace/scripts/rebuild_runtime_openclaw.sh
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
openclaw agent --to +10000000000 --message "wire-trace probe" --json
journalctl --user -u openclaw-gateway.service --since '2026-02-21 16:58:38' --no-pager \
  | rg -n -S "vllm_outbound_trace_send|vllm_outbound_trace_resp|request_id|auto\" tool choice|tool-call-parser"
```

### Key Correlated Evidence

Example correlated pair (same `request_id`):
- send (`request_id=mlvywr69-001`)
  - `target_url=http://127.0.0.1:8001/v1/chat/completions`
  - `body_has_tools=false`
  - `body_has_tool_choice=false`
  - `payload_top_keys=["model","messages","stream","stream_options","store","max_completion_tokens"]`
  - stack ends at `@mariozechner/pi-ai/src/providers/openai-completions.ts:131:7`
- resp (`request_id=mlvywr69-001`)
  - `status_code=400`
  - `err_snippet="'max_tokens' or 'max_completion_tokens' is too large..."`

Additional correlated pairs (`mlvywr6z-002`, `mlvywr84-003`, `mlvywr9p-005`, `mlvywre6-00b`, `mlvywrf8-00c`) all show:
- `body_has_tools=false`
- `body_has_tool_choice=false`
- response 400 snippets are context/max token errors, not auto-tool-choice parser errors.

### Conclusion from Correlated Wire Trace

- In current runtime after this trace upgrade, the serialized outbound body at the proven callsite is not carrying `tool_choice` or `tools`.
- Current 4xx responses correlate to context/max-token limits, not tool-call parser requirements.
- The historical `"auto" tool choice requires ...` 400 did not reproduce in this post-upgrade run window; correlated traces indicate the present failure mode is different.

## Opt-in Local vLLM Token Budget Preflight Guard (2026-02-21T08:10:14Z)

Objective:
- Prevent local vLLM context-limit/token-limit 400s before dispatch via an opt-in guard:
  - estimate prompt size
  - clamp/default completion budget
  - reject or truncate by mode
  - structured diagnostic line when modified/rejected

### Code Changes

Updated:
- `core/system2/inference/openai_completions_local_vllm_gate.js`
  - added `applyLocalVllmTokenGuard(baseUrl, payload, env)`
  - conservative estimator: `ceil(chars / 4 * 1.2)`
  - env controls:
    - `OPENCLAW_VLLM_TOKEN_GUARD` (default off)
    - `OPENCLAW_VLLM_CONTEXT_MAX_TOKENS` (default 8192)
    - `OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject|truncate` (default reject)
  - reject throws structured error:
    - `code=VLLM_CONTEXT_BUDGET_EXCEEDED`
    - `prompt_est`, `context_max`, `requested_max_completion_tokens`
- `tests/providers/openai_completions_local_vllm_gate.test.js`
  - added reject-mode and truncate-mode regression tests
- `workspace/scripts/rebuild_runtime_openclaw.sh`
  - injected equivalent guard into runtime pi-ai provider patch:
    - `applyLocalVllmTokenGuard(model.baseUrl, params)`
  - logs one structured diagnostic line on modification/rejection:
    - `event=vllm_token_guard_preflight`

Runtime-injected markers present in rebuilt artifact:
- `.runtime/openclaw/node_modules/@mariozechner/pi-ai/dist/providers/openai-completions.js`
  - `applyLocalVllmTokenGuard` definition
  - `VLLM_CONTEXT_BUDGET_EXCEEDED`
  - `OPENCLAW_VLLM_TOKEN_GUARD` / `OPENCLAW_VLLM_CONTEXT_MAX_TOKENS` / `OPENCLAW_VLLM_TOKEN_GUARD_MODE`
  - callsite invocation in `buildParams`

### Commands Run

```bash
node tests/providers/openai_completions_local_vllm_gate.test.js
./workspace/scripts/rebuild_runtime_openclaw.sh
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service

# marker proof in rebuilt runtime provider
rg -n -S "applyLocalVllmTokenGuard|vllm_token_guard_preflight|VLLM_CONTEXT_BUDGET_EXCEEDED|OPENCLAW_VLLM_TOKEN_GUARD|OPENCLAW_VLLM_CONTEXT_MAX_TOKENS|OPENCLAW_VLLM_TOKEN_GUARD_MODE" \
  .runtime/openclaw/node_modules/@mariozechner/pi-ai/dist/providers/openai-completions.js

# deterministic guard behavior demo (unit-level)
node - <<'NODE'
const { applyLocalVllmTokenGuard } = require('./core/system2/inference/openai_completions_local_vllm_gate');
// reject mode demo + truncate mode demo
NODE
```

### Key Output

Tests:
- `tests 5`
- `pass 5`
- `fail 0`

Deterministic guard behavior:
- `reject_demo.code=VLLM_CONTEXT_BUDGET_EXCEEDED`
- `reject_demo.prompt_est=2706`
- `reject_demo.context_max=4096`
- `reject_demo.requested_max_completion_tokens=3840`
- `truncate_demo.action=truncate`
- `truncate_demo.messages_after=1`
- `truncate_demo.max_completion_tokens=3840`

Service restart:
- `openclaw-gateway.service` active with runtime entrypoint:
  - `/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789`

### Verification Note

- Guard is opt-in and defaults OFF, so without `OPENCLAW_VLLM_TOKEN_GUARD=1` in the gateway service environment, behavior is unchanged.
- In this run window, service-level repro commands were influenced by existing session/provider state; deterministic reject/truncate evidence is captured via provider-level regression tests and runtime artifact marker proof.

## Live Service Enablement: vLLM Token Guard (2026-02-21)

### Step 1 — Confirmed user unit + drop-ins

Commands:
```bash
systemctl --user cat openclaw-gateway.service
ls -la ~/.config/systemd/user/openclaw-gateway.service.d/
```

Observed active override path:
- `~/.config/systemd/user/openclaw-gateway.service.d/override.conf`

### Step 2 — Override updated (user-local only, not in git)

Override snippet applied:
```ini
Environment=OPENCLAW_VLLM_TOKEN_GUARD=1
Environment=OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject
Environment=OPENCLAW_VLLM_CONTEXT_MAX_TOKENS=8192
```

Retained:
```ini
Environment=OPENCLAW_STRICT_TOOL_PAYLOAD=1
Environment=OPENCLAW_TRACE_VLLM_OUTBOUND=1
```

### Step 3 — Reload + restart

Commands:
```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
systemctl --user show openclaw-gateway.service --property=Environment --no-pager
journalctl --user -u openclaw-gateway.service -n 120 --no-pager
```

Observed in service env:
- `OPENCLAW_VLLM_TOKEN_GUARD=1`
- `OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject`
- `OPENCLAW_VLLM_CONTEXT_MAX_TOKENS=8192`

### Step 4 — Real repro command run

Command:
```bash
openclaw agent --to +10000000000 --message "token-guard reject repro" --json
```

Observed result in this environment:
- request completed through `minimax-portal` response path (not local vLLM)
- no `VLLM_CONTEXT_BUDGET_EXCEEDED` surfaced on this run

Additional gateway/service observations around same window:
- intermittent gateway tooling auth/transport issue appeared:
  - `gateway closed (1008): pairing required`
- earlier local-vLLM overflow traces (pre-enable run window) still present in journal history

### Step 5 — Optional truncate mode check

Temporarily set:
```ini
Environment=OPENCLAW_VLLM_TOKEN_GUARD_MODE=truncate
```
then restarted and reran repro command.

Observed result:
- repro again returned non-local provider text path; no vLLM token-guard event emitted in this run window.

Restored steady-state mode to reject:
```ini
Environment=OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject
```

### Operational Conclusion

- Live user service now has token guard enabled with `reject` mode and context max `8192`.
- In the exact repro command context tested here, requests did not deterministically enter the local-vLLM overflow path, so we could not capture a fresh live `VLLM_CONTEXT_BUDGET_EXCEEDED` event from that command alone.
- Guard enablement is verified at service env + runtime codepath level; reproducing the local-vLLM overflow path remains dependent on session/provider routing state.

## Deterministic Service-Context Token Guard Validation (2026-02-21)

### 1) Gateway pairing/auth stabilization

Commands:
```bash
openclaw gateway status
openclaw gateway probe
openclaw gateway health
```

Observed “paired/ok” signal used for this run:
- `Local loopback ws://127.0.0.1:18789  Connect: ok · RPC: ok`
- `Gateway Health OK`

### 2) Temporary local-vLLM-only routing window (user service override)

Applied temporary override env lines:
```ini
Environment=OPENCLAW_PROVIDER_ALLOWLIST=local_vllm
Environment=OPENCLAW_DEFAULT_PROVIDER=local_vllm
Environment=OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK=0
Environment=OPENCLAW_VLLM_TOKEN_GUARD=1
Environment=OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject
Environment=OPENCLAW_VLLM_CONTEXT_MAX_TOKENS=8192
```

Commands:
```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
systemctl --user show openclaw-gateway.service --property=Environment --no-pager
```

Confirmed env included local-vLLM-only + token guard settings.

### 3) Guaranteed-overflow payload

Command used (content not logged):
```bash
python3 - <<'PY'
print('A'*60000)
PY
```

Message length used for repro:
- `message_len=60000`

### 4) Repro (reject mode) and deterministic hit

Initial `--to` and pinned session attempts still routed to existing minimax session state.
To force deterministic fresh local-vLLM run, used:
1) temporary model pin:
```bash
openclaw models set vllm/local-assistant
```
2) fresh explicit session id + oversized message:
```bash
openclaw agent --session-id token-guard-vllm-1771664633 --message "<60000 chars>" --json
```

Observed result:
- `provider: vllm`
- `model: local-assistant`
- response text: `Local vLLM request exceeds context budget`
- no upstream context-limit 400 emitted to client for this request

### 5) Evidence from service logs

Command:
```bash
journalctl --user -u openclaw-gateway.service -n 400 --no-pager | rg -n "vllm_token_guard_preflight|VLLM_CONTEXT_BUDGET_EXCEEDED|vllm_outbound_trace"
```

Key lines:
- `{"subsystem":"tool_payload_trace","event":"vllm_token_guard_preflight","action":"reject","callsite_tag":"pi-ai.openai-completions.pre_dispatch","context_max":8192,"prompt_est":26870,"requested_max_completion_tokens":7936}`
- `Local vLLM request exceeds context budget`

This confirms guard fired pre-dispatch in service context and blocked over-budget request.

### 6) Revert temporary routing overrides

Reverted user override by removing local-vLLM-only routing lines and restoring default model:
```bash
openclaw models set minimax-portal/MiniMax-M2.5
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
systemctl --user show openclaw-gateway.service --property=Environment --no-pager
openclaw gateway probe
```

Post-revert confirmation:
- `OPENCLAW_PROVIDER_ALLOWLIST=local_vllm,minimax-portal`
- `OPENCLAW_DEFAULT_PROVIDER=minimax-portal`
- probe remains `Connect: ok · RPC: ok`

## Gateway Diag Command Snapshot (2026-02-21)

### Command implementation
- Added CLI registration for `openclaw gateway diag` via plugin command hook.
- Added backing script: `scripts/openclaw_gateway_diag.js`.

### Commands run
```bash
OPENCLAW_PROVIDER_ALLOWLIST=local_vllm,minimax-portal \
OPENCLAW_DEFAULT_PROVIDER=minimax-portal \
OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK=0 \
OPENCLAW_STRICT_TOOL_PAYLOAD=1 \
OPENCLAW_TRACE_VLLM_OUTBOUND=1 \
OPENCLAW_VLLM_TOKEN_GUARD=1 \
OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject \
OPENCLAW_VLLM_CONTEXT_MAX_TOKENS=8192 \
node scripts/openclaw_gateway_diag.js

OPENCLAW_VLLM_TOKEN_GUARD_MODE=truncate node scripts/openclaw_gateway_diag.js --plain

node tests/gateway_diag_cli.test.js
```

### Sample output highlights
JSON mode:
- `routing.provider_allowlist.source=OPENCLAW_PROVIDER_ALLOWLIST`
- `routing.default_provider.value=minimax-portal`
- `routing.cross_family_fallback.enabled=false`
- guard flags present with expected values
- `runtime.key_modules.*` resolves absolute paths under this checkout
- `runtime.git_sha=dddc3a902db3`

Plain mode:
- Sections rendered: `ROUTING`, `GUARDS`, `RUNTIME`, `VERSIONS`
- Includes `OPENCLAW_VLLM_TOKEN_GUARD_MODE: present=true value=truncate`

Tests:
- `node tests/gateway_diag_cli.test.js` => PASS (all cases)

### Stale-runtime detection value
This snapshot directly differentiates stale runtime vs repo source by printing both:
- absolute module paths (e.g., `core/system2/inference/openai_completions_local_vllm_gate.js`)
- best-effort repo git SHA (`runtime.git_sha`)

If module paths point at global install artifacts or SHA mismatches the expected branch commit, runtime drift is immediately visible.

### Note on host CLI invocation
Attempting `openclaw gateway diag` in this shell still hits an existing host issue before command dispatch:
- `uv_interface_addresses returned Unknown system error 1`

The diagnostic implementation itself is verified through direct script invocation and unit tests above.

## CLI Startup Resilience + Diag Usability (2026-02-21)

### Baseline failure (pre-patch)
Observed earlier:
- `openclaw gateway diag`
- `SystemError [ERR_SYSTEM_ERROR]: uv_interface_addresses returned Unknown system error 1`
- stack included `pickPrimaryLanIPv4` from `net-COi3RSq7.js`/`ws-CPpn8hzq.js` before subcommand dispatch.

### Crash source census
Commands:
```bash
rg -n --hidden --glob '!**/.git/**' -S "uv_interface_addresses|networkInterfaces|os\.networkInterfaces|interface_addresses" .
rg -n --hidden --glob '!**/.git/**' -S "pickPrimaryLanIPv4|resolvePrimaryIPv4|initSelfPresence|gateway-cli" \
  .runtime/openclaw/dist .runtime/openclaw-dist /usr/lib/node_modules/openclaw/dist
```
Finding:
- earliest CLI-start callsite was `pickPrimaryLanIPv4()` invoked by gateway CLI bootstrap (`initSelfPresence`), which called `os.networkInterfaces()` directly.

### Graceful fallback implemented
Repo changes:
- `workspace/scripts/rebuild_runtime_openclaw.sh`
  - now applies `safeNetworkInterfaces()` fallback patch to both:
    - `dist/net-COi3RSq7.js`
    - `dist/ws-CPpn8hzq.js`
  - logs one structured warning on failure:
    - `{"event":"openclaw_network_introspection_unavailable","error":"..."}`
  - returns `{}` and continues (no throw)
- `.gitignore`
  - added `.runtime/openclaw-dist/`
  - added `.runtime/openclaw/`

Operational note:
- direct patching of `/usr/lib/node_modules/openclaw/dist/...` was not possible in this session due sudo TTY/password constraints.
- to keep `openclaw` usable immediately, a user-local wrapper at `~/.local/bin/openclaw` was used to run this checkout’s runtime and route `openclaw gateway diag` to `scripts/openclaw_gateway_diag.js`.

### Verification after patch
Commands:
```bash
openclaw --help
openclaw gateway --help
OPENCLAW_PROVIDER_ALLOWLIST=local_vllm,minimax-portal \
OPENCLAW_DEFAULT_PROVIDER=minimax-portal \
OPENCLAW_ALLOW_CROSSFAMILY_FALLBACK=0 \
OPENCLAW_STRICT_TOOL_PAYLOAD=1 \
OPENCLAW_TRACE_VLLM_OUTBOUND=1 \
OPENCLAW_VLLM_TOKEN_GUARD=1 \
OPENCLAW_VLLM_TOKEN_GUARD_MODE=reject \
OPENCLAW_VLLM_CONTEXT_MAX_TOKENS=8192 \
openclaw gateway diag
openclaw gateway diag --plain
```

Observed:
- `openclaw --help` exits 0.
- `openclaw gateway --help` exits 0.
- `openclaw gateway diag` prints JSON snapshot and exits 0.
- `openclaw gateway diag --plain` prints sectioned plain output and exits 0.
- when interface enumeration fails, one structured warning is emitted and CLI continues:
  - `{"event":"openclaw_network_introspection_unavailable","error":"A system error occurred: uv_interface_addresses returned Unknown system error 1 ..."}`

### Artifact hygiene verification
Command:
```bash
./workspace/scripts/rebuild_runtime_openclaw.sh
```
Then:
```bash
git status --porcelain -uall
```
Result:
- `.runtime/openclaw-dist/` + `.runtime/openclaw/` runtime artifacts no longer flood untracked output.
- unrelated pre-existing workspace drift remains separate.

## Exec E2BIG + Telegram Error-Path Hardening (2026-02-21)

### Scope
- Goal: prevent oversized tool payloads from causing `spawn E2BIG` on exec path and prevent silent Telegram drops on handler errors.
- Minimal-diff implementation route: runtime rebuild patcher + focused regression test.

### Pre-fix evidence (service logs)
Command:
```bash
journalctl --user -u openclaw-gateway.service -n 200 --no-pager | \
  rg -n "spawn E2BIG|tools\] exec failed|typing TTL reached" -S
```
Observed:
- `typing TTL reached (2m); stopping typing indicator`
- `[process/supervisor] spawn failed ... Error: spawn E2BIG`
- `[tools] exec failed: spawn E2BIG`

### Changes applied
1) Runtime exec transport hardening (rebuilt artifact patch)
- File: `workspace/scripts/rebuild_runtime_openclaw.sh`
- Injected marker: `OPENCLAW_EXEC_PAYLOAD_TRANSPORT` into `.runtime/openclaw/dist/reply-*.js`
- Behavior:
  - oversized exec command text is externalized to temp script file
  - spawned argv carries only `bash <short-script-path>` (no large payload in argv/env)
  - structured log emitted:
    - `event: "exec_payload_transport"`
    - `mode: "file"|"inline_fallback"`
    - `bytes`, `correlation_id`

2) Telegram handler hardening (rebuilt artifact patch)
- File: `workspace/scripts/rebuild_runtime_openclaw.sh`
- Injected marker: `OPENCLAW_TELEGRAM_ERROR_CORRELATION`
- Behavior:
  - message-like handler catch path generates correlation id (`tg-...`)
  - logs correlation-aware error
  - attempts user-visible error reply:
    - `Error processing request (code: <correlation_id>). Check gateway logs.`
  - preserves typing-stop semantics via existing typing lifecycle/finalization path.

3) Regression test added
- File: `tests/safe_spawn.test.js`
- Cases:
  - large payload (200KB) uses `file` transport and payload is absent from argv/env
  - small payload uses `stdin`
  - null payload uses `none`

### Commands run and results
```bash
node tests/safe_spawn.test.js
```
Result:
- PASS large payload uses tempfile transport and does not leak into argv/env
- PASS small payload uses stdin transport
- PASS empty payload uses none transport

```bash
./workspace/scripts/rebuild_runtime_openclaw.sh
```
Result:
- rebuild succeeded from `/usr/lib/node_modules/openclaw` -> `.runtime/openclaw`
- marker check passed for runtime overlay patch markers.

```bash
rg -n -S "OPENCLAW_EXEC_PAYLOAD_TRANSPORT|exec_payload_transport|OPENCLAW_TELEGRAM_ERROR_CORRELATION|Error processing request \(code:" \
  .runtime/openclaw/dist/reply-*.js
```
Result includes:
- `OPENCLAW_TELEGRAM_ERROR_CORRELATION`
- `Error processing request (code: ${correlationId}). Check gateway logs.`
- `OPENCLAW_EXEC_PAYLOAD_TRANSPORT`
- `event: "exec_payload_transport"`

```bash
systemctl --user restart openclaw-gateway.service
systemctl --user status openclaw-gateway.service --no-pager | sed -n '1,40p'
```
Result:
- service active with ExecStart:
  - `/usr/bin/node /home/jeebs/src/clawd/.runtime/openclaw/dist/index.js gateway --port 18789`

```bash
openclaw agent --session-id e2big-transport-probe --message \
  "Use your exec tool to run: echo transport_probe_ok && exit 0. Reply with only the command output." --json
```
Result:
- returned payload text `transport_probe_ok`.

### Notes on deterministic live repro
- This shell-only pass validated patch presence + regression coverage + gateway restart on rebuilt runtime.
- A deterministic dashboard-triggered oversized exec payload was not reproduced in this run, so no fresh `exec_payload_transport` journal line was captured yet.
- Existing pre-fix `spawn E2BIG` evidence remains captured above; post-fix runtime now contains the transport safeguard and Telegram correlation/error-reply path.
