$ErrorActionPreference = 'Stop'
Write-Host '=== OpenClaw Intent Failure Scan (stdout) ==='

function Convert-ToWslPath([string]$windowsPath) {
  $p = $windowsPath -replace '\\', '/'
  if ($p -match '^([A-Za-z]):/(.*)$') {
    return "/mnt/$($matches[1].ToLower())/$($matches[2])"
  }
  return $p
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$target = Join-Path $repoRoot 'workspace/scripts/intent_failure_scan.py'

if (Get-Command python -ErrorAction SilentlyContinue) {
  & python $target --stdout
  exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 $target --stdout
  exit $LASTEXITCODE
}

if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
  $linuxTarget = Convert-ToWslPath $target
  & wsl.exe python3 $linuxTarget --stdout
  exit $LASTEXITCODE
}

Write-Error 'No Python runtime found (python, py, or wsl.exe).'
exit 127
