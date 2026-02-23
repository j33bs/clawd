# AUDIT_SNAPSHOT.md — Last Audit Signals

Updated after each audit completes. Compact record for quick comparison.

| Signal | Value |
|---|---|
| **date** | 2026-02-23 |
| **commit** | *not checked this audit — session focused on governance docs* |
| **regression** | NOT RUN (pending; scripts/regression.sh expects missing node files) |
| **verify** | NOT RUN |
| **gateway** | unknown (not checked) |
| **telegram** | unknown (not checked this session) |
| **cron_jobs** | 5 (unchanged from 2026-02-08) |
| **agents** | 2 (main/Dali, claude-code) |
| **governance_changed** | yes — see GOVERNANCE_LOG.md entries 2026-02-23 |
| **secrets_in_tracked** | unresolved from prior audit (Groq API key; needs rotation) |
| **open_handoffs** | unknown (not checked) |
| **shrine_reading** | this audit — OPEN_QUESTIONS.md grew; some machinery touched (trails.py, phi_metrics.md overhaul, nomenclature fixes across 4 canonical docs) |
| **engine_signals** | trails.py: measure_inquiry_momentum() added (INV-005 partial); phi_metrics.md: ablation protocol defined (INV-001 methodology closed, data row pending); 4 nomenclature fixes across canonical docs |
| **open_investigations** | INV-001 (Φ proxy, data pending), INV-002 (reservoir null test), INV-003 (continuity comparison), INV-004 (wander attribution), INV-005 (instrument now exists), INV-006 (ghost presence), INV-007 (same-substrate divergence) |

---

**Prior snapshot:** 2026-02-08 (15-day gap — no audit ran in between)
**Next audit should:** run regression.sh, inspect open_handoffs count, check Telegram status, file INV-001 first data row
