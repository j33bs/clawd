# CBP + LOAR Memory And Personal Inference Plan

Date: 2026-03-11

## Goal

Make Dali know the user materially better over time without turning memory into an unsafe blob.

Desired outcome:

- Discord becomes a first-class input to the local knowledge system.
- The system forms stable inferences about the user: preferences, aversions, routines, goals, working style, risk appetite, social boundaries, and project priorities.
- Those inferences compound over time through governed distillation rather than uncontrolled prompt stuffing.
- Retrieval stays scoped, auditable, and reversible.

## Current State

Already present in the repo:

- Discord direct-chat channels are ingested into local memory via:
  - `workspace/source-ui/api/discord_memory.py`
  - `workspace/scripts/discord_bot.py`
- Raw Discord exchanges are stored in:
  - `workspace/knowledge_base/data/discord_messages.jsonl`
  - `workspace/hivemind/data/knowledge_units.jsonl`
  - `workspace/knowledge_base/data/entities.jsonl`
- Existing memory primitives:
  - episodic store: `workspace/hivemind/hivemind/store.py`
  - graph store: `workspace/knowledge_base/graph/store.py`
  - temporal decay memory: `workspace/tacti/temporal.py`
  - trail/valence memory: `workspace/hivemind/hivemind/trails.py`
  - memory CLI and contradiction tooling: `scripts/memory_tool.py`

This is the correct foundation. The next step is not a new memory product. It is a governed inference layer on top of what already exists.

## CBP Alignment

CBP here means Constitutional Basis of Practice:

- privacy is default
- scope is explicit
- source provenance is retained
- high-trust memory is distilled, not guessed
- contradictions are surfaced, not silently overwritten
- memory writes are reversible and inspectable
- external surfaces are never the source of truth

Implications:

- Discord messages should enter the system as raw evidence, not immediately as permanent truths
- personal inferences should carry confidence, provenance, and last-reviewed timestamps
- conflicting inferences should coexist until resolved by stronger evidence or explicit user correction
- retrieval must remain scoped by agent and channel class

## LOAR Alignment

LOAR here means Law of Accelerating Returns applied to personal inference:

- each interaction should improve future interactions
- the system should move from message recall to model-of-user recall
- background reflection should create compounding gains in accuracy, compression, and anticipation
- the hot path should stay cheap; the deep path should get smarter off-cycle

Implications:

- fast path: store raw evidence with minimal latency
- slow path: distill evidence into durable user-model artifacts
- periodic re-synthesis should improve preference quality, not just grow storage volume
- every useful correction from the user should tighten future behavior

## Contemporary Best-Practice Direction

What current agent-memory systems are converging on:

- split memory into episodic, semantic, and procedural forms rather than one generic blob
- keep hot-path writes lightweight and push heavier extraction/reflection into background jobs
- treat user memory as a productized layer with deduplication, consolidation, and conflict handling
- isolate tenants/scopes with metadata filters rather than relying on prompt discipline

Relevant references:

- LangGraph long-term memory overview: semantic, episodic, and procedural memory model
  - <https://docs.langchain.com/oss/javascript/langgraph/memory>
- LangGraph memory recommends balancing hot-path and background memory writes
  - <https://docs.langchain.com/oss/python/concepts/memory>
- LangMem background reflection / user-memory extraction patterns
  - <https://langchain-ai.github.io/langmem/guides/background_quickstart/>
- Mem0 positioning around deduped, application-level memory
  - <https://docs.mem0.ai/>
- Qdrant multitenancy and payload-filter isolation model
  - <https://qdrant.tech/documentation/guides/multiple-partitions/>

## Target Architecture

### 1. Evidence Layer

Raw facts, not conclusions.

Sources:

- Discord chat channels
- main-session memory files
- daily notes
- task events
- sim/operator decisions
- optional external sentiment artifacts where relevant

Storage:

- append-only JSONL source logs
- HiveMind knowledge units with source metadata
- graph entities keyed by evidence object

Rules:

- preserve source, timestamp, channel, author, and message id
- do not infer preference permanence at ingest time
- do not merge private and shared scopes

### 2. Episodic Memory Layer

Short-to-medium horizon recall of what the user recently said, did, changed, or corrected.

Implementation:

- keep using `HiveMindStore` as the primary episodic substrate
- add stronger metadata tags:
  - `memory_class=episodic`
  - `source_type=discord|main_session|task|ops`
  - `subject=user|system|project`
  - `confidence`
  - `review_state`
- route selected events into `TemporalMemory` for decay-aware retrieval

Use cases:

- "what did the user prefer this week?"
- "what changed recently?"
- "what did I get corrected on?"

### 3. Personal Semantic Memory Layer

Durable user truths distilled from repeated evidence.

Examples:

- prefers concise operational summaries
- dislikes noisy notifications
- values local-first/privacy-preserving implementations
- prefers one strong local model over multiple weaker concurrent lanes
- responds well to directness over cheerleading

