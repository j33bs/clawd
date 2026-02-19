from __future__ import annotations

from typing import Any, Dict, List

from .flags import is_enabled
from .peer_graph import PeerGraph
from .physarum_router import PhysarumRouter
from .reservoir import Reservoir
from .trails import TrailStore


def _env_enabled(name: str) -> bool:
    return is_enabled(name)


def _norm(values: Dict[str, float]) -> Dict[str, float]:
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if hi - lo <= 1e-9:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


class TactiDynamicsPipeline:
    """
    Composes Murmuration + Reservoir + Physarum + Trails under feature flags.
    """

    def __init__(
        self,
        *,
        agent_ids: List[str],
        seed: int = 0,
        peer_k: int = 5,
        trail_store: TrailStore | None = None,
    ):
        self.agent_ids = sorted(dict.fromkeys(str(a) for a in agent_ids))
        self.seed = int(seed)
        self.enable_murmuration = _env_enabled("ENABLE_MURMURATION")
        self.enable_reservoir = _env_enabled("ENABLE_RESERVOIR")
        self.enable_physarum = _env_enabled("ENABLE_PHYSARUM_ROUTER")
        self.enable_trails = _env_enabled("ENABLE_TRAIL_MEMORY")
        self.peer_graph = PeerGraph.init(self.agent_ids, k=peer_k, seed=self.seed)
        self.reservoir = Reservoir.init(dim=32, leak=0.35, spectral_scale=0.9, seed=self.seed + 1)
        self.physarum = PhysarumRouter(seed=self.seed + 2)
        self.trails = trail_store or TrailStore()

    def _trail_agent_bias(self, context_text: str, candidate_agents: List[str]) -> Dict[str, float]:
        if not self.enable_trails:
            return {a: 0.0 for a in candidate_agents}
        hits = self.trails.query(context_text, k=8)
        bias = {a: 0.0 for a in candidate_agents}
        for hit in hits:
            meta = hit.get("meta", {})
            if not isinstance(meta, dict):
                continue
            target = str(meta.get("agent", ""))
            signal = float(meta.get("reward", 0.0) or 0.0)
            if target in bias:
                bias[target] += signal * float(hit.get("effective_strength", 0.0))
        return bias

    def plan_consult_order(
        self,
        *,
        source_agent: str,
        target_intent: str,
        context_text: str,
        candidate_agents: List[str],
        n_paths: int = 3,
    ) -> Dict[str, Any]:
        source = str(source_agent)
        candidates = [str(a) for a in candidate_agents if str(a) and str(a) != source]
        if not candidates:
            return {
                "consult_order": [],
                "paths": [[source]],
                "reservoir": {"routing_hints": {"confidence": 0.0}},
                "scores": {},
            }

        paths = (
            self.physarum.propose_paths(source, target_intent, self.peer_graph, n_paths=n_paths)
            if self.enable_physarum
            else [[source] + self.peer_graph.peers(source)[:1]]
        )
        first_hop_votes: Dict[str, float] = {a: 0.0 for a in candidates}
        for idx, path in enumerate(paths):
            if len(path) < 2:
                continue
            hop = path[1]
            if hop in first_hop_votes:
                first_hop_votes[hop] += 1.0 / (1.0 + idx)

        peer_scores = {a: self.peer_graph.edge_weight(source, a) if self.enable_murmuration else 1.0 for a in candidates}
        trail_bias = self._trail_agent_bias(context_text, candidates)
        state = (
            self.reservoir.step(
                {"intent": target_intent, "context": context_text},
                {"source": source, "candidates": candidates},
                {"votes": first_hop_votes},
            )
            if self.enable_reservoir
            else [0.0] * self.reservoir.dim
        )
        readout = self.reservoir.readout(state)
        reservoir_gain = float(readout.get("routing_hints", {}).get("confidence", 0.0))

        combined = {}
        for agent in candidates:
            combined[agent] = (
                (1.0 * peer_scores.get(agent, 0.0))
                + (0.9 * first_hop_votes.get(agent, 0.0))
                + (0.6 * trail_bias.get(agent, 0.0))
                + (0.3 * reservoir_gain)
            )
        normalized = _norm(combined)
        consult_order = sorted(candidates, key=lambda aid: (-normalized.get(aid, 0.0), aid))
        return {
            "consult_order": consult_order,
            "paths": paths,
            "reservoir": readout,
            "scores": normalized,
            "trail_bias": trail_bias,
        }

    def observe_outcome(
        self,
        *,
        source_agent: str,
        path: List[str],
        success: bool,
        latency: float,
        tokens: float,
        reward: float,
        context_text: str,
    ) -> None:
        if len(path) >= 2:
            src = str(path[0])
            for dst in path[1:]:
                if self.enable_murmuration:
                    self.peer_graph.observe_interaction(
                        src,
                        str(dst),
                        {
                            "success": bool(success),
                            "latency": float(latency),
                            "tokens": float(tokens),
                            "user_reward": float(reward),
                        },
                    )
                src = str(dst)
            if self.enable_physarum:
                self.physarum.update([str(x) for x in path], float(reward))
                self.physarum.prune(min_k=max(1, min(3, len(self.agent_ids) - 1)), max_k=min(7, max(2, len(self.agent_ids) - 1)))

        if self.enable_trails:
            self.trails.add(
                {
                    "text": context_text,
                    "tags": ["tacti_dynamics", "routing"],
                    "strength": 1.0 + max(0.0, float(reward)),
                    "meta": {
                        "agent": str(path[1]) if len(path) > 1 else str(source_agent),
                        "reward": float(reward),
                        "success": bool(success),
                        "path": list(path),
                    },
                }
            )
            self.trails.decay()
        self.peer_graph.tick(1.0)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "agent_ids": list(self.agent_ids),
            "seed": self.seed,
            "flags": {
                "ENABLE_MURMURATION": self.enable_murmuration,
                "ENABLE_RESERVOIR": self.enable_reservoir,
                "ENABLE_PHYSARUM_ROUTER": self.enable_physarum,
                "ENABLE_TRAIL_MEMORY": self.enable_trails,
            },
            "peer_graph": self.peer_graph.snapshot(),
            "reservoir": self.reservoir.snapshot(),
            "physarum": self.physarum.snapshot(),
            "trail_store": self.trails.snapshot(),
        }

    @classmethod
    def load(cls, payload: Dict[str, Any]) -> "TactiDynamicsPipeline":
        pipeline = cls(
            agent_ids=[str(x) for x in payload.get("agent_ids", [])],
            seed=int(payload.get("seed", 0)),
        )
        if isinstance(payload.get("peer_graph"), dict):
            pipeline.peer_graph = PeerGraph.load(payload["peer_graph"])
        if isinstance(payload.get("reservoir"), dict):
            pipeline.reservoir = Reservoir.load(payload["reservoir"])
        if isinstance(payload.get("physarum"), dict):
            pipeline.physarum = PhysarumRouter.load(payload["physarum"])
        if isinstance(payload.get("trail_store"), dict):
            pipeline.trails = TrailStore.load(payload["trail_store"])
        return pipeline
