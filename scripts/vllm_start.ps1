[CmdletBinding()]
param(
  [int]$Port = 8000,
  [string]$Model = $env:VLLM_MODEL,
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
    Fail "docker not found on PATH. Install Docker Desktop (WSL2 backend) or use a WSL2-based vLLM runbook." 2
  }
  if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
    Fail "Missing compose file: $ComposeFile" 2
  }
  if ([string]::IsNullOrWhiteSpace($Model)) {
    Fail "VLLM_MODEL is required. Set -Model or env VLLM_MODEL to a local path or HuggingFace model id." 2
  }

  $oldPort = $env:VLLM_PORT
  $oldModel = $env:VLLM_MODEL

  $env:VLLM_PORT = [string]$Port
  $env:VLLM_MODEL = [string]$Model

  Write-Host "Starting vLLM (OpenAI-compatible) on 127.0.0.1:$Port ..."
  Write-Host "Compose: $ComposeFile"

  & docker compose -f $ComposeFile up -d
  if ($LASTEXITCODE -ne 0) {
    Fail "docker compose up failed (exit=$LASTEXITCODE)." 2
  }

  Write-Host "OK"
  exit 0
}
catch {
  Write-Host ("ERROR: {0}" -f $_.Exception.Message)
  exit 1
}
finally {
  if ($null -ne $oldPort) { $env:VLLM_PORT = $oldPort } else { Remove-Item Env:VLLM_PORT -ErrorAction SilentlyContinue }
  if ($null -ne $oldModel) { $env:VLLM_MODEL = $oldModel } else { Remove-Item Env:VLLM_MODEL -ErrorAction SilentlyContinue }
}