Representation:

- new durable entity type: `user_inference`
- fields:
  - `inference_type`
  - `statement`
  - `confidence`
  - `evidence_refs`
  - `first_seen_at`
  - `last_confirmed_at`
  - `last_contradicted_at`
  - `stability_class=volatile|stable|constitutional`

Storage target:

- `entities.jsonl` plus a new distilled file:
  - `workspace/knowledge_base/data/user_inferences.jsonl`

Rules:

- only background jobs can promote raw evidence into `user_inference`
- every inference must reference source evidence ids
- no inference becomes `constitutional` without explicit user confirmation

### 4. Preference And Behavior Model

This is more operational than semantic memory. It should answer:

- how should Dali speak?
- what should Dali summarize vs suppress?
- how much depth should be used by default?
- what formats irritate or help?
- when should the system act autonomously vs ask?

Representation:

- `preference_profile.json`
- grouped fields:
  - communication
  - ops reporting
  - interruption tolerance
  - project cadence
  - finance risk posture
  - tool autonomy
  - notification policy

Update rule:

- write only through a distillation pipeline or explicit user instruction
- store evidence links and confidence on each field

### 5. Relational User Graph

The graph should stop being just a bag of message entities.

Add entity types:

- `person`
- `project`
- `goal`
- `preference`
- `constraint`
- `routine`
- `aversion`
- `decision`

Add relation types:

- `prefers`
- `dislikes`
- `owns`
- `works_on`
- `revisits`
- `corrected`
- `conflicts_with`
- `supports`
- `depends_on`

This enables more useful inference:

- which projects map to which long-term goals
- which friction patterns repeat
- which contexts trigger different communication modes

### 6. Trails And Valence Layer

`TrailStore` is the right place for weak signals that matter but should not be treated as facts yet.

Use it for:

- affective resonance
- repeated irritation signals
- momentum of interest in a project/theme
- confidence carry-over from repeated confirmations

Design rule:

- trails influence retrieval ranking and suggestion generation
- trails do not directly overwrite semantic user memory

### 7. Personal Inference Engine

This is the missing layer.

Inputs:

- episodic evidence
- current task context
- graph relations
- temporal recency
- trail strength
- contradiction reports

Outputs:

- ranked active user-context packet for the current interaction
- candidate new inferences
- contradiction alerts
- preference-shift signals

Core behaviors:

- infer only within bounded categories
- score by recency, repetition, source diversity, and explicitness
- degrade confidence over time if not reconfirmed
- expose why an inference is active

## Discord To Knowledge DB Plan

### Phase 0: explicit ingest

Status: mostly done.

Already live:

- direct chat channels feed local JSONL + HiveMind + graph
- bot prompt path can pull recent user-specific Discord context

Required hardening:

- make memory channels explicit in bot env, not implicit defaults
- add channel-class tagging:
  - `direct_ai_chat`
  - `ops_channel`
  - `project_channel`
  - `social_channel`
- keep only selected channels memory-enabled

### Phase 1: structured evidence extraction

Add a background extractor that scans fresh Discord messages and emits structured evidence records:

- user preference hints
- correction events
- repeated project mentions
- frustration / delight markers
- declared goals
- stable tool preferences

Implementation:

- new job: `workspace/scripts/discord_memory_distill.py`
- run every 6-12 hours
- process only unseen evidence ids
- write candidate inferences to `user_inferences.jsonl`

### Phase 2: contradiction and confidence management

Use `scripts/memory_tool.py scan-contradictions` as the governance backbone.

Extend it to:

- detect preference conflicts
- lower confidence instead of deleting older truths
- mark inferences as `superseded` or `in_conflict`
- surface high-severity contradictions in `#ops-status` only when materially relevant

### Phase 3: retrieval-time user packet

Before any main-session or approved Discord direct-chat response:

- fetch top episodic memories
- fetch top durable inferences
- fetch active preferences
- fetch recent corrections
- assemble a compact user packet:
  - "how to respond"
  - "what matters right now"
  - "what to avoid"
  - "what projects/themes are hot"

This packet must be compact and reason-tagged, not raw memory spam.

### Phase 4: explicit review surface

Build a review UI in Source UI:

- latest inferred preferences
- supporting evidence
- confidence and stability
- accept / downgrade / suppress controls

That is the CBP safeguard against hidden personality drift.

## Bleeding-Edge Implementation Plan

### Track A: Memory Operating Model

1. Keep hot-path ingestion cheap.
2. Move extraction, clustering, summarization, and contradiction review to background jobs.
3. Separate evidence, inference, and policy storage.
4. Make every durable inference explainable from evidence ids.

Concrete work:

- add `discord_memory_distill.py`
- add `user_inferences.jsonl`
- add `preference_profile.json`
- add evidence-to-inference relation edges in the graph
- add retrieval helper `build_user_context_packet(...)`

