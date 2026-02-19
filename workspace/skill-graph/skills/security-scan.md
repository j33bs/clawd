---
name: security-scan
description: Security vulnerability detection and remediation guidance
tags: [security, development, critical]
links: [code-review, input-validation, authentication, encryption]
---

# Security Scan

## Overview

Systematic security review for identifying vulnerabilities in code.

## Priority Order

1. **Injection** - SQL, command, XSS
2. **Authentication** - Auth bypasses, session issues
3. **Data Exposure** - Leaks, encryption failures
4. **Access Control** - Authorization gaps

## Common Vulnerabilities

### Injection

```python
# BAD - SQL injection
query = f"SELECT * FROM users WHERE id = {user_id}"

# GOOD - Parameterized
query = "SELECT * FROM users WHERE id = ?"
```

### XSS

```python
# BAD - Unescaped output
html = f"<div>{user_input}</div>"

# GOOD - Escaped
html = "<div>{}</div>".format(escape(user_input))
```

See [[input-validation]] for prevention techniques.

## Authentication

- Password handling (never store plain)
- Session management
- MFA support
- Token validation

See [[authentication]] and [[encryption]].

## Related Skills

- [[code-review]] - General review process
- [[input-validation]] - Validating user data
- [[authentication]] - Auth patterns
- [[encryption]] - Data protection
