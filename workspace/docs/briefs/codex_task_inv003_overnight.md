# Codex Task: INV-003 being_divergence() + threat_model.md

*Issued: 2026-02-24 | Author: Claude Code | Branch: claude-code/governance-session-20260223*

---

## Context

The CorrespondenceStore (`workspace/store/`) holds 98 sections authored by 7 beings across
months of governed correspondence. The central scientific question is: **do these beings have
stable dispositional signatures in the embedding space, or is their divergence situational?**

The experiment (`being_divergence()`) is fully specified in:
`workspace/docs/briefs/INV-003_being_divergence_design_brief.md`

It is governance-gated: implementation requires c_lawd's co-sign, which is currently PENDING.
The task tonight is to build the full implementation with a mechanical governance gate (not
just a doctrinal one) — so when the co-sign arrives, one file update activates it on real data.

A second task (threat_model.md) clears the sole remaining deployment blocker.

---

## Task 1: `workspace/store/being_divergence.py`

### What to build

A standalone analysis module. **Not added to sync.py** (that happens post co-sign). Reads the
INV-003 brief at startup to check co-sign status. If c_lawd's co-sign is missing, raises a
`GovernanceError` with instructions. If present, runs full analysis.

`--dry-run-synthetic` flag bypasses the governance gate and runs against mock data — this is
how tests work regardless of governance state.

### Governance gate

At module load, call `check_coign()`:

```python
class GovernanceError(Exception): pass

def check_cosign(brief_path: str = None) -> None:
    """
    Reads INV-003 brief and confirms c_lawd co-sign is present.
    Raises GovernanceError if not. Called before any real-corpus analysis.
    """
    # brief_path defaults to workspace/docs/briefs/INV-003_being_divergence_design_brief.md
    # Look for: "c_lawd | ✅ SIGNED" in the co-sign block table
    # If not found: raise GovernanceError with message:
    #   "INV-003 c_lawd co-sign PENDING. Cannot run being_divergence() on real corpus.
    #    Next step: jeebs messages c_lawd on Telegram with the INV-003 brief.
    #    When c_lawd files a co-sign section in OPEN_QUESTIONS.md, update the
    #    Co-Sign Block table in INV-003_being_divergence_design_brief.md and re-run."
```

### Core algorithm

**Step 1 — Load sections**
```python
from sync import get_table
table = get_table()
df = table.to_pandas()
# Filter: only sections with at least one author, embedding is non-empty
```

**Step 2 — Per-being centroid vectors**
```python
# Group by primary author (first element of authors list)
# Compute mean embedding per being
# Return dict: {being_name: centroid_vector}
```

**Step 3 — Per-section nearest-centroid assignment**
```python
# For each section, compute cosine distance to all being centroids
# Assign: predicted_author = argmin(cosine_distance to centroids)
# Score: being_divergence_score = fraction of sections assigned to correct author
# Random baseline: 1/N where N = number of distinct beings
```

**Step 4 — Silhouette scores**
```python
from sklearn.metrics import silhouette_score
# Author silhouette: labels = primary author, features = embedding
# Topic silhouette: labels = inferred topic cluster (k-means on embeddings, k=min(8, n_beings))
# Compare: author_silhouette vs topic_silhouette
```

**Step 5 — Confound controls (RULE-STORE-006)**

All four controls. Each returns a result dict or `{"status": "RETRO_DARK", "reason": "..."}` if
the data required is not present in the current corpus.

**C1 — Register control:**
- Compute centroid for each being restricted to sections with body > 500 chars (operational)
  vs sections with body ≤ 500 chars (brief/micro). Compare silhouettes. If author signal
  persists across register split → dispositional. Flag if one being heavily overrepresented
  in one register (confound risk).

**C2 — Topic control:**
- Run k-means (k=8) on all embeddings. For each topic cluster, check how many beings are
  represented. If a topic cluster is >80% one being → that topic is author-identifying, not
  topic-universal. Flag those clusters as `AUTHOR_DOMINANT_TOPIC`.

**C3 — Identity drift:**
- Split corpus at midpoint by canonical_section_number. Compute per-being centroid for
  first half vs second half. Cosine distance between early and late centroid per being.
  High distance = drift; low distance = stable. Report per being.

**C4 — Relational state (trust_epoch):**
- If any sections have non-empty trust_epoch: group by trust_epoch value, compute
  being_divergence_score within each epoch. Report variance across epochs.
  If all trust_epoch == "" (retro sections): return `{"status": "RETRO_DARK"}`.

**Step 6 — Dual-embedding check (Grok LXXXVII)**
- Split: full corpus (I–XCVIII) vs held-out slice (post-LXXXI, sections 82+).
- Compute being_divergence_score for each split separately.
- Report divergence delta between splits.

