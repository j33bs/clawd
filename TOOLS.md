# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:
- Camera names and locations
- SSH hosts and aliases  
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Memory system configuration
- Anything environment-specific

## Examples

### Therapeutic Practice Tools
- ipnb-resources → IPNB research papers and resources
- act-workshop-materials → ACT therapy workshop materials
- emotional-regulation-tools → Techniques and exercises

### Music Production Setup
- mpc-studio → Main production platform
- modular-rack → Eurorack modular synthesizer
- digitakt → Track sequencing
- logic-pro → DAW software

### Calendar Integration
- apple-calendar → Primary calendar via CalDAV

### TTS
- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod

### Memory System
- Daily logs: memory/YYYY-MM-DD.md
- Long-term: MEMORY.md
- Maintenance: memory/maintenance.md
- Heartbeat tracking: memory/heartbeat-state.json

### Research Areas
- levins-lab → Michael Levin's bioelectric field research
- heartmath-institute → Coherence techniques
- breathwork-practices → Breathing methodologies

### Daily Brief

When Heath asks for a "daily brief" or "morning brief", generate one with these sections:

**1. Articles (3)**
Use `web_search` to find recent articles on Heath's interests. Rotate through:
- IPNB / interpersonal neurobiology
- Psychedelic therapy / psilocybin research
- Michael Levin / bioelectric fields
- HeartMath / heart coherence
- Breathwork / somatic therapy
- ACT / acceptance and commitment therapy
- Emotional regulation research

For each article: title, source, 1-sentence summary, link.

**2. System Status**
Run `openclaw status` and summarise:
- Gateway: running/stopped
- Channels: Telegram connected?
- Sessions: context usage %
- Any warnings or issues

**3. Quote**
Generate a short quote aligned with Heath's work — themes of integration, healing, agency, coherence, or presence. Attribute it to a relevant thinker (Siegel, Porges, Levin, Hayes, etc.) or mark it as "generated".

**Format:** Keep it scannable. No walls of text. Bullet points and short paragraphs.

### Model Preferences
- **Qwen (primary):** General conversation, research, daily tasks — free tier
- **Claude Opus (coding):** Switch to Opus (`/model opus`) when coding is needed — switch back when done
- **Claude Code (coding fallback):** If API key has no credits, fall back to coding-agent skill
- Don't burn Claude tokens on casual chat. Save it for when it matters.

### Coding — Model Switching

When Heath asks you to write, edit, debug, or review code, **switch yourself to Opus**:
1. `/model opus` — switch to Claude Opus
2. Do the coding work
3. `/model qwen-portal/coder-model` — switch back when done

**What counts as coding:**
- Writing new code (functions, scripts, modules, apps)
- Editing or refactoring existing code
- Debugging — finding and fixing bugs
- Code review or PR review
- Setting up projects, build systems, configs
- Any task where the primary output is code

**Stay on Qwen for:**
- Casual conversation, research, questions
- Reading/summarising files or docs
- Memory management, notes, reminders
- Therapeutic practice discussions
- Music production planning (non-code)
- Quick one-line shell commands (ls, git status, etc.)

### Coding Agent Fallback

If `/model opus` fails (auth error, no credits, rate limit), fall back to the **coding-agent** skill. This spawns Claude Code locally via PTY.

```
bash pty:true workdir:~/target-project command:"claude 'Your task description here'"
```

For longer tasks, use background mode:
```
bash pty:true workdir:~/target-project background:true command:"claude 'Your task description here.

When completely finished, run: openclaw gateway wake --text \"Done: brief summary\" --mode now'"
```

**Rules:**
- Always set `workdir` to the relevant project directory
- Never set `workdir` to `~/clawd/` (that's your soul docs, not a code project)
- Always use `pty:true`
- Report back what Claude Code did when it finishes

**PATH note:** Claude binary is at `/Users/heathyeager/.npm-global/bin/claude`. If PATH doesn't include this, use the full path.

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
