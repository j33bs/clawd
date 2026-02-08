$ErrorActionPreference = 'Stop'
Write-Host '=== OpenClaw Verify Telegram Allowlist ==='

function Convert-ToWslPath([string]$windowsPath) {
  $p = $windowsPath -replace '\\', '/'
  if ($p -match '^([A-Za-z]):/(.*)$') {
    return "/mnt/$($matches[1].ToLower())/$($matches[2])"
  }
  return $p
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$target = Join-Path $repoRoot 'workspace/scripts/verify_allowlist.py'

if (Get-Command py -ErrorAction SilentlyContinue) {
  $ver = (& py -3 --version 2>&1)
  Write-Host "Interpreter: $ver (py -3)"
  & py -3 $target
  exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
  $ver = (& python --version 2>&1)
  Write-Host "Interpreter: $ver (python)"
  & python $target
  exit $LASTEXITCODE
}

if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
  $linuxTarget = Convert-ToWslPath $target
  $ver = (& wsl.exe sh -lc "python3 --version" 2>&1)
  Write-Host "Interpreter: $ver (wsl python3)"
  & wsl.exe python3 $linuxTarget
  exit $LASTEXITCODE
}

Write-Error 'No Python runtime found. Install Python and ensure `py` or `python` is on PATH.'
exit 127
