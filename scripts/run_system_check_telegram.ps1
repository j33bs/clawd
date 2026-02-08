$ErrorActionPreference = 'Stop'
Write-Host '=== OpenClaw Telegram System Check ==='

function Convert-ToWslPath([string]$windowsPath) {
  $p = $windowsPath -replace '\\', '/'
  if ($p -match '^([A-Za-z]):/(.*)$') {
    return "/mnt/$($matches[1].ToLower())/$($matches[2])"
  }
  return $p
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$target = Join-Path $repoRoot 'workspace/system_check_telegram.js'

if (Get-Command node -ErrorAction SilentlyContinue) {
  & node $target
  exit $LASTEXITCODE
}

if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
  $linuxTarget = Convert-ToWslPath $target
  & wsl.exe node $linuxTarget
  exit $LASTEXITCODE
}

Write-Error 'No Node runtime found (node or wsl.exe).'
exit 127
