[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Utf8Json {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)]$Value
  )

  $json = $Value | ConvertTo-Json -Depth 12
  [System.IO.File]::WriteAllText($Path, $json + "`n", [System.Text.UTF8Encoding]::new($false))
}

$timestamp = (Get-Date).ToUniversalTime().ToString('o')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$evidenceDir = Join-Path $repoRoot '.tmp/system1_evidence'
$resultPath = Join-Path $evidenceDir 'start_gateway_task_result.json'

New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

$result = [ordered]@{
  status = 'not_found'
  task_name = $null
  task_path = $null
  timestamp = $timestamp
}

try {
  $tasks = Get-ScheduledTask | Where-Object {
    $_.TaskName -match 'OpenClaw' -and $_.TaskName -match 'Gateway'
  }
} catch {
  $result.status = 'query_failed'
  $result.error = $_.Exception.Message
  Write-Utf8Json -Path $resultPath -Value $result
  Write-Output 'query_failed'
  Write-Output 'Unable to query Scheduled Tasks. Run this from Windows PowerShell with ScheduledTasks access.'
  exit 1
}

if (-not $tasks) {
  Write-Utf8Json -Path $resultPath -Value $result
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
  Write-Utf8Json -Path $resultPath -Value $result
  Write-Output 'query_failed'
  Write-Output 'OpenClaw Gateway task state is unavailable.'
  exit 1
}

if ($state -eq 'Running') {
  $result.status = 'already_running'
  Write-Utf8Json -Path $resultPath -Value $result
  Write-Output 'already_running'
  exit 0
}

$listener = Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $listener) {
  $result.port_owner_pid = [int]$listener.OwningProcess
  $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
  if ($null -ne $proc) {
    $result.port_owner_name = $proc.ProcessName
  }
  $ownerName = if ($null -ne $proc) { [string]$proc.ProcessName } else { '' }
  if ($ownerName -and $ownerName -ne 'node') {
    $result.status = 'port_in_use'
    $result.error = 'Port 18789 is already bound by a non-node process.'
    Write-Utf8Json -Path $resultPath -Value $result
    Write-Output 'port_in_use'
    Write-Output 'Port 18789 is in use by another process. Stop that process (or move it off 18789) and rerun .\openclaw.ps1 gateway heal.'
    exit 1
  }
}

try {
  Start-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
  Start-Sleep -Seconds 1
  $postTask = Get-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
  $postState = [string]($postTask | Select-Object -ExpandProperty State -ErrorAction SilentlyContinue)

  if ($postState -eq 'Running') {
    $result.status = 'started'
    Write-Utf8Json -Path $resultPath -Value $result
    Write-Output 'started'
    exit 0
  }

  $result.status = 'start_requested'
  Write-Utf8Json -Path $resultPath -Value $result
  Write-Output 'start_requested'
  exit 0
} catch {
  $message = $_.Exception.Message
  if ($message -match 'Access is denied|0x80070005') {
    $result.status = 'admin_required'
    $result.error = 'Access denied when starting the OpenClaw Gateway task.'
    Write-Utf8Json -Path $resultPath -Value $result
    Write-Output 'admin_required'
    Write-Output 'Access denied starting the OpenClaw Gateway task. Re-run this command from an elevated PowerShell session.'
    exit 1
  }

  $result.status = 'start_failed'
  $result.error = $message
  Write-Utf8Json -Path $resultPath -Value $result
  Write-Output 'start_failed'
  Write-Output "Failed to start OpenClaw Gateway task: $message"
  exit 1
}
