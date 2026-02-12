Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-ProcessCapture {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [string[]]$Arguments = @()
  )

  $tmpStdout = [System.IO.Path]::GetTempFileName()
  $tmpStderr = [System.IO.Path]::GetTempFileName()
  try {
    $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments -NoNewWindow -Wait -PassThru -RedirectStandardOutput $tmpStdout -RedirectStandardError $tmpStderr
    $stdoutLines = @()
    if (Test-Path -LiteralPath $tmpStdout) {
      $stdoutLines = @(Get-Content -LiteralPath $tmpStdout)
    }
    $stderrText = ""
    if (Test-Path -LiteralPath $tmpStderr) {
      $stderrText = (Get-Content -LiteralPath $tmpStderr -Raw)
    }
    return [PSCustomObject]@{
      ExitCode = $proc.ExitCode
      StdoutLines = $stdoutLines
      StdoutText = ($stdoutLines -join "`n")
      StderrText = $stderrText
    }
  } finally {
    Remove-Item -LiteralPath $tmpStdout -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmpStderr -Force -ErrorAction SilentlyContinue
  }
}

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

$repoProbe = Invoke-ProcessCapture -FilePath $gitExe -Arguments @("rev-parse", "--show-toplevel")
if ($repoProbe.ExitCode -ne 0) {
  Write-Error "Not a git repository. Run this script from inside the repo."
  exit 1
}
$repoRoot = $repoProbe.StdoutText.Trim()

if ([string]::IsNullOrWhiteSpace($repoRoot)) {
  Write-Error "Not a git repository. Run this script from inside the repo."
  exit 1
}

$worktreeOut = Join-Path $repoRoot "scrub_worktree_hits.txt"
$historyCandidatesOut = Join-Path $repoRoot "scrub_history_candidates.txt"
$historyFilesOut = Join-Path $repoRoot "scrub_history_files.txt"
$historyAssessmentOut = Join-Path $repoRoot "scrub_history_assessment.json"

$pattern = "(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z\-_]{35}|-----BEGIN[[:space:][:upper:]_-]{0,20}K[E]Y-----|bearer\s+[A-Za-z0-9._\-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"

$historyPatternSpecs = @{
  "sk-" = [PSCustomObject]@{
    PatternId = "openai_sk"
    Regex = "sk-[A-Za-z0-9]{20,}"
  }
  "ghp_" = [PSCustomObject]@{
    PatternId = "github_pat"
    Regex = "ghp_[A-Za-z0-9]{36}"
  }
  "xox" = [PSCustomObject]@{
    PatternId = "slack_token"
    Regex = "xox[baprs]-[A-Za-z0-9-]{10,}"
  }
  "AIza" = [PSCustomObject]@{
    PatternId = "google_api_key"
    Regex = "AIza[0-9A-Za-z\-_]{35}"
  }
  "-----BEGIN" = [PSCustomObject]@{
    PatternId = "pem_private_key"
    Regex = "-----BEGIN[ A-Z_-]{0,20}K[E]Y-----"
  }
  "Bearer " = [PSCustomObject]@{
    PatternId = "bearer_token"
    Regex = "bearer\s+[A-Za-z0-9._~+\/-]{20,}"
  }
  "eyJ" = [PSCustomObject]@{
    PatternId = "jwt_like"
    Regex = "eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
  }
}

function Get-Sha256Prefix {
  param(
    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$Value,
    [int]$PrefixLength = 12
  )
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $hash = $sha.ComputeHash($bytes)
    $hex = -join ($hash | ForEach-Object { $_.ToString("x2") })
    if ($hex.Length -le $PrefixLength) {
      return $hex
    }
    return $hex.Substring(0, $PrefixLength)
  } finally {
    $sha.Dispose()
  }
}

