# Design Brief: Filesystem guardrail for repo-scoped reads

Date: 2026-02-05

## What
Introduce a guarded filesystem helper that:
- Resolves all paths against a single workspace root.
- Denies reads for macOS sandbox paths (Library, Autosave, Containers, DerivedData).
- Blocks access outside the repo unless explicitly allowed.
- Provides safe fallbacks to repo-visible paths when a deny occurs.

## Why
Recent failures came from unintended probes into macOS sandbox paths. A guardrail prevents drift, enforces repo-scoped reads, and keeps behavior auditable and reversible.

## Constraints
- Preserve existing behavior for repo-relative reads.
- Do not require Full Disk Access or non-repo reads by default.
- Keep changes minimal and localized to script file I/O helpers.
- Provide a simple regression check.
