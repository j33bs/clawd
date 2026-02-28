# Dali Security Hardening Audit

- UTC Timestamp: 20260227T232332Z

## git rev-parse HEAD
6d9246bcd4c62a1755061b3cf72ff9c661e2518f

## git status --porcelain
?? scripts/tailscale_serve_openclaw.sh
?? workspace/audit/dali_security_hardening_20260227T232332Z.md

## node --version ; python3 --version
v22.22.0
Python 3.12.3

## systemctl --user status openclaw-gateway.service --no-pager || true
● openclaw-gateway.service - OpenClaw Gateway (user-owned)
     Loaded: loaded (/home/jeebs/.config/systemd/user/openclaw-gateway.service; enabled; preset: enabled)
    Drop-In: /home/jeebs/.config/systemd/user/openclaw-gateway.service.d
             └─10-provider-lock.conf, 20-repo-runner.conf, 99-userprefix-execstart.conf, override.conf, zzzz-userprefix-execstart.conf, zzzzz-repo-runner-final.conf
     Active: active (running) since Sat 2026-02-28 06:54:28 AEST; 2h 29min ago
   Main PID: 8774 (openclaw)
      Tasks: 38 (limit: 38169)
     Memory: 592.7M (peak: 2.6G)
        CPU: 52.855s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/openclaw-gateway.service
             ├─8774 openclaw
             └─8825 openclaw-gateway

Feb 28 09:01:53 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: **Warning (1):**
Feb 28 09:01:53 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: - No auth rate limiting — vulnerable to brute force
Feb 28 09:01:53 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: **Fixes:**
Feb 28 09:01:53 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: 1. Set `gateway.controlUi.allowedOrigins` to your trusted domain(s)
Feb 28 09:01:53 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: 2. Set `gateway.auth.rateLimit` (e.g., `{ maxAttempts: 10, windowMs: 60000 }`)
Feb 28 09:01:53 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: Want me to apply these fixes now?
Feb 28 09:02:29 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: 2026-02-28T09:02:29.879+10:00 ⚠️ System monitor: coder_vllm (port 8002) is down — connection refused.
Feb 28 09:02:29 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: Everything else fine — main vLLM, gateway, disk, memory all good.
Feb 28 09:02:29 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: Want me to restart the coder instance?
Feb 28 09:03:22 jeebs-Z490-AORUS-MASTER run_openclaw_gateway_repo_dali.sh[8825]: 2026-02-28T09:03:22.619+10:00 Consciousness: feeling good, actively processing

## tailscale status
100.113.160.1  jeebs-z490-aorus-master  heathyeager@  linux  -                    
100.84.143.50  heaths-macbook-pro       heathyeager@  macOS  idle, tx 276 rx 404  

## tailscale serve status || true
https://jeebs-z490-aorus-master.tail5e5706.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:18789


## PLAN (CSA-3 Plan/Apply split)

1. Files to touch (exact paths)
- /home/jeebs/src/clawd/tools/gateway_security_hardening_patch.mjs
- /home/jeebs/src/clawd/tools/apply_gateway_security_hardening.sh
- /home/jeebs/src/clawd/scripts/run_openclaw_gateway_repo_dali.sh
- /home/jeebs/src/clawd/tests/gateway_security_hardening_patch.test.js
- /home/jeebs/src/clawd/tools/run_security_gates.sh
- /home/jeebs/src/clawd/workspace/audit/dali_security_hardening_20260227T232332Z.md

2. New config keys + defaults
- `gateway.auth.rateLimit` default: `{ "maxAttempts": 10, "windowMs": 60000 }` (server-side auth limiter enabled by default)
- `gateway.controlUi.allowedOrigins` behavior hardening:
  - `production`: explicit allowlist required; empty/missing denies non-loopback browser origins
  - `development`/`test`: default localhost allowlist (`http://127.0.0.1:<port>`, `http://localhost:<port>`) when explicit list not provided
  - wildcard and non-http(s) entries rejected during normalization

3. Test plan (exact commands)
- `node --test tests/gateway_security_hardening_patch.test.js`
- `bash tools/run_security_gates.sh`
- `npm test`
- `python3 -m unittest -v`
- `bash workspace/scripts/verify_preflight.sh`

4. Rollback plan (exact commands)
- Runtime rollback (non-destructive):
  - `git revert <hardening_commit_sha>`
  - `systemctl --user restart openclaw-gateway.service`
