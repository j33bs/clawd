# Proposal D — Minimal GitHub Actions regression gate

timestamp_utc: 20260227T053243Z
Intent: Enforce regression on push/PR (warn-only).
Scope: .github/workflows/regression-gate.yml
Safety: continue-on-error true (non-blocking); reversible via git revert.
Verification: workflow triggers on next push/PR and completes.
