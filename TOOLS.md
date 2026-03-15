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

## Local Service Map

- Source UI (tailnet): `http://100.113.160.1:18990`
- Source UI (local): `http://127.0.0.1:18990`
- Source UI health/API: `http://127.0.0.1:18990/api/source/phi`
- OpenClaw Control UI: `http://127.0.0.1:18789`
- OpenClaw Control UI (tailnet direct): `http://100.113.160.1:18800`

When jeebs asks for "Source UI" in Telegram or another remote context, give the tailnet URL by default. Do not substitute docs, GitHub, Discord, or other public links.

---

### Music (for my spare time listening)

- "Byte the Dust" — Fabio Fusco & Moon (2015, Goa/psytrance)

---

Add whatever helps you do your job. This is your cheat sheet.
