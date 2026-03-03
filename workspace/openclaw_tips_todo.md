# OpenClaw 50+ Tips - Action Items

*Source: @aiedge_ article Feb 2026*

## Foundational
- [ ] Learn prompt engineering fundamentals
- [ ] Learn AI creativity (not just chatbot usage)
- [ ] Try other agentic tools first (n8n, Manus, Zapier) before OpenClaw
- [ ] Set explicit scope limits in prompts (directories, editable files)
- [ ] Force plan-first approach before execution
- [ ] Design workflows, not one-off tasks
- [ ] Use iteration prompt: "surprise me daily with improvements"
- [ ] Match model power to task (light = refactors, heavy = architecture)
- [ ] Prioritize RAM over CPU
- [ ] Use SSD, not HDD
- [ ] Create reusable prompt templates (refactor, debug, audit, feature)
- [ ] Use 5-part structure: Objective → Context → Constraints → Plan → Output

## Best Practices
- [ ] Treat chat history as cache, state + artifacts as source of truth
- [ ] Keep workspace (AGENTS.md) in git for backup
- [ ] Combine multiple models (GPT + Opus + open source)
- [ ] End sessions cleanly (summarize changes, verify VC)
- [ ] Document structural changes for future maintainability
- [ ] Enable multi-chat (Telegram, WhatsApp, Slack)
- [ ] Break complex tasks into phases (analysis → refactor → validation → optimization)
- [ ] Learn/create slash commands

## Security
- [ ] Bind to localhost (private by default)
- [ ] Consider separate device for OpenClaw
- [ ] Treat community skills as malicious until verified
- [ ] Run under non-admin user
- [ ] Only connect to necessary services

## Memory & Workflow
- [ ] Enable memory flush before compaction (`compaction.memoryFlush.enabled: true`)
- [ ] Set up session memory search
- [ ] Set up voice prompting (ElevenLabs TTS)
- [ ] Conduct time audit → share with agent → consult on automation opportunities

## Heartbeat
- [ ] Keep HEARTBEAT.md lean (minimize token burn)
- [ ] Rotate through checks rather than run all every time
