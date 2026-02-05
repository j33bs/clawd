# Credential Rotation Protocol

Standard procedures for rotating credentials in the OpenClaw system.

---

## Gateway Token

### Rotation Frequency
- **Scheduled**: Every 90 days
- **Unscheduled**: Immediately upon suspected compromise

### Rotation Process

1. **Generate new token**
   ```bash
   # Generate cryptographically secure token
   openssl rand -hex 24
   ```

2. **Update secrets.env**
   ```bash
   # Edit secrets.env with new token
   OPENCLAW_GATEWAY_TOKEN=<new-token>
   ```

3. **Restart gateway service**
   ```bash
   # Stop existing gateway
   # Start with new token
   openclaw gateway restart
   ```

4. **Verify connectivity**
   ```bash
   # Test gateway health
   curl -H "Authorization: Bearer <new-token>" http://localhost:18789/health
   ```

5. **Log rotation**
   - Add entry to `sources/security/audit_log.md`
   - Record: timestamp, old token hash (last 8 chars), new token hash (last 8 chars)

---

## OAuth Tokens (Qwen Portal)

### Management
- **Primary**: Managed automatically by OpenClaw runtime (refresh flow)
- **Manual**: Only required if tokens become invalid or compromised

### Manual Rotation Process

1. **Revoke existing tokens**
   - Log into Qwen Portal
   - Revoke active sessions/tokens

2. **Re-authenticate**
   ```bash
   openclaw auth login qwen-portal
   ```

3. **Verify new tokens**
   ```bash
   openclaw status --deep
   ```

4. **Log rotation** in audit log

---

## Anthropic API Key

### Rotation Frequency
- **Scheduled**: Every 180 days or per org policy
- **Unscheduled**: Immediately upon suspected compromise

### Rotation Process

1. **Generate new key**
   - Log into Anthropic Console
   - Create new API key
   - Note: Old key remains valid until explicitly revoked

2. **Update secrets.env**
   ```bash
   ANTHROPIC_API_KEY=<new-key>
   ```

3. **Test connectivity**
   ```bash
   # Verify Claude API access
   curl -H "x-api-key: <new-key>" https://api.anthropic.com/v1/models
   ```

4. **Revoke old key** in Anthropic Console

5. **Log rotation** in audit log

---

## Device Identity

### Rotation Frequency
- **Scheduled**: Never (device identity is persistent)
- **Unscheduled**: Only on compromise or device migration

### Rotation Process

1. **Backup current identity** (if recoverable)
   ```bash
   cp identity/device.json identity/device.json.rotating
   ```

2. **Delete identity file**
   ```bash
   rm identity/device.json
   ```

3. **Restart OpenClaw**
   - New identity auto-generates on startup

4. **Re-pair all devices**
   - All connected devices must be re-paired
   - Previous pairing tokens become invalid

5. **Update dependent configurations**

6. **Log rotation** in audit log with reason

---

## Compromise Response Protocol

If ANY credential is suspected compromised:

### Immediate Actions (within 1 hour)

1. **Rotate affected credential** using procedures above
2. **Revoke old credential** at source (portal, console, etc.)
3. **Review access logs** for unauthorized activity
4. **Document incident** in `governance/incidents/INCIDENT-YYYY-MM-DD-NNN.md`

### Follow-up Actions (within 24 hours)

1. **Conduct post-incident review**
2. **Identify root cause** of compromise
3. **Implement preventive measures**
4. **Update audit log** with full incident record

### Notification Requirements

| Credential Type | Notification Required |
|-----------------|----------------------|
| Gateway token | Internal only |
| OAuth tokens | Internal only |
| Anthropic API key | Internal only |
| Device private-key | Internal + consider external if data accessed |

---

## Rotation Schedule

| Credential | Frequency | Next Rotation | Owner |
|------------|-----------|---------------|-------|
| Gateway token | 90 days | TBD | operator |
| OAuth tokens | Auto | N/A | system |
| Anthropic API key | 180 days | TBD | operator |
| Device identity | Never | N/A | system |

---

*This document is CANONICAL.*
*Modifications require Category B (Security) process.*
