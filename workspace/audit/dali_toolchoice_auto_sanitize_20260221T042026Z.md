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

