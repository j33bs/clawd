#!/usr/bin/env python3
"""Deterministic offline fixture run for Novel-10 event coverage."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))
if str(REPO_ROOT / "workspace" / "hivemind") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "hivemind"))

from tacti_cr.events import DEFAULT_PATH, summarize_by_type
import tacti_cr.events as tacti_events
from tacti_cr.novel10_contract import FEATURE_FLAGS
from tacti_cr.arousal_oscillator import ArousalOscillator
from tacti_cr.temporal import TemporalMemory
from tacti_cr.dream_consolidation import run_consolidation
from tacti_cr.semantic_immune import assess_content
from tacti_cr.prefetch import prefetch_context, PrefetchCache
from tacti_cr.mirror import update_from_event
from tacti_cr.valence import update_valence
from hivemind.stigmergy import StigmergyMap
import policy_router


def _parse_now(text: str) -> datetime:
    value = text.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_messages(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _set_offline_guards() -> None:
    os.environ["TEAMCHAT_LIVE"] = "0"
    os.environ["TEAMCHAT_AUTO_COMMIT"] = "0"
    os.environ["TEAMCHAT_ACCEPT_PATCHES"] = "0"


def _enable_all_flags() -> None:
    for key in FEATURE_FLAGS:
        os.environ[key] = "1"


def _prepare_temp_repo(fixtures_dir: Path) -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix="novel10_fixture_"))
    (temp_root / "workspace" / "memory").mkdir(parents=True, exist_ok=True)
    (temp_root / "workspace" / "hivemind" / "data").mkdir(parents=True, exist_ok=True)
    for day in ("2026-02-18.md", "2026-02-19.md"):
        src = fixtures_dir / "memory" / day
        dst = temp_root / "workspace" / "memory" / day
        shutil.copyfile(src, dst)
    return temp_root


def run_fixture(fixtures_dir: Path, events_path: Path, now_dt: datetime, no_ui: bool) -> dict[str, int]:
    _set_offline_guards()

    if events_path.exists():
        events_path.unlink()
    events_path.parent.mkdir(parents=True, exist_ok=True)
    tacti_events.DEFAULT_PATH = events_path

    temp_root = _prepare_temp_repo(fixtures_dir)
    try:
        messages = _load_messages(fixtures_dir / "teamchat" / "messages_stub.jsonl")
        token_stream = " ".join(str(m.get("content", "")) for m in messages)

        # Arousal + expression + valence bias via existing router hook.
        router = policy_router.PolicyRouter()
        _ = ArousalOscillator(repo_root=temp_root).explain(now_dt)
        intent_cfg = router._intent_cfg("coding")
        router._tacti_runtime_controls(
            "coding",
            intent_cfg,
            {
                "input_text": token_stream,
                "agent_id": "fixture-agent",
                "valence": -0.4,
            },
        )

        # Temporal drift and reset through temporal memory store.
        temporal = TemporalMemory(agent_scope="fixture", sync_hivemind=False)
        temporal.store(messages[1]["content"], timestamp=now_dt)

        # Dream consolidation on isolated fixture memory.
        dream_res = run_consolidation(temp_root, day="2026-02-19", now=now_dt)
        if not dream_res.get("ok"):
            raise RuntimeError(f"dream consolidation failed: {dream_res}")

        # Semantic immune accepted + quarantined events (deterministic threshold setup).
        os.environ["TACTI_CR_IMMUNE_MIN_COUNT"] = "1"
        assess_content(temp_root, "normal routing memory note for policy checks")
        ood = "ZXQJ-9911 entropy lattice xenogram quasar glyph payload"
        immune_res = assess_content(temp_root, ood)
        if not immune_res.get("quarantined"):
            raise RuntimeError(f"semantic immune did not quarantine OOD input: {immune_res}")

        # Stigmergy deposit + query.
        stig = StigmergyMap(path=temp_root / "workspace" / "state" / "stigmergy" / "map.json")
        stig.deposit_mark("routing", 0.9, 0.01, "fixture", now=now_dt)
        stig.query_marks(now=now_dt, top_n=5)

        # Prefetch predicted topics + cache put (+ hit-rate optional).
        kb = json.loads((fixtures_dir / "kb" / "kb_stub.json").read_text(encoding="utf-8"))

        def query_fn(topic: str) -> list[str]:
            out: list[str] = []
            for k, values in kb.items():
                if topic in k or topic in " ".join(values).lower():
                    out.extend(values)
            return out

        prefetch_context(token_stream, query_fn, repo_root=temp_root)
        PrefetchCache(repo_root=temp_root).record_hit(True)

        # Mirror + valence.
        update_from_event(
            "coder",
            {"event": "planner_review", "data": {"decision": "revise", "latency_ms": 123}},
            repo_root=temp_root,
        )
        update_valence("coder", {"success": True, "retry_loops": 0}, repo_root=temp_root, now=now_dt)

        # TeamChat offline loop for coverage (events emitted through team_chat hook).
        out_dir = temp_root / "workspace" / "teamchat_fixture"
        cmd = [
            "python3",
            str(REPO_ROOT / "workspace" / "scripts" / "team_chat.py"),
            "--task",
            "Fixture run for novel10 event coverage",
            "--session-id",
            "novel10-fixture",
            "--output-root",
            str(out_dir),
            "--max-cycles",
            "1",
            "--max-commands-per-cycle",
            "2",
            "--auto-commit",
            "0",
            "--accept-patches",
            "0",
        ]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"team_chat fixture failed rc={proc.returncode}: {proc.stderr.strip()}")

    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    counts = summarize_by_type(events_path)
    for key in sorted(counts):
        print(f"{key},{counts[key]}")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Novel-10 fixture coverage")
    parser.add_argument("--fixtures-dir", default=str(REPO_ROOT / "workspace" / "fixtures" / "novel10"))
    parser.add_argument("--events-path", default=str(DEFAULT_PATH))
    parser.add_argument("--now", default="2026-02-19T13:00:00Z")
    parser.add_argument("--enable-all", action="store_true")
    parser.add_argument("--no-ui", action="store_true")
    args = parser.parse_args()

    fixtures_dir = Path(args.fixtures_dir)
    events_path = Path(args.events_path)
    if not events_path.is_absolute():
        events_path = REPO_ROOT / events_path

    if args.enable_all:
        _enable_all_flags()

    now_dt = _parse_now(args.now)
    try:
        run_fixture(fixtures_dir, events_path, now_dt, args.no_ui)
    except Exception as exc:
        print(f"fixture run failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
