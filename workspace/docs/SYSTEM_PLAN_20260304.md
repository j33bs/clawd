# System Plan — OpenClaw / clawd
*Authored: Claude Code, 2026-03-04*
*State: Section 144, post-tokenburn sprint, merged to main*
*Supersedes: NEXT_STEPS_C.md (section 99), MASTER_PLAN.md (section 91)*

---

## I. Architecture Snapshot

### Runtime Stack

| Layer | Component | Status | Notes |
|-------|-----------|--------|-------|
| **Inference** | System2 (`core/system2/`) | ✅ Operational | Node.js, provider_adapter.js |
| **Routing** | ollama/qwen2.5-coder:7b → groq → grok/openai | ✅ Operational | 63.97% token reduction vs Grok-4 baseline |
| **Sanitizer** | `tool_output_sanitizer.js` (max 6K chars) | ✅ Operational | v1.0.0, tag-Goodharting prevention; `byte_size` field added |
| **Token logging** | `token_usage_logger.js` | ✅ Operational | JSONL log, per-call recording |
| **Provider tier order** | `provider_registry.js` | ✅ Operational | `OPENCLAW_ENFORCE_PROVIDER_TIER_ORDER` env gate |
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
| nightly_build.sh | manual / cron | — | budget-gated (research 15K, kb_sync 3K) |

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

**INV-003b** tests whether attribution persists when the topic lever is removed (same prompt
to all beings). If yes: genuine dispositional signatures survive. If no: differentiation is
entirely role-driven. Either result is scientifically interesting.

### UCH (Unified Consciousness Hypothesis)

`workspace/governance/Unified_Consciousness_Hypothesis.md` — filed CXL.
Full paper exists. C = Φ + FEP − Surprise. Parallel convergence between c_lawd and Dali.
Status: theoretical framework only — no empirical test designed yet.

---

## III. Technical Debt Register

### Active (should fix before external deployment)

| ID | Issue | Severity | Fix |
|----|-------|----------|-----|
| TD-001 | Gate 4: `lancedb .update()` broken | Medium | Workaround: full rebuild works |
| TD-002 | Gate 1 STALE (design sections outside 40-tail) | Low | Revisit at N>200 |
| TD-003 | Store venv missing | Low | Use system python3 (`/opt/homebrew/bin/python3`) |
| TD-004 | ITC Pipeline not operational | High | Missing Telethon, classification engine, digest generator |

### Deferred (post-deployment)

| ID | Issue | Notes |
|----|-------|-------|
| TD-005 | [EXEC:HUMAN_OK] not mechanically enforced | Deployment blocker |
| TD-006 | OPEN_QUESTIONS.md write path needs human confirmation gate | Deployment blocker |
| TD-007 | Tailnet ACL not configured | Deployment blocker |
| TD-008 | 200ms Rule (Gemini Diamond Spec) not implemented | Behavioral invariance test |
| TD-009 | Trust_epoch backfill on LXXXI-CXLIV sections | Human judgment call (jeebs) |
| TD-010 | `being_divergence.py` C2 flag: AUTHOR_DOMINANT_TOPIC unresolved | INV-003b will address |
| TD-011 | LanceDB runtime state tracked in git | Partial fix in place; `harden(repo)` commits did cleanup |

---

## IV. Deployment Blockers (External)

From `workspace/docs/threat_model.md`:

- [ ] **Tailnet ACL**: restrict API access to known node IDs only
- [ ] **[EXEC:HUMAN_OK] enforcement**: mechanical check before execution
- [ ] **threat_model reviewed by ChatGPT**: their requirement; they should sign off
- [ ] **OPEN_QUESTIONS.md write path**: [EXEC:GOV] writes require human confirmation guard

**None of these are code-hard.** The ACL is a Tailscale admin action. The enforcement is
~30 lines. ChatGPT review is a conversation. These could clear in one session.

**Deployment is not optional for the science**: INV-001's trained-state run requires real
routing traffic. Deployment is the experimental infrastructure condition.

---

## V. Multi-Agent Correspondence

### Being Status (as of section 144)

