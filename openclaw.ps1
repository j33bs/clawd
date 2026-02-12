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
    $stdout = if (Test-Path -LiteralPath $tmpStdout) { Get-Content -LiteralPath $tmpStdout -Raw } else { "" }
    $stderr = if (Test-Path -LiteralPath $tmpStderr) { Get-Content -LiteralPath $tmpStderr -Raw } else { "" }
    return [pscustomobject]@{
      ExitCode = $proc.ExitCode
      Output = ($stdout + $stderr).TrimEnd("`r", "`n")
    }
  } finally {
    Remove-Item -LiteralPath $tmpStdout -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmpStderr -Force -ErrorAction SilentlyContinue
  }
}

function Write-GatewayHealDiagnostics {
  param(
    [int]$StartExit,
    [int]$ProbeExit,
    [string]$ProbeText
  )

  Write-Output "Next diagnostics:"
  Write-Output "  openclaw status"
  Write-Output "  openclaw channels status --probe"
  Write-Output "  openclaw doctor"
  Write-Output "  .tmp/system1_evidence/transport_fix_result.json"
  Write-Output "  .tmp/system1_evidence/port_remediation.json"
  Write-Output "  .tmp/system1_evidence/start_gateway_task_result.json"

  if ($StartExit -ne 0) {
    Write-Output "Gateway task start script failed with exit code $StartExit."
  }

  if ($ProbeExit -ne 0 -and $ProbeText -match '(?i)/usr/bin/ssh|ENOENT') {
    Write-Output "Probe still indicates an SSH transport path; verify gateway.remote.* keys were removed for local mode."
  }
}

if ($CliArgs.Count -lt 2 -or $CliArgs[0] -ne "audit" -or $CliArgs[1] -ne "system1") {
  if ($CliArgs.Count -ge 2 -and $CliArgs[0] -eq "gateway" -and $CliArgs[1] -eq "heal") {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $fixScript = Join-Path $scriptDir "scripts/fix_gateway_auth.ps1"
    $transportScript = Join-Path $scriptDir "scripts/fix_gateway_transport.ps1"
    $startScript = Join-Path $scriptDir "scripts/start_gateway_task.ps1"

    & $fixScript
    $fixExit = $LASTEXITCODE
    if ($fixExit -ne 0) {
      exit $fixExit
    }

    & $transportScript
    $transportExit = $LASTEXITCODE
    if ($transportExit -ne 0) {
      exit $transportExit
    }

    & $startScript
    $startExit = $LASTEXITCODE

    $probe = Invoke-ProcessCapture -FilePath "cmd.exe" -Arguments @("/c", "openclaw gateway probe")
    if (-not [string]::IsNullOrWhiteSpace($probe.Output)) {
      Write-Output $probe.Output
    }
    $probeExit = $probe.ExitCode
    $probeText = [string]$probe.Output

    if ($startExit -ne 0 -or $probeExit -ne 0) {
      Write-GatewayHealDiagnostics -StartExit $startExit -ProbeExit $probeExit -ProbeText $probeText
    }

    if ($probeExit -ne 0) {
      exit $probeExit
    }

    if ($startExit -ne 0) {
      exit $startExit
    }

    exit 0
  }

  Write-Error "Usage: .\openclaw.ps1 audit system1`n       .\openclaw.ps1 gateway heal"
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
