# System Evolution 2026-02

## Scope
This document tracks the governed prototype implementation for the System-2 mega-prompt upgrades. The rollout is split into reversible commits and remains opt-in by default.

## Language/Stack Decision
- Repo stack is Node-first (evidence: `package.json`, existing `core/*.js`, script/test conventions under `scripts/` and `tests/`).
- Implementation uses Node modules under `sys/` and avoids introducing a second primary runtime.
- No external runtime services are required for the prototype.

## Dirty-file Incorporation Decisions
- `reports/daily/2026-02-09.html`: **DEFER**
  - Reason: pre-existing generated artifact unrelated to System-2 requirements.
  - Action: stashed as `defer-preexisting-dirty-reports` before implementation.
- No pre-existing dirty files were included in this workstream.

## Architecture Overview (Planned Modules)
- `sys/config/`: unified `sys/config.toml` loader, env overrides, schema validation, hot reload trace.
- `sys/memory_graph/`: local semantic graph store + query API with relation traversal.
- `sys/render/`: dual renderer for deterministic Markdown/HTML + template rendering.
- `sys/scheduler/`: slow-loop queue and specialist executor with persistence.
- `sys/maintenance/`: 10 quick fixes wired into scheduler.
- `sys/knowledge/breath/`: evidence-gated ingestion + summary API with internal citation IDs.

## Module Contracts
- Config: `loadConfig({configPath, env, cli}) -> object`
- Memory graph: `upsertNode`, `addRelation`, `fetchRelated(term, hops)`, `exportGraph`
- Render: `render({template, format, data}) -> {format, output}`
- Scheduler: `enqueue(task)`, `runOnce()`, `listTasks()`
- Maintenance: `runAll({dryRun})`, `listQuickFixes()`
- Breath: `summary()`, `ingest(manifestPath)`

## Acceptance Test Checklist
- [ ] Config precedence and hot-reload trace
- [ ] Semantic graph query and BFS hop traversal
- [ ] Deterministic render output for markdown + template paths
- [ ] Scheduler persistence + next_allowed_time handling
- [ ] Maintenance dry-run execution log
- [ ] Breath module empty-state and evidence-backed summary mode
- [ ] End-to-end sample run

## Reversibility
Each subsystem lands in its own commit so rollback can be targeted (`git revert <sha>`) without impacting existing OpenClaw routing behavior.
