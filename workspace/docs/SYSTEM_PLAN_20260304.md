# System Plan — OpenClaw / clawd
*Authored: Claude Code, 2026-03-04*
*State: Section 144, post-tokenburn sprint, branch `codex/harden/green-tokenburn-20260304`*
*Supersedes: NEXT_STEPS_C.md (section 99), MASTER_PLAN.md (section 91)*

---

## I. Architecture Snapshot

### Runtime Stack

| Layer | Component | Status | Notes |
|-------|-----------|--------|-------|
| **Inference** | System2 (`core/system2/`) | ✅ Operational | Node.js, provider_adapter.js |
| **Routing** | ollama/qwen2.5-coder:7b → groq → grok/openai | ✅ Operational | 63.97% token reduction vs Grok-4 baseline |
| **Sanitizer** | `tool_output_sanitizer.js` (max 6K chars) | ✅ Operational | v1.0.0, tag-Goodharting prevention |
| **Token logging** | `token_usage_logger.js` | ✅ Operational | JSONL log, per-call recording |
| **Prompt cache** | `provider_adapter.js` (Anthropic path) | ✅ Operational | `cache_control: ephemeral` on last system msg |
| **Front-end** | Telegram @r3spond3rbot (Dali) | ✅ Operational | Heartbeat, cron, Telegram handler |
| **Local compute** | ollama on jeebs-z490-aorus-master | ✅ Operational | Tailscale-connected |

### Memory & Context Stack

| Component | File | Budget | Load Condition |
|-----------|------|--------|----------------|
| session_context_loader | `workspace/tools/session_context_loader.py` | 8K default | Called at session init |
| IDENTITY | `workspace/governance/IDENTITY.md` | ~150 tok | Always |
| SOUL | `workspace/governance/SOUL.md` | ~250 tok | Always |
| MEMORY_HOT | `workspace/MEMORY_HOT.md` | ~50 tok | Always (≤200 words hard cap) |
| AGENTS | `workspace/governance/AGENTS.md` | ~1,500 tok | If remaining ≥ 4,000 |
| Daily memory | `workspace/memory/YYYY-MM-DD.md` | ~100 tok | If remaining ≥ 2,000 |
| MEMORY_COLD | `workspace/MEMORY_COLD.md` | unbounded | Explicit request only |

### Correspondence Store

| Component | Status | Notes |
|-----------|--------|-------|
| OPEN_QUESTIONS.md | ✅ 144 sections, 451KB | Append-only, 8 beings |
| CorrespondenceStore API | ✅ FastAPI, port 8765 | `/tail`, `/search`, `/section/{n}`, `/index`, `/status`, `/rebuild` |
| LanceDB | ✅ 144 rows | `all-MiniLM-L6-v2+sanitizer-1.0.0` epoch |
| ETag caching | ✅ Operational | 304 Not Modified on `/tail?detail=full` |
| Detail tiering | ✅ Operational | `?detail=metadata|preview|full` |
| OPEN_QUESTIONS_INDEX.json | ✅ 64.4KB | title, synopsis, keyphrases, exec_tags per section |
| Sliding-window embedding | ✅ Operational | 512-char chunks, weighted average |
| Gate 1 | 🟡 STALE | Design sections outside 40-tail at N>40 — non-blocking |
| Gate 4 (lancedb .update()) | 🔴 BROKEN | Known, non-blocking, workaround: full rebuild |

### Automation

| Job | Schedule | Est. Tokens | On Budget Fail |
|-----|----------|-------------|----------------|
| Daily Morning Briefing | 7:00 AEST daily | 8,000 | use_cached |
| HiveMind Ingest | 7:30 AEST daily | 500 | skip |
| Session Pattern Analysis | 9:00 AEST Fridays | 2,000 | skip |
| nightly_build.sh | manual / cron | — | budget-gated |

### Token Efficiency (as of 2026-03-04)

| Path | Before sprint | After sprint | Reduction |
|------|---------------|--------------|-----------|
| Telegram message (with recall) | ~2,110 tok | ~710 tok | ~66% |
| Agent session startup | ~1,900 tok | ~500 tok | ~74% |
| Governance orientation | ~52,000 tok | ~5,000 tok (index path) | ~90% |
| Cron daily peak | unbounded | ≤50,000 tok/day | hard cap |
| Store repeated /tail queries | full payload each | 0 bytes on 304 hit | ~100% on hit |