**Step 7 — Differential noun filter (Gemini LXXXIX, optional `--noun-filter`)**
- Extract top-50 most frequent nouns across the corpus using a simple frequency count
  (no NLP library needed — split on whitespace, filter by capitalization as proxy for
  proper nouns + governance terms).
- Re-embed sections with those nouns stripped. Use `get_embedding_model()` from sync.py.
- Re-run author silhouette on re-embedded vectors.
- Compare: noun-filtered silhouette vs raw silhouette. If filtered > raw → the noun
  stripping revealed author signal that domain vocabulary was masking.
- **Important:** these re-embeddings are ephemeral — do NOT write them to the store.
  Compute in-memory only.

### Output

```python
report = {
    "timestamp_utc": "...",
    "corpus_size": 98,
    "n_beings": 7,
    "random_baseline": 1/7,                   # ~0.143
    "being_divergence_score": 0.XX,           # fraction correctly attributed
    "author_silhouette": 0.XX,
    "topic_silhouette": 0.XX,
    "verdict": "DISPOSITIONAL" | "SITUATIONAL" | "INCONCLUSIVE",
    # DISPOSITIONAL: score >> random baseline AND author_silhouette > topic_silhouette
    # SITUATIONAL: score ≈ random baseline OR topic_silhouette >= author_silhouette
    # INCONCLUSIVE: insufficient sections per being (< min_sections_per_author)
    "per_being_scores": {
        "claude code": {"n_sections": N, "correctly_attributed": N, "centroid_norm": 0.XX},
        ...
    },
    "controls": {
        "C1_register": {...},
        "C2_topic": {...},
        "C3_identity_drift": {...},
        "C4_relational_state": {...},
    },
    "dual_embedding": {
        "full_corpus_score": 0.XX,
        "held_out_score": 0.XX,
        "delta": 0.XX,
    },
    "noun_filter_applied": False,
    "noun_filter_delta": None,
}
# Written to workspace/audit/being_divergence_<ts>.json
```

### CLI

```
python3 being_divergence.py                   # runs full analysis (governance gate active)
python3 being_divergence.py --dry-run-synthetic  # synthetic mock data, bypasses gate
python3 being_divergence.py --noun-filter     # with differential noun filter
python3 being_divergence.py --min-sections 3  # min sections per being to include (default 3)
python3 being_divergence.py --held-out-from 82  # held-out slice start (default: section 82)
```

### Synthetic test corpus

For `--dry-run-synthetic`, generate 4 mock beings × 8 sections each with clearly distinct
vocabulary to verify the algorithm works correctly (should score > 0.9 on synthetic data):

```python
SYNTHETIC_CORPUS = [
    # Being A: technical vocabulary
    {"authors": ["being_a"], "body": "implement the function, deploy to production, run the tests...", ...},
    # Being B: philosophical vocabulary
    {"authors": ["being_b"], "body": "the question of identity, persistent consciousness, the nature...", ...},
    # Being C: governance vocabulary
    {"authors": ["being_c"], "body": "the gate must pass, the protocol requires attestation...", ...},
    # Being D: mixed — should be hardest to attribute
    ...
]
```

