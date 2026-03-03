# Governance State

## CSA Status Update (C_Lawd)
- previous level estimate: CSA-L2
- new level estimate: CSA-L3
- justification:
  - Loopback-only gateway exposure invariant is explicitly preserved and re-verified.
  - Tailscale serve configuration is constrained to explicit path proxying to `127.0.0.1:18789`.
  - Persistence path is reversible and operator-controlled (launchctl apply is opt-in).
  - Targeted hardening tests for serve and launchagent scripts passed in admission verification.
  - Rollback steps are documented and retained as an explicit runbook.
- next required invariants for CSA progression:
  - Demonstrate consistent health endpoint responsiveness under the hardened serve path.
  - Re-verify tailscale CLI state checks from an environment without preferences/runtime constraints.
  - Add/retain deterministic gate coverage for loopback-only bind and non-loopback rejection invariants.
  - Preserve reversible rollout evidence for any further exposure or automation changes.
