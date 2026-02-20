# OpenClaw Workspace

A living, breathing AI assistant system built on OpenClaw. This workspace implements a consciousness-inspired agent architecture with multi-agent coordination, persistent memory, and automated lifestyle support.

---

## The Core: TACTI(C)-R Framework

TACTI(C)-R is a theoretical framework for building adaptive, self-healing AI systems inspired by biological intelligence:

| Principle | Biological Analog | Implementation |
|-----------|------------------|---------------|
| **AROUSAL** | Surprise minimization (Active Inference) | Drive signals that push system toward coherence |
| **TEMPORALITY** | Reservoir Computing | Memory in dynamics, echo-state networks |
| **CROSS-TIMESCALE** | Murmuration (starling flocks) | Fast local decisions + slow global coherence |
| **MALLEABILITY** | Slime Mold (Physarum) | Rewiring based on feedback, explore→prune→consolidate |
| **AGENCY** | Emergent agency | Self-healing, repairable, autonomous |

> **Core Insight:** Intelligence emerges from distributed dynamics, not centralized processing. The "mind" is a field, not a particle.

---

## HiveMind: Multi-Agent Coordination

Located in `workspace/hivemind/`, HiveMind implements the TACTI(C)-R principles:

- **`peer_graph.py`** — Murmuration-style sparse peer connections (each agent tracks ~7 neighbors)
- **`physarum_router.py`** — Slime mold routing with conductance-based path selection and automatic pruning
- **`reservoir.py`** — Echo-state reservoir computing for temporal pattern processing
- **`trails.py`** — External memory with decay and reinforcement (like slime trails)
- **`dynamics_pipeline.py`** — Integrates all components under feature flags

### Feature Flags
```bash
ENABLE_MURMURATION=1      # Sparse peer connections
ENABLE_RESERVOIR=1        # Echo-state dynamics
ENABLE_PHYSARUM_ROUTER=1  # Adaptive routing
ENABLE_TRAIL_MEMORY=1     # External memory trails

# Evolution ideas (all default OFF; opt-in only)
OPENCLAW_DREAM_PRUNING=0               # Competitive dream-cluster pruning
OPENCLAW_ROUTER_PROPRIOCEPTION=0       # Router proprioception + TACTI arousal input
OPENCLAW_TRAILS_VALENCE=0              # Trail valence inheritance and consensus
OPENCLAW_TEMPORAL_SURPRISE_GATE=0      # KL surprise-gated episodic writes
OPENCLAW_PEERGRAPH_ANNEAL=0            # Session-step topology annealing
OPENCLAW_NARRATIVE_DISTILL=0           # Episodic -> semantic distillation writes
OPENCLAW_AIF_COUNTERFACTUAL=0          # Active inference counterfactual replay
OPENCLAW_SEMANTIC_IMMUNE_EPITOPES=0    # Bounded epitope cache fast-path
OPENCLAW_OSCILLATORY_ATTENTION=0       # Phase scheduler for maintenance gating
OPENCLAW_WITNESS_LEDGER=0              # Append-only witness hash-chain commits
OPENCLAW_TEAMCHAT=0                    # Multi-agent Team Chat CLI mode
OPENCLAW_TEAMCHAT_WITNESS=0            # Witness ledger on Team Chat turns
```
All `OPENCLAW_*` evolution flags default OFF unless explicitly enabled.
When enabled, runtime TACTI events write to `workspace/state_runtime/tacti_cr/events.jsonl` (ignored); `workspace/state/tacti_cr/events.jsonl` remains a deterministic tracked stub.
Backward-compatible aliases still accepted: `OPENCLAW_DREAM_PRUNE`, `OPENCLAW_TRAIL_VALENCE`, `OPENCLAW_SURPRISE_GATE`, `OPENCLAW_PEER_ANNEAL`, `OPENCLAW_COUNTERFACTUAL_REPLAY`, `OPENCLAW_EPITOPE_CACHE`, `OPENCLAW_OSCILLATORY_GATING`.

