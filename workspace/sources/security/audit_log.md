# Security Audit Log

Track all security-relevant events for the OpenClaw system.

---

## Event Categories

| Category | Description | Example |
|----------|-------------|---------|
| CREDENTIAL_ACCESS | Read/write of credential files | Rotating gateway token |
| AUTH_ATTEMPT | Login/authentication attempts | Device pairing |
| EXTERNAL_ACTION | Actions affecting external systems | Sending Telegram message |
| CONFIG_CHANGE | Security configuration changes | Updating .gitignore |
| GATE_PASS | Changes passing admission gates | PR merged |
| GATE_BLOCK | Changes blocked by gates | Secret detected in commit |
| INCIDENT | Security incident | Credential exposure |

---

## Log Entries

### 2026-02-05 - System Initialization

| Timestamp | Event | Category | Details | Actor |
|-----------|-------|----------|---------|-------|
| 2026-02-05T21:10:00Z | Repository initialized | CONFIG_CHANGE | Security-first .gitignore created | system |
| 2026-02-05T21:12:00Z | Hooks installed | CONFIG_CHANGE | pre-commit and pre-push hooks active | system |
| 2026-02-05T21:15:00Z | Governance structure created | CONFIG_CHANGE | GOVERNANCE_LOG.md initialized | system |

---

## Pending Items

- [ ] Historical backup files with exposed secrets require secure deletion
- [ ] Secrets migration from plaintext config to secrets.env
- [ ] Token rotation after migration complete

---

*This log is append-only for entries. Status updates are permitted.*
*Each entry requires: Timestamp, Event, Category, Details, Actor.*
