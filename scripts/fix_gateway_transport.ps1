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

function Is-LocalGatewayMode {
  param([AllowNull()][string]$Mode)

  if ([string]::IsNullOrWhiteSpace($Mode)) {
    return $false
  }

  $normalized = $Mode.Trim().ToLowerInvariant()
  return @('local', 'loopback').Contains($normalized)
}

function Classify-TransportMode {
  param([Parameter(Mandatory = $true)]$Config)

  $mode = if ($null -ne $Config.PSObject.Properties['gateway'] -and $null -ne $Config.gateway.PSObject.Properties['mode']) { [string]$Config.gateway.mode } else { '' }
  if (-not (Is-LocalGatewayMode -Mode $mode)) {
    return 'non-local'
  }

  $remote = $null
  if ($null -ne $Config.PSObject.Properties['gateway'] -and $null -ne $Config.gateway.PSObject.Properties['remote']) {
    $remote = $Config.gateway.remote
  }

  if ($null -eq $remote) {
    return 'local-ws'
  }

  $transport = if ($null -ne $remote.PSObject.Properties['transport']) { [string]$remote.transport } else { '' }
  $sshTarget = if ($null -ne $remote.PSObject.Properties['sshTarget']) { [string]$remote.sshTarget } else { '' }
  $sshIdentity = if ($null -ne $remote.PSObject.Properties['sshIdentity']) { [string]$remote.sshIdentity } else { '' }
  $remoteUrl = if ($null -ne $remote.PSObject.Properties['url']) { [string]$remote.url } else { '' }

  if ($transport -eq 'ssh' -or -not [string]::IsNullOrWhiteSpace($sshTarget) -or -not [string]::IsNullOrWhiteSpace($sshIdentity)) {
    return 'ssh'
  }

  if (-not [string]::IsNullOrWhiteSpace($remoteUrl)) {
    return 'ssh-prone-via-remote-url'
  }

  return 'local-ws'
}

$timestamp = (Get-Date).ToUniversalTime().ToString('o')
$stampForFile = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
$configPath = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
$backupPath = Join-Path $env:USERPROFILE ".openclaw\openclaw.json.bak.$stampForFile"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$evidenceDir = Join-Path $repoRoot '.tmp/system1_evidence'
$resultPath = Join-Path $evidenceDir 'transport_fix_result.json'

New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
Copy-Item -LiteralPath $configPath -Destination $backupPath -Force

$config = Read-JsonFile -Path $configPath
$beforeClass = Classify-TransportMode -Config $config
$changed = $false
$wouldChange = $false
$keysChanged = New-Object System.Collections.Generic.List[string]

Ensure-ObjectProperty -Object $config -Name 'gateway'

if ($null -eq $config.gateway.PSObject.Properties['mode'] -or [string]::IsNullOrWhiteSpace([string]$config.gateway.mode)) {
  if ($PSCmdlet.ShouldProcess($configPath, 'Set gateway.mode to local')) {
    $config.gateway | Add-Member -NotePropertyName mode -NotePropertyValue 'local' -Force
    $changed = $true
    $keysChanged.Add('gateway.mode:set-local')
  } else {
    $wouldChange = $true
  }
}

$mode = if ($null -ne $config.gateway.PSObject.Properties['mode']) { [string]$config.gateway.mode } else { '' }

if (Is-LocalGatewayMode -Mode $mode) {
  if ($null -ne $config.gateway.PSObject.Properties['remote'] -and $null -ne $config.gateway.remote) {
    $remote = $config.gateway.remote

    if ($null -ne $remote.PSObject.Properties['transport'] -and [string]$remote.transport -ne 'direct') {
      if ($PSCmdlet.ShouldProcess($configPath, 'Set gateway.remote.transport to direct')) {
        $remote.transport = 'direct'
        $changed = $true
        $keysChanged.Add('gateway.remote.transport:set-direct')
      } else {
        $wouldChange = $true
      }
    }

    foreach ($key in @('sshTarget', 'sshIdentity')) {
      if ($null -ne $remote.PSObject.Properties[$key]) {
        if ($PSCmdlet.ShouldProcess($configPath, "Remove gateway.remote.$key")) {
          $null = $remote.PSObject.Properties.Remove($key)
          $changed = $true
          $keysChanged.Add("gateway.remote.$key:removed")
        } else {
          $wouldChange = $true
        }
      }
    }

    if ($null -ne $remote.PSObject.Properties['url'] -and -not [string]::IsNullOrWhiteSpace([string]$remote.url)) {
      if ($PSCmdlet.ShouldProcess($configPath, 'Remove gateway.remote.url for local mode to avoid SSH inference in probe')) {
        $null = $remote.PSObject.Properties.Remove('url')
        $changed = $true
        $keysChanged.Add('gateway.remote.url:removed')
      } else {
        $wouldChange = $true
      }
    }
  }
}

if ($changed) {
  Write-Utf8Json -Path $configPath -Value $config
  $config = Read-JsonFile -Path $configPath
}

$afterClass = Classify-TransportMode -Config $config

$result = [ordered]@{
  timestamp = $timestamp
  changed = [bool]$changed
  what_if = [bool]$WhatIfPreference
  would_change = [bool]$wouldChange
  before_mode_classification = $beforeClass
  after_mode_classification = $afterClass
  keys_changed = @($keysChanged)
}

Write-Utf8Json -Path $resultPath -Value $result

if ($changed) {
  Write-Output 'transport_aligned'
} else {
  Write-Output 'transport_unchanged'
}

exit 0
