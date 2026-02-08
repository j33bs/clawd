# Change Admission Gate Record: Self-Improvement Constitution

Date: 2026-02-06
Gate ID: Run-007
Scope: Governance hardening for self-improvement controls

## Design Brief
- Introduce a versioned, explicit self-improvement constitution file as canonical policy.
- Add a mechanistic gate script that blocks sensitive routing/governance/economic changes unless a staged gate record is present.
- Require structured sections in gate records so design/evidence/rollback intent is explicit.
- Wire gate checks into local commit workflow via npm scripts and pre-commit template.

## Evidence Pack
- Existing routing verification remains pass/fail based:
  - `node scripts/verify_model_routing.js`
- Gate mechanism evidence:
  - `node scripts/check_change_admission_gate.js` enforces:
    - required gate record for sensitive changes
    - required sections check
    - kill-switch auto-restart anti-pattern detection
  - escape hatch requires explicit operator action (`ALLOW_EXTRA_FILES=1`).

## Rollback Plan
- Revert this gate by removing:
  - `scripts/check_change_admission_gate.js`
  - constitution file and related package script/hook references
- Restore previous behavior by removing `gate:admission` invocation from pre-commit template.
- Re-run constitutional and routing checks to confirm baseline state.

## Budget Envelope
- Baseline token burn budget impact: zero at runtime.
- Gate runs only at commit-time and does not affect inference token path.

## Expected ROI
- Reduce governance regressions from accidental or silent policy/routing/economic edits.
- Increase auditability and review quality with mandatory admitted change records.

## Kill-switch and Post-mortem
- Policy rule retained: kill-switch triggers are terminal for run.
- Gate script blocks new sensitive diffs that add `auto-restart` semantics unless explicitly overridden.
- Any override requires manual justification in commit workflow and post-mortem in follow-up gate record.


## 2026-02-08 — Constitutional instantiation (brief)
# Constitutional Instantiation Brief
- Insertion point: `core/model_call.js` in `callModel`, immediately before provider dispatch (`provider.call(...)`).
- Final system prompt is produced by `buildBudgetedMessages`/`enforcePromptBudget`; dispatch is in same function.
- New module: `core/constitution_instantiation.js`.
- API: `loadConstitutionSources({sourcePath,supportingPaths,maxChars})` and `buildConstitutionBlock({text,sha256,truncated})`.
- Audit schema (JSONL): `{ts,phase,runId,sha256,approxChars,truncated,sourceCount,sources:[{path,sha256,approxChars,truncated}]}`.
- No raw constitution text in logs; hash + sizes + paths only.
- Commit 1: observe-only `constitution_instantiated` audit, zero prompt mutation.
- Commit 2: env-gated injection (`OPENCLAW_CONSTITUTION_ENFORCE=1`), default OFF, controlled failure on load errors.
- Commit 3: operator verifier + governance runbook.
- Reversible by reverting the three commits in order.
