# C_Lawd CSA Tightening Admission

- PR: [#57](https://github.com/j33bs/clawd/pull/57)
- Branch: `codex/harden/c_lawd-csa-tightening-20260227`
- Commit range included: `ab35490..b94db1b`
- Included commits:
  - `d7244ff` phase 1 localhost verification record
  - `4f1f4ca` hardened tailscale serve wrapper + evidence
  - `05926ed` reversible launchagent install script
  - `5e9f221` phase 4 cross-node verification record
  - `049826c` phase 5 hardening checks record
  - `226a6d3` phase 6 rollback runbook
  - `b94db1b` phase 7 hygiene closeout

## Hardening Phase Summary

- Phase 0: Baseline snapshot/evidence capture.
- Phase 1: Confirmed loopback-only gateway binding.
- Phase 2: Added explicit, loopback-guarded tailscale serve wrapper.
- Phase 3: Added reversible launchd persistence script (`0600` plist, apply opt-in).
- Phase 4: Cross-node verification captured (direct LAN/tailnet-IP access remained blocked).
- Phase 5: Hardening checks recorded (`tailnet only` serve proxy to loopback).
- Phase 6: Rollback runbook documented (intentionally not executed during tightening).
- Phase 7: Git hygiene/minimal-diff closeout.

## Verification Results

- `git fetch --all --prune`: PASS
- Working branch check (`git branch --show-current`): PASS (`codex/harden/c_lawd-csa-tightening-20260227`)
- Clean worktree check (`git status --porcelain=v1`): PASS (clean at verification start)
- Targeted tests: PASS
  - Command: `node --test tests/install_tailscale_serve_launchagent.test.js tests/tailscale_serve_openclaw.test.js`
  - Result: `tests=5 pass=5 fail=0` (duration ~598ms)

## Reversible Rollout Confirmation

- Serve persistence apply remains explicit opt-in (`OPENCLAW_TAILSCALE_SERVE_LAUNCHCTL_APPLY=1`).
- Rollback commands are documented in phase 6 and can fully disable serve persistence/state.

## Residual Risks

- Environment-dependent tailscale CLI behavior was observed during parts of the run (`Failed to load preferences`), so live tailscale-state checks may require operator environment validation.
- Health probe responsiveness (`127.0.0.1:18789/health`) was not consistently reachable during captured evidence windows and remains an operational dependency outside this docs finalization.