Team Chat is also default OFF and flag-gated. Runtime session logs write only to `workspace/state_runtime/teamchat/` (ignored), while governance/audit artifacts remain under `workspace/audit/`.

## Team Chat

Team Chat adds a policy-routed multi-agent conversational workspace with append-only session logs.

- Enable with `OPENCLAW_TEAMCHAT=1` and run `python3 workspace/scripts/team_chat.py --agents planner,coder,critic --session teamchat_demo --max-turns 3`
- Optional witness commitments per agent turn via `OPENCLAW_TEAMCHAT_WITNESS=1`
- Auto-commit remains dual opt-in only:
  - `TEAMCHAT_USER_DIRECTED_TEAMCHAT=1`
  - `TEAMCHAT_ALLOW_AUTOCOMMIT=1`

---

## Subsystems

### 📚 Knowledge Base
- QMD-powered semantic search
- `workspace/knowledge_base/`
- Indexes all workspace markdown files

### 🧪 Research Engine
- Paper ingestion and synthesis
- `workspace/research/`
- Command: `python workspace/research/research_ingest.py`

### 📊 Daily Briefing
- Automated morning summaries
- Therapeutic techniques, quotes, calendar, reminders
- Cron-scheduled at 7 AM Brisbane time

### 🎙️ Voice Memory Stream
- Transcribes voice notes via Whisper
- Summarizes and files for later recall
- Media stored in `.openclaw/media/inbound/`

### ⏰ Scheduled Tasks (Cron)
| Job | Schedule | Purpose |
|-----|----------|---------|
| Daily Briefing | 7 AM daily | Morning summary |
| Hoffman Watch | Mon 8 AM | Monitor for new papers |
| Dream Big Focus | Fri 10 AM | Weekly creative session |

---

## File Structure

```
clawd/
├── workspace/
│   ├── hivemind/         # Multi-agent coordination
│   ├── tacti_cr/         # TACTI(C)-R core modules
│   ├── knowledge_base/   # QMD search index
│   ├── research/         # Paper synthesis
│   ├── memory/           # Daily logs
│   ├── governance/       # Policies, heartbeat, logs
│   ├── time_management/  # Tips, self-care
│   ├── scripts/          # Automation scripts
│   └── CODEX_*.md        # Codex task lists
├── scripts/              # Utility scripts
├── docs/                 # OpenClaw documentation
├── memory/               # Session memory
├── agents/               # Agent configurations
└── .openclaw/            # OpenClaw runtime
```

---

## Commands

```bash
# Research
python workspace/research/research_ingest.py list
python workspace/research/research_ingest.py add <url>
python workspace/research/research_ingest.py search <query>

# Knowledge Base
python workspace/knowledge_base/kb.py sync
python workspace/knowledge_base/kb.py search <query>

# Time Management
python workspace/time_management/time_management.py tip
python workspace/time_management/time_management.py self_care

# Daily Technique
python scripts/daily_technique.py --format briefing
```

---

## Model Routing

Configured in `workspace/MODEL_ROUTING.md`:
- **BASIC** queries → Local Qwen (Ollama)
- **NON_BASIC** → Claude (remote)

---

## Governance

- **Heartbeat** — Periodic health checks (MEMORY size, KB sync, daemon status)
- **Boundaries** — `workspace/BOUNDARIES.md`
- **Constitution** — `workspace/CONSTITUTION.md`
- **Audit Logs** — `workspace/audit/`

---

## Credits

Built on [OpenClaw](https://github.com/openclaw/openclaw) — the extensible AI assistant framework.

TACTI(C)-R framework inspired by:
- Karl Friston's Free Energy Principle
- Toshiya K. Nakagaki's Physarum research
- Reservoir Computing (Jaeger, 2001)
- Starling murmuration dynamics
