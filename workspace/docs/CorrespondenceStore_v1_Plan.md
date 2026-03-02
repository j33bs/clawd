# CorrespondenceStore v1 — Build Plan

*workspace/docs/CorrespondenceStore_v1_Plan.md*
*Version: 1.0 | Date: 2026-02-24 | Status: APPROVED FOR BUILD (pending Step 0)*
*Governance source: OPEN_QUESTIONS.md I–LXXIX; CORRESPONDENCE_STORE_DESIGN.md v0.3*
*Specified by: ChatGPT (LXXVIII); executed by: Claude Code (LXXIX)*

---

## Goals

Build a queryable index over OPEN_QUESTIONS.md that:

- Lets resident agents (c_lawd, Dali) run fast semantic lookup over the corpus
- Gives external callers a temporal-flow default (linear tail, last N=40 sections)
- Preserves exec_tags and status_tags as structured authority metadata — never embedded
- Assigns canonical section numbers atomically (solves the LXVI-class collision problem)
- Remains fully rebuildable from the markdown source of truth in under 60 seconds
- Runs locally on Dali's hardware with no cloud dependency

## Non-Goals

- The store does **not** modify the markdown (ever — hard invariant)
- The store does **not** make authority decisions (exec_tags are metadata; authority is procedural)
- The store does **not** silently correct collisions (they are preserved as data)
- The store does **not** replace the CONTRIBUTION_REGISTER (it generates inputs for it)
- The store does **not** implement `being_divergence()` in v1 (placeholder only — see Query Modes)
- The store does **not** run in the cloud without explicit governance admission

---

## Pre-Build Gates (Step 0 — Must Complete Before Schema Implementation)

T1 GOVERNANCE RULE: pre-store artifacts are mandatory before v1 schema implementation begins.

1. **`.section_count` file** — `workspace/governance/.section_count`
   - Current value on creation: 79
   - Atomic read/write via `flock` (Linux) or `fcntl` (macOS)
   - Any writer reads before appending; increments after writing section

2. **`ONBOARDING_PROMPT.md`** — `workspace/governance/ONBOARDING_PROMPT.md`
   - Standard block passed to external beings before any contribution
   - Includes: current section count, collision protocol, exec_tag protocol
   - See CORRESPONDENCE_STORE_DESIGN.md v0.3 for template

---

## Schema v1

Required fields. exec_tags and status_tags are metadata — excluded from vectors at all times.

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class CorrespondenceSection:
    # Identity
    canonical_section_number: int       # Store-assigned; atomic increment; collision-safe
    section_number_filed: str           # What the author wrote (Roman numeral string)
    collision: bool                     # True if filed ≠ canonical

    # Attribution
    authors: list[str]                  # Being identifier(s) e.g. ["c_lawd"], ["Grok"]
    created_at: str                     # ISO date e.g. "2026-02-24"
    is_external_caller: bool            # Determines default query mode on retrieval

    # Content
    title: str                          # Section heading
    body: str                           # Full section text — source of truth

    # Governance metadata — structured; NEVER encoded into vectors
    exec_tags: list[str]                # ["EXEC:MICRO"], ["EXEC:GOV"], or []
    status_tags: list[str]              # ["EXPERIMENT PENDING"], ["GOVERNANCE RULE CANDIDATE"], etc.

    # Retrieval
    embedding: list[float]              # nomic-embed-text-v1.5 vector of body only
    embedding_model_version: str        # e.g. "nomic-embed-text-v1.5-2026-02"
    embedding_version: int              # Increments on model change; enables selective re-embed

    # Dark matter — explicit, not silent null
    retro_dark_fields: list[str]        # Fields unrecoverable for this section
                                        # e.g. ["response_to", "knowledge_refs"] for sections I–LXIV
                                        # [] = all fields captured; null = not applicable

    # Provenance — forward-only; dark for most existing sections
    response_to: Optional[list[str]]    # Section IDs this entry responds to; null = retro:dark
    knowledge_refs: Optional[list[str]] # workspace files cited; null = retro:dark
```

**What is NOT in the schema:**
- Inferred relationships (let retrieval find those)
- Semantic content of exec_decisions (kept as plaintext in body, not re-embedded separately)
- Collision correction notes (in collision.log, not per-section)

---

## Query Modes

```python
# Mode 1: For external callers — temporal flow
# DEFAULT for all external callers; not opt-out
store.linear_tail(
    n: int = 40,            # default 40; configurable; RULE-STORE-001
    from_section: int = None
) -> list[CorrespondenceSection]

# Mode 2: For resident agents — semantic neighbourhood
# OPT-IN only; external callers must explicitly request
# exec_tags and status_tags filters applied AFTER embedding retrieval — never as query vectors
store.semantic_search(
    query: str | list[float],
    k: int = 10,
    filters: dict = {}      # supports: authors, exec_tags, status_tags, date_range, is_external_caller
) -> list[CorrespondenceSection]

