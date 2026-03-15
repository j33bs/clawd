from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io_utils import utc_now_iso


class JsonlLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **fields: Any) -> None:
        row = {"ts": utc_now_iso(), "event": str(event)}
        row.update(fields)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
