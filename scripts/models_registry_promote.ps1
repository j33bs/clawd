# Promote a previously generated proposal into the tracked intent catalog (explicit).
#
# Default behavior:
# - validate proposal
# - compute a candidate updated intent
# - write a unified diff to workspace/.state/model_registry_proposal_to_intent.diff
# - do NOT modify the tracked intent file unless -Apply is passed
#
# This script never prints secrets. It does not echo token/env values.

[CmdletBinding()]
param(
  [switch]$Apply,
  [string]$ProposalPath = "workspace/.state/model_registry_proposal.json",
  [string]$OutDiffPath = "workspace/.state/model_registry_proposal_to_intent.diff",
  [string]$AuditLogPath = "workspace/.state/model_registry_audit.log"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
  $here = Split-Path -Parent $PSScriptRoot
  return (Resolve-Path $here).Path
}

function Resolve-GitExe {
  try {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Path }
  } catch {}
  foreach ($p in @(
    "$env:ProgramFiles\\Git\\cmd\\git.exe",
    "$env:ProgramFiles\\Git\\bin\\git.exe",
    "$env:ProgramFiles(x86)\\Git\\cmd\\git.exe",
    "$env:ProgramFiles(x86)\\Git\\bin\\git.exe"
  )) {
    if ($p -and (Test-Path -LiteralPath $p -PathType Leaf)) { return $p }
  }
  return $null
}

function Read-JsonFile([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing JSON file: $Path" }
  $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
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

try {
  $repoRoot = Get-RepoRoot

  $proposalAbs = Join-Path $repoRoot $ProposalPath
  $intentPath = Join-Path $repoRoot 'agents\\main\\agent\\models.json'
  $outDiffAbs = Join-Path $repoRoot $OutDiffPath
  $auditAbs = Join-Path $repoRoot $AuditLogPath

  $proposal = Read-JsonFile $proposalAbs
  if ($null -eq $proposal.providers -or -not ($proposal.providers.PSObject.Properties.Name -contains 'local_vllm')) {
    throw 'Proposal missing providers.local_vllm'
  }

  $intent = Read-JsonFile $intentPath
  if ($null -eq $intent.providers) { throw 'Intent missing providers' }

  $candidateProviders = [ordered]@{}
  foreach ($p in ($intent.providers.PSObject.Properties.Name | Sort-Object)) {
    $candidateProviders[$p] = $intent.providers.$p
  }

  # Overlay only baseUrl/models for local_vllm if proposal is non-empty.
  $p = $proposal.providers.local_vllm
  $merged = $candidateProviders['local_vllm']
  if ($null -eq $merged) {
    $merged = [ordered]@{ enabled = 'auto'; api = 'openai-completions'; baseUrl = $p.baseUrl; models = @() }
  }

  if ($p.PSObject.Properties.Name -contains 'baseUrl' -and ($p.baseUrl -is [string]) -and -not [string]::IsNullOrWhiteSpace($p.baseUrl)) {
    $merged.baseUrl = $p.baseUrl
  }
  if ($p.PSObject.Properties.Name -contains 'models' -and ($p.models -is [System.Collections.IEnumerable])) {
    $obsModels = @($p.models)
    if ($obsModels.Count -gt 0) {
      # Normalize to intent model schema: { id, ... }
      $merged.models = @($obsModels)
    }
  }
  $candidateProviders['local_vllm'] = $merged

  $candidate = @{ providers = $candidateProviders }
  $candidatePath = Join-Path $repoRoot '.tmp\\models_intent_candidate_from_registry.json'
  Write-JsonStable -Path $candidatePath -obj $candidate

  $gitExe = Resolve-GitExe
  if ($gitExe) {
    $diff = & $gitExe diff --no-index -- "$intentPath" "$candidatePath" 2>$null
    $dir = Split-Path -Parent $outDiffAbs
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Set-Content -LiteralPath $outDiffAbs -Value ($diff + "`n") -Encoding UTF8
  } else {
    Set-Content -LiteralPath $outDiffAbs -Value ("NOTE: git not found; candidate written to {0}`n" -f $candidatePath) -Encoding UTF8
  }

  if ($Apply) {
    Copy-Item -LiteralPath $candidatePath -Destination $intentPath -Force

    $ts = (Get-Date).ToUniversalTime().ToString('o')
    $line = "$ts promoted model registry proposal to intent (providers.local_vllm)"
    $adir = Split-Path -Parent $auditAbs
    if ($adir -and -not (Test-Path -LiteralPath $adir)) { New-Item -ItemType Directory -Path $adir -Force | Out-Null }
    Add-Content -LiteralPath $auditAbs -Value ($line + "`n") -Encoding UTF8

    Write-Output ("APPLIED: updated intent catalog at agents/main/agent/models.json; diff at {0}" -f $outDiffAbs)
  } else {
    Write-Output ("PROPOSED: diff at {0} (candidate at .tmp/models_intent_candidate_from_registry.json)" -f $outDiffAbs)
  }

  exit 0
}
catch {
  Write-Output ("ERROR: {0}" -f $_.Exception.Message)
  exit 1
}
