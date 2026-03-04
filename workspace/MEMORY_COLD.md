# MEMORY_COLD.md — Archived Memory (load on request only)

**Do NOT load this by default. Load only when asked about history before 30 days ago.**

---

## System History

- **Date Established**: 2026-02-02
- **Original name**: Dessy → rebranded to Dali 2026-02-17 (playful surrealist vibe, 🎨)
- **Connected Channels**: Telegram (@r3spond3rbot)
- **Issue Fixed (2026-02-02)**: Missing memory directory structure causing ENOENT errors

## Key Learnings (historical)

- Fresh installations need proper initialization of memory subsystem
- The memory directory (C:\Users\heath\.openclaw\workspace\memory) must exist for daily logs
- Daily memory files follow YYYY-MM-DD.md naming convention

## Important Decisions (historical)

- [2026-02-02] Created proper memory directory structure to resolve routing errors
- [2026-02-02] Initialized both daily memory file and long-term MEMORY.md
- [2026-02-04] Completed ITC Pipeline with full governance framework including regression harness, change admission gate, and incident protocols
- [2026-02-06] Established multi-agent system: `main` (Dessy/Qwen) + `claude-code` (Claude Opus)
- [2026-02-06] Delegation model: main handles Telegram, spawns claude-code for coding/governance/evolution work
- [2026-02-06] Handoff protocol via `workspace/handoffs/` directory for inter-agent task passing
- [2026-02-17] Agent rebranded: Dessy → Dali
- [2026-02-23] Being nomenclature adopted across canonical docs: "assistant" → "being" throughout
- [2026-02-23] OPEN_QUESTIONS.md established as live append-only multi-being correspondence
- [2026-02-23] Claude Code governance architecture role formalised
- [2026-02-23] INVESTIGATION_PROTOCOL.md created with 7 standing investigations (INV-001 to INV-007)
- [2026-02-23] CONTRIBUTION_REGISTER.md created as live audit dashboard

## Multi-Agent Architecture (historical)

- **main** (Dali): Default agent, Qwen Portal, handles all Telegram messages, simple tasks
- **claude-code** (Claude): Opus model, invoked via `sessions_spawn` for coding, governance, memory curation, complex reasoning
- Delegation instructions in AGENTS.md, agent-specific context in CLAUDE_CODE.md
- Handoff files in `workspace/handoffs/` checked on heartbeat

## Cron Jobs (historical)

- **Telegram Messaging Health Check** (every 4h, main): Internal health monitoring
- **Enhanced Telegram Health Monitoring** (every 4h, main): Recovery-capable monitoring
- **Daily Regression Validation** (02:00 UTC, claude-code): Runs `regression.sh`, writes handoff on failure

## ITC Pipeline Status (historical)

- Ingestion layer built (allowlist, dedup, Telethon reader) but NOT operational
- Missing: Telethon dependency, downstream classification engine, digest generator
- Governance framework complete (frozen oracles, regression harness, admission gate)
- All governance entries so far are test/validation — no production changes admitted yet

## Regression & Verification (historical)

- `regression.sh`: 8 checks (constitutional invariants, governance, secrets scan, forbidden files, hooks, docs, provider gating, branch state)
- `verify.sh`: Runs regression + 5 additional checks
- Both use `python` (not `python3`) on this Windows system