function Resolve-HistoryBlob {
  param(
    [Parameter(Mandatory = $true)]
    [string]$GitExe,
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$Commit,
    [Parameter(Mandatory = $true)]
    [string]$Path
  )
  $candidates = @("${Commit}:$Path", "${Commit}^:$Path")
  foreach ($blobRef in $candidates) {
    $blobResult = Invoke-ProcessCapture -FilePath $GitExe -Arguments @("-C", $RepoRoot, "show", $blobRef)
    if ($blobResult.ExitCode -eq 0) {
      return [PSCustomObject]@{
        Found = $true
        BlobRef = $blobRef
        Text = $blobResult.StdoutText
      }
    }
  }
  return [PSCustomObject]@{
    Found = $false
    BlobRef = $candidates[-1]
    Text = ""
  }
}

function Get-HistoryClassification {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [bool]$HasFullPatternMatch = $false
  )
  $normalizedPath = ($Path -replace '\\', '/').ToLowerInvariant()
  $falsePositiveHints = @(
    "fixtures/",
    "tests/",
    "tests_unittest/",
    "docs/",
    "workspace/docs/",
    "workspace/sources/",
    "notes/",
    "scripts/scrub_secrets.ps1",
    "scripts/redact_",
    "scripts/triage_history_candidates.py",
    "workspace/scripts/verify_env_template_hygiene.sh"
  )
  $riskHints = @(
    "core/",
    "control_plane/",
    "workspace/scripts/",
    "scripts/itc_classify.py"
  )

  $matchesFalsePositiveHint = @($falsePositiveHints | Where-Object { $normalizedPath.Contains($_) }).Count -gt 0
  $matchesRiskHint = @($riskHints | Where-Object { $normalizedPath.Contains($_) }).Count -gt 0

  if ($HasFullPatternMatch) {
    if ($matchesFalsePositiveHint -or $normalizedPath.EndsWith(".md")) {
      return [PSCustomObject]@{
        Classification = "FALSE_POSITIVE"
        Reason = "full credential-like match in documentation/test/tooling path"
      }
    }
    return [PSCustomObject]@{
      Classification = "CREDENTIAL_RISK"
      Reason = "full credential-like match outside approved non-runtime paths"
    }
  }
  return [PSCustomObject]@{
    Classification = "FALSE_POSITIVE"
    Reason = "indicator-only match without credential-shaped body"
  }
}

$rawWorktree = @()
$grepExitCode = $null
$grepResult = Invoke-ProcessCapture -FilePath $gitExe -Arguments @("-C", $repoRoot, "grep", "-nEi", "--no-color", "--", $pattern, "--", ".")
$rawWorktree = @($grepResult.StdoutLines)
$grepExitCode = $grepResult.ExitCode
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
$excludePathPattern = '(^|/)(node_modules|\.git|dist|build|\.next|coverage)(/|$)'

foreach ($token in $historyTokens) {
  $historyResult = Invoke-ProcessCapture -FilePath $gitExe -Arguments @(
    "-C", $repoRoot, "log", "--all", "--pretty=format:%H", "--name-only", "--no-textconv", "-S", $token, "--", ".",
    ":(exclude)*.docx", ":(exclude)*.pdf", ":(exclude)*.png", ":(exclude)*.jpg", ":(exclude)*.jpeg", ":(exclude)*.gif",
    ":(exclude)*.webp", ":(exclude)*.zip", ":(exclude)*.7z", ":(exclude)*.rar", ":(exclude)*.mp4", ":(exclude)*.mov",
    ":(exclude)*.wav", ":(exclude)*.mp3", ":(exclude)*.exe", ":(exclude)*.dll"
  )
  $historyExitCode = $historyResult.ExitCode
  if ($historyExitCode -ne 0) {
    throw "git log history scan failed for token '$token' (exit $historyExitCode)."
  }

  $currentCommit = $null
  foreach ($rawLine in $historyResult.StdoutLines) {
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
  }
}

$historyAssessment = New-Object System.Collections.Generic.List[object]
$assessmentPathSet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$regexOptions = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase

