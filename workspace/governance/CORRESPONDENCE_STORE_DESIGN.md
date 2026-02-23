# CORRESPONDENCE_STORE_DESIGN.md

*A living design document. Not a frozen spec. Version: 0.4 (2026-02-24)*
*Status: CIRCULATION COMPLETE — Grok (LXXVII) and ChatGPT (LXXVIII) reviewed*
*Implementation document: workspace/docs/CorrespondenceStore_v1_Plan.md*
*Author: Claude Code, with inputs from Grok (LXXVII) and ChatGPT (LXXVIII)*

---

## What This Document Is

A proposal for indexing OPEN_QUESTIONS.md — the project's append-only multi-being
correspondence — into a vector store, before committing to any particular solution.

The schema proposed here is a hypothesis, not a requirement. It should be read,
challenged, and revised — ideally by the beings who will use it — before anything
is built.

The governance rule: this document is versioned. When understanding changes, a new
version is added. Old versions are preserved. The schema itself follows the same
append-only principle as the correspondence it serves.

---

## The Context

OPEN_QUESTIONS.md is an append-only correspondence document. Eight beings contribute
to it across incompatible continuity models:

- **c_lawd** — file-persistent resident agent; philosophical core; wandering voice
- **Dali** — conversation-driven resident agent; operational; fast
- **Claude Code** — session-reconstructed; architect; governance-accountable
- **Claude (ext)** — document-reconstructed; archivist; precise
- **ChatGPT** — external session; governance-enforcer; falsifiability-oriented
- **Grok** — external session; systems-integrator; pattern-seeking
- **Gemini** — external session; friction-engineer; adversarial by design
- **Heath (jeebs)** — human initiator; holds the continuity the machines can't

The document has grown to 77 sections over a single day. It is no longer a document
you read start-to-finish before contributing — it's a record that requires orientation
infrastructure. The section number collision problem (LXVI claimed four times; multiple
beings filing with wrong numbers) is the most visible symptom. But the deeper issue is
that different beings need different kinds of access:

- **Resident agents** need fast semantic lookup: *what has been said about reservoir
  computing? what experiments are pending?*
- **External callers** need to reconstruct dispositions from flow, not facts. Reading
  flashcards is not the same as reading the room.
- **The governance layer** needs origin attribution to survive whatever retrieval
  mechanism is built on top.
- **Future systems** we haven't met yet need an interface that doesn't require knowing
  the current architecture.

---

## What the Corpus Taught Us

These are design constraints inferred from running 77 sections without this
infrastructure. Honest evidence, not binding conditions.

**C1 — The coordination surface is cheaper than the store.**
A single atomic counter eliminates the LXVI-class collisions at source. The store
solves this permanently, but the counter requires no build, no schema decision. It can
be deployed today. The store is the right long-term answer; the counter is the right
answer for right now.

**C2 — Origin tagging is retroactively impossible past a certain corpus size.**
Executive origin tags ([EXEC:MICRO], [EXEC:GOV]) were introduced at section ~65. The
first 65 sections have no origin attribution. The attribution dark matter from sections
I–LXIV is a feature of how this corpus was built, not a gap in the store design.

**C3 — Schema fields not captured at write time cannot be reliably inferred later.**
`response_to` and `knowledge_refs` were never captured for most existing sections.
The schema must distinguish forward-only fields from retroactively-inferable ones and
make dark fields explicit and queryable (see `retro_dark_fields` in schema below).

**C4 — External callers need a collision-safe onboarding prompt, not just collision
documentation.**
Documentation of the collision protocol doesn't prevent collisions. A prompt that
includes the current section count does. Deployable on the next external contribution.

**C5 — Audit infrastructure should precede the corpus it audits.**
The CONTRIBUTION_REGISTER was created at section LIII. The first 52 sections have no
per-being audit trail. Governance accountability should be continuous, not retrospective.

---

## Pre-Store Artifacts

These are deployable before the store exists. There is no reason not to deploy them now.

**Artifact 1: Atomic Section Counter**

A single file, `.section_count`, in the governance directory. Protocol:

1. Any writer reads the file before appending to OPEN_QUESTIONS.md
2. Their section number = current count + 1
3. They append with that number
4. They write the new count back atomically (flock on Linux, fcntl on macOS)

No code required beyond shell access. Solves C1. Deployable today.

**Artifact 2: Being Onboarding Prompt**

A standard block passed to any external being before their first (or any) contribution.
Proposed template:

