# Skills Tiered MLX/Triage/Scaffold Audit (2026-02-22)

Append-only implementation evidence for:
- workspace/skills/mlx-infer
- workspace/skills/task-triage
- workspace/skills/scaffold-apply

## Phase 0 Baseline (2026-02-22T04:06:19Z)
```bash
git status --porcelain -uall
?? workspace/audit/skills_tiered_mlx_triage_scaffold_20260222.md

git rev-parse --abbrev-ref HEAD
main

git rev-parse --short HEAD
d58a625
```

## Phase 0 Branch Correction (2026-02-22T04:09:59Z)
```bash
git checkout codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222
git status --porcelain -uall
?? workspace/audit/skills_tiered_mlx_triage_scaffold_20260222.md

git rev-parse --abbrev-ref HEAD
codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222

git rev-parse --short HEAD
d80da3a
```

## Build Strategy Decision
- Repo root does not provide a direct TypeScript build pipeline for workspace skills.
- Implemented fallback: authored runtime-ready JS under dist/ and parallel TS source under src/.
- No external dependencies added; runtime is zero-build.

## Commands Run
```bash
node --test workspace/skills/**/tests/*.test.js
```

## Test Result
- PASS: 12 tests, 0 failures.

## Known Limitations / Follow-ups
- mlx-infer requires python3 + mlx-lm preinstalled; tests use stubs and do not exercise real MLX runtime.
- task-triage relies on external local suggestion JSON; it does not invoke mlx-infer internally by design.
- scaffold-apply does not auto-rollback previously committed steps when a later step fails (intentional).

## Files Added/Changed
- workspace/skills/mlx-infer/
  - README.md, SKILL.md
  - scripts/mlx_infer.py
  - src/{cli.ts,logger.ts}
  - dist/{cli.js,logger.js}
  - schemas/{input.schema.json,output.schema.json}
  - tests/mlx_infer_integration_stub.test.js
- workspace/skills/task-triage/
  - README.md, SKILL.md
  - config/{decision_rules.json,classifier_prompt.md}
  - src/{cli.ts,decision.ts,logger.ts}
  - dist/{cli.js,decision.js,logger.js}
  - schemas/{input.schema.json,output.schema.json}
  - tests/decision_logic.test.js
- workspace/skills/scaffold-apply/
  - README.md, SKILL.md, package.json
  - src/{cli.ts,plan_schema.ts,logger.ts}
  - dist/{cli.js,plan_schema.js,logger.js}
  - schemas/{input.schema.json,output.schema.json}
  - tests/{plan_validation.test.js,dry_run_patch_check.test.js}

## Merge Verification on main (2026-02-22T04:30:10Z)
- BR_REF: origin/codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222
- Merge commit: 8bcbba6
- Test command:     \✔ maps python error types to node-level types (0.737084ms)
✔ buildPythonArgs includes required and optional args (0.823583ms)
✔ dry-run patch check passes on valid patch (184.307333ms)
✔ dry-run patch check reports failed step on invalid patch (148.954333ms)
✔ validation fails when required fields are missing (0.86225ms)
✔ validation fails invalid operation (0.155459ms)
✔ validation rejects path traversal (0.107583ms)
✔ high-confidence LOCAL remains LOCAL (0.846708ms)
✔ low confidence escalates to REMOTE (0.077958ms)
✔ very low confidence escalates to HUMAN (0.066791ms)
✔ force_human signal triggers HUMAN (0.072541ms)
✔ openai keyword triggers HUMAN plus request_for_chatgpt (0.099791ms)
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 424.794583
- Test summary: PASS (12 tests, 0 failures)

