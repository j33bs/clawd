# scaffold-apply

Apply a structured plan locally with per-step git commits.

## Usage
```bash
node {baseDir}/dist/cli.js < plan.json
```

### Dry run
```bash
cat plan.json | node {baseDir}/dist/cli.js
```
(with `"dry_run": true` in input)

## Input
- `target_dir` (required): git worktree/repo path
- `plan[]` of `{file, operation, content?, rationale}`

## Behavior
- Validates input schema manually (no external deps).
- Refuses path traversal outside `target_dir`.
- `create|delete|patch` supported.
- Commits each successful step individually.
- Stops at first failure; prior commits are preserved.
