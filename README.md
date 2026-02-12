# OpenClaw System Architecture (System-1 + System-2)

OpenClaw in this repo is a governed, git-backed agentic system operated as two co-equal subsystems.

## System Overview

- System-1 (Windows): Tier-0 gateway, CI/audit anchor, and local tool-plane host.
- System-2 (Mac): Co-equal gateway, tool-plane host, and orchestration peer.
- Both systems follow the same routing and governance contracts; neither is a disposable sidecar.

## Architecture

```text
+-----------------------------+        federated RPC         +-----------------------------+
| System-1 (Windows)          | <--------------------------> | System-2 (Mac)              |
| - Gateway (Tier-0)          |  submit / poll / stream /   | - Gateway (peer)            |
| - CI + audit gates          |  cancel                      | - Orchestration peer        |
| - Tool plane host           |                              | - Tool plane host           |
+--------------+--------------+                              +--------------+--------------+
               |                                                            |
               | routing policy contract (inspectable, versioned)           |
               +-------------------------------+----------------------------+
                                               |
                                   +-----------v-----------+
                                   | Execution + Tool Plane|
                                   | MCP allowlists        |
                                   | Sandbox policy        |
                                   +-----------+-----------+
                                               |
                                   +-----------v-----------+
                                   | Memory + Event Logs   |
                                   | Append-only records   |
                                   | Cursor-based sync     |
                                   +-----------------------+
```

## Operational Contracts

- Governance is proposal-first and evidence-first.
- Changes must be reversible and promoted through explicit gates.
- Evidence bundles are required for audit-affecting changes.
- LOAR constraint: scale behavior by policy knobs (routing, budgets, limits), not by changing formats/contracts.

## Windows Canonical Execution

Use `scripts\ps.cmd` as the single PowerShell entrypoint on Windows.

- It prefers `pwsh` when available.
- It falls back to `powershell.exe` when `pwsh` is unavailable.
- It always uses `-NoProfile` and propagates exit codes.

Canonical commands:

```cmd
scripts\ps.cmd -File .\openclaw.ps1 audit system1
scripts\ps.cmd -ExecutionPolicy Bypass -File .\scripts\scrub_secrets.ps1
```

## Gateway Self-Heal (System-1 / Windows)

Symptom:

- Web UI shows disconnected.
- Agent replies fail.
- `openclaw gateway probe` reports unauthorized or token mismatch.

Cause:

- `gateway.auth.token` and `gateway.remote.token` drift apart.
- OpenClaw Gateway Scheduled Task is stopped.

Fix:

```cmd
scripts\ps.cmd -File .\openclaw.ps1 gateway heal
```

Expected script outputs (token-safe):

- `aligned` or `unchanged` from token alignment.
- `started` or `already_running` from gateway task startup.
- `port_in_use` when local port `18789` is occupied by another process.
- `openclaw gateway probe` output without unauthorized token mismatch errors.

Evidence artifacts:

- `.tmp/system1_evidence/gateway_auth_baseline.txt`
- `.tmp/system1_evidence/fix_gateway_auth_result.json`
- `.tmp/system1_evidence/start_gateway_task_result.json`
- `.tmp/system1_evidence/gateway_heal_output.txt`
- `.tmp/system1_evidence/gateway_probe_after_heal.txt`
- `.tmp/system1_evidence/status_after_heal.txt`

Reference troubleshooting guidance:

- `https://docs.openclaw.ai/gateway/troubleshooting`

## Configuration

- Config location: `%USERPROFILE%\.openclaw\openclaw.json`
- Validate config: `openclaw doctor`
- Apply safe automatic repairs: `openclaw doctor --fix`

Memory search rule:

- `agents.defaults.memorySearch.provider` must match a valid enum for the installed build.
- If provider is unknown for the current build, omit `memorySearch.provider` and allow OpenClaw to auto-select/disable until configured.
- For this installed build, valid values are `openai`, `local`, `gemini`, `voyage`.

## Safety and Public-Readiness

- Run secret scrub before PRs and before publishing snapshots.
- Never weaken secret-scanning patterns to suppress findings.
- Keep evidence bundles in `.tmp/system1_evidence/` for review.
- Do not commit `.tmp/` evidence artifacts.
- Keep diffs minimal and include exact rollback commands.

## Quickstart (System-1 / Windows)

1. Install prerequisites: Node.js, Python 3, and OpenClaw CLI on PATH.
2. Validate local config:

```cmd
openclaw doctor
```

3. Run System-1 audit gate:

```cmd
scripts\ps.cmd -File .\openclaw.ps1 audit system1
```

4. Run unit tests:

```cmd
python3 -m unittest discover -s tests_unittest
```

5. Run secret scrub:

```cmd
scripts\ps.cmd -ExecutionPolicy Bypass -File .\scripts\scrub_secrets.ps1
```

Expected local artifacts (review-only, not committed):

- `.tmp/system1_evidence/system1_audit_output.txt`
- `.tmp/system1_evidence/system1_evidence.json`
- `.tmp/system1_evidence/scrub_secrets_output.txt`
- `.tmp/system1_evidence/scrub_history_assessment.json`
- `.tmp/system1_evidence/scrub_worktree_assessment.json`
- `.tmp/system1_evidence/test_results.txt`
- `.tmp/system1_evidence/rollback.md`
