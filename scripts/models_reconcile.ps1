# Produce a proposed update from OBSERVED -> INTENT for human review.
#
# Intent (tracked): agents/main/agent/models.json
# Observed (untracked): workspace/.state/models_observed.json
#
# Default behavior:
# - compute candidate updated intent (intent overlaid with observed baseUrl/models)
# - write a unified diff to .tmp/models_intent_proposal.diff
# - do NOT modify the tracked intent file unless -Apply is passed
#
# This script never prints secrets; it does not echo token/env values.

[CmdletBinding()]
param(
  [switch]$Apply,
  [string]$OutDiffPath = ".tmp/models_intent_proposal.diff"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $here = Split-Path -Parent $PSScriptRoot
  return (Resolve-Path $here).Path
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
  if (-not $json.EndsWith("`n")) { $json = $json + "`n" }
  Set-Content -LiteralPath $Path -Value $json -Encoding UTF8 -NoNewline:$false
}

function Resolve-GitExe {
  $cmd = Get-Command git -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    "C:\\Program Files\\Git\\cmd\\git.exe",
    "C:\\Program Files\\Git1\\cmd\\git.exe",
    "C:\\Program Files\\Git\\bin\\git.exe",
    "C:\\Program Files\\Git1\\bin\\git.exe"
  )
  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p -PathType Leaf) { return $p }
  }
  return $null
}

$repoRoot = Get-RepoRoot
$intentPath = Join-Path $repoRoot "agents\\main\\agent\\models.json"
$observedPath = Join-Path $repoRoot "workspace\\.state\\models_observed.json"

$intent = Read-JsonFile $intentPath
$observed = Read-JsonFile $observedPath

if ($null -eq $intent.providers) { throw "Intent missing providers: $intentPath" }
if ($null -eq $observed.providers) { throw "Observed missing providers: $observedPath" }

# Candidate intent update:
# - Keep intent as the canonical list of providers.
# - For providers present in observed, propose updating baseUrl and models.
$nextProviders = [ordered]@{}
foreach ($p in ($intent.providers.PSObject.Properties.Name | Sort-Object)) {
  $intentP = $intent.providers.$p
  $obsP = $null
  if ($observed.providers.PSObject.Properties.Name -contains $p) { $obsP = $observed.providers.$p }

  $merged = [ordered]@{}
  foreach ($k in ($intentP.PSObject.Properties.Name | Sort-Object)) { $merged[$k] = $intentP.$k }

  if ($null -ne $obsP) {
    if ($obsP.PSObject.Properties.Name -contains "baseUrl" -and ($obsP.baseUrl -is [string]) -and -not [string]::IsNullOrWhiteSpace($obsP.baseUrl)) {
      $merged["baseUrl"] = $obsP.baseUrl
    }
    if ($obsP.PSObject.Properties.Name -contains "models" -and ($obsP.models -is [System.Collections.IEnumerable])) {
      $obsModels = @($obsP.models)
      # Only propose models update if observed has a non-empty list.
      if ($obsModels.Count -gt 0) { $merged["models"] = $obsModels }
    }
  }

  $nextProviders[$p] = $merged
}

$candidatePath = Join-Path $repoRoot ".tmp\\models_intent_candidate.json"
Write-JsonStable -Path $candidatePath -obj @{ providers = $nextProviders }

# Produce a unified diff for review.
$outDiffAbs = Join-Path $repoRoot $OutDiffPath
$outDir = Split-Path -Parent $outDiffAbs
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

$gitExe = Resolve-GitExe
if ($gitExe) {
  $diff = & $gitExe diff --no-index -- "$intentPath" "$candidatePath" 2>$null
  Set-Content -LiteralPath $outDiffAbs -Value ($diff + "`n") -Encoding UTF8
} else {
  $msg = @(
    "NOTE: git was not found on PATH and no known git.exe location was detected.",
    "A candidate file was generated for review:",
    "  .tmp/models_intent_candidate.json",
    "To produce a unified diff, run this script from an environment where git is available.",
    ""
  ) -join "`n"
  Set-Content -LiteralPath $outDiffAbs -Value $msg -Encoding UTF8
}

if ($Apply) {
  Copy-Item -LiteralPath $candidatePath -Destination $intentPath -Force
  Write-Output "APPLIED: updated intent catalog at agents/main/agent/models.json from observed cache; diff written to $OutDiffPath"
} else {
  Write-Output "PROPOSED: diff written to $OutDiffPath (candidate at .tmp/models_intent_candidate.json); rerun with -Apply to update intent"
}
