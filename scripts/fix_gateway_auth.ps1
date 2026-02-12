[CmdletBinding(SupportsShouldProcess = $true)]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Utf8Json {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)]$Value
  )

  $json = $Value | ConvertTo-Json -Depth 16
  [System.IO.File]::WriteAllText($Path, $json + "`n", [System.Text.UTF8Encoding]::new($false))
}

function Read-JsonFile {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Config file not found: $Path"
  }

  $raw = Get-Content -LiteralPath $Path -Raw
  return $raw | ConvertFrom-Json
}

function Ensure-ObjectProperty {
  param(
    [Parameter(Mandatory = $true)]$Object,
    [Parameter(Mandatory = $true)][string]$Name
  )

  $prop = $Object.PSObject.Properties[$Name]
  if ($null -eq $prop -or $null -eq $Object.$Name) {
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue ([pscustomobject]@{}) -Force
  }
}

function Get-TokenSnapshot {
  param([Parameter(Mandatory = $true)]$Config)

  $authToken = $null
  $remoteToken = $null
  $envToken = [string]$env:OPENCLAW_GATEWAY_TOKEN

  $gatewayProp = $Config.PSObject.Properties['gateway']
  if ($null -ne $gatewayProp -and $null -ne $Config.gateway) {
    if ($null -ne $Config.gateway.PSObject.Properties['auth'] -and $null -ne $Config.gateway.auth) {
      $authToken = [string]$Config.gateway.auth.token
    }
    if ($null -ne $Config.gateway.PSObject.Properties['remote'] -and $null -ne $Config.gateway.remote) {
      $remoteToken = [string]$Config.gateway.remote.token
    }
  }

  return [ordered]@{
    authToken = $authToken
    remoteToken = $remoteToken
    authPresent = -not [string]::IsNullOrWhiteSpace($authToken)
    remotePresent = -not [string]::IsNullOrWhiteSpace($remoteToken)
    envTokenPresent = -not [string]::IsNullOrWhiteSpace($envToken)
    envToken = $envToken
  }
}

$timestamp = (Get-Date).ToUniversalTime().ToString('o')
$stampForFile = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
$configPath = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
$backupPath = Join-Path $env:USERPROFILE ".openclaw\openclaw.json.bak.$stampForFile"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$evidenceDir = Join-Path $repoRoot '.tmp/system1_evidence'
$resultPath = Join-Path $evidenceDir 'fix_gateway_auth_result.json'

New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
Copy-Item -LiteralPath $configPath -Destination $backupPath -Force

$doctorFixUsed = $false
$doctorFixExitCode = $null
$changed = $false
$wouldChange = $false
$state = 'unchanged'

$config = Read-JsonFile -Path $configPath
$before = Get-TokenSnapshot -Config $config

if (-not ($before.authPresent -and $before.remotePresent)) {
  $doctorFixUsed = $true
  try {
    & openclaw doctor --fix --non-interactive --yes *> $null
    $doctorFixExitCode = $LASTEXITCODE
  } catch {
    $doctorFixExitCode = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 1 }
  }
  $config = Read-JsonFile -Path $configPath
}

$current = Get-TokenSnapshot -Config $config

if ($current.envTokenPresent -and (($current.authToken -ne $current.envToken) -or ($current.remoteToken -ne $current.envToken))) {
  $state = 'aligned_to_env_override'
  if ($PSCmdlet.ShouldProcess($configPath, 'Align gateway auth/remote tokens to OPENCLAW_GATEWAY_TOKEN override')) {
    Ensure-ObjectProperty -Object $config -Name 'gateway'
    Ensure-ObjectProperty -Object $config.gateway -Name 'auth'
    Ensure-ObjectProperty -Object $config.gateway -Name 'remote'

    if ($null -eq $config.gateway.auth.PSObject.Properties['token']) {
      $config.gateway.auth | Add-Member -NotePropertyName token -NotePropertyValue $current.envToken -Force
    } else {
      $config.gateway.auth.token = $current.envToken
    }

    if ($null -eq $config.gateway.remote.PSObject.Properties['token']) {
      $config.gateway.remote | Add-Member -NotePropertyName token -NotePropertyValue $current.envToken -Force
    } else {
      $config.gateway.remote.token = $current.envToken
    }

    Write-Utf8Json -Path $configPath -Value $config
    $changed = $true
    $config = Read-JsonFile -Path $configPath
    $current = Get-TokenSnapshot -Config $config
  } else {
    $wouldChange = $true
  }
} elseif (-not $current.authPresent) {
  $state = 'missing'
} elseif ((-not $current.remotePresent) -or $current.authToken -ne $current.remoteToken) {
  $state = 'aligned'
  if ($PSCmdlet.ShouldProcess($configPath, 'Align gateway.remote.token to gateway.auth.token')) {
    Ensure-ObjectProperty -Object $config -Name 'gateway'
    Ensure-ObjectProperty -Object $config.gateway -Name 'remote'

    if ($null -eq $config.gateway.remote.PSObject.Properties['token']) {
      $config.gateway.remote | Add-Member -NotePropertyName token -NotePropertyValue $current.authToken -Force
    } else {
      $config.gateway.remote.token = $current.authToken
    }

    Write-Utf8Json -Path $configPath -Value $config
    $changed = $true
    $config = Read-JsonFile -Path $configPath
    $current = Get-TokenSnapshot -Config $config
  } else {
    $wouldChange = $true
  }
}

$result = [ordered]@{
  before_tokens_present = [ordered]@{
    auth = [bool]$before.authPresent
    remote = [bool]$before.remotePresent
  }
  after_tokens_present = [ordered]@{
    auth = [bool]$current.authPresent
    remote = [bool]$current.remotePresent
  }
  changed = [bool]$changed
  doctor_fix_used = [bool]$doctorFixUsed
  timestamp = $timestamp
  state = $state
  env_override_present = [bool]$current.envTokenPresent
  what_if = [bool]$WhatIfPreference
  would_change = [bool]$wouldChange
  doctor_fix_exit_code = $doctorFixExitCode
}

Write-Utf8Json -Path $resultPath -Value $result
Write-Output $state

if ($state -eq 'missing') {
  Write-Error 'Gateway auth token is missing after openclaw doctor --fix. Set gateway.auth.token, then rerun .\openclaw.ps1 gateway heal.'
  exit 1
}

exit 0
