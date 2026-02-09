# Change Admission Gate — system evolution prototype (2026-02-09)

## design brief
Implement a governed, opt-in System-2 prototype under `sys/` with modular contracts for config, semantic memory graph, rendering, scheduler, maintenance, and evidence-gated breath knowledge.

## evidence pack
- Baseline routing verification recorded in `logs/system_evolution_2026-02-09.txt` (5/5 pass).
- Dirty pre-existing artifact triaged and deferred before implementation.
- Commit sequence is subsystem-scoped and reversible.

## rollback plan
Revert individual subsystem commits in reverse order. Because default runtime paths are untouched, rollback does not require config migration.

## budget envelope
Scope limited to local modules, scripts, docs, and tests. No external services or remote dependencies.

## expected roi
Creates a governed foundation for System-2 capabilities with local reproducibility, introspection, and opt-in activation.

## kill-switch
Leave feature flags off to disable the new prototype paths. Revert latest subsystem commit if regressions are observed.

## post-mortem
If regressions occur, record root cause, affected subsystem, and rollback SHA before re-attempting the phase.
