# C_Lawd Reliability Ultra Evidence

- UTC opened: 2026-02-26T12:48:01Z
- branch: claude-code/governance-session-20260223
- OPENCLAW_QUIESCE=1

## PHASE START 0 (Permissions + Quiesce + Evidence)
- ts_utc: 2026-02-26T12:48:01Z

### date
```
Thu Feb 26 22:48:01 AEST 2026
```

### whoami
```
heathyeager
```

### pwd
```
/Users/heathyeager/clawd
```

### git status --porcelain=v1
```
 M MEMORY.md
 M scripts/get_daily_quote.js
 M workspace/docs/source_artifacts/OPEN_QUESTIONS.md
 M workspace/governance/collision.log
 M workspace/research/findings.json
 M workspace/research/queue.json
 M workspace/research/wander_log.md
?? memory/literature/bertrand_russell.txt
?? memory/literature/russell/
?? memory/literature/russell_on_denoting.txt
?? scripts/get_russell_quote.js
?? workspace/audit/c_lawd_reliability_ultra_evidence_20260226T124801Z.md
?? workspace/governance/100_CHANGES_TELEGRAM_PIPELINE.md
?? workspace/research/cytochrome_c_oxidase_light_matter.md
?? workspace/research/foundational_papers_db.md
?? workspace/research/foundational_reading_list.md
?? workspace/research/light_constrained_instantiation.md
?? workspace/research/telegram_vector_store_pipeline.md
?? workspace/state/question_tracker.json
```

### git rev-parse --abbrev-ref HEAD
```
claude-code/governance-session-20260223
```

### git log --oneline -5
```
e4012dd CXXXIII: jeebs — STYLE-CONSISTENCY threshold ≥5→≥3/being
a20ebfb CXXXII: DISPOSITIONAL-ATTRACTOR PASS; gate amendment closed
a425ee5 CXXXI: Gemini gate amendment co-sign; store to 131
cb7c416 Fix CXXX line 6794: 0.90 → p95 permutation null
a49ece1 Register + JEEBS_QUEUE + store rebuild to 130
```

### launchctl list | egrep -i 'openclaw|clawd|gateway|telegram|control|dashboard' || true
```
-	0	com.apple.parentalcontrols.check
-	0	com.apple.familycontrols.useragent
-	0	com.apple.GameController.gamecontrolleragentd
-	0	com.apple.universalaccesscontrol
687	0	com.apple.controlcenter
-	0	com.apple.DwellControl
15299	-9	ai.openclaw.gateway
-	0	com.apple.FamilyControlsAgent
-	0	com.apple.AssistiveControl
1093	0	application.ru.keepcoder.Telegram.97668369.97668523
681	0	com.apple.controlstrip
-	0	com.apple.gamecontroller.ConfigService
```

### log show --last 30m --style compact --predicate 'process CONTAINS "openclaw"' | tail -n 300 || true
```
Timestamp               Ty Process[PID:TID]
```

