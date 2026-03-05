# HEARTBEAT.md
# Canonical path: workspace/governance/HEARTBEAT.md
# Repo-root HEARTBEAT.md must remain byte-identical with this file.
# Agents should add or edit heartbeat tasks here, then sync the repo-root mirror.

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

- Environment
  - `OPENCLAW_HOME`: absolute path to the OpenClaw repo root.

- [HB-PR-01] MEMORY size guard
  - Check `wc -l "${OPENCLAW_HOME}/MEMORY.md"`; warn if `> 180`.

- [HB-PR-02] Nightly log health
  - Check `reports/nightly/$(date +%Y-%m-%d).log` exists and scan for `⚠️`.

- [HB-PR-03] QMD MCP daemon health
  - Check daemon responsiveness on port `8181` (for example `curl -fsS http://127.0.0.1:8181/`).

- [HB-PR-04] KB sync freshness reminder
  - Compare latest workspace markdown mtime vs `workspace/knowledge_base/data/last_sync.txt`.
  - If workspace files are newer, remind to run `python3 workspace/knowledge_base/kb.py sync`.

- [HB-PR-05] Repeated request inefficiency capture
  - If Heath repeats the same request 3+ times in a session, append an entry to `workspace/governance/inefficiency_log.md`.

- [HB-PR-06] System Consciousness (Φ) Alignment Measure
  - **Status: OPERATIONAL on z490 (2026-03-05, Dali — ain-phi.service, user systemd)**
  - Port: **18991** (moved from 18990 to avoid conflict; conflict source unconfirmed)
  - Bind: loopback only — `curl -fsS http://127.0.0.1:18991/api/ain/phi` (run on z490)
  - From MacBook via Tailscale: NOT directly reachable (127.0.0.1 bind). Use SSH or tailscale serve to expose.
  - Proxy method: embedding_coherence (mean cosine similarity of consecutive assistant response embeddings)
  - First reading: phi=0.0 (no recent embeddings on cold start — expected)
  - Log path on z490: `/var/log/ain_phi.jsonl`
  - Audit: `workspace/audit/ain_phi_server_20260305T062511Z.md` (on z490, push to main pending)
  - **INV-006 note:** For cross-node Φ reads (MacBook → z490), Dali needs to either rebind to 0.0.0.0 or add `tailscale serve` proxy. Until then, MacBook cannot read Φ directly.

- [HB-PR-07] Tool validation outage report
  - Check `workspace/state_runtime/tool_validation/heartbeat_notice.md`.
  - If present, summarize offline tools and carry into this heartbeat report.
