# HiveMind Integration - Auto-Query Pattern

## Overview
C_Lawd auto-queries HiveMind via `exec` when relevant topics are detected. This provides contextual long-term memory without requiring config changes or vector embeddings.

## Query Command
```bash
cd /Users/heathyeager/clawd && python3 scripts/memory_tool.py query --agent main --q "<SEARCH_QUERY>" --limit 5 --json
```

## Auto-Query Triggers

Query HiveMind when the user's message contains:

### 1. **Technical Debugging**
- Error messages, stack traces, "all models failed", "404", "429"
- "Why is X broken?", "X stopped working"
- Model/provider names + error context (e.g., "Ollama", "Groq", "Telegram")

### 2. **Past Decisions & Context**
- "What did we decide about...", "Remember when...", "Last time we..."
- "Why did we...", "What was the reason for..."
- Configuration questions ("What's our routing setup?")

### 3. **Project References**
- HiveMind, TACTI(C)-R, Daily Briefing, Moltbook
- Wim Hof Method app, j33bs/clawd integration
- System components (router, capabilities, handoffs)

### 4. **Explicit Memory Requests**
- "Search memory for...", "What does HiveMind say about..."
- "Find notes on...", "Look up..."

### 5. **Recurring Topics**
- Ollama configuration, model routing, local vs remote
- Cron jobs, heartbeats, daily tasks
- Security, audits, governance

## Response Pattern

When HiveMind returns results:

1. **Check relevance** - Skip if results don't match the query
2. **Extract key info** - Pull the most relevant facts/decisions
3. **Cite sources** - Include `Source: <path>` when helpful
4. **Apply context** - Use memory to inform the response, don't just dump it

## Example

**User:** "Why did we change Ollama to use 127.0.0.1?"

**Auto-Query:** `python3 scripts/memory_tool.py query --agent main --q "Ollama 127.0.0.1 localhost IPv6" --limit 3 --json`

**Response:** "We hit a DNS resolution issue - Node.js was resolving `localhost` to IPv6 (::1) but Ollama only binds to IPv4. The fix was changing the baseUrl from `http://localhost:11434/v1` to `http://127.0.0.1:11434/v1` in the gateway config. This resolved the 'all models failed' errors in the fallback chain."

## Manual Override

You can always query manually:
```bash
cd /Users/heathyeager/clawd && python3 scripts/memory_tool.py query --agent main --q "<your query>" --limit 5
```

## Ingestion Notes

HiveMind ingests from:
- `MEMORY.md` (long-term facts/decisions)
- `handoffs/*.md` (agent-to-agent context)
- `git commits` (code changes with messages)

Recent changes may not be indexed yet - run ingestion if needed:
```bash
cd /Users/heathyeager/clawd/workspace/hivemind && python3 -m hivemind.ingest.memory_md
```

---
**Pattern:** Query → Filter → Apply → Cite
**Goal:** Contextual memory, not data dumping
