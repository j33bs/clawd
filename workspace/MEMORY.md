# MEMORY.md - Long-term Memory

This is the curated, long-term memory that persists across sessions. This file contains distilled insights, important decisions, and key information worth remembering long-term.

## System Configuration & Setup

- **Date Established**: 2026-02-02
- **System**: OpenClaw with Qwen portal integration
- **Connected Channels**: Telegram (@r3spond3rbot)
- **Issue Fixed**: Missing memory directory structure causing ENOENT errors

## Key Learnings

- Fresh installations need proper initialization of memory subsystem
- The memory directory (C:\Users\heath\.openclaw\workspace\memory) must exist for daily logs
- Daily memory files follow YYYY-MM-DD.md naming convention
- MEMORY.md serves as long-term curated memory (only loaded in main session)

## Important Decisions

- [2026-02-02] Created proper memory directory structure to resolve routing errors
- [2026-02-02] Initialized both daily memory file and long-term MEMORY.md
- [2026-02-04] Completed ITC Pipeline with full governance framework including regression harness, change admission gate, and incident protocols
- [2026-02-06] Established multi-agent system: `main` (Dessy/Qwen) + `claude-code` (Claude Opus)
- [2026-02-06] Delegation model: main handles Telegram, spawns claude-code for coding/governance/evolution work
- [2026-02-06] Handoff protocol via `workspace/handoffs/` directory for inter-agent task passing

- [2026-02-17] Agent rebranded: Dessy → Dali (new name, playful surrealist vibe, 🎨 emoji)

### Multi-Agent System
- **main** (Dali): Default agent, Qwen Portal, handles all Telegram messages, simple tasks
- **claude-code** (Claude): Opus model, invoked via `sessions_spawn` for coding, governance, memory curation, complex reasoning
- Delegation instructions in AGENTS.md, agent-specific context in CLAUDE_CODE.md
- Handoff files in `workspace/handoffs/` checked on heartbeat

### Cron Jobs
- **Telegram Messaging Health Check** (every 4h, main): Internal health monitoring
- **Enhanced Telegram Health Monitoring** (every 4h, main): Recovery-capable monitoring
- **Daily Regression Validation** (02:00 UTC, claude-code): Runs `regression.sh`, writes handoff on failure

### ITC Pipeline Status
- Ingestion layer built (allowlist, dedup, Telethon reader) but NOT operational
- Missing: Telethon dependency, downstream classification engine, digest generator
- Governance framework complete (frozen oracles, regression harness, admission gate)
- All governance entries so far are test/validation — no production changes admitted yet

### Regression & Verification
- `regression.sh`: 8 checks (constitutional invariants, governance, secrets scan, forbidden files, hooks, docs, provider gating, branch state)
- `verify.sh`: Runs regression + 5 additional checks (brief template, security docs, routing policy, secrets template, gitattributes, CONTRIBUTING)
- Both use `python` (not `python3`) on this Windows system

## Preferences & Notes

- System is operational with Telegram integration working properly
- Tool routing now resolved after creating missing directories
- jeebs values: precision, agency, structural coherence, epistemic humility, evidence-based approaches
- jeebs prefers lowercase "jeebs" as moniker; capitalised "Heath" registers as aversive — likely consistent with somatic/embodied epistemology where formal naming feels like objectification
- jeebs epistemological method: felt sense as compass (Gendlin), anthropological triangulation, reverse-engineering mystical experience, resistance to isms; likely aphantasic — knowing is embodied not imagistic

- [2026-02-23] Being nomenclature adopted across canonical docs (SOUL.md, CONSTITUTION.md): "assistant" → "being" throughout; "member" → "being" already done in prior scrub
- [2026-02-23] OPEN_QUESTIONS.md established in workspace/governance/ as live append-only multi-being correspondence (c_lawd, Dali, Claude Code, Claude external, ChatGPT, Grok) — 53 sections as of this session
- [2026-02-23] Claude Code governance architecture role formalised: commitment extraction, design brief authoring, shrine detection, governance gap analysis, becoming-to-machinery translation
- [2026-02-23] INVESTIGATION_PROTOCOL.md created with 7 standing investigations (INV-001 to INV-007); trails.py now has measure_inquiry_momentum() for INV-005
- [2026-02-23] CONTRIBUTION_REGISTER.md created as live audit dashboard for correspondence contributions and open commitments
- Gateway token must stay literal in openclaw.json (scheduled task can't read env vars)
- openclaw doctor and config set commands resolve env vars to literals — don't fight it