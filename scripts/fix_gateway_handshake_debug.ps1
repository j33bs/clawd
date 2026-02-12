[CmdletBinding(SupportsShouldProcess = $true)]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Utf8Json {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)]$Value
  )

  $json = $Value | ConvertTo-Json -Depth 20
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

function Patch-GatewayCliFile {
  param(
    [Parameter(Mandatory = $true)][string]$Path
  )

  $marker = '[handshake-debug-v1]'
  $anchor = 'const handshakeError = isRequestFrame ? parsed.method === "connect" ? `invalid connect params: ${formatValidationErrors(validateConnectParams.errors)}` : "invalid handshake: first request must be connect" : "invalid request frame";'

  $content = Get-Content -LiteralPath $Path -Raw
  if ($content.Contains($marker)) {
    return 'already_patched'
  }

  if (-not $content.Contains($anchor)) {
    return 'anchor_not_found'
  }

  $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
  $insertion = @'
const handshakeDebugEnabled = configSnapshot.gateway?.debugHandshake === true || process.env.OPENCLAW_DEBUG_HANDSHAKE === "1";
if (handshakeDebugEnabled && isRequestFrame && parsed.method === "connect") {
	const receivedClientId = parsed && parsed.params && typeof parsed.params === "object" && parsed.params && typeof parsed.params.client === "object" && parsed.params.client && typeof parsed.params.client.id === "string" ? parsed.params.client.id : null;
	const allowedClientIds = Object.values(GATEWAY_CLIENT_IDS);
	const anyOfHints = Array.isArray(validateConnectParams.errors) ? validateConnectParams.errors.filter((err) => err && (err.instancePath === "/client/id" || typeof err.schemaPath === "string" && err.schemaPath.includes("/anyOf/"))).map((err) => `${err.instancePath || "?"}:${err.message || "?"}`) : [];
	logWsControl.warn(`[handshake-debug-v1] invalid connect params conn=${connId} received_client_id=${receivedClientId ?? "<missing>"} allowed_client_ids=${JSON.stringify(allowedClientIds)} anyof=${JSON.stringify(anyOfHints)}`);
}
'@
  $normalizedInsertion = $insertion -replace "`n", $newline
  $replacement = $anchor + $newline + $normalizedInsertion
  $newContent = $content.Replace($anchor, $replacement)

  $backupPath = "$Path.bak.handshake-debug-v1"
  if (-not (Test-Path -LiteralPath $backupPath)) {
    Copy-Item -LiteralPath $Path -Destination $backupPath -Force
  }

  if ($PSCmdlet.ShouldProcess($Path, 'Patch handshake invalid-connect logging with token-safe client.id observability')) {
    [System.IO.File]::WriteAllText($Path, $newContent, [System.Text.UTF8Encoding]::new($false))
  }

  return 'patched'
}

$timestamp = (Get-Date).ToUniversalTime().ToString('o')
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$evidenceDir = Join-Path $repoRoot '.tmp/system1_evidence'
$resultPath = Join-Path $evidenceDir 'handshake_debug_patch_result.json'
$schemaEvidencePath = Join-Path $evidenceDir 'client_id_schema.txt'
$configPath = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
$distDir = Join-Path $env:APPDATA 'npm\node_modules\openclaw\dist'

New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

$debugFlag = Get-GatewayDebugFlag -ConfigPath $configPath
$messageChannelFiles = @()
$gatewayCliFiles = @()
$allowedClientIds = @()
$patchedFiles = New-Object System.Collections.Generic.List[string]
$alreadyPatchedFiles = New-Object System.Collections.Generic.List[string]
$anchorMissingFiles = New-Object System.Collections.Generic.List[string]
$status = 'unavailable'
$errorMessage = $null

if (-not (Test-Path -LiteralPath $distDir)) {
  $status = 'dist_not_found'
  $errorMessage = "OpenClaw dist directory not found: $distDir"
} else {
  $messageChannelFiles = Get-ChildItem -LiteralPath $distDir -Filter 'message-channel-*.js' -File -ErrorAction SilentlyContinue | Sort-Object Name
  $gatewayCliFiles = Get-ChildItem -LiteralPath $distDir -Filter 'gateway-cli-*.js' -File -ErrorAction SilentlyContinue | Sort-Object Name

  if ($messageChannelFiles.Count -gt 0) {
    $allowedClientIds = Get-AllowedClientIds -MessageChannelPath $messageChannelFiles[0].FullName
  }

  foreach ($file in $gatewayCliFiles) {
    $patchState = Patch-GatewayCliFile -Path $file.FullName
    switch ($patchState) {
      'patched' { $patchedFiles.Add($file.FullName) }
      'already_patched' { $alreadyPatchedFiles.Add($file.FullName) }
      default { $anchorMissingFiles.Add($file.FullName) }
    }
  }

  if ($patchedFiles.Count -gt 0) {
    $status = 'patched'
  } elseif ($alreadyPatchedFiles.Count -gt 0) {
    $status = 'already_patched'
  } elseif ($gatewayCliFiles.Count -gt 0) {
    $status = 'anchor_not_found'
  } else {
    $status = 'gateway_cli_not_found'
  }
}

$schemaLines = New-Object System.Collections.Generic.List[string]
$schemaLines.Add('OpenClaw client.id handshake schema snapshot')
$schemaLines.Add("timestamp=$timestamp")
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
$schemaLines.Add('Message-channel files:')
foreach ($path in ($messageChannelFiles | ForEach-Object { $_.FullName })) {
  $schemaLines.Add("- $path")
}
$schemaLines.Add('Gateway-cli files:')
foreach ($path in ($gatewayCliFiles | ForEach-Object { $_.FullName })) {
  $schemaLines.Add("- $path")
}

[System.IO.File]::WriteAllText($schemaEvidencePath, ($schemaLines -join [Environment]::NewLine) + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$result = [ordered]@{
  timestamp = $timestamp
  status = $status
  debug_handshake_flag = [bool]$debugFlag
  dist_dir = $distDir
  allowed_client_ids = @($allowedClientIds)
  message_channel_files = @($messageChannelFiles | ForEach-Object { $_.FullName })
  gateway_cli_files = @($gatewayCliFiles | ForEach-Object { $_.FullName })
  patched_files = @($patchedFiles)
  already_patched_files = @($alreadyPatchedFiles)
  anchor_missing_files = @($anchorMissingFiles)
  schema_evidence_path = $schemaEvidencePath
  error = $errorMessage
}

Write-Utf8Json -Path $resultPath -Value $result

switch ($status) {
  'patched' { Write-Output 'handshake_debug_patched' }
  'already_patched' { Write-Output 'handshake_debug_ready' }
  'dist_not_found' { Write-Output 'handshake_debug_unavailable' }
  default { Write-Output 'handshake_debug_skipped' }
}

exit 0
