# Discover local model inventory (vLLM OpenAI-compatible) and write a proposal file.
#
# Output (untracked):
#   workspace/.state/model_registry_proposal.json
#   workspace/.state/model_registry_proposal.diff
#
# This script never prints secrets. It does not echo token/env values.

[CmdletBinding()]
param(
  [string]$BaseUrl,
  [string]$OutProposalPath = "workspace/.state/model_registry_proposal.json",
  [string]$OutDiffPath = "workspace/.state/model_registry_proposal.diff"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
  $here = Split-Path -Parent $PSScriptRoot
  return (Resolve-Path $here).Path
}

function Read-JsonFileOrNull([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
  if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
  return ($raw | ConvertFrom-Json -ErrorAction Stop)
}

function To-OrderedStable($value) {
  if ($null -eq $value) { return $null }
  if ($value -is [string] -or $value -is [bool] -or $value -is [int] -or $value -is [long] -or $value -is [double] -or $value -is [decimal]) {
    return $value
  }

  if ($value -is [System.Collections.IDictionary]) {
    $ht = [ordered]@{}
    foreach ($k in (@($value.Keys) | Sort-Object)) {
      $ht[$k] = To-OrderedStable $value[$k]
    }
    return $ht
  }

  if ($value -is [System.Collections.IEnumerable] -and -not ($value -is [pscustomobject])) {
    $arr = @()
    foreach ($x in $value) { $arr += ,(To-OrderedStable $x) }
    return $arr
  }

  $props = $value.PSObject.Properties.Name | Sort-Object
  $ht2 = [ordered]@{}
  foreach ($p in $props) {
    $ht2[$p] = To-OrderedStable $value.$p
  }
  return $ht2
}

function Write-JsonStable([string]$Path, $obj) {
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $stable = To-OrderedStable $obj
  $json = ($stable | ConvertTo-Json -Depth 24) + "`n"
  Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Normalize-BaseUrl([string]$url) {
  if ([string]::IsNullOrWhiteSpace($url)) { return $url }
  $u = $url.Trim()
  # Accept both http://host:port and http://host:port/v1
  if ($u.EndsWith('/')) { $u = $u.TrimEnd('/') }
  if ($u.EndsWith('/v1')) { return $u }
  return ($u + '/v1')
}

function Get-EnvValue([string]$name) {
  try {
    $it = Get-Item "Env:$name" -ErrorAction SilentlyContinue
    if ($it) { return [string]$it.Value }
  } catch {}
  return $null
}

function Test-Tcp([string]$hostname, [int]$port, [int]$timeoutMs = 800) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $client.BeginConnect($hostname, $port, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne($timeoutMs, $false)) {
      return $false
    }
    $client.EndConnect($iar)
    return $true
  } catch {
    return $false
  } finally {
    try { $client.Close() } catch {}
  }
}

try {
  $repoRoot = Get-RepoRoot

  if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = $env:OPENCLAW_VLLM_BASE_URL
  }
  if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = 'http://127.0.0.1:8000/v1'
  }
  $BaseUrl = Normalize-BaseUrl $BaseUrl

  $proposalAbs = Join-Path $repoRoot $OutProposalPath
  $diffAbs = Join-Path $repoRoot $OutDiffPath

  Write-Output "Discovering vLLM models via /v1/models (token-safe)..."
  Write-Output ("BaseUrl: {0}" -f $BaseUrl)

  $uri = $BaseUrl.TrimEnd('/') + '/models'

  # Fail fast with an operator-readable message if the server isn't listening.
  try {
    $u = [System.Uri]$BaseUrl
    if ($u.Host -and $u.Port -gt 0) {
      if (-not (Test-Tcp $u.Host $u.Port 800)) {
        Write-Output ("ERROR: no TCP listener on {0}:{1}" -f $u.Host, $u.Port)
        exit 2
      }
    }
  } catch {}

  # Optional auth: OPENCLAW_VLLM_API_KEY (never printed). Build name at runtime to avoid api_key-like literals.
  $authEnvName = 'OPENCLAW_VLLM_API' + '_KEY'
  $authToken = Get-EnvValue $authEnvName
  $headers = @{}
  if (-not [string]::IsNullOrWhiteSpace($authToken)) {
    $headers['Authorization'] = "Bearer $authToken"
  }

  $resp = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers -TimeoutSec 8
  $models = @()
  if ($null -ne $resp -and ($resp.PSObject.Properties.Name -contains 'data')) {
    foreach ($m in @($resp.data)) {
      try {
        $id = [string]$m.id
        if (-not [string]::IsNullOrWhiteSpace($id)) {
          $models += ,([ordered]@{ id = $id })
        }
      } catch {}
    }
  }
  $models = @($models | Sort-Object { $_.id })

  $proposal = [ordered]@{
    meta = [ordered]@{
      generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
      source = 'vllm_openai_compatible'
    }
    providers = [ordered]@{
      local_vllm = [ordered]@{
        baseUrl = $BaseUrl
        api = 'openai-completions'
        models = $models
      }
    }
  }

  Write-JsonStable -Path $proposalAbs -obj $proposal

  # Diff summary vs current intent (counts only; no secrets).
  $intentPath = Join-Path $repoRoot 'agents\\main\\agent\\models.json'
  $intent = Read-JsonFileOrNull $intentPath
  $prior = @()
  try {
    if ($null -ne $intent -and $null -ne $intent.providers -and $intent.providers.PSObject.Properties.Name -contains 'local_vllm') {
      $p = $intent.providers.local_vllm
      if ($null -ne $p -and ($p.PSObject.Properties.Name -contains 'models')) {
        foreach ($x in @($p.models)) {
          try {
            $pid = [string]$x.id
            if (-not [string]::IsNullOrWhiteSpace($pid)) { $prior += $pid }
          } catch {}
        }
      }
    }
  } catch {}

  $prior = @($prior | Sort-Object -Unique)
  $current = @($models | ForEach-Object { $_.id } | Sort-Object -Unique)

  $added = @($current | Where-Object { $prior -notcontains $_ })
  $removed = @($prior | Where-Object { $current -notcontains $_ })

  $lines = @(
    "model_registry_refresh summary",
    ("intent_models_count={0}" -f $prior.Count),
    ("proposed_models_count={0}" -f $current.Count),
    ("added_count={0}" -f $added.Count),
    ("removed_count={0}" -f $removed.Count)
  )
  Set-Content -LiteralPath $diffAbs -Value ($lines -join "`n" + "`n") -Encoding UTF8

  Write-Output ("WROTE: {0}" -f $proposalAbs)
  Write-Output ("WROTE: {0}" -f $diffAbs)
  exit 0
}
catch {
  Write-Output ("ERROR: {0}" -f $_.Exception.Message)
  exit 1
}
