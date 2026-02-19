from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Dict, Iterable, List


def _tanh(x: float) -> float:
    return math.tanh(x)


def _safe_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _feature_items(value: Any, prefix: str = "") -> Iterable[tuple[str, float]]:
    if isinstance(value, dict):
        for key in sorted(value.keys()):
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _feature_items(value[key], next_prefix)
        return
    if isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            next_prefix = f"{prefix}[{idx}]"
            yield from _feature_items(item, next_prefix)
        return
    if isinstance(value, str):
        for token in value.split():
            if token:
                yield (f"{prefix}:{token.lower()}", 1.0)
        return
    yield (prefix or "value", _safe_float(value))


def _hash_bucket(text: str, dim: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % dim


class Reservoir:
    """
    Deterministic reservoir with feature-hash input projection and linear readout.
    """

    def __init__(
        self,
        *,
        dim: int = 32,
        leak: float = 0.35,
        spectral_scale: float = 0.9,
        seed: int = 0,
    ):
        self.dim = max(4, int(dim))
        self.leak = max(0.0, min(1.0, float(leak)))
        self.spectral_scale = max(0.0, float(spectral_scale))
        self.seed = int(seed)
        self._rng = random.Random(self.seed)
        self._state = [0.0 for _ in range(self.dim)]
        self._W = self._init_recurrent()
        self._readout = [self._rng.uniform(-0.8, 0.8) for _ in range(self.dim)]
        self._session_id = "default"

    @classmethod
    def init(cls, dim: int, leak: float, spectral_scale: float, seed: int) -> "Reservoir":
        return cls(dim=dim, leak=leak, spectral_scale=spectral_scale, seed=seed)

    def _init_recurrent(self) -> List[List[float]]:
        scale = (self.spectral_scale / math.sqrt(self.dim)) if self.dim > 0 else 0.0
        matrix: List[List[float]] = []
        for _ in range(self.dim):
            row = [self._rng.uniform(-1.0, 1.0) * scale for _ in range(self.dim)]
            matrix.append(row)
        return matrix

    def _project_features(self, *feature_groups: Any) -> List[float]:
        vec = [0.0 for _ in range(self.dim)]
        for group_idx, group in enumerate(feature_groups):
            prefix = f"g{group_idx}"
            for key, val in _feature_items(group, prefix=prefix):
                bucket = _hash_bucket(key, self.dim)
                vec[bucket] += float(val)
        return vec

    def step(
        self,
        input_features: Dict[str, Any] | List[Any],
        agent_features: Dict[str, Any] | List[Any],
        adjacency_features: Dict[str, Any] | List[Any],
    ) -> List[float]:
        external = self._project_features(input_features, agent_features, adjacency_features)
        recurrent = [0.0 for _ in range(self.dim)]
        for i in range(self.dim):
            acc = 0.0
            row = self._W[i]
            for j in range(self.dim):
                acc += row[j] * self._state[j]
            recurrent[i] = acc

        next_state = [0.0 for _ in range(self.dim)]
        for i in range(self.dim):
            activation = _tanh(recurrent[i] + external[i])
            next_state[i] = ((1.0 - self.leak) * self._state[i]) + (self.leak * activation)
        self._state = next_state
        return list(self._state)

    def readout(self, state: List[float] | None = None) -> Dict[str, Any]:
        vec = list(state if state is not None else self._state)
        if not vec:
            return {"weights": [], "routing_hints": {"confidence": 0.0}, "response_plan": {"mode": "default"}}
        score = 0.0
        for i, val in enumerate(vec[: self.dim]):
            score += val * self._readout[i]
        confidence = 1.0 / (1.0 + math.exp(-score))
        top_dims = sorted(range(len(vec)), key=lambda idx: abs(vec[idx]), reverse=True)[:5]
        return {
            "weights": [round(vec[idx], 6) for idx in top_dims],
            "routing_hints": {
                "confidence": round(confidence, 6),
                "top_dimensions": top_dims,
            },
            "response_plan": {
                "mode": "focused" if confidence >= 0.6 else "exploratory",
                "score": round(score, 6),
            },
        }

    def reset(self, session_id: str | None = None) -> None:
        self._state = [0.0 for _ in range(self.dim)]
        if session_id:
            self._session_id = str(session_id)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "dim": self.dim,
            "leak": self.leak,
            "spectral_scale": self.spectral_scale,
            "seed": self.seed,
            "session_id": self._session_id,
            "state": list(self._state),
            "W": self._W,
            "readout": list(self._readout),
        }

    @classmethod
    def load(cls, payload: Dict[str, Any]) -> "Reservoir":
        res = cls(
            dim=int(payload.get("dim", 32)),
            leak=float(payload.get("leak", 0.35)),
            spectral_scale=float(payload.get("spectral_scale", 0.9)),
            seed=int(payload.get("seed", 0)),
        )
        state = payload.get("state", [])
        if isinstance(state, list) and len(state) == res.dim:
            res._state = [float(x) for x in state]
        W = payload.get("W")
        if isinstance(W, list) and len(W) == res.dim:
            matrix_ok = True
            parsed: List[List[float]] = []
            for row in W:
                if not isinstance(row, list) or len(row) != res.dim:
                    matrix_ok = False
                    break
                parsed.append([float(v) for v in row])
            if matrix_ok:
                res._W = parsed
        readout = payload.get("readout")
        if isinstance(readout, list) and len(readout) == res.dim:
            res._readout = [float(x) for x in readout]
        res._session_id = str(payload.get("session_id", "default"))
        return res

