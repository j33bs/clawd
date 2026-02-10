# Secret Scrub & Audit Runbook

Use this workflow to detect and remediate secret-like material without printing values.

## 1) Scan

Run:

```powershell
pwsh -File scripts/scrub_secrets.ps1
```

This writes:

- `scrub_worktree_hits.txt` (`path:line` only)
- `scrub_history_candidates.txt` (commit hashes + candidate paths)
- `scrub_history_files.txt` (unique candidate paths)

Record counts only:

- `WORKTREE hits: N`
- `History files implicated: N`

Do not paste match content, file contents, or snippets into tickets, chat, or logs.

## 2) Decision Rule

- If `WORKTREE hits > 0`: run worktree redaction and scan again.
- If `History files implicated > 0`: perform history rewrite.
- If both are `0`: proceed with normal review/push flow.

## 3) Worktree Redaction

Run:

```powershell
python scripts/redact_worktree_hits.py
pwsh -File scripts/scrub_secrets.ps1
```

The redactor:

- reads `scrub_worktree_hits.txt`
- applies secret pattern replacement with `[REDACTED_SECRET]`
- creates per-file `*.bak` backups
- prints counts only

## 4) History Rewrite (filter-repo)

Before rewriting:

```powershell
git branch backup/pre-secret-scrub-$(Get-Date -Format yyyyMMdd-HHmmss)
```

Preferred for disposable artifacts (drop paths everywhere):

```powershell
git filter-repo --path openclaw.json --path secrets.env --invert-paths
```

For non-disposable files, use replace rules (pattern-only, no literal secrets):

```text
regex:(pattern_only_here)==>[REDACTED_SECRET]
```

Then:

```powershell
git filter-repo --replace-text .\replace-rules.txt
```

After rewrite, rerun the scrub scan and only then push:

```powershell
pwsh -File scripts/scrub_secrets.ps1
git push --force-with-lease
```

Never weaken scanners/hooks and never include real secrets or secret-shaped placeholders.