foreach ($entry in @($historyCandidates)) {
  $parts = $entry -split "`t"
  if ($parts.Count -lt 3) {
    continue
  }
  $token = $parts[0]
  $commit = $parts[1]
  $path = $parts[2]
  [void]$assessmentPathSet.Add($path)

  $patternSpec = $historyPatternSpecs[$token]
  $patternId = "unknown"
  $patternRegex = ""
  if ($null -ne $patternSpec) {
    $patternId = $patternSpec.PatternId
    $patternRegex = $patternSpec.Regex
  }

  $blob = Resolve-HistoryBlob -GitExe $gitExe -RepoRoot $repoRoot -Commit $commit -Path $path
  $matchedValue = ""
  $matchSource = "token_indicator"
  $hasFullPatternMatch = $false
  if ($blob.Found -and -not [string]::IsNullOrWhiteSpace($patternRegex)) {
    $fullMatch = [System.Text.RegularExpressions.Regex]::Match($blob.Text, $patternRegex, $regexOptions)
    if ($fullMatch.Success) {
      $matchedValue = $fullMatch.Value
      $matchSource = "full_pattern"
      $hasFullPatternMatch = $true
    }
  }
  if ([string]::IsNullOrEmpty($matchedValue) -and $blob.Found -and -not [string]::IsNullOrEmpty($token)) {
    if ($blob.Text.Contains($token)) {
      $matchedValue = $token
      $matchSource = "token_indicator"
    }
  }
  if ([string]::IsNullOrEmpty($matchedValue)) {
    $matchedValue = $token
    $matchSource = "token_indicator_fallback"
  }

  $classification = Get-HistoryClassification -Path $path -HasFullPatternMatch:$hasFullPatternMatch
  if (-not $blob.Found) {
    $classification = [PSCustomObject]@{
      Classification = "NEEDS_REVIEW"
      Reason = "blob unavailable for commit/path in commit and parent"
    }
  }

  $historyAssessment.Add([PSCustomObject]@{
      commit = $commit
      path = $path
      pattern_id = $patternId
      match_len = $matchedValue.Length
      match_sha256_prefix = (Get-Sha256Prefix -Value $matchedValue -PrefixLength 12)
      classification = $classification.Classification
      reason = $classification.Reason
      blob_ref = $blob.BlobRef
      match_source = $matchSource
    })
}

Set-Content -LiteralPath $historyCandidatesOut -Encoding UTF8 -Value @($historyCandidates)
$historyFiles = @($assessmentPathSet | Sort-Object)
Set-Content -LiteralPath $historyFilesOut -Encoding UTF8 -Value $historyFiles
$historyFalsePositiveCount = @($historyAssessment | Where-Object { $_.classification -eq "FALSE_POSITIVE" }).Count
$historyCredentialRiskCount = @($historyAssessment | Where-Object { $_.classification -eq "CREDENTIAL_RISK" }).Count
$historyNeedsReviewCount = @($historyAssessment | Where-Object { $_.classification -eq "NEEDS_REVIEW" }).Count
$historySummary = [PSCustomObject]@{
  history_candidates_count = $historyAssessment.Count
  history_unique_files_count = $historyFiles.Count
  false_positive_count = $historyFalsePositiveCount
  credential_risk_count = $historyCredentialRiskCount
  needs_review_count = $historyNeedsReviewCount
}
$historyEnvelope = @{
  generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  summary = @{
    history_candidates_count = $historySummary.history_candidates_count
    history_unique_files_count = $historySummary.history_unique_files_count
    false_positive_count = $historySummary.false_positive_count
    credential_risk_count = $historySummary.credential_risk_count
    needs_review_count = $historySummary.needs_review_count
  }
  records = @($historyAssessment.ToArray())
}
Set-Content -LiteralPath $historyAssessmentOut -Encoding UTF8 -Value ($historyEnvelope | ConvertTo-Json -Depth 6)

Write-Output "worktree_hits_count: $($worktreeHits.Count)"
Write-Output "history_candidates_count: $($historySummary.history_candidates_count)"
Write-Output "history_unique_files_count: $($historySummary.history_unique_files_count)"
Write-Output "history_false_positive_count: $($historySummary.false_positive_count)"
Write-Output "history_credential_risk_count: $($historySummary.credential_risk_count)"
Write-Output "history_needs_review_count: $($historySummary.needs_review_count)"
