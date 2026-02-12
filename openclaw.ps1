param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Convert-ToWslPath {
  param([Parameter(Mandatory = $true)][string]$WindowsPath)
  $p = $WindowsPath -replace '\\', '/'
  if ($p -match '^([A-Za-z]):/(.*)$') {
    return "/mnt/$($Matches[1].ToLower())/$($Matches[2])"
  }
  return $p
}

function Invoke-ProcessRelay {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [string[]]$Arguments = @()
  )

  $tmpStdout = [System.IO.Path]::GetTempFileName()
  $tmpStderr = [System.IO.Path]::GetTempFileName()
  try {
    $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments -NoNewWindow -Wait -PassThru -RedirectStandardOutput $tmpStdout -RedirectStandardError $tmpStderr
    if (Test-Path -LiteralPath $tmpStdout) {
      $stdout = Get-Content -LiteralPath $tmpStdout -Raw
      if (-not [string]::IsNullOrEmpty($stdout)) {
        Write-Output $stdout.TrimEnd("`r", "`n")
      }
    }
    if (Test-Path -LiteralPath $tmpStderr) {
      $stderr = Get-Content -LiteralPath $tmpStderr -Raw
      if (-not [string]::IsNullOrEmpty($stderr)) {
        Write-Output $stderr.TrimEnd("`r", "`n")
      }
    }
    return $proc.ExitCode
  } finally {
    Remove-Item -LiteralPath $tmpStdout -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmpStderr -Force -ErrorAction SilentlyContinue
  }
}

if ($CliArgs.Count -lt 2 -or $CliArgs[0] -ne "audit" -or $CliArgs[1] -ne "system1") {
  Write-Error "Usage: .\openclaw.ps1 audit system1"
  exit 2
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
  Write-Error "wsl.exe not found. This command requires WSL for System-1 audit execution."
  exit 127
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath $scriptDir).Path
$linuxRepo = Convert-ToWslPath -WindowsPath $repoRoot
$auditScript = "$linuxRepo/tools/system1_audit.py"
$outDir = "$linuxRepo/.tmp/system1_evidence"
$outJson = "$outDir/system1_audit_evidence.json"
$outLog = "$outDir/system1_audit_output.txt"
$outSummary = "$outDir/system1_audit_summary.txt"

$exitCode = Invoke-ProcessRelay -FilePath "wsl.exe" -Arguments @(
  "python3",
  $auditScript,
  "--repo-root", $linuxRepo,
  "--output-json", $outJson,
  "--output-log", $outLog,
  "--summary-text", $outSummary
)
exit $exitCode
