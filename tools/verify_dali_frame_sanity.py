#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image
import numpy as np


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_dali_frame_sanity.py <image>", file=sys.stderr)
        return 2
    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(json.dumps({"ok": False, "error": "missing_image", "path": str(image_path)}, indent=2))
        return 1

    arr = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.uint8)
    mean_rgb = arr.reshape((-1, 3)).mean(axis=0)
    near_white = float(((arr[..., 0] > 245) & (arr[..., 1] > 245) & (arr[..., 2] > 245)).mean())
    bright = float(((arr[..., 0] > 245) | (arr[..., 1] > 245) | (arr[..., 2] > 245)).mean())
    dark = float(((arr[..., 0] < 32) & (arr[..., 1] < 32) & (arr[..., 2] < 40)).mean())

    ok = (
        float(mean_rgb.mean()) >= 14.0
        and dark <= 0.93
        and near_white <= 0.001
        and bright <= 0.01
    )
    payload = {
        "ok": bool(ok),
        "path": str(image_path),
        "mean_rgb": [float(v) for v in mean_rgb],
        "mean_rgb_avg": float(mean_rgb.mean()),
        "near_white_ratio": near_white,
        "bright_ratio": bright,
        "dark_ratio": dark,
        "thresholds": {
            "min_mean_rgb_avg": 14.0,
            "max_dark_ratio": 0.93,
            "max_near_white_ratio": 0.001,
            "max_bright_ratio": 0.01,
        },
    }
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