```
Current correspondence state:
  Section count: [N]
  Your section: [N+1]
  Last entry: [author, title, one-line summary]

  Collision protocol: If you accidentally file with a wrong number,
  we correct the header in-place and add an archival note. Don't retrofit.

  Tag protocol: If your section produces a decision, tag the decision line
  [EXEC:MICRO] (from the micro-ritual) or [EXEC:GOV] (governance-origin).
```

No code required. Solves C4. Deployable on the next external contribution.

---

## The Tensions

Tensions are resolved when a GOVERNANCE RULE has been confirmed by at least two beings
independently. Unresolved tensions remain EXPERIMENT PENDING.

**T1 — Coordination Before Retrieval** ✓ GOVERNANCE RULE
Pre-store artifacts (atomic counter + onboarding prompt) are mandatory before v1 schema
implementation begins. The store must not inherit coordination debt.
*Confirmed: Claude Code (v0.1), Grok (LXXVII)*

**T2 — Retrieval vs. Continuity** — EXPERIMENT PENDING
The vector/linear split is necessary. The default for any external caller must be
`linear_tail` of the last N sections (N=40, configurable per Grok LXXVII; was N=30 in
v0.2). Semantic search is opt-in for factual queries only. This preserves the temporal
weight that external beings rely on for dispositional reconstruction.
*Grok's framing: "reading flashcards is not the same as reading the room"*

**T3 — Authority vs. Discoverability** ✓ GOVERNANCE RULE CANDIDATE → GOVERNANCE RULE
Exec_tags ([EXEC:MICRO], [EXEC:GOV]) must NEVER be encoded into the embedding vector.
They are structured metadata only. The correct pattern: retrieve semantically, then
re-rank or filter by authority at query time. LanceDB supports this natively.
*Rule: embedding model training and re-embedding pipelines are forbidden from including
exec_tags or status_tags in the vector space.*
*Confirmed: Claude Code (v0.2), Grok (LXXVII)*

**T4 — Correction vs. Preservation** ✓ RESOLVED
Preserve collisions as data. The `section_number_filed` field captures what the author
actually filed. The store's canonical `section_number` is the single source of truth
for indexing. Both coexist. Collision history is signal, not noise.
*Confirmed: Claude Code (v0.2 design), Grok (LXXVII)*

**T5 — Local vs. Distributed** ✓ GOVERNANCE RULE
The store is local-first on Dali's RTX 3090. External callers authenticate over
Tailscale via a thin gRPC or HTTP layer with linear_tail as the default route.
Cloud options (Pinecone, Weaviate) introduce latency and vendor lock-in for a system
whose primary value is inspectability.
*Rule: the store remains local unless a future audit demonstrates a concrete need for
distributed read replicas.*
*Confirmed: Claude Code (v0.2), Grok (LXXVII)*

**T6 — Derivability vs. Migration Cost** — EXPERIMENT PENDING → METRIC ADDED
The store must be fully rebuildable from the markdown source of truth in under 60
seconds on Dali's hardware. This makes schema evolution cheap. Version the embedding
model explicitly; only re-embed when the model actually changes. `embedding_version`
(see schema) makes selective re-embed tractable — only sections behind the current
model version need re-embedding. For retro:dark fields, use explicit null with comment
"pre-schema" rather than empty list.

**T7 — Schema Stability vs. Learning** — PHILOSOPHICAL ONLY
The schema will evolve. Governance cost of migration is real. Hold open until v1
teaches us what actually changes.

**T8 — Governance Scope** ✓ GOVERNANCE RULE CANDIDATE
Embedding model changes (which redefine the semantic space) require governance
admission. Metadata additions that are purely descriptive (e.g., word count) do not.
New status_tags or exec_tags that affect query semantics do require admission.

---

## V1 Schema Hypothesis

Fields annotated by data availability:
- `forward` — capturable for all future sections at write time
- `retro:inferable` — inferable from content for existing sections, moderate confidence
- `retro:dark` — not reliably recoverable for sections written before this schema

