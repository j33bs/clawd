[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [switch]$Apply,
  [switch]$Revert
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Apply -and $Revert) {
  throw 'Use either -Apply or -Revert, not both.'
}

function Write-Utf8Json {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)]$Value
  )

  $json = $Value | ConvertTo-Json -Depth 24
  [System.IO.File]::WriteAllText($Path, $json + "`n", [System.Text.UTF8Encoding]::new($false))
}

function Read-JsonFile {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Config file not found: $Path"
  }

  return (Get-Content -LiteralPath $Path -Raw) | ConvertFrom-Json
}

function Get-GatewayDebugFlag {
  param([Parameter(Mandatory = $true)][string]$ConfigPath)

  if (-not (Test-Path -LiteralPath $ConfigPath)) {
    return $false
  }

  try {
    $config = Read-JsonFile -Path $ConfigPath
    if ($null -eq $config.PSObject.Properties['gateway'] -or $null -eq $config.gateway) {
      return $false
    }
    if ($null -eq $config.gateway.PSObject.Properties['debugHandshake']) {
      return $false
    }
    return [bool]$config.gateway.debugHandshake
  } catch {
    return $false
  }
}

function Get-AllowedClientIds {
  param([Parameter(Mandatory = $true)][string]$MessageChannelPath)

  $raw = Get-Content -LiteralPath $MessageChannelPath -Raw
  $match = [regex]::Match($raw, 'const GATEWAY_CLIENT_IDS = \{(?<body>[\s\S]*?)\};')
  if (-not $match.Success) {
    return @()
  }

  $ids = New-Object System.Collections.Generic.List[string]
  $valueMatches = [regex]::Matches($match.Groups['body'].Value, ':\s*"([^"]+)"')
  foreach ($m in $valueMatches) {
    $id = [string]$m.Groups[1].Value
    if (-not [string]::IsNullOrWhiteSpace($id) -and -not $ids.Contains($id)) {
      $ids.Add($id)
    }
  }
  return @($ids)
}

function Get-PatchPlan {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Marker,
    [Parameter(Mandatory = $true)][string]$Anchor,
    [Parameter(Mandatory = $true)][string]$Insertion
  )

  $content = Get-Content -LiteralPath $Path -Raw
  if ($content.Contains($Marker)) {
    return [pscustomobject]@{
      state = 'already_patched'
      new_content = $null
    }
  }

  if (-not $content.Contains($Anchor)) {
    return [pscustomobject]@{
      state = 'anchor_not_found'
      new_content = $null
    }
  }

  $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
  $normalizedInsertion = $Insertion -replace "`n", $newline
  $replacement = $Anchor + $newline + $normalizedInsertion
  $newContent = $content.Replace($Anchor, $replacement)

  return [pscustomobject]@{
    state = 'patchable'
    new_content = $newContent
  }
}

$mode = if ($Apply) { 'apply' } elseif ($Revert) { 'revert' } else { 'inspect' }
$timestamp = (Get-Date).ToUniversalTime().ToString('o')
$stampForFile = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$evidenceDir = Join-Path $repoRoot '.tmp/system1_evidence'
$resultPath = Join-Path $evidenceDir 'handshake_debug_patch_result.json'
$schemaEvidencePath = Join-Path $evidenceDir 'client_id_schema.txt'
$configPath = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
$distDir = Join-Path $env:APPDATA 'npm\node_modules\openclaw\dist'

New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

$marker = '[handshake-debug-v1]'
$anchor = 'const handshakeError = isRequestFrame ? parsed.method === "connect" ? `invalid connect params: ${formatValidationErrors(validateConnectParams.errors)}` : "invalid handshake: first request must be connect" : "invalid request frame";'
$insertion = @'
const handshakeDebugEnabled = configSnapshot.gateway?.debugHandshake === true || process.env.OPENCLAW_DEBUG_HANDSHAKE === "1";
if (handshakeDebugEnabled && isRequestFrame && parsed.method === "connect") {
	const receivedClientId = parsed && parsed.params && typeof parsed.params === "object" && parsed.params && typeof parsed.params.client === "object" && parsed.params.client && typeof parsed.params.client.id === "string" ? parsed.params.client.id : null;
	const allowedClientIds = Object.values(GATEWAY_CLIENT_IDS);
	const anyOfHints = Array.isArray(validateConnectParams.errors) ? validateConnectParams.errors.filter((err) => err && (err.instancePath === "/client/id" || typeof err.schemaPath === "string" && err.schemaPath.includes("/anyOf/"))).map((err) => `${err.instancePath || "?"}:${err.message || "?"}`) : [];
	logWsControl.warn(`[handshake-debug-v1] invalid connect params conn=${connId} received_client_id=${receivedClientId ?? "<missing>"} allowed_client_ids=${JSON.stringify(allowedClientIds)} anyof=${JSON.stringify(anyOfHints)}`);
}
'@

