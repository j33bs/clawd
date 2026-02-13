# gateway_inspect.ps1
# Read-only inspection + regression diff for OpenClaw gateway (Scheduled Task launcher).
# Token-safe: redacts secrets/tokens from any printed strings and persisted reports.

[CmdletBinding()]
param(
  [int]$Port = 18789,
  [string[]]$TaskActionMatch = @("gateway.cmd", "openclaw"),
  [string]$MalformedNeedle = "C:\Users\heath.openclaw",
  [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------
# Utilities
# ---------------------------

$ScriptVersion = "2026-02-13.1"
$ReportLines = New-Object System.Collections.Generic.List[string]
$CollectedStrings = New-Object System.Collections.Generic.List[string]

function Write-ReportLine {
  param([AllowEmptyString()][string]$Line)
  $safe = Redact-Text $Line
  $ReportLines.Add($safe) | Out-Null
  Write-Host $safe
}

function Write-Section {
  param([Parameter(Mandatory=$true)][string]$Title)
  Write-ReportLine ""
  Write-ReportLine ("=" * 78)
  Write-ReportLine $Title
  Write-ReportLine ("=" * 78)
}

function Add-CollectedString {
  param([string]$s)
  if ([string]::IsNullOrEmpty($s)) { return }
  $CollectedStrings.Add($s) | Out-Null
}

function Get-Sha256Hex {
  param([string]$s)
  if ($null -eq $s) { return $null }
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($s)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $hash = $sha.ComputeHash($bytes)
    return ([System.BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Redact-Text {
  param([string]$s)
  if ([string]::IsNullOrWhiteSpace($s)) { return $s }

  $out = $s

  # 1) Authorization headers / Bearer tokens
  $out = [regex]::Replace($out, '(?i)\b(Authorization\s*[:=]\s*Bearer\s+)([A-Za-z0-9._\-+=/]+)', '${1}<redacted>')
  $out = [regex]::Replace($out, '(?i)\b(Bearer\s+)([A-Za-z0-9._\-+=/]{18,})\b', '${1}<redacted>')

  # 2) CLI flags: --token <v>, --token=<v>, --api-key, --secret, --password, etc.
  $out = [regex]::Replace(
    $out,
    '(?i)(--(?:api[-_]?key|token|secret|password|passwd))(?:\s+|=)(\"[^\"]*\"|''[^'']*''|\S+)',
    '${1}=<redacted>'
  )

  # 3) Env-style assignments containing KEY/TOKEN/SECRET/PASSWORD/PASSWD (quoted or unquoted)
  $out = [regex]::Replace(
    $out,
    '(?i)\b([A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD)[A-Z0-9_]*)\s*=\s*(\"[^\"]*\"|''[^'']*''|[^\s]+)',
    '${1}=<redacted>'
  )

  # 4) Raw token shapes (common)
  $out = [regex]::Replace($out, '\bsk-[A-Za-z0-9]{10,}\b', 'sk-<redacted>')
  $out = [regex]::Replace($out, '\bghp_[A-Za-z0-9]{30,}\b', 'ghp_<redacted>')
  $out = [regex]::Replace($out, '\bxox[a-zA-Z]-[A-Za-z0-9-]{10,}\b', 'xox<redacted>')
  $out = [regex]::Replace($out, '\b\d{6,}:[A-Za-z0-9_-]{20,}\b', '<redacted:telegram_bot_token>')

  return $out
}

function Sanitize-Value {
  param($v)
  if ($null -eq $v) { return $null }

  if ($v -is [string]) {
    Add-CollectedString $v
    return (Redact-Text $v)
  }

  if ($v -is [System.DateTime]) { return $v.ToString("o") }
  if ($v -is [bool] -or $v -is [int] -or $v -is [long] -or $v -is [double] -or $v -is [decimal]) { return $v }

  if ($v -is [System.Collections.IDictionary]) {
    $o = [ordered]@{}
    foreach ($k in @($v.Keys) | Sort-Object) {
      $o[[string]$k] = Sanitize-Value $v[$k]
    }
    return $o
  }

  if ($v -is [System.Collections.IEnumerable] -and -not ($v -is [pscustomobject])) {
    $arr = @()
    foreach ($x in $v) { $arr += ,(Sanitize-Value $x) }
    return $arr
  }

  # Generic object: sanitize its note properties.
  $ht = [ordered]@{}
  foreach ($p in @($v.PSObject.Properties | Sort-Object Name)) {
    if (-not $p) { continue }
    $name = $p.Name
    $val = $p.Value
    $ht[$name] = Sanitize-Value $val
  }
  return $ht
}

function Safe-StringDump {
  param([string]$label, $obj)
  if ($null -eq $obj) {
    Write-ReportLine "${label}: <null>"
    return
  }
  $san = Sanitize-Value $obj
  $json = $san | ConvertTo-Json -Depth 12
  foreach ($line in ($json -split "`r?`n")) {
    Write-ReportLine "${label}: $line"
    $label = " " * $label.Length
  }
}

function Find-MalformedHits {
  param([string]$needle, [hashtable]$stringsBySection)
  $hits = @()
  foreach ($k in @($stringsBySection.Keys) | Sort-Object) {
    $vals = @($stringsBySection[$k])
    $count = 0
    foreach ($s in $vals) {
      if ([string]::IsNullOrEmpty($s)) { continue }
      if ($s.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { $count++ }
    }
    if ($count -gt 0) {
      $hits += [pscustomobject]@{ section = $k; count = $count }
    }
  }
  return $hits
}

function Invoke-SelfTest {
  # No external/system calls. Do not print any raw token-like literals.
  $cases = @(
    @{ name = "auth_bearer"; input = "Authorization: Bearer NOT_A_SECRET"; expect = "<redacted>" },
    @{ name = "cli_token_eq"; input = "--token=NOT_A_SECRET"; expect = "<redacted>" },
    @{ name = "cli_token_sp"; input = "--token NOT_A_SECRET"; expect = "<redacted>" },
    @{ name = "cli_apikey"; input = "--api-key NOT_A_SECRET"; expect = "<redacted>" },
    @{ name = "env_token"; input = "SOME_TOKEN=NOT_A_SECRET"; expect = "<redacted>" }
  )

  foreach ($c in $cases) {
    $r = Redact-Text ([string]$c.input)
    if ($r.IndexOf([string]$c.expect, [System.StringComparison]::Ordinal) -lt 0) {
      throw ("SelfTest failed: redaction missing for case '{0}'" -f $c.name)
    }
    if ($r -eq [string]$c.input) {
      throw ("SelfTest failed: redaction did not change input for case '{0}'" -f $c.name)
    }
  }

  Write-Host "SelfTest PASS"
}

# ---------------------------
# Run directory
# ---------------------------

try {
  if ($SelfTest) {
    Invoke-SelfTest
    exit 0
  }

  # This script lives in scripts/. Repo root is parent of $PSScriptRoot.
  $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
  $TmpRoot = Join-Path $RepoRoot ".tmp\gateway_inspect"

  if (-not (Test-Path -LiteralPath $TmpRoot)) {
    New-Item -ItemType Directory -Path $TmpRoot -Force | Out-Null
  }

  $PreviousRunDir = $null
  $prior = @(Get-ChildItem -LiteralPath $TmpRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "run_*" } | Sort-Object Name)
  if ($prior.Count -gt 0) { $PreviousRunDir = $prior[-1].FullName }

  # Include milliseconds to avoid collisions when run twice within the same second.
  $RunStamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
  $RunDir = Join-Path $TmpRoot ("run_{0}" -f $RunStamp)
  New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

  $ReportJsonPath = Join-Path $RunDir "report.json"
  $ReportTxtPath  = Join-Path $RunDir "report.txt"
  $DiffJsonPath   = Join-Path $RunDir "diff.json"
  $DiffTxtPath    = Join-Path $RunDir "diff.txt"

  $report = [ordered]@{
    meta = [ordered]@{
      scriptVersion = $ScriptVersion
      timestampUtc  = (Get-Date).ToUniversalTime().ToString("o")
      computerName  = $env:COMPUTERNAME
      userName      = $env:USERNAME
      repoRoot      = $RepoRoot
      runDir        = $RunDir
      previousRunDir = $PreviousRunDir
    }
    inspection = [ordered]@{
      port = $Port
      listener = [ordered]@{
        connections = @()
        processes   = @()
        errors      = @()
      }
      scheduledTasks = [ordered]@{
        matchTerms = $TaskActionMatch
        tasks      = @()
        errors     = @()
      }
      malformedPath = [ordered]@{
        needle = $MalformedNeedle
        hits   = @()
        totalCount = 0
      }
    }
  }

  $stringsBySection = @{
    "process.commandLine" = @()
    "task.action.execute" = @()
    "task.action.arguments" = @()
    "task.action.workingDirectory" = @()
  }

  # ---------------------------
  # A1) TCP listener ownership
  # ---------------------------

  Write-Section ("A1) TCP Listener Ownership (Port {0})" -f $Port)

  $connections = @()
  try {
    # Avoid -LocalPort because it can throw when there are zero matches, which can
    # cause powershell.exe -Command to exit 1 even though "listener missing" is an
    # expected condition (we want exit 2 per contract).
    $connections = @(
      Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalPort -eq $Port } |
        Sort-Object LocalAddress, LocalPort, OwningProcess
    )
  } catch {
    $msg = "Get-NetTCPConnection failed: " + $_.Exception.Message
    $report.inspection.listener.errors += $msg
    Write-ReportLine $msg
  }

  if (-not $connections -or $connections.Count -eq 0) {
    Write-ReportLine ("No LISTEN socket found on port {0}." -f $Port)
  } else {
    $connRows = $connections | Select-Object LocalAddress, LocalPort, OwningProcess
    $report.inspection.listener.connections = @(
      $connRows | ForEach-Object {
        [ordered]@{
          LocalAddress   = [string]$_.LocalAddress
          LocalPort      = [int]$_.LocalPort
          OwningProcess  = [int]$_.OwningProcess
        }
      }
    )

    # Human table
    ($connRows | Format-Table -AutoSize -Wrap | Out-String -Width 240).TrimEnd() -split "`r?`n" | ForEach-Object { Write-ReportLine $_ }

    $pids = @($connections | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -and $_ -gt 0 } | Sort-Object)
    foreach ($targetPid in $pids) {
      Write-ReportLine ""
      Write-ReportLine ("OwningProcess PID: {0}" -f $targetPid)

      $proc = $null
      try {
        $proc = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $targetPid) -ErrorAction Stop
      } catch {
        $msg = "Win32_Process query failed for PID {0}: {1}" -f $targetPid, $_.Exception.Message
        $report.inspection.listener.errors += $msg
        Write-ReportLine $msg
      }

      if ($proc) {
        $cmd = [string]$proc.CommandLine
        $exe = [string]$proc.ExecutablePath
        $name = [string]$proc.Name

        $stringsBySection["process.commandLine"] += $cmd
        Add-CollectedString $cmd

        $procObj = [ordered]@{
          ProcessId      = [int]$proc.ProcessId
          Name           = $name
          ExecutablePath = $exe
          CommandLine    = (Redact-Text $cmd)
          CommandLineSha256 = (Get-Sha256Hex (Redact-Text $cmd))
        }
        $report.inspection.listener.processes += $procObj

        # Print (sanitized)
        Write-ReportLine ("ProcessId      : {0}" -f $procObj.ProcessId)
        Write-ReportLine ("Name           : {0}" -f (Redact-Text $procObj.Name))
        Write-ReportLine ("ExecutablePath : {0}" -f (Redact-Text $procObj.ExecutablePath))
        Write-ReportLine ("CommandLine    : {0}" -f $procObj.CommandLine)
      }
    }
  }

  # ---------------------------
  # A2) Scheduled Tasks enumeration
  # ---------------------------

  Write-Section "A2) Scheduled Tasks Enumeration (Actions contain match terms)"

  $allTasks = @()
  try {
    $allTasks = @(Get-ScheduledTask -ErrorAction Stop)
  } catch {
    $msg = "Get-ScheduledTask failed: " + $_.Exception.Message
    $report.inspection.scheduledTasks.errors += $msg
    Write-ReportLine $msg
  }

  $matches = @()
  foreach ($t in $allTasks) {
    $hit = $false
    $actions = @($t.Actions)

    foreach ($a in $actions) {
      $execute = $null
      $args = $null
      $wd = $null
      try { $execute = $a.Execute } catch {}
      try { $args = $a.Arguments } catch {}
      try { $wd = $a.WorkingDirectory } catch {}

      $hay = @()
      if ($execute) { $hay += [string]$execute }
      if ($args)    { $hay += [string]$args }
      if ($wd)      { $hay += [string]$wd }

      foreach ($needle in $TaskActionMatch) {
        if (($hay -join "`n").IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
          $hit = $true
          break
        }
      }
      if ($hit) { break }
    }

    if ($hit) { $matches += $t }
  }

  Write-ReportLine ("Matched tasks: {0}" -f $matches.Count)

  $summary = @($matches | Select-Object TaskName, TaskPath, State | Sort-Object TaskPath, TaskName)
  if ($summary.Count -gt 0) {
    ($summary | Format-Table -AutoSize -Wrap | Out-String -Width 240).TrimEnd() -split "`r?`n" | ForEach-Object { Write-ReportLine $_ }
  }

  foreach ($t in ($matches | Sort-Object TaskPath, TaskName)) {
    Write-Section ("Task Detail: {0}{1}" -f $t.TaskPath, $t.TaskName)

    $taskObj = [ordered]@{
      TaskName  = [string]$t.TaskName
      TaskPath  = [string]$t.TaskPath
      State     = [string]$t.State
      Principal = (Sanitize-Value ($t.Principal | Select-Object *))
      Actions   = @()
      Triggers  = @()
      Settings  = (Sanitize-Value ($t.Settings | Select-Object *))
      RuntimeInfo = $null
    }

    # Principal
    Write-ReportLine "[Principal]"
    Safe-StringDump "  " ($taskObj.Principal)

    # Actions
    Write-ReportLine "[Actions]"
    foreach ($a in @($t.Actions)) {
      $execute = $null
      $args = $null
      $wd = $null
      try { $execute = $a.Execute } catch {}
      try { $args = $a.Arguments } catch {}
      try { $wd = $a.WorkingDirectory } catch {}

      $stringsBySection["task.action.execute"] += [string]$execute
      $stringsBySection["task.action.arguments"] += [string]$args
      $stringsBySection["task.action.workingDirectory"] += [string]$wd

      Add-CollectedString ([string]$execute)
      Add-CollectedString ([string]$args)
      Add-CollectedString ([string]$wd)

      $actionProj = [ordered]@{
        Execute          = (Sanitize-Value ([string]$execute))
        Arguments        = (Sanitize-Value ([string]$args))
        WorkingDirectory = (Sanitize-Value ([string]$wd))
        ArgumentsSha256  = (Get-Sha256Hex (Redact-Text ([string]$args)))
      }
      $taskObj.Actions += $actionProj

      # Deterministic projection (always shows WorkingDirectory)
      Write-ReportLine "  - Execute          : $($actionProj.Execute)"
      Write-ReportLine "    Arguments        : $($actionProj.Arguments)"
      Write-ReportLine "    WorkingDirectory : $($actionProj.WorkingDirectory)"
    }

    # Triggers
    Write-ReportLine "[Triggers]"
    foreach ($tr in @($t.Triggers)) {
      $taskObj.Triggers += (Sanitize-Value ($tr | Select-Object *))
    }
    Safe-StringDump "  " ($taskObj.Triggers)

    # Settings
    Write-ReportLine "[Settings]"
    Safe-StringDump "  " ($taskObj.Settings)

    # Runtime info
    Write-ReportLine "[RuntimeInfo]"
    try {
      $info = Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $t.TaskPath -ErrorAction Stop
      $taskObj.RuntimeInfo = (Sanitize-Value ($info | Select-Object *))
      Safe-StringDump "  " ($taskObj.RuntimeInfo)
    } catch {
      $msg = "Get-ScheduledTaskInfo failed: " + $_.Exception.Message
      $report.inspection.scheduledTasks.errors += $msg
      Write-ReportLine $msg
    }

    $report.inspection.scheduledTasks.tasks += $taskObj
  }

  # ---------------------------
  # A3) Malformed-path detection
  # ---------------------------

  Write-Section "A3) Malformed-Path Detection"

  $hits = @(Find-MalformedHits -needle $MalformedNeedle -stringsBySection $stringsBySection)
  $total = 0
  foreach ($h in $hits) { $total += [int]$h.count }

  $report.inspection.malformedPath.hits = @($hits)
  $report.inspection.malformedPath.totalCount = $total

  Write-ReportLine ("Needle: {0}" -f $MalformedNeedle)
  Write-ReportLine ("Total hits: {0}" -f $total)
  if ($hits.Count -gt 0) {
    Write-ReportLine "Hit sections:"
    foreach ($h in $hits) {
      Write-ReportLine ("  - {0}: {1}" -f $h.section, $h.count)
    }
  }

  # ---------------------------
  # B) Persist report
  # ---------------------------

  $ReportText = ($ReportLines -join "`r`n") + "`r`n"
  Set-Content -LiteralPath $ReportTxtPath -Value $ReportText -Encoding UTF8

  $reportJson = ($report | ConvertTo-Json -Depth 24) + "`n"
  Set-Content -LiteralPath $ReportJsonPath -Value $reportJson -Encoding UTF8

  # ---------------------------
  # B5) Diff with previous run
  # ---------------------------

  Write-Section "B) Regression Diff (Current vs Previous)"

  $diffObj = [ordered]@{
    meta = [ordered]@{
      currentRunDir  = $RunDir
      previousRunDir = $PreviousRunDir
      timestampUtc   = (Get-Date).ToUniversalTime().ToString("o")
      scriptVersion  = $ScriptVersion
    }
    listener = [ordered]@{
      previousPids = @()
      currentPids  = @()
      pidChanged   = $null
      commandLineChanged = $null
    }
    tasks = [ordered]@{
      previousTaskIds = @()
      currentTaskIds  = @()
      added   = @()
      removed = @()
      actionChanges = @()
    }
    malformedPath = [ordered]@{
      previousTotal = $null
      currentTotal  = $report.inspection.malformedPath.totalCount
      changed       = $null
      failRisen     = $null
    }
  }

  if (-not $PreviousRunDir) {
    Write-ReportLine "No previous run found; diff skipped."
    Set-Content -LiteralPath $DiffTxtPath -Value ("No previous run found.`r`n") -Encoding UTF8
    Set-Content -LiteralPath $DiffJsonPath -Value (($diffObj | ConvertTo-Json -Depth 24) + "`n") -Encoding UTF8
  } else {
    $prevReportPath = Join-Path $PreviousRunDir "report.json"
    if (-not (Test-Path -LiteralPath $prevReportPath -PathType Leaf)) {
      Write-ReportLine "Previous report.json not found; diff skipped."
      Set-Content -LiteralPath $DiffTxtPath -Value ("Previous report.json not found.`r`n") -Encoding UTF8
      Set-Content -LiteralPath $DiffJsonPath -Value (($diffObj | ConvertTo-Json -Depth 24) + "`n") -Encoding UTF8
    } else {
      $prev = Get-Content -LiteralPath $prevReportPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop

      $prevPids = @()
      $currPids = @()
      try { $prevPids = @($prev.inspection.listener.processes | ForEach-Object { [int]$_.ProcessId }) } catch {}
      try { $currPids = @($report.inspection.listener.processes | ForEach-Object { [int]$_.ProcessId }) } catch {}
      $prevPids = @($prevPids | Sort-Object)
      $currPids = @($currPids | Sort-Object)

      $diffObj.listener.previousPids = $prevPids
      $diffObj.listener.currentPids = $currPids
      $diffObj.listener.pidChanged = -not (@($prevPids) -join "," -eq @($currPids) -join ",")

      $prevCmdHashes = @()
      $currCmdHashes = @()
      try { $prevCmdHashes = @($prev.inspection.listener.processes | ForEach-Object { [string]$_.CommandLineSha256 }) } catch {}
      try { $currCmdHashes = @($report.inspection.listener.processes | ForEach-Object { [string]$_.CommandLineSha256 }) } catch {}
      $diffObj.listener.commandLineChanged = -not (@($prevCmdHashes) -join "," -eq @($currCmdHashes) -join ",")

      $prevTaskIds = @()
      $currTaskIds = @()
      try { $prevTaskIds = @($prev.inspection.scheduledTasks.tasks | ForEach-Object { [string]($_.TaskPath + "|" + $_.TaskName) }) } catch {}
      try { $currTaskIds = @($report.inspection.scheduledTasks.tasks | ForEach-Object { [string]($_.TaskPath + "|" + $_.TaskName) }) } catch {}

      $diffObj.tasks.previousTaskIds = $prevTaskIds
      $diffObj.tasks.currentTaskIds = $currTaskIds

      $prevSet = [System.Collections.Generic.HashSet[string]]::new()
      foreach ($id in $prevTaskIds) { [void]$prevSet.Add($id) }
      $currSet = [System.Collections.Generic.HashSet[string]]::new()
      foreach ($id in $currTaskIds) { [void]$currSet.Add($id) }

      $added = @()
      foreach ($id in $currTaskIds) { if (-not $prevSet.Contains($id)) { $added += $id } }
      $removed = @()
      foreach ($id in $prevTaskIds) { if (-not $currSet.Contains($id)) { $removed += $id } }

      $diffObj.tasks.added = $added
      $diffObj.tasks.removed = $removed

      # Action field changes per task
      $prevTasksById = @{}
      foreach ($t in @($prev.inspection.scheduledTasks.tasks)) {
        $id = [string]($t.TaskPath + "|" + $t.TaskName)
        $prevTasksById[$id] = $t
      }
      $currTasksById = @{}
      foreach ($t in @($report.inspection.scheduledTasks.tasks)) {
        $id = [string]($t.TaskPath + "|" + $t.TaskName)
        $currTasksById[$id] = $t
      }

      $commonIds = @()
      foreach ($id in $currTaskIds) { if ($prevSet.Contains($id)) { $commonIds += $id } }

      $actionChanges = @()
      foreach ($id in $commonIds) {
        $pt = $prevTasksById[$id]
        $ct = $currTasksById[$id]
        $pActions = @($pt.Actions)
        $cActions = @($ct.Actions)

        $max = [Math]::Max($pActions.Count, $cActions.Count)
        for ($i = 0; $i -lt $max; $i++) {
          $pa = if ($i -lt $pActions.Count) { $pActions[$i] } else { $null }
          $ca = if ($i -lt $cActions.Count) { $cActions[$i] } else { $null }

          $pExec = if ($pa) { [string]$pa.Execute } else { "" }
          $cExec = if ($ca) { [string]$ca.Execute } else { "" }
          $pArgsHash = if ($pa) { [string]$pa.ArgumentsSha256 } else { "" }
          $cArgsHash = if ($ca) { [string]$ca.ArgumentsSha256 } else { "" }
          $pWd = if ($pa) { [string]$pa.WorkingDirectory } else { "" }
          $cWd = if ($ca) { [string]$ca.WorkingDirectory } else { "" }

          if ($pExec -ne $cExec -or $pArgsHash -ne $cArgsHash -or $pWd -ne $cWd) {
            $actionChanges += [ordered]@{
              taskId = $id
              actionIndex = $i
              previous = [ordered]@{ Execute = $pExec; ArgumentsSha256 = $pArgsHash; WorkingDirectory = $pWd }
              current  = [ordered]@{ Execute = $cExec; ArgumentsSha256 = $cArgsHash; WorkingDirectory = $cWd }
            }
          }
        }
      }
      $diffObj.tasks.actionChanges = $actionChanges

      $prevMalformed = $null
      try { $prevMalformed = [int]$prev.inspection.malformedPath.totalCount } catch { $prevMalformed = $null }
      $currMalformed = [int]$report.inspection.malformedPath.totalCount
      $diffObj.malformedPath.previousTotal = $prevMalformed
      $diffObj.malformedPath.currentTotal = $currMalformed
      if ($null -ne $prevMalformed) {
        $diffObj.malformedPath.changed = ($prevMalformed -ne $currMalformed)
        $diffObj.malformedPath.failRisen = ($prevMalformed -eq 0 -and $currMalformed -gt 0)
      }

      # Write human diff
      $diffLines = New-Object System.Collections.Generic.List[string]
      $diffLines.Add(("Previous: {0}" -f $PreviousRunDir)) | Out-Null
      $diffLines.Add(("Current : {0}" -f $RunDir)) | Out-Null
      $diffLines.Add("") | Out-Null

      $diffLines.Add("Listener PID(s):") | Out-Null
      $diffLines.Add(("  prev: {0}" -f (@($prevPids) -join ", "))) | Out-Null
      $diffLines.Add(("  curr: {0}" -f (@($currPids) -join ", "))) | Out-Null
      $diffLines.Add(("  changed: {0}" -f $diffObj.listener.pidChanged)) | Out-Null
      $diffLines.Add(("CommandLine changed (redacted hash): {0}" -f $diffObj.listener.commandLineChanged)) | Out-Null
      $diffLines.Add("") | Out-Null

      $diffLines.Add("Scheduled tasks match set:") | Out-Null
      $diffLines.Add(("  added  : {0}" -f (@($added) -join "; "))) | Out-Null
      $diffLines.Add(("  removed: {0}" -f (@($removed) -join "; "))) | Out-Null
      $diffLines.Add(("  actionChanges: {0}" -f $actionChanges.Count)) | Out-Null
      $diffLines.Add("") | Out-Null

      $diffLines.Add("Malformed-path detection:") | Out-Null
      $diffLines.Add(("  prev total: {0}" -f $prevMalformed)) | Out-Null
      $diffLines.Add(("  curr total: {0}" -f $currMalformed)) | Out-Null
      if ($null -ne $prevMalformed) {
        $diffLines.Add(("  changed : {0}" -f $diffObj.malformedPath.changed)) | Out-Null
        $diffLines.Add(("  FAIL (0->>0): {0}" -f $diffObj.malformedPath.failRisen)) | Out-Null
      }

      $diffText = (($diffLines -join "`r`n") + "`r`n")
      Set-Content -LiteralPath $DiffTxtPath -Value $diffText -Encoding UTF8
      Set-Content -LiteralPath $DiffJsonPath -Value (($diffObj | ConvertTo-Json -Depth 24) + "`n") -Encoding UTF8

      # Echo a short diff summary to console
      Write-ReportLine ("Listener PIDs prev=[{0}] curr=[{1}] changed={2}" -f (@($prevPids) -join ","), (@($currPids) -join ","), $diffObj.listener.pidChanged)
      Write-ReportLine ("Tasks added={0} removed={1} actionChanges={2}" -f $added.Count, $removed.Count, $actionChanges.Count)
      if ($null -ne $prevMalformed) {
        Write-ReportLine ("Malformed total prev={0} curr={1} FAIL_0_to_gt0={2}" -f $prevMalformed, $currMalformed, $diffObj.malformedPath.failRisen)
      }
    }
  }

  # ---------------------------
  # Exit codes
  # ---------------------------

  $listenerExists = $false
  try { $listenerExists = ($report.inspection.listener.connections.Count -gt 0) } catch { $listenerExists = $false }
  $malformedCount = [int]$report.inspection.malformedPath.totalCount

  Write-Section "Exit Status"
  Write-ReportLine ("Listener exists: {0}" -f $listenerExists)
  Write-ReportLine ("Malformed-path hits: {0}" -f $malformedCount)
  Write-ReportLine ("Report JSON: {0}" -f $ReportJsonPath)
  Write-ReportLine ("Report TXT : {0}" -f $ReportTxtPath)
  Write-ReportLine ("Diff JSON  : {0}" -f $DiffJsonPath)
  Write-ReportLine ("Diff TXT   : {0}" -f $DiffTxtPath)

  if (-not $listenerExists -or $malformedCount -gt 0) {
    exit 2
  }
  exit 0
}
catch {
  # Unexpected script errors: exit 1
  try {
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host "SCRIPT ERROR"
    Write-Host ("=" * 78)
    Write-Host (Redact-Text $_.Exception.Message)
    if ($_.InvocationInfo) {
      Write-Host ("ERROR_LINE: " + $_.InvocationInfo.ScriptLineNumber)
      $line = $_.InvocationInfo.Line
      if ($null -eq $line) { $line = "" }
      Write-Host ("ERROR_CMD : " + (Redact-Text $line))
    }
  } catch {}
  exit 1
}
