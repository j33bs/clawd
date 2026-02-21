# Follow-up Scope: TACTI Scaffold Imports

- Branch: `fix/tacti-scaffold-imports-20260221`
- Scope: resolve scaffold import regressions only (e.g. missing `cache_epitope` symbols); no policy/routing changes.

## Acceptance Criterion

`python3 -m pytest -q workspace/tacti_cr/tests/test_evolution_scaffolds.py`

Pass condition: scaffold import tests run and pass without import errors.
