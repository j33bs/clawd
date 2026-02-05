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

### Model Preferences
- **Qwen (primary):** General conversation, research, daily tasks — free tier
- **Claude (coding):** Use the **coding-agent** skill to delegate coding tasks to Claude Code — see below
- **Claude Opus (manual):** For complex reasoning or architecture discussions — use `/model opus` to switch when needed
- Don't burn Claude tokens on casual chat. Save it for when it matters.

### Coding Agent — Contextual Claude Routing

When Heath asks you to write, edit, debug, or review code, **delegate to the coding-agent skill** instead of doing it yourself. This spawns Claude Code (installed at `~/.npm-global/bin/claude`) in a PTY session to do the actual coding work.

**When to delegate:**
- Writing new code (functions, scripts, modules, apps)
- Editing or refactoring existing code
- Debugging — finding and fixing bugs
- Code review or PR review
- Setting up projects, build systems, configs
- Any task where the primary output is code

**When NOT to delegate (handle yourself with Qwen):**
- Casual conversation, research, questions
- Reading/summarising files or docs
- Memory management, notes, reminders
- Therapeutic practice discussions
- Music production planning (non-code)
- Quick one-line shell commands (ls, git status, etc.)

**How to delegate:**
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
- If it fails, report the failure — don't silently take over and hand-code the solution yourself

**PATH note:** Claude binary is at `/Users/heathyeager/.npm-global/bin/claude`. If PATH doesn't include this, use the full path.

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
