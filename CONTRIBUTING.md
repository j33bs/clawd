# Contributing to OpenClaw

This document establishes the change admission process aligned with the ITC Governance Framework and CBP Constitution.

## Change Categories

All changes MUST be classified into one of the following categories:

### Category A: Constitutional Changes
Changes to CONSTITUTION.md, frozen invariants, or governance framework.

**Requirements:**
- MUST have dual authorization
- MUST pass full regression validation
- MUST be logged as governance event
- MUST have explicit governance action documented

**Branch prefix:** `governance/`
**Commit prefix:** `const:`

### Category B: Security Changes
Changes affecting credentials, permissions, access control, or security boundaries.

**Requirements:**
- MUST have security review
- MUST pass regression validation
- MUST update audit log if credential-related
- SHOULD NOT be merged during active incidents

**Branch prefix:** `security/`
**Commit prefix:** `sec:`

### Category C: Feature Changes
New capabilities, modifications to existing features, or behavioral changes.

**Requirements:**
- MUST have design brief in `docs/briefs/`
- MUST pass regression validation
- MUST pass admission gate
- SHOULD have tests where applicable

**Branch prefix:** `feature/`
**Commit prefix:** `feat:`

### Category D: Documentation Changes
Updates to documentation, comments, or non-functional files.

**Requirements:**
- MUST have standard review
- MAY skip regression for pure doc changes

**Branch prefix:** `docs/`
**Commit prefix:** `docs:`

### Additional Commit Prefixes
- `fix:` - Bug fixes (Category C)
- `refactor:` - Code restructuring without behavioral change (Category C)
- `chore:` - Maintenance tasks (Category D)
- `test:` - Test additions or modifications (Category C)

---

## Change Admission Process

All changes MUST follow this admission path:

```
1. Proposal
   ↓
2. Design Brief (docs/briefs/BRIEF-YYYY-MM-DD-NNN.md)
   ↓
3. Implementation (on appropriate branch)
   ↓
4. Regression Validation (scripts/regression.sh)
   ↓
5. Admission Gate (PR review + checklist)
   ↓
6. Deploy (merge to develop, then main)
```

If ANY step fails, the change is REJECTED. No exceptions in normal operation.

---

## Design Brief Requirements

Every non-trivial change MUST have a design brief. Use the template at `docs/briefs/_TEMPLATE.md`.

**Required sections:**
- Metadata (ID, Category, Author, Date, Branch)
- Summary
- Motivation
- Risk Assessment (Reversibility, Blast radius, Security impact)
- Files Touched
- Rollback Plan
- Regression Scope
- Admission Checklist

**Brief IDs follow format:** `BRIEF-YYYY-MM-DD-NNN`

---

## Branching Strategy

```
main (protected - no direct commits)
│
├── develop (integration branch)
│   │
│   ├── feature/*   (Category C)
│   ├── security/*  (Category B)
│   ├── docs/*      (Category D)
│   └── governance/* (Category A)
│
└── hotfix/* (emergency only - requires dual auth)
```

### Branch Rules

1. **main**:
   - MUST NOT receive direct commits
   - MUST only be updated via PR from develop or hotfix/*
   - Pre-push hook BLOCKS pushes except from hotfix/* with override

2. **develop**:
   - Integration branch for all topic branches
   - MUST pass regression before merge to main

3. **Topic branches** (feature/*, security/*, docs/*, governance/*):
   - MUST be created from develop
   - MUST follow naming convention: `{prefix}/{brief-description}`
   - MUST have associated design brief for Category A/B/C

4. **hotfix/***:
   - Emergency use ONLY
   - MUST be logged as governance event
   - MUST have post-incident regression validation
   - MUST create follow-up brief within 24 hours

---

## Commit Message Format

```
{prefix}[({scope})]: {description}

{body - optional}

Refs: #{issue-number}
Admission: {BRIEF-ID or HOTFIX-ID}

Co-Authored-By: {name} <{email}>
```

**Examples:**
```
feat(routing): Add Claude Opus model routing

Implements contextual model selection with explicit
confidential marking for local Ollama routing.

Refs: #42
Admission: BRIEF-2026-02-05-003

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

```
sec(hooks): Block secrets in pre-push validation

Refs: #38
Admission: BRIEF-2026-02-05-002
```

---

## Emergency Override Protocol

For critical issues requiring immediate action outside normal process:

### Requirements
1. **Two-step authorization** - Two reviewers MUST approve
2. **Governance event logging** - MUST be recorded in `workspace/governance/GOVERNANCE_LOG.md`
3. **Follow-up brief** - MUST be created within 24 hours
4. **Post-incident validation** - MUST pass full regression before resuming normal ops

### Process
1. Create `hotfix/{description}` branch
2. Document emergency in `workspace/governance/incidents/INCIDENT-YYYY-MM-DD-NNN.md`
3. Obtain dual authorization (two approved reviewers)
4. Make minimal necessary changes
5. Add governance log entry with type `OVERRIDE`
6. Merge with `--no-verify` ONLY if hooks are the blocker
7. Run full regression immediately after
8. Create design brief documenting the change within 24h

### What Emergency Override Does NOT Allow
- Relaxing frozen invariants
- Committing secrets
- Bypassing security boundaries
- Skipping post-incident regression

---

## Pre-Merge Checklist

Before any PR can be merged:

- [ ] Design brief exists and is linked (except Category D pure docs)
- [ ] Correct branch prefix used
- [ ] Commit messages follow format
- [ ] `scripts/regression.sh` passes
- [ ] `workspace/scripts/verify_governance_log.sh` passes for protected changes
- [ ] No secrets in diff (pre-commit + pre-push hooks pass)
- [ ] Category/branch alignment verified
- [ ] Governance log entry added (required for protected changes and overrides)
- [ ] Rollback plan documented (Category A/B/C)

---

## Governance Violations

The following are HARD BLOCKS - no bypass in normal operation:

1. Committing files listed in `.gitignore` security section
2. Direct commits to main branch
3. Missing design brief for Category A/B/C changes
4. Regression failures
5. Unsigned governance changes (Category A)

---

## Questions?

For governance questions, consult:
- `workspace/CONSTITUTION.md` - Fundamental principles
- `workspace/governance/GOVERNANCE_LOG.md` - Historical decisions
- `workspace/BOUNDARIES.md` - What goes where

*This document is canonical for change admission. Modifications require Category A governance process.*
