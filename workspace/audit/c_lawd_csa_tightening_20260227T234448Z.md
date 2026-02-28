# C_LAWD CSA Tightening (20260227T234448Z)

## Phase 0 - Snapshot + Evidence Bootstrap

### git rev-parse HEAD
```
9c90a31e2e753346a3444768deec491ec0290637
```

### git status --porcelain
```
 M MEMORY.md
 M memory/literature/state.json
 M workspace/governance/OPEN_QUESTIONS.md
 M workspace/research/findings.json
 M workspace/research/queue.json
 M workspace/research/wander_log.md
?? memory/2026-02-28.md
?? scripts/tailscale_serve_openclaw.sh
?? workspace/audit/_evidence/
?? workspace/audit/c_lawd_tailscale_serve_hardening_20260227T204737Z.md
?? workspace/governance/.open_questions.lock
?? workspace/governance/open_questions_shards/
?? workspace/state_runtime/memory/
```

### tailscale version
```
The Tailscale CLI failed to start: Failed to load preferences.
```

### tailscale status
```
The Tailscale CLI failed to start: Failed to load preferences.
```

### tailscale ip -4 || true
```
The Tailscale CLI failed to start: Failed to load preferences.
```

### tailscale serve status || true
```
The Tailscale CLI failed to start: Failed to load preferences.
```

### launchctl print gui/501/ai.openclaw.gateway | grep -A6 -E 'state|program|arguments|job state' || true
```
	state = running

	program = /bin/zsh
	arguments = {
		/bin/zsh
		/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh
	}

	working directory = /Users/heathyeager/clawd

--
		state = active
		active count = 1
		name = ai.openclaw.gateway
	}

	jetsam coalition = {
		ID = 17037
--
		state = active
		active count = 1
		name = ai.openclaw.gateway
	}

	spawn type = daemon (3)
	jetsam priority = 40
--
	job state = running

	properties = partial import | keepalive | runatload | inferred program
}
```

### lsof -nP -iTCP:18789 -sTCP:LISTEN || true
```
COMMAND  PID        USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
node    4764 heathyeager   16u  IPv4 0x86f82e099d4318cb      0t0  TCP 127.0.0.1:18789 (LISTEN)
node    4764 heathyeager   17u  IPv6 0x60d2b1b3d69f528b      0t0  TCP [::1]:18789 (LISTEN)
```

### curl -sS -D- http://127.0.0.1:18789/health -o /dev/null || true
```
curl: (7) Failed to connect to 127.0.0.1 port 18789 after 0 ms: Couldn't connect to server
```

## Interpretation (Phase 0)

- Gateway LaunchAgent reports running.
- Local listener observed on `127.0.0.1:18789` and `[::1]:18789`.
- Health endpoint probe failed at capture time.
- Tailscale CLI probes are blocked in this execution environment (`Failed to load preferences`).

## Phase 1 - Enforce Localhost-Only Binding

### Phase 1 Action
```
Gateway wrapper already defaults to loopback bind; no code change applied.
```

### OPENCLAW_WRAPPER_DRYRUN=1 scripts/run_openclaw_gateway_repo.sh 2>&1
```
OPENCLAW_REPO_RUNTIME=openclaw_gateway
OPENCLAW_REPO_ROOT=/Users/heathyeager/clawd
OPENCLAW_REPO_SHA=ab35490
OPENCLAW_REPO_BRANCH=codex/harden/c_lawd-csa-tightening-20260227
OPENCLAW_ENTRYPOINT=openclaw gateway run
OPENCLAW_BUILD repo_sha=ab35490 branch=codex/harden/c_lawd-csa-tightening-20260227 entrypoint=openclaw gateway run
OPENCLAW_GATEWAY_BIND=loopback OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_TAILNET_MODE bind=loopback control_ui=local allowed_origins_count=0 dryrun=1
OPENCLAW_TAILNET_BIND_HOST=127.0.0.1
OPENCLAW_WRAPPER_DRYRUN_COMMAND=openclaw gateway run --bind loopback --port 18789
```

### lsof -nP -iTCP:18789 -sTCP:LISTEN || true
```
COMMAND  PID        USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
node    4764 heathyeager   16u  IPv4 0x86f82e099d4318cb      0t0  TCP 127.0.0.1:18789 (LISTEN)
node    4764 heathyeager   17u  IPv6 0x60d2b1b3d69f528b      0t0  TCP [::1]:18789 (LISTEN)
```

### curl -sS --max-time 2 -D- http://127.0.0.1:18789/health -o /dev/null || true
```
curl: (7) Failed to connect to 127.0.0.1 port 18789 after 0 ms: Couldn't connect to server
```

## Interpretation (Phase 1)

- Wrapper-reported bind host remains `127.0.0.1`.
- Live listener remains loopback-only (`127.0.0.1` + `::1`).
- No bind-hardening code delta required in this phase.

## Phase 2 - Configure Tailscale Serve (HTTPS Proxy)

### Phase 2 Action
```
Added scripts/tailscale_serve_openclaw.sh with explicit serve path "/" and loopback-only proxy guard.
```

### OPENCLAW_TAILSCALE_SERVE_DRYRUN=1 scripts/tailscale_serve_openclaw.sh
```
OPENCLAW_TAILSCALE_SERVE_DRYRUN_COMMAND=tailscale serve --yes --bg --https=443 / http://127.0.0.1:18789
```

