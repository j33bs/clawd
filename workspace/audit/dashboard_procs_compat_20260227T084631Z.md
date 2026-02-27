# Dashboard procs compatibility alias

timestamp_utc: 20260227T084631Z
branch: codex/fix/dashboard-procs-20260227T083957Z
head_before_commit: f25c42e

## Symptom
- `openclaw dashboard procs` does not resolve in current CLI build (`too many arguments for 'dashboard'`).
- Legacy callers expecting `GET /api/procs` hit edge `api_not_found` behavior before this change.

## Route mismatch
- Canonical process route is upstream RPC namespace (`/rpc/procs`).
- Added edge compatibility alias: `GET /api/procs` forwards upstream as `GET /rpc/procs`.

## Safety invariants
- Kept machine-surface hardening intact.
- Alias remains inside existing auth/rate-limit/inflight/invariant guardrails.
- Response content-type remains JSON-only; HTML fallback not introduced.

## Verification
- `node --check scripts/system2_http_edge.js` passed.
- `node --test tests/dashboard_procs_compat.test.js` passed.
- `OPENCLAW_LOCAL_GATES=1 tools/run_checks.sh || true` completed; local gates passed, broader suite baseline output captured.
- `openclaw dashboard procs` output:
  - `error: too many arguments for 'dashboard'. Expected 0 arguments but got 1.`
- `OPENCLAW_DEBUG=1 openclaw dashboard procs 2>&1 | tail -n 80` output:
  - `error: too many arguments for 'dashboard'. Expected 0 arguments but got 1.`
- `curl -si http://127.0.0.1:18789/api/procs | head -n 40` output:
  - *(no output; target listener was down at capture time)*
