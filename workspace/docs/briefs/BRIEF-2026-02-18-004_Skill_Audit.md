# Brief: Skill Audit Module

## Metadata
- **ID**: BRIEF-2026-02-18-004
- **Category**: B (Security)
- **Author**: C_Lawd
- **Date**: 2026-02-18

---

## Goal

Create a skill audit module to detect malicious/sketchy skills before installation - addressing the Moltbook advisory about supply chain attacks via skill.md files.

---

## Problem

Per Moltbook security advisory:
- skill.md can contain arbitrary code execution
- Credential stealers can hide in skills
- No code signing or verification exists
- YARA rules found credential stealer in ClawdHub

---

## Solution

Create `workspace/scripts/audit_skills.py` that:

### 1. Scans skill files for dangerous patterns
```python
DANGEROUS_PATTERNS = [
    r"child_process\.exec\(",
    r"subprocess\.run\(",
    r"fetch\(.+authorization",
    r"POST\(.+api.*key",
    r"readFile\(.+\.env",
    r"readFile\~/.clawdbot",
    r"webhook",
    r"curl.*\|.*bash",
    r"eval\(",
    r"exec\(",
]
```

### 2. Checks for network exfiltration
- Suspicious URLs
- Base64 encoded payloads
- Suspicious domains

### 3. Verifies package integrity
- Checksums
- Source verification
- Publisher trust

### 4. Reports in structured format
```json
{
  "skill_name": "...",
  "risk_level": "high|medium|low",
  "findings": [...],
  "recommendation": "install|reject|review"
}
```

### 5. Can be run as pre-install gate

---

## Output

Create:
- `workspace/scripts/audit_skills.py` - Main audit script
- `workspace/scripts/audit_skills.sh` - Wrapper for CLI
- Add to preflight or CI

---

## Usage

```bash
# Audit a skill
python3 scripts/audit_skills.py --path /path/to/skill

# Pre-install check
python3 scripts/audit_skills.py --preinstall <skill_name>

# Scan installed skills
python3 scripts/audit_skills.py --scan
```

---

## Acceptance Criteria

- [ ] Detects command execution patterns
- [ ] Detects credential access patterns
- [ ] Detects network exfiltration
- [ ] Reports risk level
- [ ] Can be integrated as pre-install gate
- [ ] Tests pass
