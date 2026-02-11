# SALVAGE REPORT: system2 unified integration

- Generated at: 2026-02-11T20:21:50.916Z
- Analyzed commit: `9f35bc1ab7d802e60923c95679febc0325555007`
- File inventory size: 170
- Code files scanned: 37
- Findings: 20 MISSING_RELATIVE_REQUIRE entries

## Counts by File (Top Offenders)

| File | Missing Relative Requires |
| --- | ---: |
| core/model_runtime.js | 7 |
| core/model_call.js | 4 |
| core/providers/litellm_proxy_provider.js | 1 |
| core/system2/gateway.js | 1 |
| core/system2/startup_invariants.js | 1 |
| core/system2/tool_plane.js | 1 |
| core/telegram_client.js | 1 |
| scripts/audit_system2.mjs | 1 |
| scripts/system2_invariant_probe.js | 1 |
| tests/litellm_proxy_provider.test.js | 1 |
| tests/sys_config.test.js | 1 |

## Findings

| Type | File | Specifier |
| --- | --- | --- |
| MISSING_RELATIVE_REQUIRE | core/model_call.js | ./normalize_error |
| MISSING_RELATIVE_REQUIRE | core/model_call.js | ./continuity_prompt |
| MISSING_RELATIVE_REQUIRE | core/model_call.js | ./prompt_audit |
| MISSING_RELATIVE_REQUIRE | core/model_call.js | ./constitution_instantiation |
| MISSING_RELATIVE_REQUIRE | core/model_runtime.js | ./cooldown_manager |
| MISSING_RELATIVE_REQUIRE | core/model_runtime.js | ./governance_logger |
| MISSING_RELATIVE_REQUIRE | core/model_runtime.js | ./providers/oath_claude_provider |
| MISSING_RELATIVE_REQUIRE | core/model_runtime.js | ./providers/anthropic_claude_api_provider |
| MISSING_RELATIVE_REQUIRE | core/model_runtime.js | ./providers/local_qwen_provider |
| MISSING_RELATIVE_REQUIRE | core/model_runtime.js | ./providers/local_ollama_provider |
| MISSING_RELATIVE_REQUIRE | core/model_runtime.js | ./providers/local_openai_compat_provider |
| MISSING_RELATIVE_REQUIRE | core/providers/litellm_proxy_provider.js | ../normalize_error |
| MISSING_RELATIVE_REQUIRE | core/system2/gateway.js | ../../sys/config |
| MISSING_RELATIVE_REQUIRE | core/system2/startup_invariants.js | ../../sys/config |
| MISSING_RELATIVE_REQUIRE | core/system2/tool_plane.js | ../../sys/audit/redaction |
| MISSING_RELATIVE_REQUIRE | core/telegram_client.js | ./telegram_circuit_breaker |
| MISSING_RELATIVE_REQUIRE | scripts/audit_system2.mjs | ../sys/config |
| MISSING_RELATIVE_REQUIRE | scripts/system2_invariant_probe.js | ../sys/config |
| MISSING_RELATIVE_REQUIRE | tests/litellm_proxy_provider.test.js | ../core/normalize_error |
| MISSING_RELATIVE_REQUIRE | tests/sys_config.test.js | ../sys/config |

## Suggested Minimal Remediation Strategies (Not Applied)

- Restore missing sibling modules that existing relative paths already reference.
- Prefer targeted path corrections only where specifier typos are proven.
- Add narrow compatibility entrypoints (for example index.js wrappers) only when needed.
- Avoid broad refactors; re-run deterministic tests after each small patch set.