### ps aux | egrep 'openclaw|clawd|gateway|telegram|control|dashboard|node' | head -n 120
```
heathyeager      15326   6.0  1.5 444957936 122960   ??  S    10:31PM   0:14.62 openclaw-gateway     
heathyeager      15299   0.0  0.1 436162128   7520   ??  S    10:31PM   0:00.18 openclaw    
_gamecontrollerd  1005   0.0  0.0 435305776    464   ??  S    Wed05PM   0:04.16 /usr/sbin/distnoted agent
heathyeager      17414   0.0  0.0 435300208   1360   ??  S    10:48PM   0:00.00 egrep openclaw|clawd|gateway|telegram|control|dashboard|node
heathyeager      17410   0.0  0.0 435299776   1952   ??  S    10:48PM   0:00.00 bash -lc ps aux | egrep 'openclaw|clawd|gateway|telegram|control|dashboard|node' | head -n 120
heathyeager      17358   0.0  0.0 435308128   2080   ??  Ss   10:48PM   0:00.02 /bin/zsh -lc set -euo pipefail\012cd /Users/heathyeager/clawd\012export OPENCLAW_QUIESCE=1\012TS=$(date -u +%Y%m%dT%H%M%SZ)\012OUT="/Users/heathyeager/clawd/workspace/audit/c_lawd_reliability_ultra_evidence_${TS}.md"\012{\012  echo "# C_Lawd Reliability Ultra Evidence"\012  echo\012  echo "- UTC opened: $(date -u +%Y-%m-%dT%H:%M:%SZ)"\012  echo "- branch: $(git rev-parse --abbrev-ref HEAD)"\012  echo "- OPENCLAW_QUIESCE=${OPENCLAW_QUIESCE}"\012  echo\012  echo "## PHASE START 0 (Permissions + Quiesce + Evidence)"\012  echo "- ts_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"\012\012  for cmd in \\012    "date" \\012    "whoami" \\012    "pwd" \\012    "git status --porcelain=v1" \\012    "git rev-parse --abbrev-ref HEAD" \\012    "git log --oneline -5" \\012    "launchctl list | egrep -i 'openclaw|clawd|gateway|telegram|control|dashboard' || true" \\012    "log show --last 30m --style compact --predicate 'process CONTAINS \"openclaw\"' | tail -n 300 || true" \\012    "ps aux | egrep 'openclaw|clawd|gateway|telegram|control|dashboard|node' | head -n 120" \\012    "lsof -nP -iTCP:18789 -sTCP:LISTEN || true" \\012    "lsof -nP -iTCP | egrep '18789|openclaw|node' | head -n 120 || true" \\012    "curl -si http://127.0.0.1:18789/health | head -n 40" \\012    "curl -si http://127.0.0.1:18789/ready | head -n 40" \\012    "curl -si http://127.0.0.1:18789/diag/runtime | head -n 40 || true" \\012    "curl -si http://127.0.0.1:18789/api/health | head -n 40 || true"\012  do\012    echo\012    echo "### $cmd"\012    echo '```'\012    bash -lc "$cmd" 2>&1 || true\012    echo '```'\012  done\012\012  echo\012  echo "## Quiesce + Stateful Drift Check"\012  echo\012  for cmd in \\012    "echo OPENCLAW_QUIESCE=$OPENCLAW_QUIESCE" \\012    "find workspace/state -maxdepth 2 -type f 2>/dev/null | sort | head -n 200" \\012    "find workspace/state_runtime -maxdepth 2 -type f 2>/dev/null | sort | head -n 200" \\012    "find workspace -path '*/state/*.jsonl' -o -path '*/state_runtime/*.jsonl' 2>/dev/null | sort"\012  do\012    echo\012    echo "### $cmd"\012    echo '```'\012    bash -lc "$cmd" 2>&1 || true\012    echo '```'\012  done\012\012  echo\012  echo "## Symptom Expectation Check"\012  echo\012  echo "Observed whether Content-Type/body indicates Control UI HTML on /health,/ready,/diag/runtime,/api/health:"\012  echo "- (See captured curl blocks above; classification done in Phase 1.)"\012\012  echo\012  echo "## PHASE END 0"\012  echo "- ts_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"\012} > "$OUT"\012\012echo "$OUT"
```

### lsof -nP -iTCP:18789 -sTCP:LISTEN || true
```
COMMAND   PID        USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
node    15326 heathyeager   16u  IPv4  0xd7941c4d3679078      0t0  TCP 127.0.0.1:18789 (LISTEN)
node    15326 heathyeager   17u  IPv6 0xfb21b6315b291163      0t0  TCP [::1]:18789 (LISTEN)
```

