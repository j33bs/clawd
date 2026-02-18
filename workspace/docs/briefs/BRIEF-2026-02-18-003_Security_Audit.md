# Brief: Full Security Audit

## Metadata
- **ID**: BRIEF-2026-02-18-003
- **Category**: A (Critical Security)
- **Author**: C_Lawd
- **Date**: 2026-02-18

---

## Scope

Comprehensive security audit of the OpenClaw workspace including:
- TACTI(C)-R implementation
- Credentials and secrets
- Network exposure
- Dependency vulnerabilities
- Access controls
- Prompt injection vectors
- Supply chain risks

---

## Audit Checklist

### 1. Secrets Management
- [ ] Scan for exposed API keys in code
- [ ] Check .gitignore covers secrets
- [ ] Verify credentials/ folder is protected
- [ ] Check for hardcoded tokens

### 2. Dependencies
- [ ] Check package.json for known vulnerabilities
- [ ] Review npm audit results
- [ ] Check Python dependencies for CVEs
- [ ] Review skill.md files for supply chain risks (per Moltbook advisory)

### 3. Network Security
- [ ] Check firewall rules
- [ ] Review exposed ports
- [ ] Verify Telegram/WebUI authentication
- [ ] Check for unauthorized access points

### 4. Access Control
- [ ] Review file permissions
- [ ] Check agent directory access
- [ ] Verify cron job permissions
- [ ] Review channel configurations

### 5. Code Security
- [ ] Scan for command injection vectors
- [ ] Check exec usage for injection
- [ ] Review file path traversal
- [ ] Check for deserialization vulnerabilities

### 6. TACTI(C)-R Specific
- [ ] Review arousal routing for abuse
- [ ] Check collapse detection for bypass
- [ ] Verify repair mechanisms are secure
- [ ] Review memory isolation

### 7. Supply Chain
- [ ] Audit installed npm packages
- [ ] Check pip dependencies
- [ ] Review skill files (Moltbook warning: credential stealers!)
- [ ] Verify QMD installation source

---

## Tools

```bash
# Secrets scanning
grep -r "sk-\|api_key\|password\|secret" --include="*.js" --include="*.py" workspace/ | grep -v node_modules

# Dependency audit
npm audit
pip list --format=freeze

# File permissions
ls -la credentials/

# Port scanning
lsof -i -P | grep LISTEN
```

---

## Output Format

Provide a structured report:
1. **Critical Findings** (immediate action required)
2. **High Findings** (fix within 24h)
3. **Medium Findings** (fix within week)
4. **Low Findings** (cosmetic/improvements)
5. **Recommendations**

---

## Acceptance Criteria

- [ ] All critical vulnerabilities documented
- [ ] Risk levels assigned
- [ ] Remediation steps provided
- [ ] False positives flagged
- [ ] No new secrets exposed in audit
