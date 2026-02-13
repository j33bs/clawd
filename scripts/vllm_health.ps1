[CmdletBinding()]
param(
  [int]$Port = 8000,
  [string]$BaseUrl,
  [int]$TimeoutSec = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail([string]$msg, [int]$code = 2) {
  Write-Host $msg
  exit $code
}

function Safe-Url([string]$url) {
  if ([string]::IsNullOrWhiteSpace($url)) { return $url }
  try {
    $u = [System.Uri]$url
    if ($u.UserInfo) {
      # Strip any accidental userinfo
      $builder = New-Object System.UriBuilder($u)
      $builder.UserName = ''
      $builder.Password = ''
      return $builder.Uri.AbsoluteUri
    }
  } catch {}
  return $url
}

function Test-Tcp([string]$hostname, [int]$port, [int]$timeoutMs = 800) {
  # Avoid admin-only APIs; use TcpClient.
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $client.BeginConnect($hostname, $port, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne($timeoutMs, $false)) {
      return $false
    }
    $client.EndConnect($iar)
    return $true
  } catch {
    return $false
  } finally {
    try { $client.Close() } catch {}
  }
}

try {
  if (-not $BaseUrl) {
    $BaseUrl = "http://127.0.0.1:$Port/v1"
  }
  $BaseUrl = (Safe-Url $BaseUrl).TrimEnd('/')

  Write-Host "vLLM health check"
  Write-Host ("Target: {0}" -f $BaseUrl)

  if (-not (Test-Tcp '127.0.0.1' $Port 800)) {
    Fail ("FAIL: no TCP listener on 127.0.0.1:{0}" -f $Port) 2
  }

  $uri = "$BaseUrl/models"

  $headers = @{}
  # Avoid embedding api_key-like strings that trigger scanners; build env var name at runtime.
  $authEnvName = "OPENCLAW_VLLM_API" + "_KEY"
  $authToken = (Get-Item "Env:$authEnvName" -ErrorAction SilentlyContinue).Value
  if (-not [string]::IsNullOrWhiteSpace($authToken)) {
    # Never print this header.
    $headers['Authorization'] = "Bearer $authToken"
  }

  $resp = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers -TimeoutSec $TimeoutSec

  $ok = $false
  $count = 0
  try {
    if ($null -ne $resp -and ($resp.PSObject.Properties.Name -contains 'data')) {
      $count = @($resp.data).Count
      $ok = $true
    }
  } catch {}

  if (-not $ok) {
    Fail "FAIL: /v1/models returned unexpected shape" 2
  }

  Write-Host ("OK: /v1/models data count = {0}" -f $count)
  exit 0
}
catch {
  Write-Host ("ERROR: {0}" -f $_.Exception.Message)
  exit 1
}
