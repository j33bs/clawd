# Dali Telegram Gateway Repo Alignment

UTC: 2026-02-27

## Objective
Align Telegram-serving gateway execution to repo runtime (`~/src/clawd`), enforce local-first provider defaults, and verify Telegram response path.

## Before (service drift)
Evidence: `workspace/audit/evidence/telegram_service_provenance_systemctl_20260227T110451Z.txt`

Observed:
- `ExecStart=/home/jeebs/.local/bin/openclaw gateway --port 18789`
- `WorkingDirectory=!/home/jeebs`
- Environment had non-local-first defaults from drop-ins:
  - `OPENCLAW_PROVIDER_ALLOWLIST=local_vllm,minimax-portal`
  - `OPENCLAW_DEFAULT_PROVIDER=minimax-portal`

## Changes Applied
### Repo-tracked
- Added `scripts/run_openclaw_gateway_repo_dali.sh`
  - `set -euo pipefail`
  - resolves repo root and `cd`s into it
  - sets `OPENCLAW_QUIESCE=0`
  - defaults local-first only when unset:
    - `OPENCLAW_PROVIDER_ALLOWLIST=local_vllm`
    - `OPENCLAW_DEFAULT_PROVIDER=local_vllm`
  - startup marker:
    - `gateway_repo_runner: repo=<path> head=<sha> allowlist=<value>`
  - runs `openclaw gateway --port ...` using the canonical wrapper, which resolves to repo runtime (`~/.local/bin/openclaw.real -> /home/jeebs/src/clawd/.runtime/openclaw/openclaw.mjs`)
- Added `tools/check_gateway_points_to_repo.sh`
  - verifies user unit `ExecStart` resolves to repo runner
  - verifies `WorkingDirectory` resolves to repo root
- Wired checker into `workspace/scripts/verify_preflight.sh`

### Local-only systemd override (documented)
- Added drop-ins under:
  - `/home/jeebs/.config/systemd/user/openclaw-gateway.service.d/20-repo-runner.conf`
  - `/home/jeebs/.config/systemd/user/openclaw-gateway.service.d/zzzzz-repo-runner-final.conf`
- Final effective service:
  - `ExecStart=/home/jeebs/src/clawd/scripts/run_openclaw_gateway_repo_dali.sh`
  - `WorkingDirectory=/home/jeebs/src/clawd`
  - local-first env defaults enforced

## Verification
### Service target and runtime alignment
Evidence: `workspace/audit/evidence/telegram_gateway_wrapper_fix_verify_20260227T112119Z.txt`

Confirmed:
- `./tools/check_gateway_points_to_repo.sh` => `ok`
- `systemctl --user show` reports:
  - `ExecStart ... /home/jeebs/src/clawd/scripts/run_openclaw_gateway_repo_dali.sh`
  - `WorkingDirectory=/home/jeebs/src/clawd`
  - `NRestarts=0`
- Journal shows startup marker line:
  - `gateway_repo_runner: repo=/home/jeebs/src/clawd head=5ed6cb9 allowlist=local_vllm`
- Hardening startup confirms deterministic provider surface:
  - `anthropicEnabled:false`

### Health checks
Evidence:
- `workspace/audit/evidence/telegram_gateway_wrapper_fix_verify_20260227T112119Z.txt` (`curl -sf http://127.0.0.1:18789/health` success)
- `workspace/audit/evidence/telegram_openclaw_health_20260227T113551Z.txt` (`openclaw health` exit 0)

### Telegram e2e
Evidence directory: `workspace/audit/evidence/telegram_e2e_20260227T112238Z/`

- Sandbox run showed CLI network-limit failures (`telegram_e2e.txt`), while gateway log still showed active Telegram provider.
- Escalated live-surface probe succeeded deterministically:
  - `telegram_send_escalated_20260227T113051Z.txt`
  - `openclaw message send --channel telegram --target 8159253715 ... --json`
  - Result payload:
    - `"ok": true`
    - `"messageId": "943"`
    - `"chatId": "8159253715"`

## Regression tests
- Node: `workspace/audit/evidence/telegram_alignment_node_test_20260227T112321Z.txt`
  - `pass 60`, `fail 0`, `NODE_TEST_EXIT=0`
- Python: `workspace/audit/evidence/telegram_alignment_python_test_20260227T112334Z.txt`
  - `Ran 276 tests`, `OK`, `PYTHON_TEST_EXIT=0`

## Rollback
1. Repo changes:
   - `git revert <commit_sha>`
2. Local systemd override rollback:
   - remove/drop repo-runner drop-ins:
     - `/home/jeebs/.config/systemd/user/openclaw-gateway.service.d/20-repo-runner.conf`
     - `/home/jeebs/.config/systemd/user/openclaw-gateway.service.d/zzzzz-repo-runner-final.conf`
   - `systemctl --user daemon-reload`
   - `systemctl --user restart openclaw-gateway.service`
