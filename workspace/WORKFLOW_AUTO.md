# WORKFLOW_AUTO

Automation guardrails for unattended runs:

1. Run pairing preflight before gateway/sub-agent work:
   - `workspace/scripts/check_gateway_pairing_health.sh`
2. Fail closed on preflight failure; do not auto-approve pairing.
3. Prefer user services and loopback endpoints; avoid privileged changes.
4. Record append-only evidence in `workspace/audit/` for every automated run.
5. Keep cron jobs contract-correct (`payload.kind`) and reversible.
6. Use `OPENCLAW_REPO_ROOT` when host paths differ from defaults.
