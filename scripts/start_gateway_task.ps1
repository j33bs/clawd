[CmdletBinding()]
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

  return (Get-Content -LiteralPath $Path -Raw) | ConvertFrom-Json
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

function Resolve-ConfiguredPort {
  param([Parameter(Mandatory = $true)]$Config)

  if ($null -ne $Config.PSObject.Properties['gateway'] -and $null -ne $Config.gateway) {
    if ($null -ne $Config.gateway.PSObject.Properties['port']) {
      $port = [int]$Config.gateway.port
      if ($port -gt 0) { return $port }
    }
    if ($null -ne $Config.gateway.PSObject.Properties['remote'] -and $null -ne $Config.gateway.remote -and $null -ne $Config.gateway.remote.PSObject.Properties['url']) {
      $url = [string]$Config.gateway.remote.url
      if (-not [string]::IsNullOrWhiteSpace($url)) {
        try {
          $uri = [Uri]$url
          if ($uri.Port -gt 0) { return [int]$uri.Port }
        } catch {}
      }
    }
  }
  return 18789
}

function Get-PortOwner {
  param([Parameter(Mandatory = $true)][int]$Port)

  $listen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($null -eq $listen) {
    return $null
  }

  $ownerPid = [int]$listen.OwningProcess
  $proc = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
  $commandLine = $null
  try {
    $wmi = Get-CimInstance -ClassName Win32_Process -Filter ("ProcessId = {0}" -f $ownerPid) -ErrorAction Stop
    if ($null -ne $wmi -and -not [string]::IsNullOrWhiteSpace([string]$wmi.CommandLine)) {
      $commandLine = [string]$wmi.CommandLine
    }
  } catch {}

  return [ordered]@{
    pid = $ownerPid
    process_name = if ($null -ne $proc) { [string]$proc.ProcessName } else { $null }
    command_line = $commandLine
  }
}

function Is-OpenClawOwner {
  param($Owner)

  if ($null -eq $Owner) { return $false }
  $name = [string]$Owner.process_name
  if ([string]::IsNullOrWhiteSpace($name)) { return $false }

  $normalizedName = $name.ToLowerInvariant()
  if (@('openclaw', 'openclaw.exe').Contains($normalizedName)) {
    return $true
  }

  if (@('node', 'node.exe').Contains($normalizedName)) {
    $cmd = if ($null -ne $Owner.command_line) { [string]$Owner.command_line } else { '' }
    if ($cmd -match '(?i)\bopenclaw(\.cmd)?\b' -or $cmd -match '(?i)\\openclaw\\' -or $cmd -match '(?i)\bgateway\b.*\bopenclaw\b') {
      return $true
    }
  }

  return $false
}

function Find-FreePort {
  param([int]$Start = 18789, [int]$End = 18810)

  for ($p = $Start; $p -le $End; $p++) {
    $inUse = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $inUse) {
      return $p
    }
  }
  return $null
}

$timestamp = (Get-Date).ToUniversalTime().ToString('o')
$stampForFile = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$evidenceDir = Join-Path $repoRoot '.tmp/system1_evidence'
$startResultPath = Join-Path $evidenceDir 'start_gateway_task_result.json'
$portRemediationPath = Join-Path $evidenceDir 'port_remediation.json'
$configPath = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'

New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

$portEvidence = [ordered]@{
  timestamp = $timestamp
  configured_port = $null
  initial_in_use = $false
  initial_owner = $null
  wsl_shutdown_attempted = $false
  wsl_shutdown_exit_code = $null
  post_shutdown_in_use = $false
  post_shutdown_owner = $null
  port_reassigned = $false
  old_port = $null
  new_port = $null
  selection_reason = $null
  config_backup = $null
}

$config = Read-JsonFile -Path $configPath
$configuredPort = Resolve-ConfiguredPort -Config $config
$portEvidence.configured_port = $configuredPort

