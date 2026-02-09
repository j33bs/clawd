# System Evolution 2026-02

## Scope
This document tracks the governed prototype implementation for the System-2 mega-prompt upgrades. Rollout is reversible, module-scoped, and opt-in by default so existing OpenClaw behavior stays unchanged.

## Language/Stack Decision
- Repo stack is Node-first (evidence: `package.json`, existing `core/*.js`, script/test conventions under `scripts/` and `tests/`).
- Implementation uses Node modules under `sys/`.
- No remote runtime services were introduced.

## Dirty-file Incorporation Decisions
- `reports/daily/2026-02-09.html`: **DEFER**
  - Reason: pre-existing generated artifact unrelated to System-2 requirements.
  - Action: stashed as `defer-preexisting-dirty-reports` before implementation.
- No pre-existing dirty files were included in this workstream.

## Architecture Overview
- `sys/config/`: unified config loader for TOML + env + CLI overrides and hot-reload watcher.
- `sys/memory_graph/`: local JSON-LD semantic graph memory with typed relations and BFS traversal.
- `sys/render/`: deterministic markdown runtime rendering and Handlebars-like template rendering.
- `sys/scheduler/`: slow-loop SQLite queue, specialist execution, and persisted run history.
- `sys/maintenance/`: ten quick-fix checks plus scheduler enqueue integration.
- `sys/knowledge/breath/`: evidence-gated ingestion and citation-aware summary API.
- `sys/adapters/legacy_bridge.js`: compatibility adapter for legacy memory/brief flows.

## Module Contracts
- Config:
  - `loadConfig({configPath, env, cliOverrides}) -> config`
  - `watchConfig({configPath, onReload, onError}) -> closeFn`
- Memory graph:
  - `upsertNode(node)`
  - `addRelation(from, to, relType)`
  - `fetchRelated(termOrId, hops)`
  - `resolveFileNode(path)`
  - `exportGraph()`
- Render:
  - `render({template, format, data}) -> {format, output, markdown}`
- Scheduler:
  - `createQueueStore({dbPath})`
  - `createScheduler({queueStore, outputDir, graphStore})`
  - `enqueue(task)` and `runOnce(nowIso)`
- Maintenance:
  - `listQuickFixes()`
  - `runQuickFix(name, context)`
  - `runAll(context)`
  - `enqueueMaintenanceTasks(queueStore, options)`
- Breath module:
  - `breath.summary({manifestPath})`
  - `ingestSources({manifestPath, sourceManifestPath})`

## Feature Flags and Default Safety
- Config defaults in `sys/config.toml` keep all System Evolution features disabled.
- Existing OpenClaw routing path remains unchanged unless operators explicitly run `sys/` scripts.
- No global runtime bundle or dist patching in this implementation.

## Migration Strategy
- Legacy memory files are read-only indexed through `sys/adapters/legacy_bridge.js`.
- Existing file formats remain intact; graph enrichment is additive.
- Legacy brief generation can remain markdown-only by setting compatibility mode disabled.

## Breath Module Evidence Policy
- No fabricated external findings.
- `breath.summary()` only summarizes ingested local sources with `evidence_id` citations.
- Empty-state behavior returns `no_ingested_sources` and explicit ingest instructions.
- Source ingest CLI: `node scripts/breath_ingest.js --source-manifest <path>`.

## Acceptance Checklist
- [x] Config precedence and hot-reload trace
- [x] Semantic graph query and BFS hop traversal (`fetchRelated('breathwork', 2)`)
- [x] Deterministic render output for markdown + template paths
- [x] Scheduler persistence + next_allowed_time handling
- [x] Maintenance dry-run execution and scheduler integration
- [x] Breath module empty-state and evidence-backed summary mode
- [x] End-to-end sample run with queue/query/render/hot-reload output

## Operator Commands
- Full self-test:
  - `node scripts/sys_evolution_self_test.js`
- Sample run only:
  - `node scripts/sys_evolution_sample_run.mjs`
- Memory graph tools:
  - `node scripts/memory_graph_index.js`
  - `node scripts/memory_graph_query.js breathwork 2`
- Maintenance:
  - `node scripts/maintenance_run.js --check`
  - `node scripts/maintenance_run.js --all`

## Reversibility
Each subsystem lands in its own commit; targeted rollback is `git revert <sha>` in reverse dependency order.

## Post-Implementation Report
### Progress
- Implemented unified config, semantic graph memory, dual rendering, scheduler fabric, maintenance layer, breath evidence module, compatibility adapter, and operator self-tests.
- Added a reproducible sample artifact at `docs/fixtures/brief_sample.html`.
- Logged execution traces in `logs/system_evolution_2026-02-09.txt` via command logging and migration log appends.

### Remaining Issues
- SQLite backend now uses stable `better-sqlite3` via `sys/db/sqlite_adapter.js`; operators should run the substitute lint gate after dependency updates.
- Specialist execution is local/stubbed for deterministic operation; advanced specialist intelligence remains future work.
- `sys/state/` is runtime-only and not populated in-repo by default.

### Next Evolutionary Cycle Direction
- Expand SQLite adapter observability (query timing + error counters) without altering scheduler semantics.
- Extend specialist parsers and provenance metadata for richer memory graph edges.
- Add optional UI/reporting dashboard on top of `sys/state` outputs.
