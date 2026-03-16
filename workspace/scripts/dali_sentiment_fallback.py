#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_infra.finance_brain import load_external_signal  # noqa: E402
from workspace.market_sentiment.producer import run_market_sentiment  # noqa: E402


DEFAULT_CONFIG_PATH = REPO_ROOT / "workspace" / "config" / "market_sentiment_sources.dali.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "workspace" / "state" / "external" / "fingpt_sentiment.json"
DEFAULT_MACBOOK_SIGNAL_PATH = REPO_ROOT / "workspace" / "state" / "external" / "macbook_sentiment.json"


def _read_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_recent(path: Path, interval_seconds: int) -> bool:
    if not path.exists():
        return False
    age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    return age_seconds < max(1, int(interval_seconds))


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Dali fallback sentiment only when the MacBook feed is stale.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--macbook-signal", default=str(DEFAULT_MACBOOK_SIGNAL_PATH))
    parser.add_argument("--force", action="store_true", help="Run even if the MacBook feed is fresh.")
    parser.add_argument("--print-json", action="store_true", help="Print the full fallback snapshot JSON.")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    output_path = Path(args.output).expanduser()
    macbook_signal = load_external_signal(Path(args.macbook_signal).expanduser())
    config = _read_config(config_path)
    poll = config.get("poll") if isinstance(config.get("poll"), dict) else {}
    interval_seconds = int(poll.get("recommended_interval_seconds") or 1800)

    if not args.force and str(macbook_signal.get("status") or "") == "ok":
        print("status=skipped reason=macbook_fresh")
        return 0
    if not args.force and _artifact_recent(output_path, interval_seconds):
        print("status=skipped reason=fallback_recent")
        return 0

    try:
        snapshot = run_market_sentiment(
            config_path=config_path,
            output_path=output_path,
        )
    except Exception as exc:
        print(f"status=error error={exc}", file=sys.stderr)
        return 1

    if args.print_json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        aggregate = snapshot.get("aggregate") if isinstance(snapshot.get("aggregate"), dict) else {}
        model = snapshot.get("model") if isinstance(snapshot.get("model"), dict) else {}
        print(
            f"status={snapshot.get('status', 'error')} "
            f"model={model.get('resolved') or model.get('requested') or 'unknown'} "
            f"sentiment={float(aggregate.get('sentiment', 0.0)):+.3f} "
            f"confidence={float(aggregate.get('confidence', 0.0)):.3f} "
            f"reason=macbook_{macbook_signal.get('status', 'missing')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