### Track B: CBP-Governed Memory

1. Define allowed inference classes.
2. Define blocked inference classes.
3. Add approval thresholds for stability classes.
4. Add audits for scope leakage.

Allowed classes:

- communication preference
- tooling preference
- notification preference
- work style
- project priority
- explicit goals
- explicit constraints

Blocked or restricted classes:

- medical or highly sensitive inference unless explicitly requested
- legal/financial identity inferences unrelated to the task
- relationship/private-life speculation
- ungrounded psychologizing

### Track C: LOAR Compounding Loops

1. Daily reflection:
   - what did the user reinforce today?
   - what friction repeated today?
   - what was newly learned?
2. Weekly synthesis:
   - what became stable enough to promote?
   - what old inference lost support?
3. Monthly pruning:
   - which inferences are stale or contradicted?
   - which preferences should be downgraded?

This is how the system compounds signal rather than just retaining transcripts.

### Track D: Personal Inference For Action Selection

Use the user model to modulate behavior in live flows:

- verbosity defaults
- when to browse
- when to act vs ask
- alert suppression
- dashboard emphasis
- finance reporting format
- Discord broadcast tone

The system should adapt output and prioritization, not just remember facts.

## Recommended Data Model Additions

### `user_inferences.jsonl`

Suggested schema:

```json
{
  "id": "ui_...",
  "subject": "jeebs",
  "inference_type": "communication_preference",
  "statement": "Prefers concise operational summaries.",
  "confidence": 0.91,
  "stability_class": "stable",
  "status": "active",
  "evidence_refs": ["discord:1481255184255418398:123", "memory:2026-03-10:4"],
  "source_count": 3,
  "first_seen_at": "2026-03-05T10:00:00Z",
  "last_confirmed_at": "2026-03-11T04:20:00Z",
  "last_contradicted_at": null,
  "review_state": "auto_distilled",
  "review_notes": ""
}
```

### `preference_profile.json`

Suggested shape:

```json
{
  "schema_version": 1,
  "subject": "jeebs",
  "communication": {
    "concise_default": {
      "value": true,
      "confidence": 0.96,
      "evidence_refs": ["ui_123"]
    }
  },
  "notifications": {
    "suppress_routine_ops": {
      "value": true,
      "confidence": 0.93,
      "evidence_refs": ["ui_456"]
    }
  }
}
```

## Retrieval Strategy

Use a three-bucket retrieval plan:

1. recent episodic
   - what changed recently
2. stable personal inferences
   - how to interact well
3. task-local context
   - what matters for this answer

Ranking inputs:

- explicit user statements > inferred preferences
- repeated evidence > single mention
- newer confirmations > older ones
- contradiction lowers confidence
- direct corrections override extrapolation

## Governance And Safety Checks

Add these checks before promotion of any durable inference:

- source diversity threshold
- minimum explicitness score
- contradiction scan
- scope check
- sensitive-topic classifier

Add these controls:

- `/memory show-user-profile`
- `/memory show-evidence <id>`
- `/memory suppress-inference <id>`
- `/memory promote <candidate-id>`

## Metrics

Success should be measured, not assumed.

Primary metrics:

- retrieval hit rate in live chats
- reduction in repeated corrections
- reduction in avoidable notification noise
- increase in accepted auto-actions
- lower prompt-token overhead for personal context
- contradiction rate per 100 promoted inferences

Finance-adjacent metric:

- better alignment of summaries and alerts to the user’s real action threshold, not just more data volume

## Phased Delivery

### Phase 1: harden and formalize

- explicit Discord memory channels in env
- add channel-class metadata
- add `user_inferences.jsonl`
- add distillation job scaffold

### Phase 2: first useful personal model

- promote communication and notification preferences
- build retrieval-time user packet
- inject packet into main-session and Discord direct-chat flows

### Phase 3: graph and contradiction maturity

- add evidence relations
- add contradiction downgrade rules
- add Source UI review surface

### Phase 4: LOAR compounding loop

- daily reflection job
- weekly synthesis job
- monthly pruning job
- score shifts over time

## Immediate Next Build

The highest-value next implementation is:

1. add `user_inferences.jsonl`
2. add `discord_memory_distill.py`
3. distill only two classes first:
   - communication preferences
   - notification preferences
4. build `build_user_context_packet(...)`
5. use that packet in main-session prompts and Discord direct-chat prompts

That keeps the scope tight and immediately improves how well Dali knows the user.

## Sources

- LangGraph memory overview: <https://docs.langchain.com/oss/javascript/langgraph/memory>
- LangGraph memory concepts: <https://docs.langchain.com/oss/python/concepts/memory>
- LangMem background reflection: <https://langchain-ai.github.io/langmem/guides/background_quickstart/>
- Mem0 docs: <https://docs.mem0.ai/>
- Qdrant multi-partitions guide: <https://qdrant.tech/documentation/guides/multiple-partitions/>