$debugFlag = Get-GatewayDebugFlag -ConfigPath $configPath
$messageChannelFiles = @()
$gatewayCliFiles = @()
$allowedClientIds = @()
$status = 'unavailable'
$errorMessage = $null

$filesCandidateCount = 0
$alreadyPatchedCount = 0
$wouldPatch = $false
$patchedFiles = New-Object System.Collections.Generic.List[string]
$anchorMissingFiles = New-Object System.Collections.Generic.List[string]
$backupRecords = New-Object System.Collections.Generic.List[object]
$restoredRecords = New-Object System.Collections.Generic.List[object]

if (-not (Test-Path -LiteralPath $distDir)) {
  $status = 'dist_not_found'
  $errorMessage = "OpenClaw dist directory not found: $distDir"
} else {
  $messageChannelFiles = Get-ChildItem -LiteralPath $distDir -Filter 'message-channel-*.js' -File -ErrorAction SilentlyContinue | Sort-Object Name
  $gatewayCliFiles = Get-ChildItem -LiteralPath $distDir -Filter 'gateway-cli-*.js' -File -ErrorAction SilentlyContinue | Sort-Object Name
  $filesCandidateCount = $gatewayCliFiles.Count

  if ($messageChannelFiles.Count -gt 0) {
    $allowedClientIds = Get-AllowedClientIds -MessageChannelPath $messageChannelFiles[0].FullName
  }

  if ($mode -eq 'revert') {
    foreach ($file in $gatewayCliFiles) {
      $backupPattern = "$($file.FullName).bak.handshake-debug-v1.*"
      $latestBackup = Get-ChildItem -Path $backupPattern -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
      if ($null -ne $latestBackup) {
        if ($PSCmdlet.ShouldProcess($file.FullName, "Restore from backup $($latestBackup.FullName)")) {
          Copy-Item -LiteralPath $latestBackup.FullName -Destination $file.FullName -Force
        }
        $restoredRecords.Add([ordered]@{
          file = $file.FullName
          backup = $latestBackup.FullName
        })
      }

      $plan = Get-PatchPlan -Path $file.FullName -Marker $marker -Anchor $anchor -Insertion $insertion
      if ($plan.state -eq 'already_patched') {
        $alreadyPatchedCount++
      }
    }

    $status = if ($restoredRecords.Count -gt 0) { 'reverted' } else { 'no_backups_found' }
  } else {
    foreach ($file in $gatewayCliFiles) {
      $plan = Get-PatchPlan -Path $file.FullName -Marker $marker -Anchor $anchor -Insertion $insertion
      switch ($plan.state) {
        'already_patched' {
          $alreadyPatchedCount++
        }
        'patchable' {
          $wouldPatch = $true
          if ($mode -eq 'apply') {
            $backupPath = "$($file.FullName).bak.handshake-debug-v1.$stampForFile"
            if ($PSCmdlet.ShouldProcess($file.FullName, "Backup to $backupPath")) {
              Copy-Item -LiteralPath $file.FullName -Destination $backupPath -Force
            }
            if ($PSCmdlet.ShouldProcess($file.FullName, 'Apply local handshake debug patch')) {
              [System.IO.File]::WriteAllText($file.FullName, [string]$plan.new_content, [System.Text.UTF8Encoding]::new($false))
            }
            $patchedFiles.Add($file.FullName)
            $backupRecords.Add([ordered]@{
              file = $file.FullName
              backup = $backupPath
            })
          }
        }
        default {
          $anchorMissingFiles.Add($file.FullName)
        }
      }
    }

    if ($mode -eq 'apply') {
      $status = if ($patchedFiles.Count -gt 0) { 'applied' } elseif ($alreadyPatchedCount -gt 0) { 'already_patched' } elseif ($filesCandidateCount -gt 0) { 'anchor_not_found' } else { 'gateway_cli_not_found' }
    } else {
      $status = if ($filesCandidateCount -gt 0) { 'inspected' } else { 'gateway_cli_not_found' }
    }
  }
}

