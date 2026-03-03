# Prompt for Codex: Update AGENTS.md Startup Files

## Task

Update `AGENTS.md` to include the **C_Lawd Operating Manual** in the startup file sequence.

---

## Current Startup Sequence (from AGENTS.md)

> 1. Read `SOUL.md` — this is who you are
> 2. Read `USER.md` — this is who you're helping
> 3. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context
> 4. **If in MAIN SESSION** (direct chat with your human): Also read `MEMORY.md`

---

## Required Change

Add the Operating Manual to the startup sequence. It should be read **after** SOUL.md and USER.md but **before** diving into work.

### Suggested Addition

Add to the startup sequence:

> 5. Read `workspace/governance/C_LAWD_OPERATING_MANUAL.md` — your operational playbook (reference when uncertain, not every startup)

### Alternative (if file has a different name/location)

If the file was saved elsewhere, search for it first:

```bash
find . -name "*OPERATING_MANUAL*" -o -name "*C_LAWD*" 2>/dev/null
```

---

## Notes

- The manual is a **reference document**, not a constraint to be read every single startup
- The key instruction: "Reference it when uncertain, lost, or when making significant decisions"
- Do NOT read it every time — that wastes context. Just know it's there.

---

## Deliverable

Edit `AGENTS.md` to include the Operating Manual in the startup sequence with appropriate framing (reference, not requirement).