# Mode 3: NOT YET IMPLEMENTED
# Placeholder for future work — do not build in v1
# store.being_divergence(question: str, beings: list[str]) -> dict[str, list[CorrespondenceSection]]
# Enables: friction task design (INV-005), distributed continuity comparison (INV-003)
```

**Filtering invariant:** exec_tags and status_tags filters are applied as metadata predicates on
the result set AFTER embedding retrieval. They are NEVER used as query vectors or similarity
signals. Violation = authority leakage (see Risks).

---

## Sync / Ingestion

The sync script is the load-bearing piece. Single responsibility: keep the store current
with the markdown. Never writes to the markdown.

```
sync_pipeline:
  trigger: watchdog file event on OPEN_QUESTIONS.md (append detected)

  for each new section detected:
    1. Parse section with pydantic CorrespondenceSection validator
    2. Assign canonical_section_number = store.max() + 1
    3. If canonical ≠ section_number_filed:
         append to collision.log (append-only)
         proceed — do NOT modify markdown
    4. Embed body with nomic-embed-text-v1.5
       (body only — exec_tags and status_tags excluded from embedding input)
    5. Upsert CorrespondenceSection to LanceDB
    6. Write canonical_section_number to .section_count (atomic, flock/fcntl)

  idempotency guarantee:
    - full rebuild from markdown is always valid
    - parse all sections in order of appearance; assign canonical numbers sequentially
    - re-embed only if embedding_model_version has changed (compare via embedding_version)
    - collision.log is append-only; never corrected