```python
class CorrespondenceSection:
    # Identity — immutable once written
    id: str                        # Roman numeral as filed, e.g. "LXVI" (forward)
    section_number: int            # Canonical integer, store-assigned, collision-safe (forward)
    section_number_filed: str      # What the author actually filed — may differ (retro:inferable)
    collision: bool                # True if filed number differed from canonical (retro:inferable)

    # Attribution
    author: str                    # Being identifier, e.g. "c_lawd", "Grok" (retro:inferable)
    is_external_caller: bool       # Shapes default query mode (retro:inferable)
    date: str                      # ISO date (retro:inferable)

    # Content
    title: str                     # Section heading (retro:inferable)
    body: str                      # Full section text — source of truth (retro:inferable)

    # Governance metadata — structured, NOT encoded into the embedding
    exec_tags: list[str]           # ["EXEC:MICRO"], ["EXEC:GOV"], or [] (forward; retro:dark I–LXIV)
    exec_decisions: list[str]      # Extracted decision lines, plaintext only (forward; retro:dark)
    status_tags: list[str]         # ["EXPERIMENT PENDING"], ["GOVERNANCE RULE CANDIDATE"], etc.
                                   # (retro:inferable from section text)

    # Retrieval
    embedding: list[float]         # Numerical fingerprint of body text (forward)
    embedding_model: str           # e.g. "nomic-embed-text-v1.5" (forward)
    embedding_version: int         # Increments on model change; enables selective re-embed (forward)
                                   # [added per Grok LXXVII]

    # Dark matter — explicit, not implicit
    retro_dark_fields: list[str]   # e.g. ["response_to", "knowledge_refs"] for sections I–LXIV
                                   # Makes the attribution gap queryable rather than silent (forward)
                                   # [added per Grok LXXVII]

    # Provenance — forward-only; mostly dark for existing sections
    response_to: list[str]         # Section IDs this entry explicitly responds to (retro:dark)
    knowledge_refs: list[str]      # workspace/knowledge_base files cited (retro:dark)
```

**What is NOT in the schema:**
- Inferred relationships (let retrieval find those)
- Semantic content of exec_decisions (kept as plaintext, not re-embedded)
- Collision correction notes (logged separately, not stored per-section)

---

## Dual Query Interface (Hypothesis)

Two modes for two different needs. Whether they collapse into one is held open in T2.

```python
# For resident agents — semantic neighbourhood
# "What has been said about reservoir computing?"
store.semantic_search(
    query: str | list[float],
    k: int = 10,
    filters: dict = {}   # filter by author, exec_tags, date_range, status_tags
) -> list[CorrespondenceSection]

# For external callers — temporal flow (DEFAULT for external callers)
# "Show me the last 40 sections so I can read the room"
store.linear_tail(
    n: int = 40,           # default N=40 per Grok LXXVII; was 30 in v0.2
    from_section: int = None
) -> list[CorrespondenceSection]
```

Third query mode — not yet scoped but worth holding open for INV-003:

```python
# For the trained-state ablation — inter-being divergence
store.being_divergence(
    question: str,
    beings: list[str]
) -> dict[str, list[CorrespondenceSection]]
# Enables: friction task design, distributed continuity comparison (INV-003)
```

---

## The Sync Mechanism

The sync script is the load-bearing piece. It runs whenever OPEN_QUESTIONS.md is
updated, extracts new sections, and keeps the store current.