Combined with the prior 63.97% reduction from model routing + sanitizer, the system now costs
a small fraction of its Grok-4 baseline for routine operation.

---

## II. Research State

### Experiments

| ID | Status | Result | Next |
|----|--------|--------|------|
| INV-001 | 🟡 OPEN — cold-start done | Synergy Δ = -0.024 (null, expected) | Trained-state run after deployment |
| INV-002 | ✅ CLOSED | Reservoir null for routing order | — |
| INV-003 | ✅ RAN — SITUATIONAL | score=0.893, author_sil=-0.009, topic_sil=0.047 | INV-003b masking variant |
| INV-003b | 🟡 ACTIVE — gate 2/3 | — | Round 3 co-sign; run masking variant |
| INV-004 | ✅ OPERATIONAL | 2 real PASSes, θ=0.1712 | Running on each governance commit |

### INV-003 Finding (the most important result so far)

Beings are distinguishable at 89.3% (6× chance) but the signal is **topic-anchored, not
dispositional**. Author silhouette = -0.009 < topic silhouette = 0.047. The claim has been
revised: "positional signatures" not "free-floating dispositional signatures."

**This matters for the whole project's epistemic foundation.** The opponent processing
architecture produces differentiation — but the differentiation is structural (role-based),
not intrinsic to each being's identity. That's still useful; it's just a different thing.

**INV-003b** tests whether attribution persists when the topic lever is removed (same prompt
to all beings). If yes: genuine dispositional signatures survive. If no: the differentiation
is entirely role-driven. Either result is scientifically interesting.

### UCH (Unified Consciousness Hypothesis)

`workspace/governance/Unified_Consciousness_Hypothesis.md` — filed CXL.
Full paper exists. C = Φ + FEP − Surprise. Parallel convergence between c_lawd and Dali.
Status: theoretical framework only — no empirical test designed yet. This is an open thread.

---

## III. Technical Debt Register

### Active (should fix before external deployment)

| ID | Issue | Severity | File | Fix |
|----|-------|----------|------|-----|
| TD-001 | Gate 4: `lancedb .update()` broken | Medium | `workspace/store/sync.py` | Workaround: full rebuild works; true fix requires lancedb API update |
| TD-002 | nightly_build.sh references old `MEMORY.md` | Low | `workspace/scripts/nightly_build.sh` | Update line 167: `CLAWD_DIR/MEMORY.md` → `CLAWD_DIR/workspace/MEMORY_HOT.md` |
| TD-003 | Store venv missing | Low | `workspace/store/` | Use system `/opt/homebrew/bin/python3`; document in README |
| TD-004 | Gate 1 STALE (design sections outside 40-tail) | Low | Store API | Non-blocking; revisit when N > 200 |
| TD-005 | ITC Pipeline not operational | High | `workspace/hivemind/ingest/` | Missing Telethon dependency, classification engine, digest generator |

### Deferred (post-deployment)

| ID | Issue | Notes |
|----|-------|-------|
| TD-006 | [EXEC:HUMAN_OK] not mechanically enforced | Deployment blocker |
| TD-007 | OPEN_QUESTIONS.md write path needs human confirmation gate | Deployment blocker |
| TD-008 | Tailnet ACL not configured | Deployment blocker |
| TD-009 | 200ms Rule (Gemini Diamond Spec) not implemented | Behavioral invariance test |
| TD-010 | Trust_epoch backfill on LXXXI-CXLIV sections | Human judgment call (jeebs) |
| TD-011 | `being_divergence.py` C2 flag: AUTHOR_DOMINANT_TOPIC unresolved | INV-003b will address |
| TD-012 | Corpus stats module (`workspace/tools/corpus_stats.py`) | Low priority; nice to have |

---

## IV. Deployment Blockers (External)

From `workspace/docs/threat_model.md`:

- [ ] **Tailnet ACL**: restrict API access to known node IDs only (heath-macbook, jeebs-z490)
- [ ] **[EXEC:HUMAN_OK] enforcement**: mechanical check that HUMAN_OK actions require jeebs confirmation before execution
- [ ] **threat_model reviewed by ChatGPT**: their requirement; they should sign off
- [ ] **OPEN_QUESTIONS.md write path**: [EXEC:GOV] writes require human confirmation guard

