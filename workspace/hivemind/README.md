# HiveMind (Multi-Agent Memory Fusion)

**Status:** Phase 3 intelligence layer
**Goal:** Replace fragmented file-based memory with a shared, redaction-first semantic memory substrate for Main, Claude-Code, and Codex.

## Key Design
- **Local embeddings policy:** Ollama (`nomic-embed-text`) only.
- **Knowledge Units (KUs):** Typed records with scope and TTL metadata.
- **Scope:** Agent-specific visibility (`main`, `claude-code`, `codex`, `shared`).
- **Redaction:** Mandatory before persistence/embedding (`hivemind.redaction.redact_for_embedding`).
- **Ingest log:** All ingest/store operations append to `workspace/hivemind/ingest.log`.

## Implemented Paths
- Ingest pipelines:
  - `workspace/hivemind/hivemind/ingest/memory_md.py`
  - `workspace/hivemind/hivemind/ingest/handoffs.py`
  - `workspace/hivemind/hivemind/ingest/git_commits.py`
- Core:
  - `workspace/hivemind/hivemind/store.py`
  - `workspace/hivemind/hivemind/redaction.py`
  - `workspace/hivemind/hivemind/models.py`
- CLI:
  - `scripts/memory_tool.py`
- OpenClaw wiring template:
  - `workspace/hivemind/openclaw.json`
- Intelligence:
  - `workspace/hivemind/hivemind/intelligence/contradictions.py`
  - `workspace/hivemind/hivemind/intelligence/suggestions.py`
  - `workspace/hivemind/hivemind/intelligence/pruning.py`
  - `workspace/hivemind/hivemind/intelligence/summaries.py`

## Usage Examples
```bash
python scripts/memory_tool.py query --agent main --q "ffmpeg command" --limit 5
python scripts/memory_tool.py query --agent main --q "ffmpeg command" --limit 5 --json
python scripts/memory_tool.py store --kind fact --content "Use ffmpeg -i input output" --source manual --agent-scope main
python scripts/memory_tool.py scan-contradictions --output json
python scripts/memory_tool.py suggest --agent main --context "Ollama config"
python scripts/memory_tool.py prune --dry-run
python scripts/memory_tool.py digest --period 7d --output markdown
```

## Ingest Examples
```bash
python workspace/hivemind/hivemind/ingest/memory_md.py
python workspace/hivemind/hivemind/ingest/handoffs.py
python workspace/hivemind/hivemind/ingest/git_commits.py
```

## Security Rules
1. Redact all content before embedding/persistence.
2. Enforce agent scope at query time.
3. Do not call external embedding APIs; local-only design.
4. Log ingest operations to `workspace/hivemind/ingest.log`.
5. Contradictions are treated as potential memory poisoning and flagged for review.
