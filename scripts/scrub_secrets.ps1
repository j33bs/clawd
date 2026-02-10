Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$gitExe = $null
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if ($null -ne $gitCmd) {
  $gitExe = $gitCmd.Source
}
if ([string]::IsNullOrWhiteSpace($gitExe)) {
  try {
    $cmdWhereMatches = @(cmd.exe /c where git 2>$null)
    $cmdWhereGit = ($cmdWhereMatches | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1)
    if (-not [string]::IsNullOrWhiteSpace($cmdWhereGit)) {
      $cmdWhereGit = $cmdWhereGit.Trim()
      if (Test-Path -LiteralPath $cmdWhereGit) {
        $gitExe = $cmdWhereGit
      }
    }
  } catch {
  }
}
if ([string]::IsNullOrWhiteSpace($gitExe)) {
  $whereMatches = @(where.exe git 2>$null)
  $whereGit = $null
  if ($whereMatches.Count -gt 0) {
    $whereGit = $whereMatches[0]
  }
  if (-not [string]::IsNullOrWhiteSpace($whereGit)) {
    $whereGit = $whereGit.Trim()
    if (Test-Path -LiteralPath $whereGit) {
      $gitExe = $whereGit
    }
  }
}
if ([string]::IsNullOrWhiteSpace($gitExe)) {
  $gitCandidates = @()
  if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
    $gitCandidates += Join-Path $env:ProgramFiles "Git\cmd\git.exe"
    $gitCandidates += Join-Path $env:ProgramFiles "Git\bin\git.exe"
    $gitCandidates += Join-Path $env:ProgramFiles "Git1\cmd\git.exe"
    $gitCandidates += Join-Path $env:ProgramFiles "Git1\bin\git.exe"
  }
  if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles(x86)})) {
    $gitCandidates += Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe"
    $gitCandidates += Join-Path ${env:ProgramFiles(x86)} "Git\bin\git.exe"
  }
  if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    $gitCandidates += Join-Path $env:LOCALAPPDATA "Programs\Git\cmd\git.exe"
    $gitCandidates += Join-Path $env:LOCALAPPDATA "Programs\Git\bin\git.exe"
  }
  if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $gitCandidates += Join-Path $env:USERPROFILE "scoop\apps\git\current\cmd\git.exe"
  }
  if (-not [string]::IsNullOrWhiteSpace($env:ChocolateyInstall)) {
    $gitCandidates += Join-Path $env:ChocolateyInstall "bin\git.exe"
  }
  foreach ($candidate in $gitCandidates) {
    if (Test-Path -LiteralPath $candidate) {
      $gitExe = $candidate
      break
    }
  }
}
if ([string]::IsNullOrWhiteSpace($gitExe)) {
  $desktopGitCandidates = @()
  if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    $desktopGitCandidates += @(
      Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "GitHubDesktop") -Directory -Filter "app-*" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      ForEach-Object { Join-Path $_.FullName "resources\app\git\cmd\git.exe" }
    )
    $desktopGitCandidates += @(
      Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "GitHub") -Directory -Filter "PortableGit_*" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      ForEach-Object { Join-Path $_.FullName "cmd\git.exe" }
    )
  }
  foreach ($candidate in $desktopGitCandidates) {
    if (Test-Path -LiteralPath $candidate) {
      $gitExe = $candidate
      break
    }
  }
}
if ([string]::IsNullOrWhiteSpace($gitExe)) {
  throw "git.exe not found. Install Git for Windows or ensure git is on PATH."
}

try {
  $repoRoot = (& $gitExe rev-parse --show-toplevel 2>$null).Trim()
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

$pattern = "(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z\-_]{35}|-----BEGIN[ A-Z_-]{0,20}K[E]Y-----|bearer\s+[A-Za-z0-9._\-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"

$rawWorktree = @()
$grepExitCode = $null
Push-Location -LiteralPath $repoRoot
try {
  $rawWorktree = & $gitExe grep -nEi --no-color -- $pattern -- . 2>$null
  $grepExitCode = $LASTEXITCODE
} finally {
  Pop-Location
}
if ($grepExitCode -eq 1) {
  $rawWorktree = @()
} elseif ($null -eq $grepExitCode -or $grepExitCode -gt 1) {
  throw "git grep failed."
} else {
  $rawWorktree = @(
    @($rawWorktree) |
    Where-Object {
      if ($_ -notmatch '^([^:]+):') {
        return $false
      }
      $filePath = ($Matches[1] -replace '\\', '/')
      $filePath -notmatch '(^|/)node_modules/' -and $filePath -notmatch '(^|/)\.git/'
    }
  )
}

$worktreeHits = @()
foreach ($line in @($rawWorktree)) {
  if ($line -match '^([^:]+:[0-9]+):') {
    $worktreeHits += $Matches[1]
  }
}
Set-Content -LiteralPath $worktreeOut -Encoding UTF8 -Value $worktreeHits

$historyTokens = @("sk-", "ghp_", "xox", "AIza", "-----BEGIN", "Bearer ", "eyJ")
$historyCandidates = New-Object System.Collections.Generic.List[string]
$historyFilesSet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$excludePathPattern = '(^|/)(node_modules|\.git|dist|build|\.next|coverage)(/|$)'

foreach ($token in $historyTokens) {
  $tmpStdout = [System.IO.Path]::GetTempFileName()
  $tmpStderr = [System.IO.Path]::GetTempFileName()
  try {
    & $gitExe -C $repoRoot log --all --pretty=format:%H --name-only --no-textconv -S $token -- . ':(exclude)*.docx' ':(exclude)*.pdf' ':(exclude)*.png' ':(exclude)*.jpg' ':(exclude)*.jpeg' ':(exclude)*.gif' ':(exclude)*.webp' ':(exclude)*.zip' ':(exclude)*.7z' ':(exclude)*.rar' ':(exclude)*.mp4' ':(exclude)*.mov' ':(exclude)*.wav' ':(exclude)*.mp3' ':(exclude)*.exe' ':(exclude)*.dll' 1>$tmpStdout 2>$tmpStderr
    $historyExitCode = $LASTEXITCODE
    if ($historyExitCode -ne 0) {
      throw "git log history scan failed for token '$token' (exit $historyExitCode)."
    }

    $currentCommit = $null
    foreach ($rawLine in Get-Content -LiteralPath $tmpStdout) {
      $line = $rawLine.Trim()
      if ($line -eq "") {
        continue
      }
      if ($line -match '^[0-9a-fA-F]{40}$') {
        $currentCommit = $line.ToLowerInvariant()
        continue
      }
      if ($null -eq $currentCommit) {
        continue
      }
      $normalizedPath = ($line -replace '\\', '/')
      if ($normalizedPath -match $excludePathPattern) {
        continue
      }
      $historyCandidates.Add("$token`t$currentCommit`t$normalizedPath")
      [void]$historyFilesSet.Add($normalizedPath)
    }
  } finally {
    Remove-Item -LiteralPath $tmpStdout -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmpStderr -Force -ErrorAction SilentlyContinue
  }
}

Set-Content -LiteralPath $historyCandidatesOut -Encoding UTF8 -Value @($historyCandidates)
$historyFiles = @($historyFilesSet | Sort-Object)
Set-Content -LiteralPath $historyFilesOut -Encoding UTF8 -Value $historyFiles

Write-Output "worktree_hits_count: $($worktreeHits.Count)"
Write-Output "history_candidates_count: $($historyCandidates.Count)"
Write-Output "history_unique_files_count: $($historyFiles.Count)"