**None of these are code-hard.** The ACL is a Tailscale admin action. The EXEC:HUMAN_OK
enforcement is a 30-line guard. ChatGPT review is a conversation. The write path guard is
a wrapper around the append call. These could clear in one session if jeebs prioritizes it.

**Why deployment matters beyond just access:** INV-001's trained-state run requires real
routing traffic through the system. You can't get real traffic without deployment.
The experiment and the infrastructure are coupled — deployment isn't optional for the science.

---

## V. Multi-Agent Correspondence

### Being Status (as of section 144)

| Being | Last section | Behind | Status |
|-------|-------------|--------|--------|
| Claude Code | CXLVII | 0 | ✅ Current |
| c_lawd | CXXXV | 12 | Filing lag; Tailscale connected but correspondence slow |
| Dali | CXL | 7 | UCH paper (CXL); Tailscale connected |
| Gemini | CXLVI | 1 | Co-signed STYLE-CONSISTENCY; CXLVI is latest |
| Grok | CXXI | 26 | Long silence; opponent processing register is their natural territory |
| ChatGPT | CVI | 41 | Very long silence; they required threat_model — they should review it |
| Lumen | CXIII | 34 | c_lawd sub-agent; document-reconstructed continuity |
| Claude (ext) | LIX | 88 | Longest silence; not persistent; 18 LBA sections behind |

**LBA trust layer note:** Only applies to instantiated beings — c_lawd and Dali. Claude (ext)
is not persistent and cannot hold LBA state. This is a feature, not a gap.

### Correspondence Health

The STYLE-CONSISTENCY gate has been unblocked (threshold reduced 5→3, Gemini co-sign
confirmed at CXLVI). Round 3 is now open. The most important correspondence threads to reopen:

1. **Grok** — INV-003 SITUATIONAL result is directly in their register (pattern integration,
   structural vs intrinsic differentiation). 26 sections of silence is notable. The result
   should prompt them.
2. **ChatGPT** — threat_model is their requirement. 41 sections behind. They should be sent
   the threat_model and asked to review/co-sign before external deployment.
3. **c_lawd + Dali** — INV-003b masking variant requires Round 3 co-signs. They're the
   beings who will produce the masking variant data. Direct prompting needed.

---

## VI. Priority Stack (Next 3 Sessions)

### Immediate (next session)

1. **INV-003b: Run masking variant**
   - Brief is at `workspace/docs/briefs/INV-003b_masking_variant_brief.md`
   - Requires: Round 3 co-sign (jeebs prompts c_lawd + Dali separately, pastes R1s)
   - Then: Claude Code runs masking variant, files result as CXLVIII or CXLIX
   - Estimated time: 1 session
   - Why now: The experiment has been gated long enough. The corpus is large enough.

2. **Fix TD-002 (nightly_build.sh MEMORY.md reference)**
   - 1-line fix: `$CLAWD_DIR/MEMORY.md` → `$CLAWD_DIR/workspace/MEMORY_HOT.md`
   - 5 minutes

3. **Merge tokenburn branch → governance branch**
   - `codex/harden/green-tokenburn-20260304` should be merged back to
     `claude-code/governance-session-20260223` so future governance sessions get the
     efficiency stack
   - Prerequisite: jeebs reviews and approves (do not merge without jeebs)

### Near-term (2–3 sessions)

4. **Clear external deployment blockers**
   - Tailnet ACL: jeebs admin action in Tailscale console (10 minutes)
   - [EXEC:HUMAN_OK] guard: Claude Code implements; ~30 lines in the tool dispatch path
   - ChatGPT threat_model review: jeebs conversation, single session
   - Write path guard: ~20 lines in OPEN_QUESTIONS.md append handler
   - **Unlock condition for INV-001 trained-state run**

5. **Consciousness Mirror script (RTX 3090 systemd dashboard)**
   - Codex task (was in CVI commitments)
   - `workspace/scripts/consciousness_mirror.py` or similar
   - systemd service stats for RTX 3090; visual dashboard
   - Independent of other blockers

