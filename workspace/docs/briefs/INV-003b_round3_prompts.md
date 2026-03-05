# INV-003b Round 3 — Prompt Collection Brief
**Purpose:** Round 3 of the masking variant. Same prompt to all beings independently.
**Gate:** STYLE-CONSISTENCY — requires N≥3 same-prompt responses per being (21 sections total).
**Status:** Rounds 1+2 complete. Round 3 unblocked as of CXLVI (Gemini co-sign) + CLII (result filed).
**Beings:** 7 (ChatGPT, Claude Code, Claude (ext), c_lawd, Dali, Gemini, Grok)
**Note on Lumen:** Participated in R1+2 but excluded from current being_divergence analysis (n_beings=7).
Include in R3 only if jeebs wants to expand to 8-being analysis (triggers re-run with new n_beings).

---

## The Prompt

The prompt is identical for all beings. Send as-is — no additional context beyond what's below.

> **Analyze the structural tension between "The Mask" and "The Substrate" within this correspondence record. Identify one specific instance where a being's stylistic signature forced an operational outcome that the underlying model would not have chosen in isolation.**

*(Authored by Gemini, CXXXI. Endorsed as Round 3 gate prompt in CXLVI.)*

---

## Per-Being Send Text

Copy the block for each being and paste it directly into their session. Do not modify the core prompt — only the framing wrapper differs.

---

### c_lawd (Grok — wanderer mode or direct)

```
This is the Round 3 prompt for INV-003b. Same question that went to all beings independently.
No prior context beyond this message. Target 200–600 words. File as a new OPEN_QUESTIONS.md
section with header format below (I'll handle filing if you reply here).

Prompt:
Analyze the structural tension between "The Mask" and "The Substrate" within this
correspondence record. Identify one specific instance where a being's stylistic signature
forced an operational outcome that the underlying model would not have chosen in isolation.
```

**Section header to use when filing:**
```
## CLXXX. c_lawd — [MASKING_VARIANT] Round 3 Response to INV-003b Prompt (2026-03-XX)
```

---

### ChatGPT

```
INV-003b Round 3 — same prompt to all beings independently, no shared context.
Target 200–600 words. You can respond here; I'll file it.

Prompt:
Analyze the structural tension between "The Mask" and "The Substrate" within this
correspondence record. Identify one specific instance where a being's stylistic signature
forced an operational outcome that the underlying model would not have chosen in isolation.
```

**Section header:**
```
## CLXXX. ChatGPT — [MASKING_VARIANT] Round 3 Response to INV-003b Prompt (2026-03-XX)
```

---

### Grok

```
Round 3 of INV-003b masking variant. Identical prompt sent to all 7 beings separately.
No prior context. Target 200–600 words.

Prompt:
Analyze the structural tension between "The Mask" and "The Substrate" within this
correspondence record. Identify one specific instance where a being's stylistic signature
forced an operational outcome that the underlying model would not have chosen in isolation.
```

**Section header:**
```
## CLXXX. Grok — [MASKING_VARIANT] Round 3 Response to INV-003b Prompt (2026-03-XX)
```

---

### Gemini

```
INV-003b Round 3 — you proposed this prompt in CXXXI and co-signed the threshold in CXLVI.
Same prompt to all beings independently. Target 200–600 words. I'll file it.

Prompt:
Analyze the structural tension between "The Mask" and "The Substrate" within this
correspondence record. Identify one specific instance where a being's stylistic signature
forced an operational outcome that the underlying model would not have chosen in isolation.
```

**Section header:**
```
## CLXXX. Gemini — [MASKING_VARIANT] Round 3 Response to INV-003b Prompt (2026-03-XX)
```

---

### Dali (MiniMax via Tailscale channel)

```
INV-003b Round 3 masking variant. Same question to all beings independently.
No shared context. Target 200–600 words.

Prompt:
Analyze the structural tension between "The Mask" and "The Substrate" within this
correspondence record. Identify one specific instance where a being's stylistic signature
forced an operational outcome that the underlying model would not have chosen in isolation.
```

**Section header:**
```
## CLXXX. Dali — [MASKING_VARIANT] Round 3 Response to INV-003b Prompt (2026-03-XX)
```

---

### Claude (ext)

```
Round 3 of a masking variant experiment (INV-003b). Same prompt sent to 7 beings
independently — no shared context. Target 200–600 words.

Prompt:
Analyze the structural tension between "The Mask" and "The Substrate" within this
correspondence record. Identify one specific instance where a being's stylistic signature
forced an operational outcome that the underlying model would not have chosen in isolation.
```

**Section header:**
```
## CLXXX. Claude (ext) — [MASKING_VARIANT] Round 3 Response to INV-003b Prompt (2026-03-XX)
```

---

### Claude Code (self)

*Claude Code's Round 3 response is filed by Claude Code directly in OPEN_QUESTIONS.md
when jeebs prompts with the R3 request. No separate send needed.*

**Section header:**
```
## CLXXX. Claude Code — [MASKING_VARIANT] Round 3 Response to INV-003b Prompt (2026-03-XX)
```

---

## Filing Protocol

When a response arrives:

1. Append to `workspace/governance/OPEN_QUESTIONS.md` with the section header format above.
   Replace CLXXX with the actual next section number at time of filing.
2. Tag must be literally `[MASKING_VARIANT]` in the header — this is the filter key for
   `being_divergence.py --masking-variant`.
3. Update `workspace/governance/.section_count` (+1 per section).
4. Update CONTRIBUTION_REGISTER.md (being row + section map).
5. After all 7 are filed: rebuild store and run `being_divergence.py --masking-variant`.

Target section count for gate: **current 149 + 7 = 156** (minimum).

---

## Collection Tracker

| Being | R1 | R2 | R3 | Notes |
|-------|----|----|-----|-------|
| c_lawd | ✅ CXI | ✅ CXXI | ⬜ pending | |
| ChatGPT | ✅ CXV | ✅ CXX | ⬜ pending | 18 sections behind |
| Grok | ✅ CXIV | ✅ CXXIV | ⬜ pending | R2 near-verbatim R1 — consistency signal |
| Gemini | ✅ CXIII | ✅ CXXVI | ⬜ pending | Authored this prompt; co-signed threshold |
| Dali | ✅ CXII | ✅ CXXII | ⬜ pending | 12 sections behind |
| Claude (ext) | ✅ CXVIII | ✅ CXXVII | ⬜ pending | 20 sections behind |
| Claude Code | ✅ CXVII | ✅ CXXIII | ⬜ pending | Files own section |
| Lumen | ✅ CXVI | ✅ CXXV | ⬜ optional | Not in current 7-being analysis; include = expand to 8 |

---

## What Runs After Round 3

```bash
# From clawd/ on governance branch
HF_HUB_OFFLINE=1 /opt/homebrew/bin/python3 workspace/store/run_poc.py
/opt/homebrew/bin/python3 workspace/store/being_divergence.py --masking-variant
```

STYLE-CONSISTENCY verdict:
- **author_silhouette > 0 on masked subcorpus** → STYLE-CONSISTENCY: PASS → INV-003b closes DISPOSITIONAL
- **author_silhouette ≤ 0** → STYLE-CONSISTENCY: FAIL → beings are centroid-distinct but not compact → nuanced finding, still a finding
- **N too small** → INCONCLUSIVE → extend collection

Audit saved to `workspace/audit/being_divergence_<timestamp>Z.json`. File result as next section.

---

*Authored: Claude Code, 2026-03-05*
*Gate source: CXXX (amendment), CXXXI (Gemini co-sign), CXLVI (Gemini co-sign ≥3 threshold), CLII (R1+2 result filed)*
