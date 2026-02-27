# Quiesce writer evidence (20260227T022512Z)

## git status --porcelain=v1
```
 M workspace/research/findings.json
 M workspace/research/queue.json
 M workspace/research/wander_log.md
?? governance/
?? workspace/audit/quiesce_writer_events_jsonl_20260227T022512Z.md
?? workspace/profile/
```

## Key writer hits
```
./README.md:55:When enabled, runtime TACTI events write to `workspace/state_runtime/tacti_cr/events.jsonl` (ignored); `workspace/state/tacti_cr/events.jsonl` remains a deterministic tracked stub.
./workspace/tacti/README.md:118:- Unified runtime events are append-only JSONL at `workspace/state/tacti_cr/events.jsonl`.
./workspace/state_runtime/README.md:6:- `workspace/state/tacti_cr/events.jsonl`
./workspace/state_runtime/README.md:21:- It can also write to `workspace/state/tacti_cr/events.jsonl` via TACTI fallback paths; that protected path is quiesce-guarded.
./workspace/tacti/events.py:12:DEFAULT_PATH = Path("workspace/state/tacti_cr/events.jsonl")
./workspace/tacti/events.py:14:PROTECTED_PATH = Path("workspace/state/tacti_cr/events.jsonl")
./workspace/scripts/verify_tacti_cr_novel10_fixture.py:39:    parser.add_argument("--events-path", default="workspace/state/tacti_cr/events.jsonl")
./workspace/scripts/verify_tacti_cr_novel10_fixture.sh:25:  --events-path workspace/state/tacti_cr/events.jsonl \
./workspace/scripts/verify_tacti_cr_novel10_fixture.sh:31:  --events-path workspace/state/tacti_cr/events.jsonl
./workspace/scripts/policy_router.py:498:            if str(path).endswith("workspace/state/tacti_cr/events.jsonl"):
./workspace/scripts/quiesce_status.sh:10:echo "- workspace/state/tacti_cr/events.jsonl"
```

## workspace/tacti/events.py (writer boundary)
```
     1	"""Unified TACTI-CR runtime event contract (append-only JSONL)."""
     2	
     3	from __future__ import annotations
     4	
     5	import json
     6	import os
     7	import sys
     8	from datetime import datetime, timezone
     9	from pathlib import Path
    10	from typing import Any, Iterable
    11	
    12	DEFAULT_PATH = Path("workspace/state/tacti_cr/events.jsonl")
    13	QUIESCE_ENV = "OPENCLAW_QUIESCE"
    14	PROTECTED_PATH = Path("workspace/state/tacti_cr/events.jsonl")
    15	
    16	
    17	def _utc_iso_z(now: datetime | None = None) -> str:
    18	    dt = now or datetime.now(timezone.utc)
    19	    if dt.tzinfo is None:
    20	        dt = dt.replace(tzinfo=timezone.utc)
    21	    else:
    22	        dt = dt.astimezone(timezone.utc)
    23	    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    24	
    25	
    26	def _coerce_json(payload: Any) -> dict[str, Any]:
    27	    if not isinstance(payload, dict):
    28	        raise TypeError("payload must be a dict")
    29	    try:
    30	        json.dumps(payload, ensure_ascii=True)
    31	    except TypeError as exc:
    32	        raise TypeError("payload must be JSON-serializable") from exc
    33	    return payload
    34	
    35	
    36	def _resolve(path: Path | str | None = None) -> Path:
    37	    target = Path(path) if path is not None else DEFAULT_PATH
    38	    if target.is_absolute():
    39	        return target
    40	    root = Path(__file__).resolve().parents[2]
    41	    return root / target
    42	
    43	
    44	def _is_quiesced() -> bool:
    45	    return os.getenv(QUIESCE_ENV) == "1"
    46	
    47	
    48	def _is_protected_target(path: Path) -> bool:
    49	    root = Path(__file__).resolve().parents[2]
    50	    protected = (root / PROTECTED_PATH).resolve()
    51	    try:
    52	        return path.resolve() == protected
    53	    except Exception:
    54	        return str(path) == str(protected)
    55	
    56	
    57	def emit(event_type: str, payload: dict, *, now: datetime | None = None, session_id: str | None = None) -> None:
    58	    path = _resolve()
    59	    if _is_quiesced() and _is_protected_target(path):
    60	        print(f"QUIESCED: skipping write to {path}", file=sys.stderr)
    61	        return
    62	    path.parent.mkdir(parents=True, exist_ok=True)
    63	    if not isinstance(event_type, str) or not event_type.strip():
    64	        return
    65	    try:
    66	        coerced_payload = _coerce_json(payload)
    67	    except TypeError:
    68	        coerced_payload = {"_stringified": str(payload)}
    69	    row = {
    70	        "ts": _utc_iso_z(now),
    71	        "type": str(event_type),
    72	        "payload": coerced_payload,
    73	        "schema": 1,
    74	    }
    75	    if session_id:
    76	        row["session_id"] = str(session_id)
    77	    try:
    78	        with path.open("a", encoding="utf-8") as handle:
    79	            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    80	    except Exception as exc:
    81	        print(f"warning: tacti_cr.events emit failed: {exc}", file=sys.stderr)
    82	
    83	
    84	def read_events(path: Path | str | None = None) -> Iterable[dict[str, Any]]:
    85	    target = _resolve(path)
    86	    if not target.exists():
    87	        return []
    88	    out: list[dict[str, Any]] = []
    89	    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
    90	        if not line.strip():
    91	            continue
    92	        try:
    93	            row = json.loads(line)
    94	        except Exception as exc:
    95	            raise ValueError(f"malformed jsonl at line {lineno}") from exc
    96	        if not isinstance(row, dict):
    97	            raise ValueError(f"malformed event object at line {lineno}")
    98	        out.append(row)
    99	    return out
   100	
   101	
   102	def summarize_by_type(path: Path | str | None = None) -> dict[str, int]:
   103	    counts: dict[str, int] = {}
   104	    for row in read_events(path):
   105	        key = str(row.get("type") or row.get("event") or "")
   106	        if not key:
   107	            continue
   108	        counts[key] = counts.get(key, 0) + 1
   109	    return counts
   110	
   111	
   112	__all__ = ["DEFAULT_PATH", "emit", "read_events", "summarize_by_type", "_coerce_json"]
```