- If runtime patching was applied and immediate reset is needed before revert:
  - `OPENCLAW_SOURCE_DIR=/usr/lib/node_modules/openclaw OPENCLAW_RUNTIME_DIR=/home/jeebs/src/clawd/.runtime/openclaw bash workspace/scripts/rebuild_runtime_openclaw.sh`

## APPLY — Implemented Changes

### Fix A: Control UI `allowedOrigins` hardening

- Located enforcement in runtime gateway bundle (`.runtime/openclaw/dist/gateway-cli-*.js`) at origin-check and runtime-config load paths.
- Added strict normalization and validation through deterministic patching:
  - trim entries
  - reject empty
  - reject wildcard patterns (`*`)
  - reject non-http(s) schemes
- Enforced stricter behavior:
  - explicit allowlist is authoritative
  - production cross-origin remains denied unless explicitly allowed
  - development/test keeps localhost-only fallback when explicit allowlist is empty

### Fix B: auth rate limiting

- Enabled server-side auth limiter by default for gateway auth checks by patching runtime construction logic.
- Defaulted limiter config to:
  - `maxAttempts: 10`
  - `windowMs: 60000`
- Browser auth limiter remains active with `exemptLoopback: false`.

### CSA-3 scaffolding

- Added deterministic patch tool:
  - `tools/gateway_security_hardening_patch.mjs`
- Added apply wrapper:
  - `tools/apply_gateway_security_hardening.sh`
- Wired runner to apply patch before gateway start:
  - `scripts/run_openclaw_gateway_repo_dali.sh`
- Added deterministic security gate script:
  - `tools/run_security_gates.sh`
- Added focused unit tests:
  - `tests/gateway_security_hardening_patch.test.js`

## Regression and Gate Results

### Targeted tests

- `node --test tests/gateway_security_hardening_patch.test.js` → PASS
- `bash tools/run_security_gates.sh` → PASS

### Full regression

- `npm test` → PASS (`OK 43 test group(s)`)
- `python3 -m unittest -v` → PASS (`Ran 276 tests`, `OK`, `skipped=1`)

### Integrity/preflight guard

- `bash workspace/scripts/verify_preflight.sh` initially failed while repo was intentionally dirty during apply phase and gateway service restart was blocked by CANON guard.
- Resolution: stage/commit changes to restore clean tree, restart gateway service, rerun preflight.

## Operational Notes

- One-time privileged Tailscale operator setup may be required on this host for non-root serve writes:
  - `sudo tailscale set --operator=jeebs`
- This command was documented only and was **not executed** in this task.

## Evidence Command Block

~~~bash
git rev-parse HEAD
git status --porcelain
bash tools/run_security_gates.sh
npm test
python3 -m unittest -v
bash workspace/scripts/verify_preflight.sh
systemctl --user status openclaw-gateway.service --no-pager
curl -sf http://127.0.0.1:18789/health
tailscale status
tailscale serve status
~~~

## Rollback

~~~bash
git revert HEAD
systemctl --user restart openclaw-gateway.service
~~~

If runtime patching must be reset before/without git revert:

~~~bash
OPENCLAW_SOURCE_DIR=/usr/lib/node_modules/openclaw OPENCLAW_RUNTIME_DIR=/home/jeebs/src/clawd/.runtime/openclaw bash workspace/scripts/rebuild_runtime_openclaw.sh
~~~

## Final Verification (Post-Commit)

- Commit: `HEAD` (resolved at verification time)
- Gateway service recovery after patch idempotency fix: PASS
  - `systemctl --user status openclaw-gateway.service` => `active (running)`
  - startup log includes: `PATCH_NOOP /home/jeebs/src/clawd/.runtime/openclaw/dist/gateway-cli-Bs_SXkBW.js`
  - bundle coverage check: both `gateway-cli-Bs_SXkBW.js` and `gateway-cli-DVgFqyNu.js` report `PATCH_OK`
- Local health endpoint:
  - `curl http://127.0.0.1:18789/health` => `HTTP 200`
- Preflight integrity guard:
  - `bash workspace/scripts/verify_preflight.sh` => `EXIT=0`

### Failure + Resolution Notes

1. Service restart failed during APPLY while worktree was dirty (CANON guard); expected and resolved by committing changes.
2. Service restart then failed because patcher was non-idempotent on already-patched runtime bundle.
3. Added idempotent early-exit (`PATCH_NOOP`) in patch tool; service restart succeeded.
