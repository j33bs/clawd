# Restore Quarantined Tree

## Apply tracked changes
```bash
git apply tracked_worktree.patch
git apply staged_index.patch   # only if you had staged changes
```

## Restore untracked files
```bash
tar -xzf untracked_files.tgz
```

## Verify
```bash
git status --porcelain=v1 -uall
```