$schemaLines = New-Object System.Collections.Generic.List[string]
$schemaLines.Add('OpenClaw client.id handshake schema snapshot')
$schemaLines.Add("timestamp=$timestamp")
$schemaLines.Add("mode=$mode")
$schemaLines.Add("debug_handshake_flag=$debugFlag")
$schemaLines.Add("dist_dir=$distDir")
$schemaLines.Add('')
$schemaLines.Add('Allowed client.id constants:')
foreach ($id in $allowedClientIds) {
  $schemaLines.Add("- $id")
}
$schemaLines.Add('')
$schemaLines.Add('Schema references:')
$schemaLines.Add('- message-channel-*.js: GATEWAY_CLIENT_IDS constant set')
$schemaLines.Add('- net-*.js: GatewayClientIdSchema = union(literal GATEWAY_CLIENT_IDS)')
$schemaLines.Add('- net-*.js: ConnectParamsSchema.client.id = GatewayClientIdSchema')
$schemaLines.Add('- gateway-cli-*.js: invalid connect params branch uses validateConnectParams(parsed.params)')
$schemaLines.Add('')
$schemaLines.Add('Expected auth/device requirements at connect:')
$schemaLines.Add('- connect.params.auth supports token/password and is evaluated by authorizeGatewayConnect.')
$schemaLines.Add('- connect.params.device requires id/publicKey/signature/signedAt; nonce is required for non-local clients.')
$schemaLines.Add('- device signature freshness and signature validity are enforced; invalid signatures close with 1008.')
$schemaLines.Add('- missing required device identity can close with 1008 (NOT_PAIRED/device identity required).')
$schemaLines.Add('')
$schemaLines.Add('Supported debug toggles:')
$schemaLines.Add('- OPENCLAW_DEBUG_HANDSHAKE=1 (supported in patched gateway-cli dist)')
$schemaLines.Add('- gateway.debugHandshake=true (only if your build config schema accepts it)')

[System.IO.File]::WriteAllText($schemaEvidencePath, ($schemaLines -join [Environment]::NewLine) + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$messageChannelFilePaths = @()
foreach ($item in $messageChannelFiles) {
  $messageChannelFilePaths += [string]$item.FullName
}

$gatewayCliFilePaths = @()
foreach ($item in $gatewayCliFiles) {
  $gatewayCliFilePaths += [string]$item.FullName
}

$patchedFilePaths = @()
foreach ($item in $patchedFiles) {
  $patchedFilePaths += [string]$item
}

$anchorMissingFilePaths = @()
foreach ($item in $anchorMissingFiles) {
  $anchorMissingFilePaths += [string]$item
}

$backupList = @()
foreach ($item in $backupRecords) {
  $backupList += $item
}

$restoredList = @()
foreach ($item in $restoredRecords) {
  $restoredList += $item
}

$result = [ordered]@{
  timestamp = $timestamp
  mode = $mode
  status = $status
  debug_handshake_flag = [bool]$debugFlag
  dist_dir = $distDir
  files_candidate_count = $filesCandidateCount
  would_patch = [bool]$wouldPatch
  already_patched_count = $alreadyPatchedCount
  allowed_client_ids = @($allowedClientIds)
  message_channel_files = $messageChannelFilePaths
  gateway_cli_files = $gatewayCliFilePaths
  patched_files = $patchedFilePaths
  anchor_missing_files = $anchorMissingFilePaths
  backups = $backupList
  restored = $restoredList
  schema_evidence_path = $schemaEvidencePath
  error = $errorMessage
}

Write-Utf8Json -Path $resultPath -Value $result

if ($mode -eq 'inspect') {
  Write-Output 'handshake_debug_inspect'
  Write-Output 'Inspect mode: no installed dist files were modified.'
  Write-Output 'To collect handshake logs, prefer supported toggles first:'
  Write-Output '  set OPENCLAW_DEBUG_HANDSHAKE=1'
  Write-Output 'If you need local diagnostic patching, run:'
  Write-Output '  .\openclaw.ps1 gateway handshake-debug --apply'
  Write-Output 'Rollback local patch backups with:'
  Write-Output '  .\openclaw.ps1 gateway handshake-debug --revert'
} elseif ($mode -eq 'apply') {
  Write-Output 'handshake_debug_apply'
  Write-Output 'Apply mode modified local installed dist files for diagnostics only.'
  Write-Output 'Rollback command:'
  Write-Output '  .\openclaw.ps1 gateway handshake-debug --revert'
} else {
  Write-Output 'handshake_debug_revert'
  if ($restoredRecords.Count -eq 0) {
    Write-Output 'No matching backups found to restore.'
  }
}

exit 0