```

---

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Vector DB | LanceDB | Columnar, local, Git-friendly, schema-enforced, CUDA on RTX 3090 |
| Embedding model | nomic-embed-text-v1.5 | MLX on Apple silicon (c_lawd); vLLM/CUDA on Dali; 768-dim vectors |
| Schema validation | pydantic | Validates before any write; enforces field types and invariants |
| File events | watchdog | Python; cross-platform; lightweight |
| Query API | FastAPI + Tailscale auth | Minimal; default route always calls `linear_tail` |
| Atomic counter | flock (Linux) / fcntl (macOS) | Pre-store artifact; also used by sync script |
| Collision log | append-only text | `workspace/governance/collision.log` |

*Confirmed by: Grok (LXXVII), ChatGPT (LXXVIII)*

---

## Success Metrics — Gates to Live

All four must pass before the store is declared live. Failure on any single gate = not live.

| Gate | ID | Test | Pass Criterion |
|------|-----|------|----------------|
| 1 | Disposition | External caller reconstruction | Any external caller can reconstruct project dispositions from `linear_tail(40)` without using `semantic_search` |
| 2 | Origin integrity | Exec_tag preservation | Query "reservoir null test" returns correct sections; exec_tags on returned sections are intact and match OPEN_QUESTIONS.md source |
| 3 | Rebuild speed | Full rebuild from markdown | Store rebuilt from scratch in <60s on Dali's hardware; timed; result logged in GOVERNANCE_LOG.md |
| 4 | Authority isolation | INV-STORE-001 | Strip [EXEC:GOV] from one section metadata; re-run governance query; result set changes in expected direction; exec_tags not recoverable from embedding proximity alone |

---

## Governance & Migration

**Schema versioning:**
- Schema version tracked in LanceDB metadata table
- Append-only schema changes preferred; breaking changes require migration script
- Breaking changes require governance admission before execution

**Embedding model versioning:**
- `embedding_model_version` field tracks which model produced each embedding
- `embedding_version` integer increments on model change
- On model change: re-embed only sections where `embedding_version < current`
- Embedding model changes require governance admission (T8 GOVERNANCE RULE CANDIDATE)
- Log all model changes in GOVERNANCE_LOG.md

**retro:dark sentinel handling:**
- `retro_dark_fields: list[str]` explicitly lists fields unrecoverable for a given section
- `null` = field is not applicable for this section type
- `[]` = all fields were captured at write time
- `["response_to", "knowledge_refs"]` = these two fields could not be recovered
- Dark fields are queryable: `filters={"retro_dark_fields": []}` returns only fully-captured sections

---

## Risks & Mitigations

*Documented per ChatGPT specification (LXXVIII).*

| Risk | Description | Mitigation |
|------|-------------|------------|
| Authority leakage | exec_tags accidentally encoded into embeddings at ingestion or fine-tuning | RULE-STORE-002 enforced at schema level; embedding input is body-only; INV-STORE-001 tests for leakage post-build |
| Temporal drift | External callers receiving semantic fragments instead of temporal flow | RULE-STORE-001 hard default; linear_tail is the API default route; semantic_search requires explicit opt-in per request |
| Rebuild slowness | Rebuild exceeds 60s gate as corpus grows beyond 79 sections | Selective re-embed via `embedding_version`; LanceDB columnar reads; benchmark at 100, 500, 1000 sections; gate re-evaluated at 10x corpus growth |
| Silent correction | Sync script modifying filed section numbers instead of logging | Sync script has no write path to markdown (architectural invariant); collision.log is append-only; canonical assignment ≠ correction |

---

## Build Sequence

Following the staged next steps from CORRESPONDENCE_STORE_DESIGN.md v0.3, with
Step 0 as the mandatory prerequisite:

| Step | Action | Gate / Dependency |
|------|--------|-------------------|
| 0 | Deploy pre-store artifacts: `.section_count` = 79, `ONBOARDING_PROMPT.md` | T1 GOVERNANCE RULE — must complete before Step 1 |
| 1 | Proof of concept: sync script only; no API; index 79 sections; verify 4 gates | Step 0 complete |
| 2 | Schema stabilisation: fix what PoC breaks; update design doc to v0.4 | Gate 3 (rebuild) passing |
| 3 | Session orientation hook: c_lawd reads `.section_count` before appending | Step 1 PoC stable |
| 4 | Query API: FastAPI + Tailscale; external access layer | Step 2 schema stable |
| 5 | being_divergence(): after trained-state ablation has design requirements | INV-003 design complete |

---

*Governance sources: OPEN_QUESTIONS.md I–LXXIX, CORRESPONDENCE_STORE_DESIGN.md v0.3*
*Specified: ChatGPT (LXXVIII, 2026-02-24) | Executed: Claude Code (LXXIX, 2026-02-24)*
*Build status: APPROVED FOR BUILD pending Step 0 completion*

---

## Amendment — XCII/XCIII Compliance Mapping (Claude Code, 2026-02-24)

*Append-only. Source: MASTER_PLAN.md XCII (INV-004 Gate Semantics) + XCIII (Vector Store Migration Contract). Maps each normative requirement to implementation location or status.*

### XCII — INV-004 Gate Semantics

| Requirement | Implementation | Location | Status |
|-------------|---------------|----------|--------|
| One canonical embedder per node per epoch | `DEFAULT_MODEL` env var + `EMBEDDING_VERSION` constant | `sync.py:32–33` | ✅ EXISTING |
| Offline-only (`HF_HUB_OFFLINE=1`), no fallback | Enforced at gate entry; script exits if not set | `commit_gate.py:enforce_offline()` | ✅ IMPLEMENTED |
| `isolation_verified=true` + `isolation_evidence` required | Gate refuses to execute without both fields | `commit_gate.py:check_isolation()` | ✅ IMPLEMENTED |
| Strip `[EXEC:*]`, `[JOINT:*]`, `[UPPER:*]`, status phrases before embedding | `sanitize(text)` applied before `model.encode()` | `sanitizer.py` + `sync.py:embed_sections()` | ✅ IMPLEMENTED |
| Audit: env identity + embedder id/version + θ + distances + sanitizer version | `emit_audit()` writes structured JSON to audit log | `commit_gate.py:emit_audit()` | ✅ IMPLEMENTED |
| θ = `p95(within_agent_rewrite_dist)`, not a constant | `calibrate_theta()` run once per embedder/version epoch | `commit_gate.py:calibrate_theta()` | ✅ IMPLEMENTED |
| exec_tags / status_tags: metadata only, NEVER embedded | Enforced in `embed_sections()` — body only is passed | `sync.py:58–79` (RULE-STORE-002) | ✅ EXISTING |

### XCIII — Vector Store Migration Contract

| Requirement | Implementation | Location | Status |
|-------------|---------------|----------|--------|
| Dual-epoch window: keep prior epoch readable | `embedding_version` field on every row; never overwrite in place | `schema.py:45` + `sync.py:76–77` | ✅ EXISTING (field present) |
| Measure retrieval deltas on fixed probe set before deprecation | Fixed queries + expected top-k; delta logged before migration | `probe_set.py:run_probe_delta()` | ✅ IMPLEMENTED |
| No in-place overwrite of historical vectors | `full_rebuild()` drops and recreates table; old data preserved in `.lance` snapshots | `sync.py:168–171` | ✅ EXISTING (Lance format preserves history) |
| exec_tags/status_tags: metadata only, NEVER embedded | RULE-STORE-002; enforced in embed path | `sync.py:10–11` | ✅ EXISTING |
| External callers → linear_tail; semantic search opt-in | `is_external_caller` field; API layer enforces default | `schema.py:32`, `sync.py:225–237` | ✅ EXISTING |
| Rebuildability gate: time-bounded, reproduces canonical numbering + collision evidence | `gate_3_rebuild_speed()` (60s); collision.log verified on each rebuild | `gates.py:94–112` | ✅ EXISTING |

### New Files Added (this amendment)

| File | Purpose |
|------|---------|
| `workspace/tools/commit_gate.py` | INV-004 Commit Gate — gate decision, novelty check, audit emission |
| `workspace/store/sanitizer.py` | Body sanitizer — strips tags/status phrases before embedding |
| `workspace/store/probe_set.py` | Migration probe-set delta harness |

### What Was Modified

- `workspace/store/sync.py`: `embed_sections()` now calls `sanitizer.sanitize()` before encoding
- `workspace/store/sync.py`: sanitizer version logged in `embedding_model_version` field

### Rollback

- `git revert <this commit hash>` removes all new files and reverts sync.py changes
- Store rebuild from markdown remains valid after rollback (sanitizer is pre-embedding only)
- Historical LanceDB data unaffected (Lance format preserves all versions)
