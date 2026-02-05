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

- [x] Secrets migration from plaintext config to secrets.env - COMPLETED 2026-02-05
- [ ] Historical backup files with exposed secrets require secure deletion:
  - `openclaw.json.bak` - contains gateway token
  - `openclaw.json.bak_20260204_231447` - contains gateway token
  - `workspace.bak_20260204_230710/` - may contain sensitive data
  - `workspace.bak_20260204_231007/` - may contain sensitive data
  - `workspace/.git.bak/` - workspace git history backup
  - `openclaw.json.pre-multimodel-backup` - pre-migration backup (contains token)
- [ ] Secure delete backups after 7-day validation period

---

## Incident Log

### 2026-02-05 - Backup Files with Secrets Identified

**Severity**: Medium (files on disk, not in VCS)
**Status**: Documented, pending scheduled cleanup

Backup files containing plaintext gateway token identified during history scan:
- These files ARE excluded from git by .gitignore
- They remain on local filesystem only
- No secrets were committed to git history (verified)

**Recommended Action**: Secure deletion after 7-day validation period to ensure system operates correctly with new secrets.env configuration.

**Note**: Token was NOT rotated per user request - values were moved to secure storage, not changed.

---

*This log is append-only for entries. Status updates are permitted.*
*Each entry requires: Timestamp, Event, Category, Details, Actor.*
