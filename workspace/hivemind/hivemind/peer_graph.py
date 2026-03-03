from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Any, Dict, List


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class _EdgeState:
    weight: float
    success_ema: float = 0.0
    latency_ema: float = 0.0
    tokens_ema: float = 0.0
    touches: int = 0
    last_touch_t: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weight": self.weight,
            "success_ema": self.success_ema,
            "latency_ema": self.latency_ema,
            "tokens_ema": self.tokens_ema,
            "touches": self.touches,
            "last_touch_t": self.last_touch_t,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "_EdgeState":
        return cls(
            weight=float(payload.get("weight", 0.0)),
            success_ema=float(payload.get("success_ema", 0.0)),
            latency_ema=float(payload.get("latency_ema", 0.0)),
            tokens_ema=float(payload.get("tokens_ema", 0.0)),
            touches=int(payload.get("touches", 0)),
            last_touch_t=float(payload.get("last_touch_t", 0.0)),
        )


class PeerGraph:
    """
    Sparse local peer topology with local-rule updates.

    No global coordinator is required: each agent's peer set is updated
    using only local edge stats + local load estimates.
    """

    def __init__(
        self,
        *,
        agent_ids: List[str],
        k: int = 5,
        seed: int = 0,
        base_weight: float = 1.0,
        decay_rate: float = 0.015,
        churn_rate: float = 0.08,
    ):
        self._agents = sorted(dict.fromkeys(str(a) for a in agent_ids))
        self._k = max(1, int(k))
        self._seed = int(seed)
        self._rng = random.Random(self._seed)
        self._t = 0.0
        self._base_weight = float(base_weight)
        self._decay_rate = float(decay_rate)
        self._churn_rate = float(churn_rate)
        self.session_step = 0
        self._edges: Dict[str, Dict[str, _EdgeState]] = {agent: {} for agent in self._agents}
        self._peer_load: Dict[str, float] = {agent: 0.0 for agent in self._agents}
        self._init_topology()

    @classmethod
    def init(cls, agent_ids: List[str], k: int = 5, seed: int = 0) -> "PeerGraph":
        return cls(agent_ids=agent_ids, k=k, seed=seed)

    def _target_k(self) -> int:
        if len(self._agents) <= 1:
            return 0
        return min(self._k, len(self._agents) - 1)

    def _anneal_enabled(self) -> bool:
        value = str(
            os.environ.get(
                "OPENCLAW_PEERGRAPH_ANNEAL",
                os.environ.get("OPENCLAW_PEER_ANNEAL", "0"),
            )
        ).strip().lower()
        return value in {"1", "true", "yes", "on"}

    def anneal_temperature(self, arousal: float | None = None) -> float:
        if not self._anneal_enabled():
            return 1.0
        t0 = 1.0
        t_min = 0.1
        k = 0.08
        base = max(t_min, t0 * math.exp(-k * max(0, int(self.session_step))))
        if arousal is None:
            return base
        arousal_factor = max(0.6, min(1.4, 0.8 + (0.4 * float(arousal))))
        return max(t_min, min(1.5, base * arousal_factor))

    def current_churn_probability(self, arousal: float | None = None) -> float:
        return self._churn_rate * self.anneal_temperature(arousal=arousal)

    def _init_topology(self) -> None:
        target = self._target_k()
        for src in self._agents:
            candidates = [a for a in self._agents if a != src]
            self._rng.shuffle(candidates)
            for dst in candidates[:target]:
                self._edges[src][dst] = _EdgeState(weight=self._base_weight)

    def peers(self, agent_id: str) -> List[str]:
        src = str(agent_id)
        if src not in self._edges:
            return []
        ranked = sorted(
            self._edges[src].items(),
            key=lambda kv: (-kv[1].weight, self._peer_load.get(kv[0], 0.0), kv[0]),
        )
        return [peer for peer, _ in ranked]

    def observe_interaction(self, src: str, dst: str, signal: Dict[str, Any]) -> None:
        source = str(src)
        target = str(dst)
        if source not in self._edges or target not in self._edges or source == target:
            return
        if target not in self._edges[source]:
            self._edges[source][target] = _EdgeState(weight=self._base_weight * 0.7)

        edge = self._edges[source][target]
        success = 1.0 if bool(signal.get("success")) else 0.0
        latency = float(signal.get("latency", 0.0) or 0.0)
        tokens = float(signal.get("tokens", 0.0) or 0.0)
        user_reward = float(signal.get("user_reward", 0.0) or 0.0)
        explicit_load = signal.get("load")
        load_value = float(explicit_load) if isinstance(explicit_load, (int, float)) else (latency / 1000.0)
        load_value = _clamp(load_value, 0.0, 10.0)

        alpha = 0.25
        edge.success_ema = (1.0 - alpha) * edge.success_ema + alpha * success
        edge.latency_ema = (1.0 - alpha) * edge.latency_ema + alpha * latency
        edge.tokens_ema = (1.0 - alpha) * edge.tokens_ema + alpha * tokens
        edge.touches += 1
        edge.last_touch_t = self._t

        self._peer_load[target] = (1.0 - alpha) * self._peer_load[target] + alpha * load_value

        quality = (1.1 * success) + (0.3 * user_reward)
        cost = (0.001 * latency) + (0.0003 * tokens) + (0.25 * self._peer_load[target])
        delta = quality - cost
        edge.weight = _clamp(edge.weight + (0.12 * delta), 0.01, 20.0)

        self._ensure_k_for_agent(source)

    def tick(self, dt: float, arousal: float | None = None) -> None:
        delta_t = max(0.0, float(dt))
        self._t += delta_t
        self.session_step += 1
        if delta_t <= 0:
            return

        decay = math.exp(-self._decay_rate * delta_t)
        stale_decay = math.exp(-0.03 * delta_t)
        for src in self._agents:
            for dst, edge in list(self._edges[src].items()):
                edge.weight = _clamp(edge.weight * decay, 0.01, 20.0)
                age = self._t - edge.last_touch_t
                if age > 1.0:
                    edge.weight = _clamp(edge.weight * stale_decay, 0.01, 20.0)

        churn_probability = self.current_churn_probability(arousal=arousal)
        for agent in self._agents:
            if self._rng.random() < churn_probability:
                self._churn_one_peer(agent, temperature=self.anneal_temperature(arousal=arousal))
            self._ensure_k_for_agent(agent)

    def _candidate_new_peer(self, src: str) -> str | None:
        neighbors = set(self._edges[src].keys())
        options = [a for a in self._agents if a != src and a not in neighbors]
        if not options:
            return None
        self._rng.shuffle(options)
        options.sort(key=lambda aid: (self._peer_load.get(aid, 0.0), aid))
        return options[0]

    def _churn_one_peer(self, src: str, temperature: float = 1.0) -> None:
        peers = self.peers(src)
        if not peers:
            return
        weakest = peers[-1]
        candidate = self._candidate_new_peer(src)
        if not candidate:
            return
        weakest_weight = self._edges[src][weakest].weight
        candidate_bias = 1.0 / (1.0 + self._peer_load.get(candidate, 0.0))
        candidate_weight = max(0.01, self._base_weight * candidate_bias)
        delta = candidate_weight - (weakest_weight * 0.6)
        temp = max(0.05, float(temperature))
        accept_prob = 1.0 / (1.0 + math.exp(-(delta / temp)))
        if self._rng.random() <= accept_prob:
            self._edges[src].pop(weakest, None)
            self._edges[src][candidate] = _EdgeState(weight=candidate_weight)

    def _ensure_k_for_agent(self, src: str) -> None:
        target = self._target_k()
        if target <= 0:
            self._edges[src] = {}
            return
        while len(self._edges[src]) < target:
            candidate = self._candidate_new_peer(src)
            if candidate is None:
                break
            self._edges[src][candidate] = _EdgeState(weight=self._base_weight * 0.8)
        while len(self._edges[src]) > target:
            weakest = self.peers(src)[-1]
            self._edges[src].pop(weakest, None)

    def edge_weight(self, src: str, dst: str) -> float:
        edge = self._edges.get(str(src), {}).get(str(dst))
        return float(edge.weight) if edge else 0.0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "agents": list(self._agents),
            "k": self._k,
            "seed": self._seed,
            "time": self._t,
            "session_step": self.session_step,
            "base_weight": self._base_weight,
            "decay_rate": self._decay_rate,
            "churn_rate": self._churn_rate,
            "peer_load": dict(self._peer_load),
            "edges": {
                src: {dst: edge.to_dict() for dst, edge in edges.items()}
                for src, edges in self._edges.items()
            },
        }

    @classmethod
    def load(cls, payload: Dict[str, Any]) -> "PeerGraph":
        graph = cls(
            agent_ids=[str(x) for x in payload.get("agents", [])],
            k=int(payload.get("k", 5)),
            seed=int(payload.get("seed", 0)),
            base_weight=float(payload.get("base_weight", 1.0)),
            decay_rate=float(payload.get("decay_rate", 0.015)),
            churn_rate=float(payload.get("churn_rate", 0.08)),
        )
        graph._t = float(payload.get("time", 0.0))
        graph.session_step = int(payload.get("session_step", 0))
        loads = payload.get("peer_load", {})
        if isinstance(loads, dict):
            for agent, value in loads.items():
                if agent in graph._peer_load:
                    graph._peer_load[agent] = float(value)

        edges = payload.get("edges", {})
        if isinstance(edges, dict):
            graph._edges = {agent: {} for agent in graph._agents}
            for src, row in edges.items():
                if src not in graph._edges or not isinstance(row, dict):
                    continue
                for dst, raw_state in row.items():
                    if dst not in graph._edges or dst == src or not isinstance(raw_state, dict):
                        continue
                    graph._edges[src][dst] = _EdgeState.from_dict(raw_state)
        for agent in graph._agents:
            graph._ensure_k_for_agent(agent)
        return graph
