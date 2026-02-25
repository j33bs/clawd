from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

try:
    from ._common import memory_ext_enabled, runtime_dir
except ImportError:  # pragma: no cover
    from _common import memory_ext_enabled, runtime_dir


class EchoState:
    def __init__(self, window: int = 50, dim: int = 16, seed: int = 23, state_path: Optional[Path] = None):
        self.window = int(window)
        self.dim = int(dim)
        self.seed = int(seed)
        self.state_path = state_path or runtime_dir("memory_ext", "reservoir_state.json")
        self.inputs: List[str] = []
        self.state: List[float] = [0.0] * self.dim
        self.step = 0
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(payload, dict):
            self.inputs = [str(x) for x in payload.get("inputs", [])][-self.window :]
            raw_state = payload.get("state", [])
            if isinstance(raw_state, list) and len(raw_state) == self.dim:
                self.state = [float(x) for x in raw_state]
            self.step = int(payload.get("step", len(self.inputs)))

    def _save(self) -> None:
        if not memory_ext_enabled():
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, object] = {"inputs": self.inputs[-self.window :], "state": self.state, "step": self.step}
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _embed(self, text: str) -> List[float]:
        digest = hashlib.sha256("{seed}:{text}".format(seed=self.seed, text=text).encode("utf-8")).digest()
        values: List[float] = []
        for i in range(self.dim):
            b = digest[i % len(digest)]
            values.append((float(b) / 255.0) * 2.0 - 1.0)
        return values

    def update(self, current_input: str) -> List[float]:
        vec = self._embed(current_input)
        phase = math.sin(float(self.step + 1))
        self.state = [0.7 * old + 0.3 * (new * phase) for old, new in zip(self.state, vec)]
        self.step += 1
        self.inputs.append(str(current_input))
        self.inputs = self.inputs[-self.window :]
        self._save()
        return list(self.state)

    def predict_next_state(self, current_input: str) -> float:
        state = self.update(current_input)
        return sum(state) / float(len(state) or 1)

    def echo_memory(self, query: str) -> List[str]:
        terms = set(str(query or "").lower().split())
        if not terms:
            return self.inputs[-5:]
        scored = []
        for item in self.inputs:
            tokens = set(item.lower().split())
            score = len(terms & tokens)
            scored.append((score, item))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [item for score, item in scored if score > 0][:5]


__all__ = ["EchoState"]
