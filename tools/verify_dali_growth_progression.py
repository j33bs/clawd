#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def _load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)


def _load_state(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DALI growth between two framebuffer captures.")
    parser.add_argument("before_image")
    parser.add_argument("after_image")
    parser.add_argument("--before-state")
    parser.add_argument("--after-state")
    parser.add_argument("--min-diff-mean", type=float, default=4.0)
    parser.add_argument("--min-diff-ratio", type=float, default=0.06)
    parser.add_argument("--min-colony-delta", type=float, default=0.02)
    args = parser.parse_args()

    before_path = Path(args.before_image)
    after_path = Path(args.after_image)
    if not before_path.exists() or not after_path.exists():
        payload = {
            "ok": False,
            "error": "missing_image",
            "before_image": str(before_path),
            "after_image": str(after_path),
        }
        print(json.dumps(payload, indent=2))
        return 1

    before = _load_rgb(before_path)
    after = _load_rgb(after_path)
    if before.shape != after.shape:
        payload = {
            "ok": False,
            "error": "shape_mismatch",
            "before_shape": list(before.shape),
            "after_shape": list(after.shape),
        }
        print(json.dumps(payload, indent=2))
        return 1

    diff = np.abs(after - before)
    diff_mean = float(diff.mean())
    diff_luma = diff.mean(axis=2)
    diff_ratio = float((diff_luma >= 10.0).mean())

    before_state = _load_state(Path(args.before_state)) if args.before_state else {}
    after_state = _load_state(Path(args.after_state)) if args.after_state else {}
    before_colony = float(before_state.get("colony_memory_level", 0.0) or 0.0)
    after_colony = float(after_state.get("colony_memory_level", 0.0) or 0.0)
    colony_delta = after_colony - before_colony

    ok = (
        diff_mean >= args.min_diff_mean
        and diff_ratio >= args.min_diff_ratio
        and colony_delta >= args.min_colony_delta
    )
    payload = {
        "ok": bool(ok),
        "before_image": str(before_path),
        "after_image": str(after_path),
        "diff_mean": diff_mean,
        "diff_ratio": diff_ratio,
        "before_colony_memory_level": before_colony,
        "after_colony_memory_level": after_colony,
        "colony_memory_delta": colony_delta,
        "thresholds": {
            "min_diff_mean": args.min_diff_mean,
            "min_diff_ratio": args.min_diff_ratio,
            "min_colony_delta": args.min_colony_delta,
        },
    }
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
