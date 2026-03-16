# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

### Music (for my spare time listening)

- "Byte the Dust" — Fabio Fusco & Moon (2015, Goa/psytrance)

---

Add whatever helps you do your job. This is your cheat sheet.

### Source UI

- Live Source UI backlog: `http://100.113.160.1:18990`
- When asked in direct chat or Telegram to add something to Source UI backlog, use the hidden control tag:
  `<source-ui-task>{"title":"...","description":"...","priority":"high","project":"source-ui"}</source-ui-task>`
- Do not claim `queued`, `visible`, `live`, or `flowing` unless the final reply includes a verified line:
  `Source UI receipt: #<id> <title> (<status>)`
