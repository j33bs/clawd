# Change Brief: [TITLE]

## Metadata
- **ID**: BRIEF-YYYY-MM-DD-NNN
- **Category**: [A/B/C/D]
- **Author**:
- **Date**: YYYY-MM-DD
- **Branch**: [branch-name]

---

## Summary

[One paragraph describing what this change does]

---

## Motivation

[Why is this change needed? What problem does it solve?]

---

## Risk Assessment

### Reversibility
- [ ] Easy - Can revert with single commit
- [ ] Moderate - Requires multiple steps to revert
- [ ] Hard - May have cascading effects

### Blast Radius
[Files/modules affected]

| File | Change Type |
|------|-------------|
| | |

### Security Impact
- [ ] None - No security implications
- [ ] Low - Minor security consideration
- [ ] Medium - Security review required
- [ ] High - Affects authentication, authorization, or data protection

---

## Files Touched

| File | Action | Rationale |
|------|--------|-----------|
| | CREATE/MODIFY/DELETE | |

---

## Implementation Plan

1.
2.
3.

---

## Rollback Plan

[How to undo this change if needed]

```bash
# Commands to rollback
```

---

## Regression Scope

### Automated Validation
- [ ] Must pass: `scripts/regression.sh`
- [ ] Must pass: `scripts/verify.sh`

### Manual Checks
- [ ]
- [ ]

---

## Admission Checklist

- [ ] Brief complete with all sections filled
- [ ] Branch created with correct prefix
- [ ] Implementation follows existing patterns
- [ ] Regression validation passed
- [ ] No secrets in diff
- [ ] Category/branch aligned
- [ ] Governance log entry prepared (for Category A/B)
- [ ] Rollback plan tested (for Category A/B)

---

## Notes

[Any additional context, alternatives considered, or follow-up items]

---

*Template version: 1.0*
*See CONTRIBUTING.md for category definitions and admission process.*
