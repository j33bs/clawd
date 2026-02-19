---
name: code-review
description: Systematic code review techniques including pattern detection, security scanning, and architecture feedback
tags: [development, code-quality, security]
links: [style-guide, testing, security-scan, refactoring]
---

# Code Review

## When to Use

Use this skill when reviewing pull requests, code changes, or conducting pair programming sessions.

## Core Principles

1. **Start with intent** - Understand what the change is trying to accomplish before nitpicking style
2. **Look for patterns** - Common bugs, anti-patterns, and architectural issues
3. **Security first** - Scan for vulnerabilities before elegance
4. **Be constructive** - Suggest improvements, don't just criticize

## Review Checklist

- [ ] Does the code do what it's supposed to?
- [ ] Are there obvious bugs or edge cases?
- [ ] Is there proper error handling?
- [ ] Are there security vulnerabilities? (see [[security-scan]])
- [ ] Is the code testable? (see [[testing]])
- [ ] Does it follow the [[style-guide]]?
- [ ] Could this be refactored for clarity? (see [[refactoring]])

## Pattern Detection

### Code Smells

- Long functions (>50 lines)
- Deep nesting (>3 levels)
- Duplicate code
- Magic numbers
- Missing documentation

### Security Concerns

- SQL injection vectors
- XSS vulnerabilities
- Authentication/authorization gaps
- Sensitive data exposure
- Input validation

## Giving Feedback

Good feedback is:
- Specific and actionable
- Focused on the code, not the person
- Educational when possible
- Balanced (praise good patterns too)

## Related

- [[testing]] - Ensuring code works
- [[security-scan]] - Finding vulnerabilities
- [[refactoring]] - Improving existing code
- [[style-guide]] - Code standards
