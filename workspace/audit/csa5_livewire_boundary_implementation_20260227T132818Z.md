# CSA5 Livewire Boundary Implementation (Dali)

## Objective
Implemented structural CANON/LIVEWIRE separation to prevent dirty-repo hard stops in CANON while preserving a dirty-permitted LIVEWIRE space with auditable snapshots.

## Baseline discovery (before changes)
Commands run:
- `date -Is`
- `git rev-parse --show-toplevel`
- `git status --porcelain=v1`
- `git branch --show-current`
- `git rev-parse HEAD`
- `ls -la .`

Observed baseline:
- Branch: `main`
- HEAD: `6c6a52d0d74c550b92026f0cdeed8cf81b15d2d2`
- Dirty path: `tools/apply_tailscale_serve_dashboard.sh`

Captured BEFORE snapshot:
- `workspace/audit/worktree_dirty_snapshot_20260227T132118Z_BEFORE.md`

Then restored unexpected dirty tracked file:
- `git checkout -- tools/apply_tailscale_serve_dashboard.sh`

## Implemented topology + scripts
Created:
- `tools/bootstrap_livewire_worktree.sh`
- `tools/print_worktree_mode.sh`
- `tools/guard_worktree_boundary.sh`
- `tools/promote_livewire_patch.sh`
- `tools/worktree_dirty_allowlist.txt`
- `tools/tests/test_worktree_boundary.sh`

Wired guard at entrypoints:
- `scripts/run_openclaw_gateway_repo_dali.sh`
- `tools/apply_tailscale_serve_dashboard.sh`
- `workspace/scripts/rebuild_runtime_openclaw.sh`

Guard behavior implemented:
- Clean -> exit 0
- LIVEWIRE dirty -> snapshot + exit 0
- CANON dirty:
  - allowlisted-only -> snapshot + exit 0
  - non-allowlisted -> snapshot, auto-repair (`git restore --staged .`, `git restore .`), fail with explicit remaining paths if still dirty
- Snapshot truncation logic for `git diff` > 2000 lines (first 500 + last 200)

## Bootstrap + deterministic tests
Executed:
- `bash tools/bootstrap_livewire_worktree.sh`
- `bash tools/tests/test_worktree_boundary.sh`

Results:
- Bootstrap created/confirmed: `/home/jeebs/src/clawd/.worktrees/livewire`
- Test output: `ok`
- Deterministic behaviors verified:
  - CANON mode auto-restores tracked dirt and emits snapshot
  - LIVEWIRE mode preserves dirt and emits snapshot

## Demonstration evidence (isolated worktrees)
Executed isolated demonstration for explicit behavior trace:
- CANON test worktree:
  - before dirty: clean
  - after dirty: `M README.md`
  - after guard: only snapshot artifact remained (`worktree_dirty_snapshot_*_CANON.md`)
- LIVEWIRE test worktree:
  - after dirty: `M README.md`
  - after guard: `M README.md` persisted plus snapshot (`worktree_dirty_snapshot_*_LIVEWIRE.md`)

## Mode and worktree verification
Executed:
- `git worktree list`
- `bash tools/print_worktree_mode.sh` from CANON
- `bash tools/print_worktree_mode.sh` from `.worktrees/livewire`

Observed:
- CANON prints `CANON`
- LIVEWIRE prints `LIVEWIRE`
- livewire worktree registered at `.worktrees/livewire`

## Rollback
If full rollback is needed:
1. Revert commit containing this change set:
   - `git revert <commit_sha>`
2. Remove LIVEWIRE worktree:
   - `git worktree remove .worktrees/livewire`
   - `git branch -D livewire` (optional)
3. Remove local exclude line manually from `.git/info/exclude`:
   - `.worktrees/`
4. Remove created scripts/files if needed (via git revert or explicit restore).

## Notes
- No service stop/restart was performed.
- No network auth or tailscale ACL mutation was performed.
- Changes are localized and reversible.