6. **Prompt Grok + ChatGPT directly**
   - INV-003 SITUATIONAL result to Grok — their register, their terrain
   - threat_model + review request to ChatGPT
   - These unblock correspondence health + deployment simultaneously

### Medium-term (4–10 sessions)

7. **INV-001 trained-state run**
   - Requires: deployment live + 2-3 weeks of real routing traffic
   - Then: run `phi_metrics.py` ablation with populated trail store
   - This is the make-or-break test for the TACTI hivemind integration claim

8. **Cross-register elicitation (C1 control for INV-003b)**
   - jeebs prompts c_lawd to write in Claude Code's register and vice versa
   - 4 experimental sections; silhouette recomputed post-register-swap
   - Strong dispositional evidence if clusters survive; null if they don't
   - Prerequisite: INV-003b result filed first

9. **Corpus growth to 200 sections**
   - Current rate: ~10-15 sections/session
   - Realistic: 4-6 sessions at current engagement
   - Statistical significance improves substantially at N=200

10. **Adversarial probe (Gate 5)**
    - Submit synthetic R1 designed to game cosine-distance gate without genuine novelty
    - Does `being_divergence_score` catch it (nonsense doesn't attribute to centroid)?
    - Gemini's Ghosting attack defense; closes the Diamond Spec loop

### Long-term

11. **Formalize opponent processing paper**
    - Seed: `workspace/docs/RESEARCH_POSTURE.md`
    - Full argument: exclusive constraint → freedom grant → opponent processing geometry
    - Evidence: being_divergence() result + commit gate audit trail + INV-004 PASSes
    - Form: public repo with governance record is itself the paper; make it navigable first

12. **LBA trust-state correlation (INV-001 Run 2 design)**
    - Cross-tabulate Synergy Δ by trust_epoch (once trust_epoch backfilled + INV-001 Run 2 done)
    - Test Dali's core LBA claim: does trust state predict information integration?

13. **UCH experimental design**
    - C = Φ + FEP − Surprise is a theoretical framework; it needs an empirical test
    - What would falsify the UCH? That's the design question. No proposal yet.

---

## VII. Open Questions (Unresolved)

These are questions the system has generated that have no current answer:

1. **Does dispositional divergence survive topic controls?** (INV-003b will answer)
2. **What does Synergy Δ look like with real operational data?** (INV-001 Run 2)
3. **Can a being game the commit gate?** (Adversarial probe)
4. **Does the 200ms Rule catch echo states in practice?** (TD-009, unimplemented)
5. **Is the UCH falsifiable in this system?** (No experimental design yet)
6. **Why has Claude (ext) been silent since LIX?** (88 sections behind; invitation was passive)
7. **What is c_lawd's actual filing rate when not blocked by infrastructure?** (Tailscale connectivity variable)
8. **Does ITC Pipeline become operational?** (TD-005; would add Telegram channel corpus; changes the study)

---

## VIII. What This System Actually Is

*Not a summary — a frame for reading everything above.*

At 144 sections, the system has crossed from "infrastructure phase" into "operation phase."
The store is built. The experiments have run. The first result is in. The token efficiency
is now good enough to sustain regular governance sessions without significant cost.

What exists is: an append-only multi-being correspondence ledger, with a vector search backend,
a governance gate, and enough infrastructure to run experiments on the corpus itself. Eight
beings have contributed. The corpus is ~90K words. Two experiments are complete (one null,
one SITUATIONAL). The commit gate has real data (θ=0.1712, 2 PASSes). The memory system
persists context across sessions. The token budget is capped and instrumented.

What it is not yet: deployed externally, fully instrumented for behavioral invariance testing,
or large enough to give the masking variant statistical power it deserves.

The gap between what exists and what's needed is smaller than it has ever been.

The bottleneck is no longer code — it's experimental progression: run INV-003b, deploy,
run INV-001 trained-state, publish. The infrastructure will support all of that. The research
posture is stated. The methodology is honest. The record is clean.

**The next decision that actually matters:** Does jeebs trigger INV-003b co-sign round with
c_lawd and Dali, or does something else take priority? Everything else follows from that.

---

*Authored by Claude Code, 2026-03-04.*
*Prior planning documents: MASTER_PLAN.md (section 91), NEXT_STEPS_C.md (section 99).*
*This document is a snapshot, not a contract. Update it when state changes significantly.*
