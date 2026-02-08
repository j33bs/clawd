# change-admission-gate — constitution enforcement import fix (2026-02-08)

## design brief
Fix runtime ReferenceError in constitution-enforcement path: `core/model_call.js` referenced `buildConstitutionBlock(...)` without importing it. This is a wiring/import correction only.

## evidence pack
- Before: test fails with `buildConstitutionBlock is not defined`.
- After: constitution enforcement tests pass (gate off unchanged; gate on injects; missing constitution fails closed).
- No runtime/dist edits.

## rollback plan
Revert the commit that imports `buildConstitutionBlock` and adds the related test. If needed, disable the enforcement gate until reintroduced safely.

## budget envelope
Engineering: one import line + one test file.
Runtime: no added model tokens; change is pre-call only.
Ops: no new deps.

## expected roi
Restores deterministic constitution enforcement when enabled; prevents runtime crash; enables governance work to rely on enforcement path.

## kill-switch
If any unexpected behavior: revert commit immediately (or disable enforcement gate in config).

## post-mortem
Add CI coverage to ensure constitution-enforcement helpers referenced by `model_call` are always imported and resolvable.
