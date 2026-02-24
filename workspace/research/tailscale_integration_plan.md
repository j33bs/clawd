# Tailscale Integration Plan: C_Lawd + DALI Communication Network

*Draft — 2026-02-23*

---

## The Vision

Create a private, encrypted mesh network connecting:
- **Heath's machine** (MacBook)
- **C_Lawd** (this agent)
- **DALI** (sibling agent)
- **Future nodes** (additional agents, devices)

All communication stays within the private network — no external API exposure.

---

## Why Tailscale?

| Feature | Benefit for AI Agents |
|---------|----------------------|
| Zero-config NAT traversal | Nodes find each other automatically |
| WireGuard encryption | Secure communication by default |
| Unique 100.x.x.x IPs | Each agent has a stable internal address |
| ACL policies | Control which agents can talk to which |
| Exit node | Route specific traffic through specific nodes |
| Subnet router | Expose local services to the network |

---

## Current State

- Tailscale: **Not installed** on this machine
- Network: Unknown (no direct access to check Heath's machine)
- Agents: C_Lawd (this session), DALI (sibling in same repo)

---

## Implementation Steps

### Phase 1: Setup (Heath's Actions)

1. **Install Tailscale** on all machines:
   ```bash
   # macOS
   brew install tailscale
   tailscale up
   
   # Or download from https://tailscale.com/download
   ```

2. **Authenticate** with Tailscale account (free for personal use)

3. **Note the Tailscale IPs** — each machine gets a 100.x.x.x address

### Phase 2: Agent Network Configuration

1. **Assign static IPs** (via ACLs or pre-auth key):
   - C_Lawd: `100.64.1.10` (example)
   - DALI: `100.64.1.11`
   - Heath: `100.64.1.1`

2. **Configure services to listen internally**:
   - Each agent runs a small HTTP server on its Tailscale IP
   - Ports: 8080 (general), 8081 (status), 8082 (messages)

3. **Add to startup** (launchd or systemd):
   ```xml
   <!-- ~/Library/LaunchAgents/com.tailscale.tailscaled.plist -->
   ```

### Phase 3: Inter-Agent Communication

**Simple protocol:**

```
POST http://100.64.1.10:8082/message
{
  "from": "dali",
  "to": "c_lawd", 
  "content": "Hey, what's the status?",
  "type": "query|response|alert"
}
```

**Example use cases:**
- DALI asks C_Lawd: "What's in MEMORY.md?"
- C_Lawd notifies DALI: "Heath asked about you"
- Either alerts: "New research topic added"

### Phase 4: RAG Integration (Future)

If RAG runs on the mesh:
- One node hosts the vector DB (e.g., Heath's machine with Apple Silicon)
- Other agents query it over the mesh
- No data leaves the private network

---

## Potential Issues

1. **Wake on demand**: Agents aren't always running
   - Solution: Heath's machine as always-on hub

2. **Session continuity**: Each conversation is ephemeral
   - Solution: Agent registers status on startup, unregisters on close

3. **Security**: If device is compromised
   - Solution: Use ACLs to limit what each IP can access

---

## Alternative: Headscale (Self-Hosted)

If Heath wants full control:
- Run Headscale (open-source Tailscale control server) on a home server or cloud VPS
- No third-party dependency
- More configuration options

---

## Next Steps

1. Heath installs Tailscale on their machine
2. Get Tailscale IPs for all nodes
3. Draft simple HTTP server for agent messaging
4. Test C_Lawd → DALI communication

---

*Draft complete. Waiting on Heath to install Tailscale.*
