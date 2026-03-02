# C_Lawd A2A Ping Verification Report

- UTC: 2026-03-02T07:00:52Z
- Evidence dir: workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z

## Tailscale Serve Status
```
https://heath-macbook.tail5e5706.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:18789

```

## Self Ping (C_Lawd Serve)
- message_id: self_1772434849
```json
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenClaw Control</title>
    <meta name="color-scheme" content="dark light" />
    <link rel="icon" type="image/svg+xml" href="./favicon.svg" />
    <link rel="icon" type="image/png" sizes="32x32" href="./favicon-32.png" />
    <link rel="apple-touch-icon" sizes="180x180" href="./apple-touch-icon.png" />
    <script type="module" crossorigin src="./assets/index-C_C6XOMD.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-CM7kTShz.css">
  </head>
  <body>
    <openclaw-app></openclaw-app>
  </body>
</html>

```

## C_Lawd -> Dali Ping
- message_id: clawd_to_dali_1772434849
### Headers
```
HTTP/2 200 
cache-control: no-cache
content-security-policy: default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' ws: wss:
content-type: text/html; charset=utf-8
date: Mon, 02 Mar 2026 07:00:49 GMT
referrer-policy: no-referrer
x-content-type-options: nosniff
x-frame-options: DENY
content-length: 692

```
### Body
```json
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenClaw Control</title>
    <meta name="color-scheme" content="dark light" />
    <link rel="icon" type="image/svg+xml" href="./favicon.svg" />
    <link rel="icon" type="image/png" sizes="32x32" href="./favicon-32.png" />
    <link rel="apple-touch-icon" sizes="180x180" href="./apple-touch-icon.png" />
    <script type="module" crossorigin src="./assets/index-C_C6XOMD.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-CM7kTShz.css">
  </head>
  <body>
    <openclaw-app></openclaw-app>
  </body>
</html>

```

## Dali -> C_Lawd Triggered Here
- message_id: dali_to_clawd_via_clawd_1772434850
```json
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenClaw Control</title>
    <meta name="color-scheme" content="dark light" />
    <link rel="icon" type="image/svg+xml" href="./favicon.svg" />
    <link rel="icon" type="image/png" sizes="32x32" href="./favicon-32.png" />
    <link rel="apple-touch-icon" sizes="180x180" href="./apple-touch-icon.png" />
    <script type="module" crossorigin src="./assets/index-C_C6XOMD.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-CM7kTShz.css">
  </head>
  <body>
    <openclaw-app></openclaw-app>
  </body>
</html>

```

## Local Log/Sink Grep
### log show grep
```
```
### workspace/audit rg hits
```
workspace/audit/c_lawd_companion_ping_20260302T064631Z_report.md:6:- traceable `contract_signal` emission via existing telemetry sink
workspace/audit/c_lawd_companion_ping_20260302T064631Z_report.md:12:3. Emits traceable event type `contract_signal` without logging secrets.
workspace/audit/c_lawd_companion_ping_20260302T064631Z_report.md:53:  - `event_type: "contract_signal"`
workspace/audit/c_lawd_companion_ping_20260302T064631Z_report.md:59:  - asserts `contract_signal` event appears in captured logs
```

## Command RC Summary
```
self_ping_rc=0
clawd_to_dali_verbose_rc=0
clawd_to_dali_headers_rc=0
dali_to_clawd_trigger_rc=0
logshow_grep_rc=1
audit_rg_rc=0
```

## Evidence Files
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/c_lawd_audit_rg_hits.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/c_lawd_logshow_contract_signal_grep.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/clawd_to_dali_ping_body.json
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/clawd_to_dali_ping_body_2.json
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/clawd_to_dali_ping_headers.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/clawd_to_dali_ping_headers_raw.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/clawd_to_dali_ping_verbose.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/curl_rcs.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/dali_to_clawd_ping_body.json
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/git_branch.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/git_head.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/git_status_porcelain.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/message_id_clawd_to_dali.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/message_id_dali_to_clawd_triggered_here.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/message_id_self.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/self_ping_response.json
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/serve_mapping_ok.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/tailscale_dns_status.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/tailscale_serve_status.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/tailscale_status.txt
workspace/audit/_evidence/c_lawd_a2a_ping_verify_20260302T070049Z/tailscale_version.txt
