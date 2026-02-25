from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ._common import memory_ext_enabled, runtime_dir
except ImportError:  # pragma: no cover
    from _common import memory_ext_enabled, runtime_dir


class TrailNetwork:
    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path or runtime_dir("memory_ext", "slime_network.json")
        self.state: Dict[str, Any] = {"nodes": {}, "edges": {}}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(loaded, dict):
            self.state = {"nodes": dict(loaded.get("nodes", {})), "edges": dict(loaded.get("edges", {}))}

    def _save(self) -> None:
        if not memory_ext_enabled():
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def deposit_trail(self, interaction: str, importance: float) -> str:
        text = str(interaction or "")
        tid = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        nodes = self.state.setdefault("nodes", {})
        entry = nodes.setdefault(tid, {"text": text, "weight": 0.0})
        entry["weight"] = float(entry.get("weight", 0.0)) + max(0.0, float(importance))
        self._save()
        return tid

    def route_query(self, query: str) -> List[str]:
        terms = set(str(query or "").lower().split())
        scored = []
        for tid, node in self.state.get("nodes", {}).items():
            node_terms = set(str(node.get("text", "")).lower().split())
            overlap = len(terms & node_terms)
            weight = float(node.get("weight", 0.0))
            score = float(overlap) + weight
            scored.append((score, tid))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [tid for score, tid in scored if score > 0][:5]

    def get_network_state(self) -> Dict[str, Any]:
        nodes = self.state.get("nodes", {})
        edges = self.state.get("edges", {})
        n_nodes = len(nodes)
        n_edges = len(edges)
        density = 0.0
        if n_nodes > 1:
            density = float(n_edges) / float(n_nodes * (n_nodes - 1))
        return {"nodes": n_nodes, "edges": n_edges, "density": density}


__all__ = ["TrailNetwork"]
