# OpenClaw Intent/Observed split runner (System-1)
#
# Goal:
# - Keep git-tracked intent catalog stable: agents/main/agent/models.json
# - Allow runtime "aliveness" to write observed state into an untracked cache:
#   workspace/.state/models_observed.json
# - Run gateway with OPENCLAW_AGENT_DIR redirected to an untracked runtime agent dir:
#   workspace/.state/agents/main/agent
# - Fail-fast if the tracked intent file changes during execution.
#
# Notes:
# - This script never prints secrets. It does not echo env var values or token contents.
# - It is safe to run repeatedly; observed cache updates are non-destructive under discovery failure
#   (an empty discovered models list will not overwrite a previously non-empty observed list).

[CmdletBinding()]
param(
  # If <= 0, run until the gateway exits (service mode).
  [int]$RunSeconds = 10,
  [int]$Port = 18789,
  [int]$PollMs = 400,
  [switch]$NoObservedUpdate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

  # Dictionaries (Hashtable, OrderedDictionary, etc.)
  if ($value -is [System.Collections.IDictionary]) {
    $ht = [ordered]@{}
    foreach ($k in (@($value.Keys) | Sort-Object)) {
      $ht[$k] = To-OrderedStable $value[$k]
    }
    return $ht
  }

  # Arrays / lists
  if ($value -is [System.Collections.IEnumerable] -and -not ($value -is [pscustomobject])) {
    $arr = @()
    foreach ($x in $value) { $arr += ,(To-OrderedStable $x) }
    return $arr
  }

  # PSCustomObject / PSObject (JSON objects)
  $ht = [ordered]@{}
  $props = @(
    $value.PSObject.Properties |
      Where-Object { $_.MemberType -eq "NoteProperty" -and $_.Name -ne "psobject" } |
      Select-Object -ExpandProperty Name
  )
  foreach ($k in ($props | Sort-Object)) {
    $ht[$k] = To-OrderedStable $value.$k
  }
  return $ht
}

function Write-JsonStable([string]$Path, $obj) {
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $stable = To-OrderedStable $obj
  $json = $stable | ConvertTo-Json -Depth 64
  # Ensure trailing newline for deterministic diffs.
  if (-not $json.EndsWith("`n")) { $json = $json + "`n" }
  Set-Content -LiteralPath $Path -Value $json -Encoding UTF8 -NoNewline:$false
}