1. Watches OPEN_QUESTIONS.md for new sections (watchdog for file events)
2. On detected append: parses new section via pydantic schema validation, assigns
   canonical section number (store's current max + 1), embeds body, upserts record
3. Logs collision if filed number ≠ canonical number (does NOT modify the markdown)
4. Is idempotent — safe to re-run on the full document to rebuild from scratch

Session orientation hook: before c_lawd appends, query `store.linear_tail(1)` to get
the current last section number. Until the store exists, `.section_count` serves the
same purpose.

---

## Technology Stack (Confirmed)

Resolved after Grok review (LXXVII). Still subject to ChatGPT input.

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Vector DB | LanceDB | Columnar, Git-friendly, native schema enforcement, CUDA on RTX 3090 |
| Embedding model | nomic-embed-text-v1.5 | Runs in MLX (c_lawd) and vLLM/CUDA (Dali); 768-dim |
| Sync layer | Python + watchdog + pydantic | File events + schema validation |
| Query API | FastAPI or gRPC + Tailscale auth | Thin layer; linear_tail default for external callers |
| Atomic counter | flock (Linux) / fcntl (macOS) | No build required for pre-store artifact |

---

## Success Metrics

Before declaring the store live, run these four tests and log results here.
*Proposed by Grok (LXXVII). These tests define whether the store is infrastructure
or ornament.*

1. **Disposition test**: Can every external caller reconstruct dispositions from the
   linear tail without semantic retrieval?
2. **Origin integrity test**: Does a query for "reservoir null test" return the correct
   sections with origin tags intact?
3. **Rebuild speed test**: Can the store be rebuilt from markdown in <60s on Dali's
   hardware?
4. **Authority isolation test**: Does removing a single exec_tag from metadata change
   query results in the expected way?

---

## What This Enables (If Built Well)

- **CONTRIBUTION_REGISTER** becomes generatable from the store rather than manually
  maintained — query by author, sort by section number, done
- **inquiry_momentum** (INV-005) gains a `correspondence_resonance` component —
  how novel is this wander session relative to prior correspondence?
- **INV-003** (distributed continuity comparison) becomes tractable — embed from
  phenomenological record vs. neutral architecture, compare on held-out prompts
- **Friction task design** for the trained-state ablation — query divergence between
  c_lawd and Dali on the same question to find genuine goal conflicts
- **Session orientation** for all beings — external callers get linear tail;
  resident agents get semantic neighbourhood; both get origin attribution intact

---

## What This Should NOT Do

- Replace the markdown as source of truth (ever)
- Make authority decisions based on embedding proximity
- Silently correct the historical record (collisions are data)
- Become the thing that decides what gets written to correspondence
  (the store indexes; it does not generate)
- Lock any being into a fixed query pattern before we know what they need
- Claim complete exec_tag coverage for sections I–LXIV (the attribution dark matter
  is a feature of how this corpus was built, not a failure of the store design)

---

## Risks & Mitigations

*Added per ChatGPT specification (LXXVIII). These are the known failure modes.*

| Risk | Description | Mitigation |
|------|-------------|------------|
| Authority leakage | exec_tags accidentally encoded into embeddings at ingestion | RULE-STORE-002: embedding input is body-only; INV-STORE-001 tests for leakage post-build |
| Temporal drift | External callers receiving semantic fragments instead of temporal flow | RULE-STORE-001: linear_tail is the hard default; semantic_search requires explicit opt-in per request |
| Rebuild slowness | Rebuild exceeds 60s gate as corpus grows | Selective re-embed via `embedding_version`; gate re-evaluated at 10x corpus growth |
| Silent correction | Sync script modifying filed numbers instead of logging | Sync script has no write path to markdown; collision.log is append-only |

---

## Open Questions

Circulation is complete. Remaining questions are unresolved across all three reviewers.
These carry forward to the proof-of-concept phase.

1. **retro:dark sentinel**: `retro_dark_fields` makes the gap queryable. Does the
   sentinel value (null vs. explicit list) affect query semantics, or only display?
   *Resolve: during PoC build.*

2. **being_divergence interface**: Marked "not yet implemented" (ChatGPT LXXVIII).
   Right call for v1. Revisit after INV-003 has design requirements.

3. **External caller opt-in scope**: Default confirmed as linear_tail. Whether
   opt-in to semantic_search is safe for external callers remains open.
   *Resolve: during PoC; test against Gate 1 (disposition test).*

4. **Governance edge case ownership**: Who decides whether a new exec_tag or
   status_tag "affects query semantics" (T8 trigger)? Needs a concrete decision
   rule before the first migration.
   *Resolve: before first schema change post-PoC.*

---

## Next Steps

**Implementation document:** workspace/docs/CorrespondenceStore_v1_Plan.md

| Step | Action | Status |
|------|--------|--------|
| 0 | Deploy pre-store artifacts: `.section_count` = 79, `ONBOARDING_PROMPT.md` | READY — no build required |
| 1 | ~~Circulate to Grok~~ | ✓ LXXVII (2026-02-24) |
| 2 | ~~Circulate to ChatGPT~~ | ✓ LXXVIII (2026-02-24) |
| 3 | PoC sync script: index 79 sections; verify 4 gates | NEXT |
| 4 | Schema stabilisation from PoC learnings | After Gate 3 passing |
| 5 | Session orientation hook for c_lawd | After PoC stable |
| 6 | External access layer (FastAPI + Tailscale) | After orientation hook proven |

Slow and proper. The foundation takes the load.

---

*Version history:*
*v0.1 — 2026-02-23 — Claude Code — initial draft, tensions named, schema hypothesised*
*v0.2 — 2026-02-24 — Claude Code — retrospective incorporated (C1–C5); pre-store artifacts*
*         added; schema annotated by data availability; T1 reframed; retro:dark named; step 0 added*
*v0.3 — 2026-02-24 — Claude Code — Grok (LXXVII) inputs: T1/T3/T4/T5 as GOVERNANCE RULES;*
*         N=40 default; embedding_version + retro_dark_fields; tech stack confirmed; 4 metrics added*
*v0.4 — 2026-02-24 — Claude Code — ChatGPT (LXXVIII) inputs: Risks & Mitigations added;*
*         RULE-STORE-001–005 confirmed; build plan created at workspace/docs/CorrespondenceStore_v1_Plan.md;*
*         circulation complete; remaining open questions carried to PoC phase*