## workspace/scripts/policy_router.py (fallback writer + quiesce guard)
```
   486	def save_circuit_state(state, path=CIRCUIT_FILE):
   487	    path.parent.mkdir(parents=True, exist_ok=True)
   488	    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
   489	
   490	
   491	def log_event(event_type, detail=None, path=EVENT_LOG):
   492	    if os.environ.get("OPENCLAW_QUIESCE") == "1":
   493	        try:
   494	            if Path(path).resolve() == TACTI_EVENT_LOG.resolve():
   495	                print(f"QUIESCED: skipping write to {path}", file=sys.stderr)
   496	                return
   497	        except Exception:
   498	            if str(path).endswith("workspace/state/tacti_cr/events.jsonl"):
   499	                print(f"QUIESCED: skipping write to {path}", file=sys.stderr)
   500	                return
   501	    path.parent.mkdir(parents=True, exist_ok=True)
   502	    entry = {
   503	        "ts": int(time.time() * 1000),
   504	        "event": event_type,
   505	    }
   506	    if detail:
   507	        entry["detail"] = _redact_detail(detail)
   508	    try:
   509	        with open(path, "a", encoding="utf-8") as f:
   510	            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
   511	    except Exception:
   512	        pass
   513	
   514	
   515	def _tacti_event(event_type, detail):
   516	    if callable(tacti_emit):
   517	        try:
   518	            tacti_emit(str(event_type), detail if isinstance(detail, dict) else {"detail": detail})
   519	            return
   520	        except Exception:
   521	            pass
   522	    log_event(event_type, detail=detail, path=TACTI_EVENT_LOG)
   523	
   524	
   525	def _flag_enabled(name):
   526	    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}
   527	
   528	
   529	def _active_inference_enabled():
   530	    return _flag_enabled("OPENCLAW_ACTIVE_INFERENCE") or _flag_enabled("ENABLE_ACTIVE_INFERENCE")
```

## tools/run_checks.sh (local gates path)
```
     1	#!/usr/bin/env bash
     2	set -euo pipefail
     3	
     4	# Local usage:
     5	#   OPENCLAW_LOCAL_GATES=1 tools/run_checks.sh
     6	# Local gates enforce launchagent alignment and machine-surface contract tripwire.
     7	if [[ "${OPENCLAW_LOCAL_GATES:-0}" == "1" ]]; then
     8	  echo "[local-gates] enabled"
     9	  if [[ "$(uname -s)" == "Darwin" ]]; then
    10	    echo "[local-gates] checking launchagent alignment"
    11	    if ! tools/check_launchagent_points_to_repo.sh; then
    12	      echo "[local-gates] FAIL launchagent alignment (see tools/check_launchagent_points_to_repo.sh)" >&2
    13	      exit 1
    14	    fi
    15	    echo "[local-gates] PASS launchagent alignment"
    16	
    17	    echo "[local-gates] running machine-surface tripwire"
    18	    if ! tools/reliability_tripwire.sh; then
    19	      echo "[local-gates] FAIL machine-surface tripwire (see tools/reliability_tripwire.sh)" >&2
    20	      exit 1
    21	    fi
    22	    echo "[local-gates] PASS machine-surface tripwire"
    23	  else
    24	    echo "[local-gates] skipped (non-macOS)"
    25	  fi
    26	fi
    27	
    28	python3 tools/check_ignored_tracking.py
    29	python3 -m unittest discover -s tests_unittest
    30	python3 tools/preflight_trading_env.py
    31	python3 tools/regression_guard.py
```

## Phase 4 verification

### node --test tests/quiesce_writer_no_runtime_writes.test.js
```
✔ OPENCLAW_QUIESCE=1 blocks tacti events.jsonl writes (73.516208ms)
ℹ tests 1
ℹ suites 0
ℹ pass 1
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 172.437917
```

