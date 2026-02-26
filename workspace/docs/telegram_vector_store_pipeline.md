# Telegram Vector Store Pipeline (Local-First)

## Export Procedure (Manual, Private Data Stays Local)

1. Open Telegram Desktop.
2. Go to `Settings -> Advanced -> Export Telegram data`.
3. Select:
   - Format: `JSON`
   - Include: `Messages`
   - Scope: chats relevant to c_lawd conversations
4. Save export under:
   - `workspace/state_runtime/ingest/telegram_exports/<YYYYMMDD>/`

Do not place raw exports under tracked source directories, and do not commit export JSON files.

## Expected Input Patterns

- Single file:
  - `workspace/state_runtime/ingest/telegram_exports/<YYYYMMDD>/result.json`
- Directory containing one or more `*.json` export files.

## Pipeline Commands

1. Ingest and normalize:

```bash
python3 workspace/scripts/telegram_ingest.py \
  --input workspace/state_runtime/ingest/telegram_exports/<YYYYMMDD> \
  --output workspace/state_runtime/ingest/telegram_normalized/messages.jsonl
```

2. Build vector store:

```bash
python3 workspace/scripts/telegram_vector_store.py build \
  --normalized workspace/state_runtime/ingest/telegram_normalized/messages.jsonl
```

3. Check store stats:

```bash
python3 workspace/scripts/telegram_vector_store.py stats
```

4. Query semantically:

```bash
python3 workspace/scripts/search_telegram.py "remember when we discussed phase 11"
```

## Embedding Backends

Order of preference (`--embedder auto`):

1. Ollama (`nomic-embed-text`) via local HTTP.
2. SentenceTransformers `all-MiniLM-L6-v2` if installed.
3. Deterministic hash fallback (test/degraded mode).

## Recall Integration Toggles

- `OPENCLAW_TELEGRAM_RECALL=1` enables context recall hook (default `0`).
- `OPENCLAW_TELEGRAM_RECALL_TOPK=6` controls top results included.
- `OPENCLAW_TELEGRAM_RECALL_MAX_CHARS=6000` caps injected recall size.
- `OPENCLAW_TELEGRAM_RECALL_CHAT_ID=<id>` optional chat filter.

## Analysis Stubs (Opt-In)

`workspace/scripts/telegram_analysis.py` supports:

- `topics`
- `sentiment`
- `alignment_patterns`
- `relationship_growth`

Enable with:

```bash
export OPENCLAW_TELEGRAM_ANALYSIS=1
```
