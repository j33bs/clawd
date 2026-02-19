# HiveMind Integration (QMD + HiveMind)

## Purpose
This document defines the dual-layer knowledge architecture used in OpenClaw System-2.

## Dual-Layer Architecture
| Layer | System | Responsibility | Data Shape |
|---|---|---|---|
| Retrieval Layer | QMD | Fast workspace retrieval (keyword + vector + rerank) | Files and document snippets |
| Memory Layer | HiveMind | Scoped memory with redaction, TTL, and integrity workflows | Knowledge Units (KUs) |

## Routing Contract
1. Query QMD first for repo/workspace grounding.
2. Query HiveMind second for long-term decisions, handoffs, and prior context.
3. Merge results with citations and scope-safe memory output.

## Data Flow
1. Source material is ingested into HiveMind from:
`/Users/heathyeager/clawd/MEMORY.md`,
`/Users/heathyeager/clawd/workspace/handoffs/*.md`,
and git commit metadata.
2. Content is redacted before persistence/embedding.
3. KUs are stored with `agent_scope`, `kind`, `source`, and optional `ttl_days`.
4. Query path enforces agent scope at read-time.

## Security Boundaries
- Redaction before embedding/persistence is mandatory.
- Agent isolation is mandatory (`main` vs `shared` vs other agent scopes).
- No external embedding API usage in local-first mode.
- Ingest and pruning actions are logged in
`/Users/heathyeager/clawd/workspace/hivemind/ingest.log`.

## Operator Commands
### QMD
```bash
npx @tobilu/qmd search "<query>" -n 5
npx @tobilu/qmd vsearch "<query>" -n 5
npx @tobilu/qmd query "<query>" -n 5
```

### HiveMind Query
```bash
python3 /Users/heathyeager/clawd/scripts/memory_tool.py query --agent main --q "<query>" --limit 5 --json
```

### HiveMind Ingest
```bash
python3 -m hivemind.cli ingest-memory
python3 -m hivemind.cli ingest-handoffs
python3 -m hivemind.cli ingest-commits
```

## Verification
- QMD index health: `npx @tobilu/qmd status`
- HiveMind query works: `python3 /Users/heathyeager/clawd/scripts/memory_tool.py query --agent main --q "routing" --limit 3`
- Scope enforcement: query from different agents returns isolated results.

## References
- `/Users/heathyeager/clawd/workspace/hivemind/README.md`
- `/Users/heathyeager/clawd/workspace/knowledge_base/KB_DESIGN.md`
- `/Users/heathyeager/clawd/scripts/memory_tool.py`
