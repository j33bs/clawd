# BOUNDARIES.md - Canonical vs Ephemeral vs Secret

This document defines what files belong where and their version control status.
Misclassification of files is a governance violation.

---

## CANONICAL (MUST be committed)

These files form the durable identity and governance substrate of the system.

### Governance Documents
- `CONSTITUTION.md` - Constitutional basis of practice
- `SOUL.md` - Core identity and values
- `IDENTITY.md` - Agent identity definition
- `AGENTS.md` - Operational procedures
- `USER.md` - User context
- `BOUNDARIES.md` - This file
- `MODEL_ROUTING.md` - Multi-model routing policy

### Memory (Long-Term Only)
- `MEMORY.md` - Curated long-term memory

### Governance Infrastructure
- `governance/GOVERNANCE_LOG.md` - Append-only event log
- `governance/admissions/*.md` - Admission records
- `governance/incidents/*.md` - Incident records
- `governance/overrides/*.md` - Override records

### Documentation
- `docs/briefs/*.md` - Design briefs
- `sources/**/*.md` - Source documentation
- `sources/itc/**` - ITC governance framework
- `sources/security/**` - Security documentation

### Scripts
- `scripts/*.sh` - Shell scripts
- `scripts/*.ps1` - PowerShell scripts

### Root Configuration
- `.gitignore` - Security exclusions
- `.gitattributes` - EOL normalization
- `CONTRIBUTING.md` - Change admission process

---

## EPHEMERAL (MUST NOT be committed)

These files are runtime state and local-only data.

### Daily Memory
- `memory/*.md` - Daily memory logs (local continuity only)
- `memory/heartbeat-state.json` - Heartbeat tracking

### Session Data
- `agents/*/sessions/*.jsonl` - Conversation logs
- `sessions.json` - Session index

### Runtime State
- `*.sqlite` - SQLite databases
- `memory/*.sqlite` - Memory databases

### Logs
- `*.log` - Log files
- `telegram_health_log.json` - Health check logs
- `telegram_health_reports.json` - Health reports

### Temporary
- `tmp/` - Temporary files
- `cache/` - Cache directories

---

## SECRET (MUST NEVER touch VCS)

These files contain credentials and MUST NEVER be committed, even encrypted.

### Environment Files
- `secrets.env` - Active secrets
- `.env` - Environment variables
- `*.env.local` - Local environment overrides

### Credentials
- `identity/device.json` - Device private-key
- `identity/device-auth.json` - Device auth tokens
- `devices/paired.json` - Paired device tokens
- `devices/pending.json` - Pending device tokens
- `credentials/*.json` - All credential files
- `agents/*/agent/auth-profiles.json` - OAuth tokens

### Key Material
- `*.pem` - PEM-encoded keys
- `*.key` - Key files
- `*.p12` - PKCS#12 files
- `*.pfx` - PFX files

### Backup Files (May Contain Secrets)
- `*.bak` - Backup files
- `*.bak_*` - Timestamped backups
- `workspace.bak_*/` - Workspace backups
- `openclaw.json.bak*` - Config backups
- `*.git.bak/` - Git backups

---

## Classification Rules

1. **When in doubt, classify as SECRET** - False positives are safer than leaks
2. **New file types** require explicit classification before first commit
3. **Reclassification** from SECRET to CANONICAL requires Category A governance
4. **Accidental commits** of SECRET files require immediate incident response

---

## Enforcement

- `.gitignore` implements SECRET and EPHEMERAL exclusions
- Pre-commit hook validates SECRET patterns
- Pre-push hook scans for leaked secrets
- Regression script verifies no forbidden files tracked

---

*This document is CANONICAL and MUST be committed.*
*Modifications require Category D (Documentation) process minimum.*
*Reclassifications affecting security require Category B.*
