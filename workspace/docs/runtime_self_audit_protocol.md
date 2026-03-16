# Runtime Self-Audit Protocol

Status: lightweight protocol for reducing path/runtime drift.

## Goal
Make it harder to confuse:
- repo intent vs live runtime behavior
- tracked artifacts vs generated runtime state
- request/UI gesture vs completed backend side effect

## Minimum audit before a claim
1. **Name the surface**
   - repo file
   - local runtime endpoint
   - background job artifact
   - external surface
2. **Check the live path**
   - example: served Source UI is `workspace/source-ui/static/`, not duplicate JS trees by default.
3. **Check a receipt**
   - endpoint field, file mtime, command output, job artifact timestamp, task id.
4. **State the claim at the right strength**
   - requested
   - observed locally
   - verified live
   - pushed

## Claim language
- **Requested only** — UI action exists but no backend receipt.
- **Observed locally** — file changed or process output seen in this workspace.
- **Verified live** — endpoint/process/artifact confirms runtime behavior.
- **Pushed** — remote push/PR/receipt exists.

## Common drift traps here
- Duplicate frontend trees with only one actually served.
- Demo fallback data looking “live”.
- Runtime sinks in `workspace/state_runtime/*` vs tracked stubs in `workspace/state/*`.
- Dirty worktree context causing accidental overclaim about what this change did.

## Small operational rule
If a user-facing surface can cheaply expose provenance, do it:
- truth source
- canonical file/path
- last updated timestamp

That turns hidden assumptions into inspectable state.
