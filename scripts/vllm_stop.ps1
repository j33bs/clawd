[CmdletBinding()]
param(
  [string]$ComposeFile = "infra/vllm/docker-compose.yml"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail([string]$msg, [int]$code = 2) {
  Write-Host $msg
  exit $code
}

try {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "docker not found on PATH." 2
  }
  if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
    Fail "Missing compose file: $ComposeFile" 2
  }

  Write-Host "Stopping vLLM (docker compose down) ..."
  & docker compose -f $ComposeFile down
  if ($LASTEXITCODE -ne 0) {
    Fail "docker compose down failed (exit=$LASTEXITCODE)." 2
  }

  Write-Host "OK"
  exit 0
}
catch {
  Write-Host ("ERROR: {0}" -f $_.Exception.Message)
  exit 1
}