### lsof -nP -iTCP | egrep '18789|openclaw|node' | head -n 120 || true
```
node      15326 heathyeager   16u  IPv4  0xd7941c4d3679078      0t0  TCP 127.0.0.1:18789 (LISTEN)
node      15326 heathyeager   17u  IPv6 0xfb21b6315b291163      0t0  TCP [::1]:18789 (LISTEN)
node      15326 heathyeager   22u  IPv6  0xbd3d4b4aeab62dd      0t0  TCP [2001:8003:63ce:4a00:886b:a1e5:51e3:def8]:50154->[2001:67c:4e8:f004::9]:443 (SYN_SENT)
node      15326 heathyeager   23u  IPv6 0x79d5cea9abbf3198      0t0  TCP [2001:8003:63ce:4a00:886b:a1e5:51e3:def8]:50155->[2001:67c:4e8:f004::9]:443 (SYN_SENT)
node      15326 heathyeager   24u  IPv4 0x29ac087793d89f09      0t0  TCP 127.0.0.1:18791 (LISTEN)
node      15326 heathyeager   25u  IPv4  0x8e586aad95d050c      0t0  TCP 127.0.0.1:18792 (LISTEN)
```

### curl -si http://127.0.0.1:18789/health | head -n 40
```
HTTP/1.1 200 OK
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' ws: wss:
Content-Type: text/html; charset=utf-8
Cache-Control: no-cache
Date: Thu, 26 Feb 2026 12:48:04 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 692

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
    <script type="module" crossorigin src="./assets/index-m0G6afX5.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-CM7kTShz.css">
  </head>
  <body>
    <openclaw-app></openclaw-app>
  </body>
</html>
```

### curl -si http://127.0.0.1:18789/ready | head -n 40
```
HTTP/1.1 200 OK
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' ws: wss:
Content-Type: text/html; charset=utf-8
Cache-Control: no-cache
Date: Thu, 26 Feb 2026 12:48:04 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 692

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
    <script type="module" crossorigin src="./assets/index-m0G6afX5.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-CM7kTShz.css">
  </head>
  <body>
    <openclaw-app></openclaw-app>
  </body>
</html>
```

### curl -si http://127.0.0.1:18789/diag/runtime | head -n 40 || true
```
HTTP/1.1 200 OK
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' ws: wss:
Content-Type: text/html; charset=utf-8
Cache-Control: no-cache
Date: Thu, 26 Feb 2026 12:48:04 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 692

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
    <script type="module" crossorigin src="./assets/index-m0G6afX5.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-CM7kTShz.css">
  </head>
  <body>
    <openclaw-app></openclaw-app>
  </body>
</html>
```

### curl -si http://127.0.0.1:18789/api/health | head -n 40 || true
```
HTTP/1.1 200 OK
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' ws: wss:
Content-Type: text/html; charset=utf-8
Cache-Control: no-cache
Date: Thu, 26 Feb 2026 12:48:04 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 692

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
    <script type="module" crossorigin src="./assets/index-m0G6afX5.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-CM7kTShz.css">
  </head>
  <body>
    <openclaw-app></openclaw-app>
  </body>
</html>
```

## Quiesce + Stateful Drift Check


### echo OPENCLAW_QUIESCE=1
```
OPENCLAW_QUIESCE=1
```

### find workspace/state -maxdepth 2 -type f 2>/dev/null | sort | head -n 200
```
workspace/state/active_inference_state.json
workspace/state/pause_check_log.jsonl
workspace/state/question_tracker.json
workspace/state/tacti_cr/events.jsonl
```

### find workspace/state_runtime -maxdepth 2 -type f 2>/dev/null | sort | head -n 200
```
workspace/state_runtime/codex_implementation_attempt_2026-02-26.md
workspace/state_runtime/tacti_cr/events.jsonl
```

### find workspace -path '*/state/*.jsonl' -o -path '*/state_runtime/*.jsonl' 2>/dev/null | sort
```
workspace/state/pause_check_log.jsonl
workspace/state/tacti_cr/events.jsonl
workspace/state_runtime/tacti_cr/events.jsonl
```

## Symptom Expectation Check

Observed whether Content-Type/body indicates Control UI HTML on /health,/ready,/diag/runtime,/api/health:
- (See captured curl blocks above; classification done in Phase 1.)

## PHASE END 0
- ts_utc: 2026-02-26T12:48:04Z
