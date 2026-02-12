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

function Get-TokenSnapshot {
  param([Parameter(Mandatory = $true)]$Config)

  $authToken = $null
  $remoteToken = $null

  $hasGateway = $null -ne $Config.PSObject.Properties['gateway']
  if ($hasGateway -and $null -ne $Config.gateway) {
    $hasAuth = $null -ne $Config.gateway.PSObject.Properties['auth']
    $hasRemote = $null -ne $Config.gateway.PSObject.Properties['remote']

    if ($hasAuth -and $null -ne $Config.gateway.auth) {
      $authToken = $Config.gateway.auth.token
    }
    if ($hasRemote -and $null -ne $Config.gateway.remote) {
      $remoteToken = $Config.gateway.remote.token
    }
  }

  $authPresent = -not [string]::IsNullOrWhiteSpace([string]$authToken)
  $remotePresent = -not [string]::IsNullOrWhiteSpace([string]$remoteToken)

  return @{
    authToken = [string]$authToken
    remoteToken = [string]$remoteToken
    authPresent = $authPresent
    remotePresent = $remotePresent
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
$changed = $false
$wouldChange = $false
$state = 'unchanged'
$doctorFixExitCode = $null

$config = Read-JsonFile -Path $configPath
$before = Get-TokenSnapshot -Config $config

if (-not ($before.authPresent -and $before.remotePresent)) {
  $doctorFixUsed = $true
  try {
    & openclaw doctor --fix --non-interactive --yes *> $null
    $doctorFixExitCode = $LASTEXITCODE
  } catch {
    if ($null -ne $LASTEXITCODE) {
      $doctorFixExitCode = $LASTEXITCODE
    } else {
      $doctorFixExitCode = 1
    }
  }
  $config = Read-JsonFile -Path $configPath
}

$current = Get-TokenSnapshot -Config $config
$modeOrUrlAdjusted = $false
$modeOrUrlNeedsAdjustment = $false

if ($current.authPresent) {
  $hasGateway = $null -ne $config.PSObject.Properties['gateway']
  if (-not $hasGateway -or $null -eq $config.gateway) {
    $config | Add-Member -NotePropertyName gateway -NotePropertyValue ([pscustomobject]@{})
    $modeOrUrlNeedsAdjustment = $true
  }

  $hasMode = $null -ne $config.gateway.PSObject.Properties['mode']
  $modeValue = if ($hasMode) { [string]$config.gateway.mode } else { '' }
  if ([string]::IsNullOrWhiteSpace($modeValue)) {
    $modeOrUrlNeedsAdjustment = $true
    if ($PSCmdlet.ShouldProcess($configPath, 'Set gateway.mode to local for System-1')) {
      if (-not $hasMode) {
        $config.gateway | Add-Member -NotePropertyName mode -NotePropertyValue 'local'
      } else {
        $config.gateway.mode = 'local'
      }
      $modeOrUrlAdjusted = $true
      $hasMode = $true
    } else {
      $wouldChange = $true
    }
  }

  $hasRemote = $null -ne $config.gateway.PSObject.Properties['remote']
  if (-not $hasRemote -or $null -eq $config.gateway.remote) {
    $config.gateway | Add-Member -NotePropertyName remote -NotePropertyValue ([pscustomobject]@{})
    $modeOrUrlNeedsAdjustment = $true
    $hasRemote = $true
  }

  $hasRemoteUrl = $null -ne $config.gateway.remote.PSObject.Properties['url']
  $remoteUrl = if ($hasRemoteUrl) { [string]$config.gateway.remote.url } else { '' }
  if ([string]::IsNullOrWhiteSpace($remoteUrl)) {
    $modeOrUrlNeedsAdjustment = $true
    if ($PSCmdlet.ShouldProcess($configPath, 'Set gateway.remote.url to ws://127.0.0.1:18789')) {
      if (-not $hasRemoteUrl) {
        $config.gateway.remote | Add-Member -NotePropertyName url -NotePropertyValue 'ws://127.0.0.1:18789'
      } else {
        $config.gateway.remote.url = 'ws://127.0.0.1:18789'
      }
      $modeOrUrlAdjusted = $true
    } else {
      $wouldChange = $true
    }
  }

  if ($modeOrUrlAdjusted) {
    Write-Utf8Json -Path $configPath -Value $config
    $changed = $true
    $config = Read-JsonFile -Path $configPath
    $current = Get-TokenSnapshot -Config $config
  }
}

if (-not $current.authPresent) {
  $state = 'missing'
} elseif ((-not $current.remotePresent) -or $current.authToken -ne $current.remoteToken) {
  $state = 'aligned'
  if ($PSCmdlet.ShouldProcess($configPath, 'Align gateway.remote.token to gateway.auth.token')) {
    $hasGateway = $null -ne $config.PSObject.Properties['gateway']
    if (-not $hasGateway -or $null -eq $config.gateway) {
      $config | Add-Member -NotePropertyName gateway -NotePropertyValue ([pscustomobject]@{})
    }

    $hasRemote = $null -ne $config.gateway.PSObject.Properties['remote']
    if (-not $hasRemote -or $null -eq $config.gateway.remote) {
      $config.gateway | Add-Member -NotePropertyName remote -NotePropertyValue ([pscustomobject]@{})
    }
    $hasRemoteToken = $null -ne $config.gateway.remote.PSObject.Properties['token']
    if (-not $hasRemoteToken) {
      $config.gateway.remote | Add-Member -NotePropertyName token -NotePropertyValue $current.authToken
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
} elseif ($modeOrUrlAdjusted -or $modeOrUrlNeedsAdjustment) {
  $state = 'aligned'
} else {
  $state = 'unchanged'
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
  what_if = [bool]$WhatIfPreference
  would_change = [bool]$wouldChange
  doctor_fix_exit_code = $doctorFixExitCode
}

Write-Utf8Json -Path $resultPath -Value $result
Write-Output $state

if ($state -eq 'missing') {
  Write-Error 'Gateway token fields are still missing after openclaw doctor --fix. Set gateway.auth.token and gateway.remote.token in %USERPROFILE%\.openclaw\openclaw.json, then rerun .\openclaw.ps1 gateway heal.'
  exit 1
}

exit 0