### scripts/tailscale_serve_openclaw.sh || true
```
The Tailscale CLI failed to start: Failed to load preferences.

The Tailscale CLI failed to start: Failed to load preferences.
```

### tailscale serve status || true
```
The Tailscale CLI failed to start: Failed to load preferences.
```

### node --test tests/tailscale_serve_openclaw.test.js
```
✔ dryrun emits explicit path-based tailscale serve command
✔ non-loopback gateway host is rejected
✔ script calls tailscale serve and tailscale serve status
ℹ tests 3
ℹ pass 3
ℹ fail 0
```

## Interpretation (Phase 2)

- Serve command syntax is now explicit and non-interactive (`--https=443 / http://127.0.0.1:18789`).
- Script forbids non-loopback upstream host values.
- Live tailscale execution remains blocked in this environment (`Failed to load preferences`).

## Phase 3 - Persist Serve via launchd

### Phase 3 Action
```
Added scripts/install_tailscale_serve_launchagent.sh to generate a 0600 LaunchAgent plist and optionally apply launchctl.
```

### HOME="<tmp>" OPENCLAW_TAILSCALE_SERVE_LAUNCHAGENT_DRYRUN=1 scripts/install_tailscale_serve_launchagent.sh | sed -n '1,40p'
```
PLIST_PATH=<tmp>/Library/LaunchAgents/ai.openclaw.tailscale-serve.plist
<?xml version="1.0" encoding="UTF-8"?>
...
<string>/Users/heathyeager/clawd/scripts/tailscale_serve_openclaw.sh</string>
...
```

### HOME="<tmp>" scripts/install_tailscale_serve_launchagent.sh
```
WROTE_PLIST=<tmp>/Library/LaunchAgents/ai.openclaw.tailscale-serve.plist
LAUNCHCTL_APPLIED=0
```

### stat <tmp>/Library/LaunchAgents/ai.openclaw.tailscale-serve.plist
```
600 <tmp>/Library/LaunchAgents/ai.openclaw.tailscale-serve.plist
```

### node --test tests/install_tailscale_serve_launchagent.test.js tests/tailscale_serve_openclaw.test.js
```
✔ dryrun prints target plist path and launchagent payload
✔ write mode creates 0600 plist without applying launchctl
✔ dryrun emits explicit path-based tailscale serve command
✔ non-loopback gateway host is rejected
✔ script calls tailscale serve and tailscale serve status
ℹ tests 5
ℹ pass 5
ℹ fail 0
```

## Interpretation (Phase 3)

- LaunchAgent persistence is now generated from repo-controlled script with locked file mode (`0600`).
- Launchctl apply remains opt-in (`OPENCLAW_TAILSCALE_SERVE_LAUNCHCTL_APPLY=1`) to keep execution reversible.

## Phase 4 - Cross-Node Verification

### tailscale status || true
```
The Tailscale CLI failed to start: Failed to load preferences.
```

### tailscale serve status || true
```
The Tailscale CLI failed to start: Failed to load preferences.
```

### ifconfig | rg "inet "
```
inet 127.0.0.1
inet 192.168.0.213
inet 100.84.143.50
```

### curl -sS -D- "http://192.168.0.213:18789/health" -o /dev/null --max-time 5 || true
```
curl: (7) Failed to connect to 192.168.0.213 port 18789 after 1 ms: Couldn't connect to server
```

### curl -sS -D- "http://100.84.143.50:18789/health" -o /dev/null --max-time 5 || true
```
curl: (7) Failed to connect to 100.84.143.50 port 18789 after 0 ms: Couldn't connect to server
```

## Interpretation (Phase 4)

- Direct LAN and tailnet-IP access to port `18789` remains blocked (loopback-only invariant preserved).
- Tailnet Serve state cannot be verified in this execution environment (`Failed to load preferences`).

## Phase 5 - Hardening Checks

### tailscale funnel status --json || true
```
{
  "TCP": {
    "443": {
      "HTTPS": true
    }
  },
  "Web": {
    "heaths-macbook-pro.tail5e5706.ts.net:443": {
      "Handlers": {
        "/": {
          "Proxy": "http://127.0.0.1:18789"
        }
      }
    }
  }
}
```

### tailscale serve status || true
```
https://heaths-macbook-pro.tail5e5706.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:18789
```

### lsof -nP -iTCP:18789 -sTCP:LISTEN || true
```
COMMAND  PID        USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
node    4764 heathyeager   16u  IPv4 0x86f82e099d4318cb      0t0  TCP 127.0.0.1:18789 (LISTEN)
node    4764 heathyeager   17u  IPv6 0x60d2b1b3d69f528b      0t0  TCP [::1]:18789 (LISTEN)
```

### curl -sS --max-time 2 -D- http://127.0.0.1:18789/health -o /dev/null || true
```
curl: (7) Failed to connect to 127.0.0.1 port 18789 after 0 ms: Couldn't connect to server
```

## Interpretation (Phase 5)

- Serve currently resolves to `tailnet only` with loopback proxy target.
- Listener remains loopback-only on `127.0.0.1` and `::1`.
- No funnel-reset mutation applied from this environment.
