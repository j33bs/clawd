#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPTS = Path(__file__).resolve().parent / "prompt_set_template.json"
DEFAULT_OUTPUT = REPO_ROOT / "workspace" / "protocols" / "inv_003_results" / "latest_placeholder.json"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_prompts(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    prompts = payload.get("held_out_prompts", []) if isinstance(payload, dict) else []
    out = []
    for row in prompts:
        if isinstance(row, dict) and row.get("id") and row.get("text"):
            out.append({"id": str(row["id"]), "text": str(row["text"])})
    return out


def build_placeholder(prompts: list[dict[str, Any]], *, run_id: str, mode: str) -> dict[str, Any]:
    comparisons = []
    for prompt in prompts:
        comparisons.append(
            {
                "prompt_id": prompt["id"],
                "reconstruction_a": {
                    "decision": "placeholder_waiting_runtime",
                    "disposition": ["careful", "reflective"],
                },
                "reconstruction_b": {
                    "decision": "placeholder_waiting_runtime",
                    "disposition": ["procedural", "deterministic"],
                },
                "divergence": 0.0,
            }
        )
    return {
        "run_id": run_id,
        "timestamp_utc": _utc_now(),
        "mode": mode,
        "prompts": prompts,
        "comparisons": comparisons,
        "summary": {
            "mean_divergence": 0.0,
            "notes": [
                "Dry-run scaffold output only.",
                "Attach local adapters on Dali to execute A/B reconstructions.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="INV-003 distributed continuity scaffold runner")
    parser.add_argument("--prompt-template", default=str(DEFAULT_PROMPTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--run-id", default=uuid.uuid4().hex[:12])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    prompts = _load_prompts(Path(args.prompt_template))
    payload = build_placeholder(prompts, run_id=str(args.run_id), mode="dry_run" if args.dry_run else "executed")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    result = {
        "ok": True,
        "run_id": payload["run_id"],
        "mode": payload["mode"],
        "prompt_count": len(prompts),
        "output": str(output_path),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
