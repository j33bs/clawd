# Proposal: Filesystem guardrail for repo-scoped reads

Date: 2026-02-05

Goal: Prevent System-2 tooling from probing macOS sandbox paths by enforcing a repo-root base path and denylist checks for file reads.

Scope:
- Add a guarded filesystem helper in scripts.
- Refactor script file reads to resolve under a single workspace root.
- Add a minimal regression check script.
