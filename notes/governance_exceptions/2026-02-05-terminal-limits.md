# Governance Exception: Terminal-only change constraint

Date: 2026-02-05

Reason:
- Repository is only writable via Xcode project tools in this environment.
- Terminal shell commands are sandbox-blocked for the repo path.

Exception:
- Changes are applied via Xcode tooling instead of terminal commands.
- Git commit and regression script execution are deferred until shell access is granted.
