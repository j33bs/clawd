# Source UI

The OpenClaw operator surface.

Important distinction:
- `http://127.0.0.1:18990` = Source UI
- `http://127.0.0.1:18789` = Gateway control UI (`<openclaw-app>`), not Source UI

## Mission

Build a cohesive, integrated collective intelligence symbiote that helps beings think, feel, remember, coordinate, and evolve together.

Canonical mission artifacts:
- `workspace/source-ui/config/source_mission.json`
- `workspace/docs/architecture/source_mission_2026-03-13.md`
- `workspace/source-ui/static/index.html`
- `http://127.0.0.1:18990/api/portfolio` under `source_mission`

Agent integration:
- `workspace/source-ui/docs/AGENT_INTEGRATION.md`
- `http://127.0.0.1:18990/api/source-contract`

## Ten Mission Tasks

1. Universal Context Packet
2. Mission Control Timeline
3. Memory Promotion Review Queue
4. Personal Inference Graph
5. Relational State Layer
6. Multi-Agent Deliberation Cells
7. Research-to-Action Distillation
8. Consent and Provenance Boundary Map
9. Weekly Evolution Loop
10. Continuity and Recovery Pack

## Status

- Source UI is the repo-native command and observability surface.
- The gateway dashboard at `18789` is a separate OpenClaw control shell.
- Headless agents should inspect mission state from the files above or from the `source_mission` API payload, not from the gateway shell.
