# 100 Changes for c_lawd Stabilization — Derived from OPEN_QUESTIONS.md

## Phase 1: Φ (Integrated Information) Measurement Infrastructure

1. Fill first row in `workspace/governance/phi_metrics.md` with baseline cold-start measurement
2. Define session boundary for Φ measurement (one coordinated task across C_Lawd + Dali)
3. Implement cut-set protocol: remove each major communication edge and compare performance
4. Create `workspace/scripts/phi_measurement.sh` to automate integration calculation steps
5. Add `phi_metrics.md` validation test: row must be added after measurement run
6. Add `phi_metrics.md` report generator (plot over time)
7. Add witness log entry each time Φ is recorded
8. Define “minimum viable Φ session” rubric in governance docs
9. Add automated “Φ overdue” reminder in heartbeat system
10. Store Φ sessions in `workspace/state/phi_sessions.jsonl`

## Phase 2: Inquiry Momentum (Reservoir + Wander) Wiring

11. Implement live inquiry_momentum logging for wander sessions (`wander_log.jsonl`)
12. Wire existing INV-005 instrument into cron wander loop
13. Add `observe_outcome()` call after wander completion
14. Add `observe_outcome()` deterministic test: wander produces outcome record
15. Implement reservoir propagation into routing order (focused vs exploratory)
16. Make downstream systems read `response_plan.mode`
17. Add explicit reservoir value log in `workspace/state/tacti_cr/events.jsonl`
18. Add “reservoir state” snapshot to dashboard status page
19. Add “reservoir state” unit test: must toggle modes correctly
20. Document reservoir semantics in `workspace/docs/reservoir_mode.md`

## Phase 3: Pause Gate + Silence Policy Governance

21. Normalize pause event logs into `pause_check_events.jsonl`
22. Add deterministic unit tests for pause decision logging
23. Add “pause gate” policy contract section to governance docs
24. Implement optional “explain pause” debug output
25. Add “pause sentinel” invariant: never send empty response
26. Implement telegram pause debug logging (`OPENCLAW_TELEGRAM_DEBUG`)
27. Add tests for pause sentinel in telegram message handler
28. Add dashboard display of pause decisions (optional)
29. Document pause gate feature flags in runbook
30. Add “pause gate health check” to stabilization status surface

## Phase 4: Telegram Channel Reliability + Admission Policy

31. Add diagnostic detection for telegram admission lockout
32. Add unit test for telegram lockout detection
33. Implement reversible runtime fix playbook (allowlist/pairing)
34. Add “telegram inbound without outbound” heuristic to diagnostics
35. Add telegram send latency metric (`elapsed_ms`) to debug log
36. Add test asserting `elapsed_ms` is logged
37. Add “telegram channel probe ok but inert” runbook section
38. Add “telegram allowlist empty” warning in gateway status
39. Add “telegram pairing pending” warning in diagnostics
40. Create audit template for telegram restoration events

## Phase 5: Gateway Lifecycle + Control UI Hardening

41. Detect “LaunchAgent loaded but port not listening” state
42. Add unit test for loaded-but-not-listening detection
43. Add `launchctl kickstart` recovery hint in diagnostics
44. Add curl probes for IPv4/IPv6 loopback in status script
45. Add gateway bind validation (loopback vs public)
46. Add “gateway.mode=local” config block detection
47. Add runbook section: dashboard unreachable recovery steps
48. Add “gateway health gate” to stabilization status surface
49. Add regression test for gateway diagnostics summary output
50. Add audit doc template for gateway recovery

## Phase 6: Drift Isolation + Live Writer Containment

51. Add drift scan that surfaces excluded-path modifications without staging
52. Add drift scan to stabilization status surface
53. Add runbook: how to quiesce live writers safely
54. Implement “excluded drift cleanup” helper script (read-only suggestions)
55. Add test: drift scan flags excluded paths when git porcelain includes them
56. Add docs: drift policy contract (what is excluded, why)
57. Add CI guard: forbid committing excluded live-mutating paths
58. Add pre-commit hook to block excluded paths by default
59. Add “drift evidence” section to audit templates
60. Add rollback guidance for drift containment changes

## Phase 7: Knowledge Base Sync Visibility (Read-only)

61. Add read-only knowledge base metadata report (last sync time, entity counts)
62. Add warning when KB is stale beyond threshold (diagnostic only)
63. Add unit test for KB metadata parsing
64. Add docs: KB sync lifecycle (what writes, when)
65. Add status surface output: KB freshness line
66. Add optional logging of KB metadata snapshots (opt-in)
67. Add runbook entry: KB drift triage
68. Add “KB drift excluded path” note in drift scan output
69. Add audit section: KB sync evidence
70. Add placeholder for later full KB ingestion governance PR

## Phase 8: External Daemon Health (AIN + QMD)

71. Add AIN port probe (18990) to stabilization status
72. Add QMD port probe (8181) to stabilization status
73. Add timeout handling and clear error messages for probes
74. Add tests mocking open/closed ports
75. Add docs: what AIN/QMD do, why health matters
76. Add runbook: restarting daemons safely (macOS)
77. Add optional auto-restart suggestion output (no action by default)
78. Add “daemon unhealthy” warning level semantics
79. Add audit notes for daemon failures
80. Add future: integrate daemon health into dashboard

## Phase 9: Disk Pressure + Cleanup Hints

81. Add disk usage summary to stabilization status
82. Add threshold-based warning (diagnostic only)
83. Add cleanup hints (safe, reversible, no auto-delete)
84. Add unit test for disk warning logic (mock)
85. Add runbook: disk pressure response
86. Add audit evidence guidelines for disk issues
87. Add future: optional user-confirmed cleanup tool
88. Add log output formatting standard for disk metrics
89. Add low-noise mode (suppress warnings unless severe)
90. Add “disk trend” placeholder for later

## Phase 10: Cron/Launchctl Health + Unified Surface

91. Create unified stabilization status surface (`stabilization_status.py`)
92. Add telegram latency aggregation (debug-log based, opt-in)
93. Add gateway lifecycle checks
94. Add routing/auth-profile diagnostic (read-only)
95. Add drift detection with excluded-path surfacing
96. Add knowledge-base sync visibility (read-only metadata)
97. Add AIN port probe (18990)
98. Add QMD port probe (8181)
99. Add disk pressure diagnostics + cleanup hint
100. Add launchctl/cron health visibility (diagnostic only)
