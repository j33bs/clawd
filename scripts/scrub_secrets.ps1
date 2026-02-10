Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
  $repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
} catch {
  Write-Error "Not a git repository. Run this script from inside the repo."
  exit 1
}

if ([string]::IsNullOrWhiteSpace($repoRoot)) {
  Write-Error "Not a git repository. Run this script from inside the repo."
  exit 1
}

$worktreeOut = Join-Path $repoRoot "scrub_worktree_hits.txt"
$historyCandidatesOut = Join-Path $repoRoot "scrub_history_candidates.txt"
$historyFilesOut = Join-Path $repoRoot "scrub_history_files.txt"

$pattern = "(?i)(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z\-_]{35}|-----BEGIN[ A-Z_-]{0,20}K[E]Y-----|bearer\s+[A-Za-z0-9._\-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"

$rawWorktree = @()
$rawWorktree = & git -C $repoRoot grep -nE --no-color -- $pattern -- . ':!node_modules' ':!.git' 2>$null
$grepExitCode = $LASTEXITCODE
if ($null -eq $grepExitCode -or $grepExitCode -gt 1) {
  throw "git grep failed."
}
if ($grepExitCode -eq 1) {
  $rawWorktree = @()
}

$worktreeHits = @()
foreach ($line in @($rawWorktree)) {
  if ($line -match '^([^:]+:[0-9]+):') {
    $worktreeHits += $Matches[1]
  }
}
Set-Content -LiteralPath $worktreeOut -Value $worktreeHits

$rawHistory = & git -C $repoRoot log --all --pretty=format:%H --name-only -G $pattern 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "git log history scan failed."
}
Set-Content -LiteralPath $historyCandidatesOut -Value @($rawHistory)

$historyFiles = @(
  @($rawHistory) |
  ForEach-Object { $_.Trim() } |
  Where-Object { $_ -ne "" -and $_ -notmatch '^[0-9a-fA-F]{40}$' } |
  Sort-Object -Unique
)
Set-Content -LiteralPath $historyFilesOut -Value $historyFiles

Write-Output "WORKTREE hits: $($worktreeHits.Count)"
Write-Output "History files implicated: $($historyFiles.Count)"