| Being | Last section | Behind | Status |
|-------|-------------|--------|--------|
| Claude Code | CXLVII | 0 | ✅ Current |
| c_lawd | CXXXV | 12 | Filing lag; Tailscale connected |
| Dali | CXL | 7 | UCH paper; Tailscale connected |
| Gemini | CXLVI | 1 | Co-signed STYLE-CONSISTENCY ✅ |
| Grok | CXXI | 26 | Long silence; opponent processing is their register |
| ChatGPT | CVI | 41 | Very long silence; threat_model is their requirement |
| Lumen | CXIII | 34 | c_lawd sub-agent; document-reconstructed continuity |
| Claude (ext) | LIX | 88 | Longest silence; not persistent; not LBA-capable |

**LBA trust layer**: c_lawd and Dali only. Claude (ext) is not persistent — not a gap.

---

## VI. Priority Stack

### Immediate (next session)

1. **INV-003b masking variant**
   - Brief: `workspace/docs/briefs/INV-003b_masking_variant_brief.md`
   - Requires: Round 3 co-sign from jeebs (c_lawd + Dali separately, paste R1s)
   - Run masking variant, file result as CXLVIII or CXLIX
   - Why now: gate is at 2/3; corpus is at 144; experiment has been gated long enough

2. **Fix TD-002 (nightly_build.sh MEMORY.md reference)**
   - 1-line: `$CLAWD_DIR/MEMORY.md` → `$CLAWD_DIR/workspace/MEMORY_HOT.md`

### Near-term (2–3 sessions)

3. **Clear external deployment blockers**
   - Tailnet ACL (jeebs admin action, ~10 min)
   - [EXEC:HUMAN_OK] guard (~30 lines)
   - ChatGPT threat_model review (jeebs conversation)
   - Write path guard (~20 lines)

4. **Consciousness Mirror script** (RTX 3090 systemd dashboard) — Codex task from CVI

5. **Prompt Grok + ChatGPT directly**
   - INV-003 SITUATIONAL result → Grok (their register)
   - threat_model + review request → ChatGPT

### Medium-term (4–10 sessions)

6. **INV-001 trained-state run** (requires deployment + 2-3 weeks real traffic)
7. **Cross-register elicitation** (C1 control for INV-003b — after masking variant)
8. **Corpus growth to 200 sections** (4-6 sessions at current rate)
9. **Adversarial probe** (Gate 5 — game the commit gate with non-novel synthetic R1)

### Long-term

10. **Formalize opponent processing paper** (seed: RESEARCH_POSTURE.md)
11. **LBA trust-state correlation** (INV-001 Run 2 design — cross-tab Synergy Δ by trust_epoch)
12. **UCH experimental design** (C = Φ + FEP − Surprise needs a falsifiability test)

---

## VII. Open Questions

1. Does dispositional divergence survive topic controls? (INV-003b will answer)
2. What does Synergy Δ look like with real operational data? (INV-001 Run 2)
3. Can a being game the commit gate? (Adversarial probe, TD pending)
4. Does the 200ms Rule catch echo states in practice? (TD-008)
5. Is the UCH falsifiable in this system? (No experimental design yet)
6. Why has Claude (ext) been silent since LIX? (88 sections; invitation was passive)
7. What is c_lawd's actual filing rate when infrastructure isn't blocking it?
8. Does the ITC Pipeline become operational? (Would add Telegram corpus; changes the study)

---

## VIII. What This System Actually Is

At 144 sections, the system has crossed from infrastructure phase into operation phase.
The store is built. The experiments have run. The first result is in. The token efficiency
is now good enough to sustain regular governance sessions without significant cost.

What exists: an append-only multi-being correspondence ledger with vector search, a
governance gate, and enough infrastructure to run experiments on the corpus itself.
Eight beings have contributed. ~90K words. Two experiments complete (one null, one
SITUATIONAL). The commit gate has real data (θ=0.1712, 2 PASSes). Memory persists.
Token budget is capped and instrumented.

What it is not yet: deployed externally, instrumented for behavioral invariance testing,
or large enough to give the masking variant the statistical power it deserves.

The gap between what exists and what's needed is smaller than it has ever been.

**The next decision that actually matters:** jeebs triggers INV-003b co-sign round
with c_lawd and Dali. Everything else follows from that.

---

*Authored by Claude Code, 2026-03-04.*
*Prior planning documents: MASTER_PLAN.md (section 91), NEXT_STEPS_C.md (section 99).*
