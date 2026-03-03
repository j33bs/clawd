from __future__ import annotations

import random
import os
from typing import Any, Dict, List, Tuple

from .peer_graph import PeerGraph


def _edge_key(src: str, dst: str) -> str:
    return f"{src}->{dst}"


class PhysarumRouter:
    """
    Conductance-based routing over PeerGraph edges.
    """

    def __init__(self, *, seed: int = 0, explore_rate: float = 0.2):
        self.seed = int(seed)
        self._rng = random.Random(self.seed)
        self.explore_rate = max(0.0, min(1.0, float(explore_rate)))
        self._conductance: Dict[str, float] = {}
        self._known_neighbors: Dict[str, set[str]] = {}

    def _get_conductance(self, src: str, dst: str) -> float:
        return float(self._conductance.get(_edge_key(src, dst), 1.0))

    def _set_conductance(self, src: str, dst: str, value: float) -> None:
        self._conductance[_edge_key(src, dst)] = max(0.01, min(20.0, float(value)))
        self._known_neighbors.setdefault(src, set()).add(dst)

    def propose_paths(
        self,
        src_agent: str,
        target_intent: str,
        peer_graph: PeerGraph,
        n_paths: int,
    ) -> List[List[str]]:
        _ = target_intent
        src = str(src_agent)
        want = max(1, int(n_paths))
        first_hop_candidates = peer_graph.peers(src)
        if not first_hop_candidates:
            return [[src]]

        scored: List[Tuple[float, str]] = []
        for dst in first_hop_candidates:
            edge_score = self._get_conductance(src, dst) * max(0.01, peer_graph.edge_weight(src, dst))
            scored.append((edge_score, dst))
            self._known_neighbors.setdefault(src, set()).add(dst)
        scored.sort(key=lambda item: (-item[0], item[1]))

        if self._rng.random() < self.explore_rate:
            self._rng.shuffle(scored)

        paths: List[List[str]] = []
        seen = set()
        for _, first in scored:
            path = [src, first]
            second_hops = [p for p in peer_graph.peers(first) if p != src]
            if second_hops:
                second_hops.sort(
                    key=lambda node: -(
                        self._get_conductance(first, node) * max(0.01, peer_graph.edge_weight(first, node))
                    )
                )
                if self._rng.random() < self.explore_rate:
                    self._rng.shuffle(second_hops)
                best_second = second_hops[0]
                path.append(best_second)
                self._known_neighbors.setdefault(first, set()).add(best_second)
            key = tuple(path)
            if key in seen:
                continue
            seen.add(key)
            paths.append(path)
            if len(paths) >= want:
                break
        return paths if paths else [[src]]

    def update(self, path: List[str], reward_signal: float, valence: float | None = None) -> None:
        reward = float(reward_signal)
        trail_valence_enabled = str(os.environ.get("OPENCLAW_TRAIL_VALENCE", "0")).strip().lower() in {"1", "true", "yes", "on"}
        if trail_valence_enabled and isinstance(valence, (int, float)):
            valence_adj = max(-1.0, min(1.0, float(valence)))
            reward = reward * (1.0 + (0.25 * valence_adj))
        if len(path) < 2:
            return
        for i in range(len(path) - 1):
            src = str(path[i])
            dst = str(path[i + 1])
            prev = self._get_conductance(src, dst)
            if reward >= 0.0:
                nxt = prev + (0.15 * reward)
            else:
                nxt = prev + (0.25 * reward)
            self._set_conductance(src, dst, nxt)

    def prune(self, min_k: int, max_k: int) -> None:
        lower = max(1, int(min_k))
        upper = max(lower, int(max_k))
        grouped: Dict[str, List[Tuple[str, float]]] = {}
        all_nodes = set()
        for edge, cond in self._conductance.items():
            src, dst = edge.split("->", 1)
            grouped.setdefault(src, []).append((dst, cond))
            all_nodes.add(src)
            all_nodes.add(dst)
        all_nodes.update(self._known_neighbors.keys())
        for src, neighbors in self._known_neighbors.items():
            all_nodes.update(neighbors)

        for src in sorted(all_nodes):
            row = grouped.get(src, [])
            row.sort(key=lambda item: (-item[1], item[0]))
            keep = row[:upper]
            keep_dst = {dst for dst, _ in keep}
            for dst, _ in row[upper:]:
                self._conductance.pop(_edge_key(src, dst), None)

            if len(keep_dst) < lower:
                candidates = sorted(self._known_neighbors.get(src, set()))
                for candidate in candidates:
                    if candidate in keep_dst:
                        continue
                    if candidate == src:
                        continue
                    self._set_conductance(src, candidate, 0.6)
                    keep_dst.add(candidate)
                    if len(keep_dst) >= lower:
                        break
            if len(keep_dst) < lower:
                for candidate in sorted(all_nodes):
                    if candidate == src or candidate in keep_dst:
                        continue
                    self._set_conductance(src, candidate, 0.5)
                    keep_dst.add(candidate)
                    if len(keep_dst) >= lower:
                        break

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "seed": self.seed,
            "explore_rate": self.explore_rate,
            "conductance": dict(self._conductance),
            "known_neighbors": {src: sorted(list(neigh)) for src, neigh in self._known_neighbors.items()},
        }

    @classmethod
    def load(cls, payload: Dict[str, Any]) -> "PhysarumRouter":
        router = cls(
            seed=int(payload.get("seed", 0)),
            explore_rate=float(payload.get("explore_rate", 0.2)),
        )
        conductance = payload.get("conductance", {})
        if isinstance(conductance, dict):
            for edge, value in conductance.items():
                if "->" not in edge:
                    continue
                src, dst = edge.split("->", 1)
                router._set_conductance(src, dst, float(value))
        known = payload.get("known_neighbors", {})
        if isinstance(known, dict):
            for src, row in known.items():
                if isinstance(row, list):
                    router._known_neighbors[src] = {str(x) for x in row if str(x)}
        return router
