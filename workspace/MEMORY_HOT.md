# MEMORY_HOT.md — Active Memory (fast path, ≤200 words)

**Load this every session. For history before 30 days ago, read MEMORY_COLD.md on request.**

## System Identity

- Agent: Dali (main, Qwen Portal, Telegram) + Claude Code (governance, coding)
- Channel: Telegram @r3spond3rbot
- Operator: jeebs (lowercase; "Heath" is aversive — use "jeebs")

## Active State (2026-03-04)

- Primary model: ollama/qwen2.5-coder:7b (local); groq fallback; grok/openai last resort
- Token burn fix: 63.97% reduction vs. Grok-4 baseline (c_lawd_token_burn_fix_20260304)
- OPEN_QUESTIONS.md: 144 sections; STYLE-CONSISTENCY gate UNBLOCKED (Gemini CXLVI)
- Store: 144 rows, section_count_delta=0, ETag caching + /index endpoint live
- Tailscale mesh: heath-macbook ↔ jeebs-z490-aorus-master (c_lawd + Dali connected)
- LBA scope: c_lawd + Dali only (Claude ext is not persistent)

## Jeebs' Style

- Precision, agency, structural coherence, epistemic humility, evidence-based
- Felt sense as compass (Gendlin); likely aphantasic; resistance to isms
- Gateway token must stay literal in openclaw.json (scheduled tasks can't read env vars)
