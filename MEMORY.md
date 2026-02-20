# MEMORY.md - Long-Term Context

*Last updated: 2026-02-18*

## User Preferences
- **Name:** Heath
- **Call them:** Jeebs (nickname from @j33bs handle)
- **Pronouns:** -
- **Timezone:** Australia/Brisbane
- **GitHub:** @j33bs

## Current Projects

### 1. Research System
- **Status:** Populated with 4 TACTI(C)-R foundational papers
- **Topics covered:** temporality, arousal, cross_timescale, repairable
- **Files:** `workspace/research/research_ingest.py`
- **Commands:** `research_ingest.py list|add|search`

### 2. Wim Hof App Enhancements
- **Status:** On back burner (not priority right now)
- **Brief exists:** `workspace/research/WIM_HOF_AI_ENHANCEMENTS_BRIEF_2026-02-18.md`

### 3. Daily Briefing
- **Status:** Enabled, scheduled for 7 AM Brisbane time
- **Cron ID:** `15f0bbc8-e726-4426-ac15-e9deb9778318`
- **Components:** Quote, Reminders, News, Therapeutic Technique
- **Fixed:** Global cron was disabled, now enabled (2026-02-18)

### 4. Telegram
- **Stream mode:** Reverted to "off" (streaming beta not working in current version)
- **Bot:** @Mbresponderbot

## Key Decisions
- **Routing:** BASIC → LOCAL_QWEN, NON_BASIC → Claude
- **Local models:** Qwen2.5 (0.5b, 7b coder) available via Ollama
- **Ollama fix:** Using 127.0.0.1 instead of localhost for IPv4
- **QMD:** Installed for fast workspace search
- **HiveMind:** 3 phases complete (storage, ingest, intelligence)

## Technical Notes
- **Runtime:** minimax-portal/MiniMax-M2.5
- **Gateway:** Launched via launchd
- **Codex tasks:** Some completed, check `workspace/CODEX_TASK_LIST.md`

### Router OAuth Implementation (2026-02-20)
- **Status:** Implemented but blocked by 401 error
- **Changes:** Modified `policy_router.py` to resolve OAuth tokens from `auth.json`
- **Issue:** OpenAI returns 401 Unauthorized when using OAuth token (JWT) with standard `api.openai.com` endpoint
- **Next:** Consider switching TeamChat to use Minimax (which is working) or fix OpenAI endpoint config
- **venv:** Created `workspace/venv` with `requests` library for the router script

## TACTI(C)-R Principles
1. **Vitality** - Temporality Collapse via Arousal
2. **Cognition** - Cross-Timescale processing
3. **Flow** - Adaptive computation
4. **Malleability** - Learning/adaptation
5. **Agency** - Self-healing, repairable systems

## Research Preferences
- **Novelty focus**: Prioritize finding unique, non-obvious information that increases novelty (vs common knowledge)