### node --test tests/no_html_on_machine_routes.test.js
```
✔ machine surface never serves html and unknown machine paths are JSON 404 (21.159208ms)
ℹ tests 1
ℹ suites 0
ℹ pass 1
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 118.024833
```

### OPENCLAW_LOCAL_GATES=1 OPENCLAW_QUIESCE=1 tools/run_checks.sh || true
```
INFO: OPENCLAW_QUIESCE=1
[local-gates] enabled
[local-gates] checking launchagent alignment
PASS: launchagent points to repo wrapper (/Users/heathyeager/clawd/scripts/run_openclaw_gateway_repo.sh)
[local-gates] PASS launchagent alignment
[local-gates] running machine-surface tripwire
PASS /health: status=200 content-type=application/json; charset=utf-8
PASS /ready: status=503 content-type=application/json; charset=utf-8
PASS /diag/runtime: status=200 content-type=application/json; charset=utf-8
PASS /api/does-not-exist: status=404 content-type=application/json; charset=utf-8
PASS /diag/does-not-exist: status=404 content-type=application/json; charset=utf-8
reliability tripwire passed for http://127.0.0.1:18789
[local-gates] PASS machine-surface tripwire
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
witness_paths_read=audit/commit_audit_log.jsonl
witness_paths_write=state_runtime/teamchat/witness_ledger.jsonl
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
witness_paths_read=audit/commit_audit_log.jsonl
witness_paths_write=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl
⚠️ witness ledger commit skipped: witness_commit_failed: ledger_path=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl audit_path=audit/commit_audit_log.jsonl error=RuntimeError: simulated_witness_commit_failure
==================================================
✅ AUDIT PASSED - Safe to commit
==================================================
==================================================
🔍 PRE-COMMIT AUDIT
==================================================
✅ tests_pass: ok
witness_paths_read=audit/commit_audit_log.jsonl
witness_paths_write=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl
❌ witness ledger commit failed (strict): witness_commit_failed: ledger_path=/Users/heathyeager/clawd/workspace/state_runtime/teamchat/witness_ledger.jsonl audit_path=audit/commit_audit_log.jsonl error=RuntimeError: simulated_witness_commit_failure
==================================================
❌ AUDIT FAILED - Commit blocked
==================================================
system2_stray_auto_ingest: ok
moved:
- moltbook_registration_plan.md -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp0oxb0_pj/home/.openclaw/ingest/moltbook_registration_plan.md
- .openclaw/workspace-state.json -> /private/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp0oxb0_pj/home/.openclaw/workspace-state.json
backups:
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp0oxb0_pj/overlay/quarantine/20260227-122722/repo_root_governance
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=dir
STOP (fail-closed: known stray path exists as dir/symlink)
path=.openclaw/workspace-state.json
kind=symlink
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp_x9d3b8q/overlay/quarantine/20260227-122724/repo_root_governance
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpp5f8ol8w/overlay/quarantine/20260227-122725/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/other/place.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp36usg18v/overlay/quarantine/20260227-122725/repo_root_governance
STOP (unrelated workspace drift detected)
untracked_disallowed_paths:
- core/integration/other.bin
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmp_6n4f5at/overlay/quarantine/20260227-122725/repo_root_governance
STOP (teammate auto-ingest requires regular files; no symlinks/dirs)
path=core/integration/econ_adapter.js
governance_auto_ingest: ok
quarantined_files=['AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md']
quarantine_dir=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpow8uyvlr/overlay/quarantine/20260227-122725/repo_root_governance
STOP (teammate auto-ingest safety scan failed)
flagged_paths:
- core/integration/econ_adapter.js: rule_openai_sk
quarantine_root=/var/folders/n7/1czk3b2d0_jbr7ngjp_6fth80000gn/T/tmpow8uyvlr/quarantine/openclaw-quarantine-20260227-122725
PYTHON_EXE=/opt/homebrew/opt/python@3.14/bin/python3.14
PYTHON_VER=3.14.3 (main, Feb  3 2026, 15:32:20) [Clang 17.0.0 (clang-1700.6.3.2)]
PYTHON3_WHICH=/opt/homebrew/bin/python3
REPO_ROOT=/Users/heathyeager/clawd
BASE_CONFIG=/Users/heathyeager/clawd/pipelines/system1_trading.yaml
BASE_CONFIG_EXISTS=0
FEATURES_OVERLAY=/Users/heathyeager/clawd/pipelines/system1_trading.features.yaml
FEATURES_OVERLAY_EXISTS=1
```

### git status --porcelain=v1 (post verification)
```
 M tools/run_checks.sh
 M workspace/research/findings.json
 M workspace/research/queue.json
 M workspace/research/wander_log.md
 M workspace/scripts/policy_router.py
 M workspace/tacti/events.py
?? governance/
?? tests/quiesce_writer_no_runtime_writes.test.js
?? workspace/audit/quiesce_writer_events_jsonl_20260227T022512Z.md
?? workspace/profile/
```

### events drift check
```
OK: workspace/state/tacti_cr/events.jsonl not modified
```