## Merge Verification on main (2026-02-22T04:30:25Z)
- BR_REF: origin/codex/feat/clawd-tiered-skills-mlx-triage-scaffold-20260222
- Merge commit: 8bcbba6
- Test command: ✔ maps python error types to node-level types (0.755583ms)
✔ buildPythonArgs includes required and optional args (0.8165ms)
✔ dry-run patch check passes on valid patch (190.017875ms)
✔ dry-run patch check reports failed step on invalid patch (155.191792ms)
✔ validation fails when required fields are missing (0.848292ms)
✔ validation fails invalid operation (0.146209ms)
✔ validation rejects path traversal (0.103ms)
✔ high-confidence LOCAL remains LOCAL (0.941083ms)
✔ low confidence escalates to REMOTE (0.081167ms)
✔ very low confidence escalates to HUMAN (0.067375ms)
✔ force_human signal triggers HUMAN (0.063083ms)
✔ openai keyword triggers HUMAN plus request_for_chatgpt (0.097834ms)
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 474.158958
- Test summary: PASS (12 tests, 0 failures)

## mlx-infer Concurrency Hardening (2026-02-22T05:08:33Z)
- Rationale: prevent crash-stale PID files in \ from causing false \ failures.
- Change: concurrency guard now removes stale PID files when process is no longer alive and/or file mtime exceeds TTL.
- TTL default: \ ms (10 minutes).
- TTL override env: \.
- Test-only env hook added: no.
- Test commands:
  - \✔ removes stale pid files for dead processes before counting (53.548042ms)
✔ removes pid file when ttl is exceeded (1.082542ms)
✔ live pid file contributes to concurrency limit (62.205459ms)
✔ maps python error types to node-level types (0.756333ms)
✔ buildPythonArgs includes required and optional args (0.808291ms)
ℹ tests 5
ℹ suites 0
ℹ pass 5
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 200.01175 (PASS: 5/5)
  - \✔ removes stale pid files for dead processes before counting (59.787791ms)
✔ removes pid file when ttl is exceeded (1.056666ms)
✔ live pid file contributes to concurrency limit (63.952792ms)
✔ maps python error types to node-level types (0.769333ms)
✔ buildPythonArgs includes required and optional args (0.905541ms)
✔ dry-run patch check passes on valid patch (202.323ms)
✔ dry-run patch check reports failed step on invalid patch (151.098917ms)
✔ validation fails when required fields are missing (0.858ms)
✔ validation fails invalid operation (0.176833ms)
✔ validation rejects path traversal (0.102583ms)
✔ high-confidence LOCAL remains LOCAL (1.449125ms)
✔ low confidence escalates to REMOTE (0.085667ms)
✔ very low confidence escalates to HUMAN (0.071792ms)
✔ force_human signal triggers HUMAN (0.064792ms)
✔ openai keyword triggers HUMAN plus request_for_chatgpt (0.100041ms)
ℹ tests 15
ℹ suites 0
ℹ pass 15
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 447.618791 (PASS: 15/15)
- Rollback: \