function Get-FileSha256([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Resolve-EffectiveProviders($intentProviders, $observedProviders) {
  $out = [ordered]@{}
  if ($null -ne $intentProviders) {
    foreach ($p in ($intentProviders.PSObject.Properties.Name | Sort-Object)) {
      $intentP = $intentProviders.$p
      $obsP = $null
      if ($null -ne $observedProviders -and $observedProviders.PSObject.Properties.Name -contains $p) { $obsP = $observedProviders.$p }

      # Start from intent and only overlay a small, explicit set of observed keys.
      $merged = [ordered]@{}
      foreach ($k in ($intentP.PSObject.Properties.Name | Sort-Object)) {
        $merged[$k] = $intentP.$k
      }

      if ($null -ne $obsP) {
        if ($obsP.PSObject.Properties.Name -contains "baseUrl" -and ($obsP.baseUrl -is [string]) -and -not [string]::IsNullOrWhiteSpace($obsP.baseUrl)) {
          $merged["baseUrl"] = $obsP.baseUrl
        }
        if ($obsP.PSObject.Properties.Name -contains "models" -and ($obsP.models -is [System.Collections.IEnumerable])) {
          # If observed has models (even empty), prefer it for the effective view.
          $merged["models"] = $obsP.models
        }
      }

      $out[$p] = $merged
    }
  }
  return $out
}

function Update-ObservedNonDestructive($priorObservedProviders, $runtimeProviders) {
  $out = [ordered]@{}

  # Start from prior observed.
  if ($null -ne $priorObservedProviders) {
    foreach ($p in ($priorObservedProviders.PSObject.Properties.Name | Sort-Object)) {
      $out[$p] = $priorObservedProviders.$p
    }
  }

  if ($null -eq $runtimeProviders) { return $out }

  foreach ($p in ($runtimeProviders.PSObject.Properties.Name | Sort-Object)) {
    $rt = $runtimeProviders.$p
    $prior = $null
    if ($out.Contains($p)) { $prior = $out[$p] }

    $next = [ordered]@{}
    if ($null -ne $prior) {
      foreach ($k in ($prior.PSObject.Properties.Name | Sort-Object)) { $next[$k] = $prior.$k }
    }

    if ($rt.PSObject.Properties.Name -contains "baseUrl" -and ($rt.baseUrl -is [string]) -and -not [string]::IsNullOrWhiteSpace($rt.baseUrl)) {
      $next["baseUrl"] = $rt.baseUrl
    }

    if ($rt.PSObject.Properties.Name -contains "models" -and ($rt.models -is [System.Collections.IEnumerable])) {
      $rtModels = @($rt.models)
      $priorModels = @()
      if ($null -ne $prior -and $prior.PSObject.Properties.Name -contains "models") { $priorModels = @($prior.models) }

      # Non-destructive under failure:
      # If runtime reports zero models but we previously had a non-empty observed list, keep the prior list.
      if ($rtModels.Count -gt 0) {
        $next["models"] = $rtModels
      } elseif ($priorModels.Count -gt 0) {
        $next["models"] = $priorModels
      } else {
        $next["models"] = @()
      }
    }

    $out[$p] = $next
  }

  return $out
}

$repoRoot = Get-RepoRoot
$intentPath = Join-Path $repoRoot "agents\\main\\agent\\models.json"
$observedPath = Join-Path $repoRoot "workspace\\.state\\models_observed.json"
$runtimeAgentDir = Join-Path $repoRoot "workspace\\.state\\agents\\main\\agent"
$runtimeModelsPath = Join-Path $runtimeAgentDir "models.json"

if (-not (Test-Path -LiteralPath $intentPath -PathType Leaf)) {
  throw "Intent models catalog not found: $intentPath"
}

# Snapshot intent hash (guard).
$intentHash0 = Get-FileSha256 $intentPath

# Load intent + observed (observed overlays only a small set of keys).
$intent = Read-JsonFileOrNull $intentPath
if ($null -eq $intent -or $null -eq $intent.providers) {
  throw "Intent models catalog must contain a top-level 'providers' object: $intentPath"
}
$observed = Read-JsonFileOrNull $observedPath
$observedProviders = $null
if ($null -ne $observed -and $null -ne $observed.providers) { $observedProviders = $observed.providers }

$effectiveProviders = Resolve-EffectiveProviders -intentProviders $intent.providers -observedProviders $observedProviders
Write-JsonStable -Path $runtimeModelsPath -obj @{ providers = $effectiveProviders }

# Launch gateway with agent dir redirected to untracked runtime dir.
$prevAgentDir = $env:OPENCLAW_AGENT_DIR
$env:OPENCLAW_AGENT_DIR = $runtimeAgentDir
try {
  $start = Get-Date
  $proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "gateway.cmd" -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden

  while (-not $proc.HasExited) {
    $elapsed = (New-TimeSpan -Start $start -End (Get-Date)).TotalSeconds
    if ($RunSeconds -gt 0 -and $elapsed -ge $RunSeconds) { break }

    Start-Sleep -Milliseconds $PollMs
    $h = Get-FileSha256 $intentPath
    if ($null -ne $intentHash0 -and $null -ne $h -and $h -ne $intentHash0) {
      try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
      throw "FAIL-FAST: tracked intent file changed during gateway run: agents/main/agent/models.json"
    }
  }

  if ($RunSeconds -gt 0 -and -not $proc.HasExited) {
    try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
} finally {
  $env:OPENCLAW_AGENT_DIR = $prevAgentDir
}

# Backstop guard (post-run compare).
$intentHash1 = Get-FileSha256 $intentPath
if ($null -ne $intentHash0 -and $null -ne $intentHash1 -and $intentHash1 -ne $intentHash0) {
  throw "FAIL-FAST: tracked intent file changed after gateway run: agents/main/agent/models.json"
}

if (-not $NoObservedUpdate) {
  $runtime = Read-JsonFileOrNull $runtimeModelsPath
  if ($null -ne $runtime -and $null -ne $runtime.providers) {
    $priorObs = Read-JsonFileOrNull $observedPath
    $priorObsProviders = $null
    if ($null -ne $priorObs -and $null -ne $priorObs.providers) { $priorObsProviders = $priorObs.providers }

    $nextObservedProviders = Update-ObservedNonDestructive -priorObservedProviders $priorObsProviders -runtimeProviders $runtime.providers
    Write-JsonStable -Path $observedPath -obj @{ providers = $nextObservedProviders }
  }
}

Write-Output "OK: gateway run completed without mutating tracked intent; observed cache updated at workspace/.state/models_observed.json"
