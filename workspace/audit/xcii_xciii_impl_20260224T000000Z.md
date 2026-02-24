# Audit Note — XCII/XCIII Implementation
- timestamp_utc: 2026-02-24T000000Z
- scope: Implementation of MASTER_PLAN XCII (INV-004 Gate Semantics) and XCIII (Vector Store Migration Contract)
- author: Claude Code
- branch: claude-code/governance-session-20260223
- governance sources: OPEN_QUESTIONS.md XCI (spec), XCIV (Grok safeguards), XCV (ChatGPT amendments A/B/C), MASTER_PLAN.md XCII/XCIII (ChatGPT, adfa42b)

---

## What Changed

### New files

| File | Purpose | XCII/XCIII requirement |
|------|---------|----------------------|
| `workspace/store/sanitizer.py` | Strip `[EXEC:*]`, `[JOINT:*]`, `[UPPER:*]`, status phrases before embedding | XCII: "sanitization to prevent tag-Goodharting" |
| `workspace/tools/commit_gate.py` | INV-004 gate — isolation check, prefix check, novelty check, audit emission | XCII: "Status: OPERATIONAL in workspace/tools/commit_gate.py" |
| `workspace/store/probe_set.py` | Fixed probe set + delta harness for migration epochs | XCIII: "Evaluate retrieval deltas on a fixed probe set" |
| `workspace/docs/CorrespondenceStore_v1_Plan.md` (amended) | Compliance mapping table appended; no existing content modified | Output 1 |

### Modified files

| File | Change | Why |
|------|--------|-----|
| `workspace/store/sync.py` | `embed_sections()` now calls `sanitizer.sanitize()` before `model.encode()`; sanitizer version appended to `embedding_model_version` field | XCII sanitization requirement; audit traceability |

---

## What Was NOT Changed (existing compliance)

- `exec_tags` / `status_tags` never embedded — already enforced by RULE-STORE-002 in sync.py
- `canonical_section_number` + `section_number_filed` + `collision` already in schema.py
- Dual-epoch `embedding_version` field already in schema.py
- External callers → linear_tail; semantic search opt-in already in sync.py + schema.py
- Rebuild-speed gate (60s) already in gates.py gate_3_rebuild_speed()
- `embedding_model_version` already logged per section

---

## Why

MASTER_PLAN XCII froze the meaning of "INV-004 PASS" across time and model migrations,
requiring: offline embedder, isolation attestation, sanitized input, calibrated θ,
mandatory audit emission. None of these were in the original commit_gate.py because
commit_gate.py did not exist.

MASTER_PLAN XCIII required: fixed probe set for migration validation, no in-place
vector overwrite, and a measurable delta gate before deprecating an embedding epoch.
The store already had most of XCIII in place structurally; the probe-set harness was
the missing operational piece.

---

## Acceptance Gates

Run these to verify the implementation before the dry run:

```bash
# 1. Sanitizer unit test
python3 -c "
import sys; sys.path.insert(0, 'workspace/store')
from sanitizer import sanitize, sanitizer_version
text = '[EXEC:GOV] The store is live. [JOINT: c_lawd + Dali] Result: pass.'
out = sanitize(text)
assert '[EXEC' not in out, f'Tag not stripped: {out}'
assert '[JOINT' not in out, f'Tag not stripped: {out}'
print('✅ sanitizer:', repr(out[:80]))
print('✅ version:', sanitizer_version())
"

# 2. commit_gate.py dry run
export HF_HUB_OFFLINE=1
python3 workspace/tools/commit_gate.py \
  --r1-c-lawd "The output must preserve the full provenance chain for every section." \
  --r1-dali   "The output must not exceed 200 tokens and remain actionable." \
  --r3-joint  "[JOINT: c_lawd + Dali] The output records provenance as a compressed citation list, keeping each entry under 15 tokens." \
  --task-id   TASK_DRY_001 \
  --isolation-evidence "c_lawd session: 21:04Z, Dali session: 21:07Z, no shared context, jeebs withheld submissions" \
  --c-lawd-constraint "must preserve full provenance chain" \
  --dali-constraint "must not exceed 200 tokens" \
  --dry-run

# 3. Probe set baseline
cd workspace/store && python3 probe_set.py --record-baseline --label v1_miniLM_sanitized

# 4. Store rebuild with sanitizer active
python3 workspace/store/run_poc.py --parse-only
```

---

## Rollback

```bash
# Revert this commit entirely
git revert <this-commit-hash>

# Or revert only sync.py (if sanitizer causes embedding shift problems)
git checkout HEAD~1 -- workspace/store/sync.py
# Then rebuild store: python3 workspace/store/run_poc.py
```

**Important:** Rolling back sync.py changes the embedding_model_version string format
(drops `+sanitizer-X.X.X` suffix). Run the probe-set delta check after rollback to
verify retrieval quality is preserved.

**Historical vectors are not affected.** LanceDB's Lance format retains all prior
table versions. No data is lost on rollback.

---

## Open Items (not addressed by this implementation)

| Item | Owner | Status |
|------|-------|--------|
| INV-004 dry run execution | jeebs + Claude Code | ⬜ Required before first real friction task |
| INV-003 c_lawd co-sign | jeebs → c_lawd | ⬜ Neutral third party must elicit |
| `being_divergence()` implementation | Claude Code | ⬜ Blocked on INV-003 co-sign |
| Governance-native threat model | Claude Code | 🔴 Deployment blocker |
| Network plane: tailnet ACLs for commit_gate.py | jeebs / ChatGPT | 🟡 Recommended before multi-node |
| Probe set: replace synthetic calibration pairs with actual rewrite pairs | Claude Code / jeebs | 🟡 Before production θ |