## mlx-infer Concurrency Hardening (corrected evidence) (2026-02-22T05:08:50Z)
- Note: previous section had shell interpolation artifacts; this corrected block is authoritative.
- Rationale: prevent crash-stale PID files in .run/mlx-infer/ from causing false CONCURRENCY_LIMIT failures.
- Change: concurrency guard now removes stale PID files when process is no longer alive and/or file mtime exceeds TTL.
- TTL default: 600000 ms (10 minutes).
- TTL override env: OPENCLAW_MLX_INFER_PID_TTL_MS.
- Test-only env hook added: no.
- Test commands and summary:
  - node --test workspace/skills/mlx-infer/tests/*.test.js -> PASS (5 tests, 0 failures)
  - node --test workspace/skills/**/tests/*.test.js -> PASS (15 tests, 0 failures)
- Rollback: git revert <commit_sha>

## Merge Verification for mlx-infer concurrency hardening (2026-02-22T05:21:53Z)
- Merge commit: 2eca151
- Test command: node --test workspace/skills/**/tests/*.test.js
- Test summary: PASS (15 tests, 0 failures)

## Merge Verification for mlx-infer concurrency hardening (2026-02-22T05:23:07Z)
- Merge commit: 2eca151
- Test command: node --test workspace/skills/**/tests/*.test.js
- Test summary: PASS (15 tests, 0 failures)

## MLX Runtime Determinism Verification (2026-02-22T05:53:54Z)
- System python discovered: /opt/homebrew/bin/python3 (Python 3.14.3).
- Venv path used: .venv-mlx (python: /private/tmp/wt_docs_main/.venv-mlx/bin/python).
- mlx-lm state: not preinstalled in system python; newly installed into .venv-mlx via pip.
- OPENCLAW_MLX_INFER_PYTHON support added: yes (mlx-infer now uses env override, fallback python3).
- Smoke command:
  - export OPENCLAW_MLX_INFER_PYTHON="/private/tmp/wt_docs_main/.venv-mlx/bin/python"
  - node workspace/skills/mlx-infer/dist/cli.js --prompt "Say hello." --max_tokens 20 --temperature 0.1
- Smoke result: FAIL with JSON error type=MLX_MISSING caused by native MLX import crash (NSRangeException in libmlx on this host).
- Test suite command: node --test workspace/skills/**/tests/*.test.js
- Test suite summary: PASS (16 tests, 0 failures).
- Rollback: git revert <commit_sha>

## MLX Smoke Failure Capture After Python Override Merge (2026-02-22T06:20:29Z)
- Note: merged OPENCLAW_MLX_INFER_PYTHON override onto main (commit b61800b).
- venv: .venv-mlx313
- python version: Python 3.13.11
- mx.default_device() probe result: native MLX/Metal device init crash (NSRangeException).
- Smoke output JSON (verbatim):
```json
{"ok":false,"error":{"type":"MLX_MISSING","message":"mlx_lm import failed","details":{"stderr":"*** Terminating app due to uncaught exception 'NSRangeException', reason: '*** -[__NSArray0 objectAtIndex:]: index 0 beyond bounds for empty array'\n*** First throw call stack:\n(\n\t0   CoreFoundation                      0x00000001905cb8fc __exceptionPreprocess + 176\n\t1   libobjc.A.dylib                     0x00000001900a2418 objc_exception_throw + 88\n\t2   CoreFoundation                      0x00000001905ea8bc CFArrayApply + 0\n\t3   libmlx.dylib                        0x000000010be03468 _ZN3mlx4core5metal6DeviceC2Ev + 204\n\t4   libmlx.dylib                        0x000000010be06c10 _ZN3mlx4core5metal6deviceENS0_6DeviceE + 80\n\t5   libmlx.dylib                        0x000000010bdd9ba8 _ZN3mlx4core5metal14MetalAllocatorC2Ev + 64\n\t6   libmlx.dylib                        0x000000010bdd9a44 _ZN3mlx4core9allocator9allocatorEv + 80\n\t7   libmlx.dylib                        0x000000010b102438 _ZN3mlx4core5array4initIPKjEEvT_ + 64\n\t8   libmlx.dylib                        0x000000010b102370 _ZN3mlx4core5arrayC2IjEESt16initializer_listIT_ENS0_5DtypeE + 152\n\t9   libmlx.dylib                        0x000000010b0fb988 _ZN3mlx4core6random3keyEy + 72\n\t10  core.cpython-313-darwin.so          0x0000000109906c7c _ZNK3mlx4core5array6nbytesEv + 706900\n\t11  core.cpython-313-darwin.so          0x0000000109908724 _ZNK3mlx4core5array6nbytesEv + 713724\n\t12  core.cpython-313-darwin.so          0x0000000109851e50 PyInit_core + 420\n\t13  Python                              0x0000000104c818c0 PyModule_ExecDef + 188\n\t14  Python                              0x0000000104d951dc _imp_exec_dynamic + 16\n\t15  Python                              0x0000000104c7fb00 cfunction_vectorcall_O + 104\n\t16  Python                              0x0000000104d4d2d4 _PyEval_EvalFrameDefault + 20012\n\t17  Python                              0x0000000104c254c4 object_vacall + 268\n\t18  Python                              0x0000000104c25338 PyObject_CallMethodObjArgs + 104\n\t19  Python                              0x0000000104d9202c PyImport_ImportModuleLevelObject + 3120\n\t20  Python                              0x0000000104d489fc _PyEval_EvalFrameDefault + 1364\n\t21  Python                              0x0000000104d4822c PyEval_EvalCode + 200\n\t22  Python                              0x0000000104d43500 builtin_exec + 440\n\t23  Python                              0x0000000104c7f8dc cfunction_vectorcall_FASTCALL_KEYWORDS + 88\n\t24  Python                              0x0000000104d4d2d4 _PyEval_EvalFrameDefault + 20012\n\t25  Python                              0x0000000104c254c4 object_vacall + 268\n\t26  Python                              0x0000000104c25338 PyObject_CallMethodObjArgs + 104\n\t27  Python                              0x0000000104d9202c PyImport_ImportModuleLevelObject + 3120\n\t28  Python                              0x0000000104d489fc _PyEval_EvalFrameDefault + 1364\n\t29  Python                              0x0000000104d4822c PyEval_EvalCode + 200\n\t30  Python                              0x0000000104d43500 builtin_exec + 440\n\t31  Python                              0x0000000104c7f8dc cfunction_vectorcall_FASTCALL_KEYWORDS + 88\n\t32  Python                              0x0000000104d4d2d4 _PyEval_EvalFrameDefault + 20012\n\t33  Python                              0x0000000104c254c4 object_vacall + 268\n\t34  Python                              0x0000000104c25338 PyObject_CallMethodObjArgs + 104\n\t35  Python                              0x0000000104d9202c PyImport_ImportModuleLevelObject + 3120\n\t36  Python                              0x0000000104d489fc _PyEval_EvalFrameDefault + 1364\n\t37  Python                              0x0000000104d4822c PyEval_EvalCode + 200\n\t38  Python                              0x0000000104db7fa4 run_eval_code_obj + 104\n\t39  Python                              0x0000000104db78f8 run_mod + 168\n\t40  Python                              0x0000000104db6304 _PyRun_StringFlagsWithName + 148\n\t41  Python                              0x0000000104db6114 _PyRun_SimpleStringFlagsWithName + 144\n\t42  Python                              0x0000000104ddbb00 Py_RunMain + 808\n\t43  Python                              0x0000000104ddc19c pymain_main + 304\n\t44  Python                              0x0000000104ddc23c Py_BytesMain + 40\n\t45  dyld                                0x0000000190115d54 start + 7184\n)\nlibc++abi: terminating due to uncaught exception of type NSException\n"}}}
```
- Test command: node --test workspace/skills/**/tests/*.test.js
- Test summary: PASS (16 tests, 0 failures).
- Conclusion: MLX/Metal device initialization crashes on this host; mlx-infer not operational yet. Recommended fallback: LOCAL non-MLX engine until MLX runtime is fixed.

## MLX Smoke Failure Capture After Python Override Merge (2026-02-22T06:21:08Z)
- Note: merged OPENCLAW_MLX_INFER_PYTHON override onto main (commit b61800b).
- venv: .venv-mlx313
- python version: Python 3.13.11
- mx.default_device() probe result: native MLX/Metal device init crash (NSRangeException).
- Smoke output JSON (verbatim):
```json
{"ok":false,"error":{"type":"MLX_MISSING","message":"mlx_lm import failed","details":{"stderr":"*** Terminating app due to uncaught exception 'NSRangeException', reason: '*** -[__NSArray0 objectAtIndex:]: index 0 beyond bounds for empty array'\n*** First throw call stack:\n(\n\t0   CoreFoundation                      0x00000001905cb8fc __exceptionPreprocess + 176\n\t1   libobjc.A.dylib                     0x00000001900a2418 objc_exception_throw + 88\n\t2   CoreFoundation                      0x00000001905ea8bc CFArrayApply + 0\n\t3   libmlx.dylib                        0x000000010be03468 _ZN3mlx4core5metal6DeviceC2Ev + 204\n\t4   libmlx.dylib                        0x000000010be06c10 _ZN3mlx4core5metal6deviceENS0_6DeviceE + 80\n\t5   libmlx.dylib                        0x000000010bdd9ba8 _ZN3mlx4core5metal14MetalAllocatorC2Ev + 64\n\t6   libmlx.dylib                        0x000000010bdd9a44 _ZN3mlx4core9allocator9allocatorEv + 80\n\t7   libmlx.dylib                        0x000000010b102438 _ZN3mlx4core5array4initIPKjEEvT_ + 64\n\t8   libmlx.dylib                        0x000000010b102370 _ZN3mlx4core5arrayC2IjEESt16initializer_listIT_ENS0_5DtypeE + 152\n\t9   libmlx.dylib                        0x000000010b0fb988 _ZN3mlx4core6random3keyEy + 72\n\t10  core.cpython-313-darwin.so          0x0000000109906c7c _ZNK3mlx4core5array6nbytesEv + 706900\n\t11  core.cpython-313-darwin.so          0x0000000109908724 _ZNK3mlx4core5array6nbytesEv + 713724\n\t12  core.cpython-313-darwin.so          0x0000000109851e50 PyInit_core + 420\n\t13  Python                              0x0000000104c818c0 PyModule_ExecDef + 188\n\t14  Python                              0x0000000104d951dc _imp_exec_dynamic + 16\n\t15  Python                              0x0000000104c7fb00 cfunction_vectorcall_O + 104\n\t16  Python                              0x0000000104d4d2d4 _PyEval_EvalFrameDefault + 20012\n\t17  Python                              0x0000000104c254c4 object_vacall + 268\n\t18  Python                              0x0000000104c25338 PyObject_CallMethodObjArgs + 104\n\t19  Python                              0x0000000104d9202c PyImport_ImportModuleLevelObject + 3120\n\t20  Python                              0x0000000104d489fc _PyEval_EvalFrameDefault + 1364\n\t21  Python                              0x0000000104d4822c PyEval_EvalCode + 200\n\t22  Python                              0x0000000104d43500 builtin_exec + 440\n\t23  Python                              0x0000000104c7f8dc cfunction_vectorcall_FASTCALL_KEYWORDS + 88\n\t24  Python                              0x0000000104d4d2d4 _PyEval_EvalFrameDefault + 20012\n\t25  Python                              0x0000000104c254c4 object_vacall + 268\n\t26  Python                              0x0000000104c25338 PyObject_CallMethodObjArgs + 104\n\t27  Python                              0x0000000104d9202c PyImport_ImportModuleLevelObject + 3120\n\t28  Python                              0x0000000104d489fc _PyEval_EvalFrameDefault + 1364\n\t29  Python                              0x0000000104d4822c PyEval_EvalCode + 200\n\t30  Python                              0x0000000104d43500 builtin_exec + 440\n\t31  Python                              0x0000000104c7f8dc cfunction_vectorcall_FASTCALL_KEYWORDS + 88\n\t32  Python                              0x0000000104d4d2d4 _PyEval_EvalFrameDefault + 20012\n\t33  Python                              0x0000000104c254c4 object_vacall + 268\n\t34  Python                              0x0000000104c25338 PyObject_CallMethodObjArgs + 104\n\t35  Python                              0x0000000104d9202c PyImport_ImportModuleLevelObject + 3120\n\t36  Python                              0x0000000104d489fc _PyEval_EvalFrameDefault + 1364\n\t37  Python                              0x0000000104d4822c PyEval_EvalCode + 200\n\t38  Python                              0x0000000104db7fa4 run_eval_code_obj + 104\n\t39  Python                              0x0000000104db78f8 run_mod + 168\n\t40  Python                              0x0000000104db6304 _PyRun_StringFlagsWithName + 148\n\t41  Python                              0x0000000104db6114 _PyRun_SimpleStringFlagsWithName + 144\n\t42  Python                              0x0000000104ddbb00 Py_RunMain + 808\n\t43  Python                              0x0000000104ddc19c pymain_main + 304\n\t44  Python                              0x0000000104ddc23c Py_BytesMain + 40\n\t45  dyld                                0x0000000190115d54 start + 7184\n)\nlibc++abi: terminating due to uncaught exception of type NSException\n"}}}
```
- Test command: node --test workspace/skills/**/tests/*.test.js
- Test summary: PASS (16 tests, 0 failures).
- Conclusion: MLX/Metal device initialization crashes on this host; mlx-infer not operational yet. Recommended fallback: LOCAL non-MLX engine until MLX runtime is fixed.

## mlx-infer Preflight Isolation Hardening (2026-02-22T10:52:33Z)
- Evidence basis: prior MLX crash-rate diagnostics in this audit (see entries from commits c770674 and ed2935b) showed repeated hard aborts during MLX/Metal init.
- Rationale: isolate MLX device initialization in a dedicated short-lived subprocess to prevent hard crashes from taking down the primary inference path.
- Behavior change:
  - Added preflight stage before mlx-lm import/generation.
  - Preflight command: python -c "import mlx.core as mx; print(mx.default_device())".
  - Timeout: 3000ms.
  - On nonzero exit, timeout, or empty stdout, CLI returns typed error:
    - error.type: MLX_DEVICE_UNAVAILABLE
    - error.message: MLX Metal device init unstable/unavailable
    - error.details: { exit_code, timed_out, stderr_head, stdout_head }
  - If preflight fails, mlx-lm import/generation path is not executed.
- Logging:
  - Emits preflight log line to stderr with stage=mlx_preflight and outcome=ok|fail, including exit_code and timed_out.
- Tests run:
  - node --test workspace/skills/**/tests/*.test.js
  - Result: PASS (19 tests, 0 failures).
- Rollback: git revert <commit_sha>

## mlx-infer Preflight Isolation Hardening (2026-02-22T10:53:10Z)
- Evidence basis: prior MLX crash-rate diagnostics in this audit (see entries from commits c770674 and ed2935b) showed repeated hard aborts during MLX/Metal init.
- Rationale: isolate MLX device initialization in a dedicated short-lived subprocess to prevent hard crashes from taking down the primary inference path.
- Behavior change:
  - Added preflight stage before mlx-lm import/generation.
  - Preflight command: python -c "import mlx.core as mx; print(mx.default_device())".
  - Timeout: 3000ms.
  - On nonzero exit, timeout, or empty stdout, CLI returns typed error:
    - error.type: MLX_DEVICE_UNAVAILABLE
    - error.message: MLX Metal device init unstable/unavailable
    - error.details: { exit_code, timed_out, stderr_head, stdout_head }
  - If preflight fails, mlx-lm import/generation path is not executed.
- Logging:
  - Emits preflight log line to stderr with stage=mlx_preflight and outcome=ok|fail, including exit_code and timed_out.
- Tests run:
  - node --test workspace/skills/**/tests/*.test.js
  - Result: PASS (19 tests, 0 failures).
- Rollback: git revert <commit_sha>

## Merge + Triage Escalation Verification (2026-02-22T12:22:57Z)
- Merge applied: origin/codex/fix/mlx-infer-preflight-isolation-20260222 -> main
- Merge commit: d67ac06
- Added config-driven triage escalation for local MLX failures:
  - Rule location: workspace/skills/task-triage/config/decision_rules.json (error_escalations[type=MLX_DEVICE_UNAVAILABLE])
  - Behavior: last_local_error.type=MLX_DEVICE_UNAVAILABLE escalates to tier=REMOTE, confidence=0.9, rationale includes "local mlx unavailable; escalated".
- Tests run:
  - node --test workspace/skills/**/tests/*.test.js
  - Summary: PASS (20 tests, 0 failures)

## Merge + Triage Escalation Verification (2026-02-22T13:56:29Z)
- Merge applied: origin/codex/fix/mlx-infer-preflight-isolation-20260222 -> main
- Merge commit: d67ac06
- Added config-driven triage escalation for local MLX failures:
  - Rule location: workspace/skills/task-triage/config/decision_rules.json (error_escalations[type=MLX_DEVICE_UNAVAILABLE])
  - Behavior: last_local_error.type=MLX_DEVICE_UNAVAILABLE escalates to tier=REMOTE, confidence=0.9, rationale includes "local mlx unavailable; escalated".
- Tests run:
  - node --test workspace/skills/**/tests/*.test.js
  - Summary: PASS (20 tests, 0 failures)

## Core ML Embedding Sub-Agent MVP (Runner + Skill) (2026-02-22T20:29:45Z)
- Branch: codex/feat/coreml-runner-embed-20260223
- Why: add a bounded LOCAL Core ML embedding primitive for routing/retrieval workflows without introducing a primary local LLM agent.

### Files added
- workspace/runners/coreml_embed_runner/Package.swift
- workspace/runners/coreml_embed_runner/Sources/CoreMLEmbedRunner/main.swift
- workspace/runners/coreml_embed_runner/build.sh
- workspace/runners/coreml_embed_runner/run.sh
- workspace/runners/coreml_embed_runner/README.md
- workspace/skills/coreml-embed/SKILL.md
- workspace/skills/coreml-embed/README.md
- workspace/skills/coreml-embed/config/default.json
- workspace/skills/coreml-embed/src/cli.ts
- workspace/skills/coreml-embed/src/logger.ts
- workspace/skills/coreml-embed/dist/cli.js
- workspace/skills/coreml-embed/dist/logger.js
- workspace/skills/coreml-embed/schemas/input.schema.json
- workspace/skills/coreml-embed/schemas/output.schema.json
- workspace/skills/coreml-embed/tests/coreml_embed_cli.test.js
- workspace/skills/coreml-embed/tests/fixtures/default.json
- workspace/skills/coreml-embed/tests/fixtures/max1.json

### Runner contract
- stdin JSON inference request with: model_path, texts[], max_text_chars, compute_units.
- stdout JSON success: ok=true, model_path, dims, embeddings, latency_ms.
- stdout JSON failure: ok=false, error{type,message,details}.
- Health mode: --health --model_path <...> with IO compatibility check.

### Skill contract and safeguards
- CLI: node workspace/skills/coreml-embed/dist/cli.js
- Health passthrough: --health
- Typed errors at skill layer: RUNNER_MISSING, RUNNER_BUILD_FAILED, RUNNER_TIMEOUT, CONCURRENCY_LIMIT, INVALID_ARGS.
- Runner errors are surfaced as-is (e.g., MODEL_NOT_FOUND).
- Concurrency guard: PID files under workspace/skills/coreml-embed/.run/coreml-embed with stale cleanup and TTL (OPENCLAW_COREML_EMBED_PID_TTL_MS, default 600000ms).

### Commands run + key outcomes
- node --test workspace/skills/coreml-embed/tests/*.test.js
  - PASS (5 tests, 0 failures)
- node --test workspace/skills/**/tests/*.test.js
  - PASS (25 tests, 0 failures)
- bash workspace/runners/coreml_embed_runner/run.sh --health --model_path /tmp/does-not-exist.mlpackage
  - Output: {"ok":false,"error":{"type":"MODEL_NOT_FOUND","message":"model_path does not exist",...}}
- printf '{...}' | node workspace/skills/coreml-embed/dist/cli.js
  - Output: {"ok":false,"error":{"type":"MODEL_NOT_FOUND","message":"model_path does not exist",...}}

### Notable implementation assumptions
- IO detection is best-effort and intentionally strict for MVP:
  - input: first String feature
  - output: first MLMultiArray feature
  - otherwise returns UNSUPPORTED_MODEL_IO with discovered input/output metadata.

### Rollback
- Revert in reverse order after merge:
  - git revert <docs-audit-sha>
  - git revert <skills-sha>
  - git revert <runner-sha>
