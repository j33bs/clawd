#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.reservoir import Reservoir  # type: ignore


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _select_memory_files(memory_dir: Path, last_n: int, window_hours: int) -> list[Path]:
    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    files = []
    for f in memory_dir.glob("*.md"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
        if mtime >= cutoff:
            files.append((mtime, f))
    files.sort(key=lambda x: (x[0], x[1].name), reverse=True)
    return [f for _, f in files[: last_n if last_n > 0 else None]]


def run_prototype(memory_files: list[Path], seed: int = 23) -> dict[str, Any]:
    reservoir = Reservoir.init(dim=32, leak=0.35, spectral_scale=0.9, seed=seed)
    processed: list[dict[str, Any]] = []
    for f in memory_files:
        text = f.read_text(encoding="utf-8", errors="ignore")[:4000]
        state = reservoir.step({"content": text}, {"path": str(f.name)}, {"length": len(text)})
        readout = reservoir.readout(state)
        processed.append(
            {
                "path": str(f.relative_to(REPO_ROOT)),
                "chars_used": len(text),
                "routing_confidence": float((readout.get("routing_hints") or {}).get("confidence", 0.0)),
            }
        )
    final_state = reservoir.snapshot()
    return {
        "timestamp_utc": _utc_now(),
        "seed": seed,
        "input_count": len(memory_files),
        "inputs": processed,
        "derived": {
            "label": "derived_temporal_integration_artifact",
            "reservoir_state": final_state,
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    ts = report["timestamp_utc"].replace("-", "").replace(":", "")
    out_dir = REPO_ROOT / "workspace" / "reports" / "sleep_consolidation"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_md = out_dir / f"{ts}_consolidation_report.md"
    derived_json = out_dir / f"{ts}_derived.json"

    lines = [
        f"# Sleep Consolidation Prototype Report ({report['timestamp_utc']})",
        "",
        "This report is append-only and marks all generated artifacts as derived.",
        "",
        f"- Input artifacts: {report['input_count']}",
        f"- Seed: {report['seed']}",
        "",
        "## Inputs",
    ]
    for item in report["inputs"]:
        lines.append(f"- {item['path']} (chars_used={item['chars_used']}, routing_confidence={item['routing_confidence']:.6f})")
    lines.append("")
    lines.append("## Derived Artifact")
    lines.append(f"- {derived_json.relative_to(REPO_ROOT)}")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    derived_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_md, derived_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Sleep consolidation prototype (offline, manual)")
    parser.add_argument("--memory-dir", default=str(REPO_ROOT / "workspace" / "memory"))
    parser.add_argument("--last-n", type=int, default=5)
    parser.add_argument("--window-hours", type=int, default=48)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = _select_memory_files(Path(args.memory_dir), args.last_n, args.window_hours)
    report = run_prototype(files, seed=args.seed)
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "inputs": [str(f) for f in files], "input_count": len(files)}, sort_keys=True))
        return 0

    report_md, derived_json = write_outputs(report)
    print(
        json.dumps(
            {
                "status": "ok",
                "report": str(report_md.relative_to(REPO_ROOT)),
                "derived": str(derived_json.relative_to(REPO_ROOT)),
                "input_count": len(files),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