$initialOwner = Get-PortOwner -Port $configuredPort
if ($null -ne $initialOwner -and -not (Is-OpenClawOwner -Owner $initialOwner)) {
  $portEvidence.initial_in_use = $true
  $portEvidence.initial_owner = $initialOwner

  $portEvidence.wsl_shutdown_attempted = $true
  try {
    $proc = Start-Process -FilePath 'wsl.exe' -ArgumentList '--shutdown' -NoNewWindow -Wait -PassThru
    $portEvidence.wsl_shutdown_exit_code = $proc.ExitCode
  } catch {
    $portEvidence.wsl_shutdown_exit_code = 1
  }

  Start-Sleep -Seconds 1
  $postOwner = Get-PortOwner -Port $configuredPort
  if ($null -ne $postOwner -and -not (Is-OpenClawOwner -Owner $postOwner)) {
    $portEvidence.post_shutdown_in_use = $true
    $portEvidence.post_shutdown_owner = $postOwner

    $freePort = Find-FreePort -Start 18789 -End 18810
    if ($null -ne $freePort) {
      $backupPath = Join-Path $env:USERPROFILE ".openclaw\openclaw.json.bak.$stampForFile"
      Copy-Item -LiteralPath $configPath -Destination $backupPath -Force

      Ensure-ObjectProperty -Object $config -Name 'gateway'
      if ($null -eq $config.gateway.PSObject.Properties['port']) {
        $config.gateway | Add-Member -NotePropertyName port -NotePropertyValue $freePort -Force
      } else {
        $config.gateway.port = $freePort
      }

      if ($null -ne $config.gateway.PSObject.Properties['remote'] -and $null -ne $config.gateway.remote -and $null -ne $config.gateway.remote.PSObject.Properties['url']) {
        $rawUrl = [string]$config.gateway.remote.url
        if (-not [string]::IsNullOrWhiteSpace($rawUrl)) {
          try {
            $uri = [Uri]$rawUrl
            if ($uri.Host -in @('127.0.0.1', 'localhost', '::1')) {
              $builder = [UriBuilder]$uri
              $builder.Port = $freePort
              $config.gateway.remote.url = $builder.Uri.AbsoluteUri.TrimEnd('/')
            }
          } catch {}
        }
      }

      $json = $config | ConvertTo-Json -Depth 20
      [System.IO.File]::WriteAllText($configPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))

      $portEvidence.port_reassigned = $true
      $portEvidence.old_port = $configuredPort
      $portEvidence.new_port = $freePort
      $portEvidence.selection_reason = "Configured port $configuredPort remained occupied after wsl --shutdown; selected first free port in range 18789-18810."
      $portEvidence.config_backup = $backupPath
      $configuredPort = $freePort
    }
  }
}

Write-Utf8Json -Path $portRemediationPath -Value $portEvidence

$result = [ordered]@{
  status = 'not_found'
  task_name = $null
  task_path = $null
  timestamp = $timestamp
}

if ($portEvidence.post_shutdown_in_use -and -not $portEvidence.port_reassigned) {
  $result.status = 'port_in_use'
  $result.error = 'Configured gateway port remained occupied after wsl --shutdown, and no free fallback port was found in 18789-18810.'
  Write-Utf8Json -Path $startResultPath -Value $result
  Write-Output 'port_in_use'
  Write-Output 'Gateway port is still occupied; free the port manually and rerun .\openclaw.ps1 gateway heal.'
  exit 1
}

try {
  $tasks = Get-ScheduledTask | Where-Object {
    $_.TaskName -match 'OpenClaw' -and $_.TaskName -match 'Gateway'
  }
} catch {
  $result.status = 'query_failed'
  $result.error = $_.Exception.Message
  Write-Utf8Json -Path $startResultPath -Value $result
  Write-Output 'query_failed'
  Write-Output 'Unable to query Scheduled Tasks. Run this from Windows PowerShell with ScheduledTasks access.'
  exit 1
}

if (-not $tasks) {
  Write-Utf8Json -Path $startResultPath -Value $result
  Write-Output 'not_found'
  exit 1
}

$task = $tasks | Select-Object -First 1
$result.task_name = $task.TaskName
$result.task_path = $task.TaskPath

$state = [string]($task | Select-Object -ExpandProperty State -ErrorAction SilentlyContinue)
if ([string]::IsNullOrWhiteSpace($state)) {
  $result.status = 'query_failed'
  $result.error = 'Scheduled Task state property is unavailable.'
  Write-Utf8Json -Path $startResultPath -Value $result
  Write-Output 'query_failed'
  Write-Output 'OpenClaw Gateway task state is unavailable.'
  exit 1
}

if ($state -eq 'Running') {
  $result.status = 'already_running'
  Write-Utf8Json -Path $startResultPath -Value $result
  Write-Output 'already_running'
  exit 0
}

try {
  Start-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
  Start-Sleep -Seconds 1
  $postTask = Get-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
  $postState = [string]($postTask | Select-Object -ExpandProperty State -ErrorAction SilentlyContinue)

  if ($postState -eq 'Running') {
    $result.status = 'started'
    Write-Utf8Json -Path $startResultPath -Value $result
    Write-Output 'started'
    exit 0
  }

  $result.status = 'start_requested'
  Write-Utf8Json -Path $startResultPath -Value $result
  Write-Output 'start_requested'
  exit 0
} catch {
  $message = $_.Exception.Message
  if ($message -match 'Access is denied|0x80070005') {
    $result.status = 'admin_required'
    $result.error = 'Access denied when starting the OpenClaw Gateway task.'
    Write-Utf8Json -Path $startResultPath -Value $result
    Write-Output 'admin_required'
    Write-Output 'Access denied starting the OpenClaw Gateway task. Re-run this command from an elevated PowerShell session.'
    exit 1
  }

  $result.status = 'start_failed'
  $result.error = $message
  Write-Utf8Json -Path $startResultPath -Value $result
  Write-Output 'start_failed'
  Write-Output "Failed to start OpenClaw Gateway task: $message"
  exit 1
}
