# OpenClaw 100 Enhancements

Purpose: Curated list of 100 targeted enhancements for OpenClaw. Each item includes id, title, priority, tranche, dependencies, acceptance criteria, and notes.

Format per item:
- id: OC-001
- title: Short title
- priority: P0|P1|P2
- tranche: 1|2|3
- depends_on: [OC-xxx,...]
- acceptance: short acceptance criteria
- notes: optional implementation notes

## Current Entries (seed)

- id: OC-001
  - title: Telegram reasoning leak fix
  - priority: P0
  - tranche: 1
  - depends_on: []
  - acceptance: Deterministic unit test reproduces leak; test passes after fix
  - notes: Sanitize reply/quote render path when reasoningLevel == "off"
  - status: implemented
  - evidence:
    - `53a2818` fix(telegram): sanitize outbound replies; block reasoning leak; fallback on empty/stripped
    - `40a1668` test(telegram): cover reasoning-strip and empty/stripped fallback
    - `18a8e71` fix(outbound): centralize sanitizer and empty fallback primitives
    - `0bd80fe` fix(telegram): default no reply threading and wire global outbound choke point
    - `b43e5e1` test(outbound,telegram): cover sanitizer fallback and reply mode payload rules

- id: OC-002
  - title: Governance hardening (.gitignore artifacts)
  - priority: P1
  - tranche: 1
  - depends_on: []
  - acceptance: Generated artifacts ignored; repo clean after CI runs
  - notes: Only ignore generated artifacts, not source/state files
  - status: implemented
  - evidence:
    - `.gitignore` contains artifact/runtime/scratch ignores with targeted exceptions (e.g. governed witness logs)
    - working tree currently clean after hardening verification runs

## Next

- Populate remaining OC-003..OC-100 entries in this file, then implement tranche-by-tranche.