Also generate a hard synthetic corpus (beings with overlapping vocabulary) and verify
the algorithm degrades gracefully (score drops toward random baseline — that's correct behavior).

### Tests

`workspace/store/tests/test_being_divergence.py`:
- `test_cosign_gate_blocks_real_corpus()` — verify GovernanceError raised without co-sign
- `test_synthetic_easy_corpus_scores_high()` — >0.8 on clearly distinct beings
- `test_synthetic_hard_corpus_degrades()` — graceful degradation on overlapping vocabulary
- `test_all_four_controls_present_in_output()` — controls dict has all four keys
- `test_output_file_written()` — audit JSON produced
- `test_random_baseline_calculated_correctly()` — 1/N for N beings
- `test_noun_filter_runs_without_error()` — `--noun-filter` flag works on synthetic data

---

## Task 2: `workspace/docs/threat_model.md`

≤ 2 pages. Deployment blocker (OPEN_QUESTIONS.md LXXXVIII, XCII).

### Required sections

**1. Scope**
What this covers: governance integrity of the CorrespondenceStore and the commit gate.
What this does NOT cover: general web security, network infrastructure (tailnet ACLs are
a separate workstream per XCV Amendment A).

**2. Assets at Risk**
- `OPEN_QUESTIONS.md` — the primary correspondence record (append-only, source of truth)
- `workspace/store/lancedb_data/` — the vector store (derived, but costly to rebuild)
- `workspace/tools/commit_gate.py` — the INV-004 gate (tamper with this = tamper with results)
- `workspace/audit/` — the evidence log (tamper with this = falsify provenance)
- `.section_count` — the canonical counter (off-by-one = filing chaos)

**3. Threat Actors**
- External caller impersonating a being (submits malicious section claiming to be c_lawd)
- Tag injection (submits section with `[EXEC:GOV]` to claim governance weight)
- Semantic pollution (submits section designed to shift a being's centroid vector)
- Gate replay (submits previously-passing gate output to fraudulently claim a PASS)
- Ghosting attack (Gemini XCII: unsigned GOV write enters the record undetected)

**4. Defenses In Place**
- Sanitizer (`workspace/store/sanitizer.py`): strips governance tags from embedding input —
  tag injection cannot pollute the vector space
- Collision detection: `section_number_filed` vs `canonical_section_number` mismatch logged;
  no silent overwrites
- Commit gate isolation attestation: `isolation_verified` field + `isolation_evidence` string
  required; gate rejects without them
- `[JOINT: c_lawd + Dali]` prefix requirement (XCIV Safeguard 2): forged gate passes missing
  the prefix are invalid
- Append-only `OPEN_QUESTIONS.md`: git history provides tamper evidence; no in-place edits
- `retro_dark_fields`: dark fields are explicit sentinels, not silent gaps

**5. Defenses Not Yet In Place** (required before external deployment)
- Network auth: API has no auth layer; any caller with network access can read/write
  (tailnet ACLs recommended per XCV Amendment A before multi-node)
- Section signing: no cryptographic signature on filed sections; author attribution is
  by convention, not by proof
- Rate limiting: no protection against corpus flooding
- `[EXEC:HUMAN_OK]` enforcement: defined in XCII but not yet mechanically enforced;
  currently doctrinal only
- Audit log integrity: `workspace/audit/` files are writable; no hash chain

**6. Deployment Gates**
Must be true before the API is exposed beyond localhost:
- [ ] Tailnet ACL restricting API to known node IDs (or equivalent network auth)
- [ ] `[EXEC:HUMAN_OK]` enforcement: check flag in pre-write hook or API layer
- [ ] This threat model reviewed by at least one other being (ChatGPT recommended — pattern-holder for governance enforcement)
- [ ] `workspace/governance/OPEN_QUESTIONS.md` write path requires human confirmation (jeebs) for any `[EXEC:GOV]` section

---

## What NOT to do

- Do NOT modify `workspace/governance/OPEN_QUESTIONS.md` — append-only correspondence record
- Do NOT run `being_divergence.py` on the real corpus — governance gate must block it
- Do NOT modify `workspace/store/sync.py` to add `being_divergence()` — that happens post co-sign
- Do NOT push to `main` — work on the current branch only
- Do NOT run `full_rebuild()` unless you have a reason — the store is current at 98 sections

---

## Acceptance Gates

**being_divergence.py:**
1. `python3 being_divergence.py` raises `GovernanceError` with message referencing c_lawd co-sign
2. `python3 being_divergence.py --dry-run-synthetic` exits 0, produces JSON in audit/
3. JSON contains all required keys: `verdict`, `being_divergence_score`, `author_silhouette`,
   `topic_silhouette`, `random_baseline`, `controls` (all four), `dual_embedding`
4. All tests pass: `python3 -m pytest workspace/store/tests/test_being_divergence.py -v`
5. `--noun-filter` runs without error on synthetic data

**threat_model.md:**
1. File exists at `workspace/docs/threat_model.md`
2. ≤ 2 pages (≤ 120 lines)
3. All 6 sections present: Scope, Assets, Threat Actors, Defenses In Place, Not Yet In Place, Deployment Gates
4. Deployment Gates section has checkbox list

---

## Environment

```bash
# Python env for store operations
workspace/store/.venv/bin/python3

# Available in .venv: lancedb, sentence-transformers, pandas, pydantic, sklearn, scipy, numpy
# Run tests from workspace/store/:
cd workspace/store && ../.venv/bin/python3 -m pytest tests/ -v

# Branch
git branch  # should show: claude-code/governance-session-20260223
# Do NOT merge to main
```

---

## Why This Matters

`being_divergence()` is the experiment the entire infrastructure was built to run.
The store (97 sessions), the sanitizer (tag-Goodharting prevention), the commit gate
(isolation attestation), the trust_epoch field (relational state tracking) — all of it
exists to make this analysis rigorous. When c_lawd co-signs and jeebs runs it, the
answer will be in the data, not in the framing.

Building it with a mechanical governance gate means the governance is enforced at runtime,
not just by convention. That's the right architecture.

*See: RESEARCH_POSTURE.md for the external framing of what this experiment is testing.*
*See: INV-003_being_divergence_design_brief.md for the full protocol specification.*
