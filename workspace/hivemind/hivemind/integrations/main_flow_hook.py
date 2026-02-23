from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from ..dynamics_pipeline import TactiDynamicsPipeline
from ..flags import TACTI_DYNAMICS_FLAGS, any_enabled


REPO_ROOT = Path(__file__).resolve().parents[4]
HIVEMIND_BASE = Path(__file__).resolve().parents[2]
DYNAMICS_STATE_PATH = HIVEMIND_BASE / "data" / "tacti_dynamics_snapshot.json"

_PIPELINE_CACHE: dict[Tuple[Tuple[str, ...], str], TactiDynamicsPipeline] = {}


def _unique(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        out.append(item)
        seen.add(item)
    return out


def _sorted_unique(values: Sequence[str]) -> List[str]:
    return sorted(_unique(values))


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _expand_policy_order(policy: Mapping[str, Any], order: Sequence[str]) -> List[str]:
    routing = policy.get("routing", {}) if isinstance(policy, Mapping) else {}
    free_order = routing.get("free_order", []) if isinstance(routing, Mapping) else []
    out: List[str] = []
    for entry in order:
        name = str(entry).strip()
        if not name:
            continue
        if name == "free":
            out.extend(str(x) for x in free_order if str(x).strip())
        else:
            out.append(name)
    return _unique(out)


def _resolve_from_runtime_catalog(
    *,
    policy: Mapping[str, Any] | None,
    context: Mapping[str, Any] | None,
    candidates: Sequence[str] | None,
) -> List[str]:
    found: List[str] = []
    if candidates:
        found.extend(str(x) for x in candidates if str(x).strip())

    if not isinstance(policy, Mapping):
        return _unique(found)

    intent = str((context or {}).get("intent", "")).strip()
    routing = policy.get("routing", {})
    intents = routing.get("intents", {}) if isinstance(routing, Mapping) else {}
    if intent and isinstance(intents, Mapping):
        intent_cfg = intents.get(intent, {})
        if isinstance(intent_cfg, Mapping):
            found.extend(_expand_policy_order(policy, intent_cfg.get("order", [])))

    providers = policy.get("providers", {})
    if isinstance(providers, Mapping):
        found.extend(str(x) for x in providers.keys())

    return _unique(found)


def _resolve_from_repo_manifests(repo_root: Path) -> List[str]:
    found: List[str] = []

    agents_dir = repo_root / "agents"
    if agents_dir.exists():
        for models_path in sorted(agents_dir.glob("*/agent/models.json")):
            found.append(models_path.parent.parent.name)

    policy_path = repo_root / "workspace" / "policy" / "llm_policy.json"
    if policy_path.exists():
        policy = _read_json(policy_path)
        providers = policy.get("providers", {})
        if isinstance(providers, Mapping):
            found.extend(str(x) for x in providers.keys())

    return _unique(found)


def resolve_agent_ids(
    context: Mapping[str, Any] | None = None,
    candidates: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> List[str]:
    """
    Resolve routing identities deterministically without hardcoded IDs.
    Order:
      1) Runtime orchestration catalog (current candidate list/policy).
      2) Canonical repo manifests (agents/*/agent/models.json, llm_policy.json providers).
      3) Empty list (fail-open: caller keeps existing behavior).
    """
    primary = _resolve_from_runtime_catalog(policy=policy, context=context, candidates=candidates)
    if primary:
        return _sorted_unique(primary)

    secondary = _resolve_from_repo_manifests(REPO_ROOT)
    if secondary:
        return _sorted_unique(secondary)

    return []


def stable_seed(agent_ids: Sequence[str], session_id: str | None = None) -> int:
    basis = "|".join(_sorted_unique([str(x) for x in agent_ids]))
    if session_id:
        basis = f"{basis}|{session_id}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def dynamics_flags_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return any_enabled(TACTI_DYNAMICS_FLAGS, environ=environ)


def _pipeline_for(agent_ids: Sequence[str], session_id: str | None = None) -> TactiDynamicsPipeline:
    canonical_ids = _sorted_unique([str(x) for x in agent_ids])
    key = (tuple(canonical_ids), str(session_id or ""))
    cached = _PIPELINE_CACHE.get(key)
    if cached is not None:
        return cached

    seed = stable_seed(canonical_ids, session_id=session_id)
    pipeline: TactiDynamicsPipeline
    if DYNAMICS_STATE_PATH.exists():
        try:
            payload = json.loads(DYNAMICS_STATE_PATH.read_text(encoding="utf-8"))
            loaded = TactiDynamicsPipeline.load(payload)
            if _sorted_unique(loaded.agent_ids) == canonical_ids:
                pipeline = loaded
            else:
                pipeline = TactiDynamicsPipeline(agent_ids=canonical_ids, seed=seed)
        except Exception:
            pipeline = TactiDynamicsPipeline(agent_ids=canonical_ids, seed=seed)
    else:
        pipeline = TactiDynamicsPipeline(agent_ids=canonical_ids, seed=seed)

    _PIPELINE_CACHE[key] = pipeline
    return pipeline


def _save_pipeline(pipeline: TactiDynamicsPipeline) -> None:
    DYNAMICS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DYNAMICS_STATE_PATH.write_text(json.dumps(pipeline.snapshot(), indent=2) + "\n", encoding="utf-8")


def tacti_enhance_plan(
    context: Mapping[str, Any] | None,
    candidates: Sequence[str],
    policy: Mapping[str, Any] | None = None,
) -> tuple[List[str], Dict[str, Any]]:
    ordered_candidates = _unique([str(x) for x in candidates])
    annotations: Dict[str, Any] = {"enabled": False, "reason": "flags_off", "agent_ids": []}
    if not dynamics_flags_enabled():
        return ordered_candidates, annotations

    context_data = dict(context or {})
    source_agent = str(context_data.get("source_agent", "router")).strip() or "router"
    session_id = str(context_data.get("session_id", "")).strip() or None
    context_text = str(context_data.get("input_text", "")).strip()
    intent = str(context_data.get("intent", "routing")).strip() or "routing"
    response_mode = str(
        context_data.get("response_mode")
        or (context_data.get("response_plan") or {}).get("mode")
        or ""
    ).strip().lower() or None

    agent_ids = resolve_agent_ids(context=context_data, candidates=ordered_candidates, policy=policy)
    if source_agent not in agent_ids:
        agent_ids.append(source_agent)
    agent_ids = _sorted_unique(agent_ids)
    if len(agent_ids) < 2 or not ordered_candidates:
        return ordered_candidates, {
            "enabled": False,
            "reason": "insufficient_agents",
            "agent_ids": agent_ids,
        }

    pipeline = _pipeline_for(agent_ids, session_id=session_id)
    plan = pipeline.plan_consult_order(
        source_agent=source_agent,
        target_intent=intent,
        context_text=context_text,
        candidate_agents=ordered_candidates,
        n_paths=min(3, max(1, len(ordered_candidates))),
        response_mode=response_mode,
    )
    consult_order = [str(x) for x in plan.get("consult_order", []) if str(x) in ordered_candidates]
    if consult_order:
        reordered = consult_order + [x for x in ordered_candidates if x not in consult_order]
    else:
        reordered = list(ordered_candidates)

    annotations = {
        "enabled": True,
        "applied": reordered != ordered_candidates,
        "source_agent": source_agent,
        "agent_ids": agent_ids,
        "consult_order": consult_order,
        "paths": plan.get("paths", []),
        "scores": plan.get("scores", {}),
        "trail_bias": plan.get("trail_bias", {}),
        "response_plan": plan.get("response_plan", {}),
        "reservoir_confidence": (
            ((plan.get("reservoir") or {}).get("routing_hints") or {}).get("confidence")
        ),
    }
    return reordered, annotations


def tacti_record_outcome(
    *,
    context: Mapping[str, Any] | None,
    path: Sequence[str],
    success: bool,
    latency: float,
    tokens: float,
    reward: float,
    policy: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    if not dynamics_flags_enabled():
        return {"enabled": False, "reason": "flags_off"}

    context_data = dict(context or {})
    source_agent = str(context_data.get("source_agent", "router")).strip() or "router"
    session_id = str(context_data.get("session_id", "")).strip() or None
    context_text = str(context_data.get("input_text", "")).strip()
    intent = str(context_data.get("intent", "routing")).strip() or "routing"

    route = _unique([str(x) for x in path])
    candidates = route[1:] if len(route) > 1 else list(route)
    agent_ids = resolve_agent_ids(context=context_data, candidates=candidates, policy=policy)
    if source_agent not in agent_ids:
        agent_ids.append(source_agent)
    for item in route:
        if item not in agent_ids:
            agent_ids.append(item)
    agent_ids = _sorted_unique(agent_ids)
    if len(agent_ids) < 2:
        return {"enabled": False, "reason": "insufficient_agents", "agent_ids": agent_ids}

    pipeline = _pipeline_for(agent_ids, session_id=session_id)
    if len(route) < 2:
        plan = pipeline.plan_consult_order(
            source_agent=source_agent,
            target_intent=intent,
            context_text=context_text,
            candidate_agents=[x for x in agent_ids if x != source_agent],
            n_paths=1,
        )
        fallback = [source_agent] + ([plan["consult_order"][0]] if plan.get("consult_order") else [])
        route = _unique(fallback)

    if len(route) < 2:
        return {"enabled": False, "reason": "no_path", "agent_ids": agent_ids}

    pipeline.observe_outcome(
        source_agent=source_agent,
        path=route,
        success=bool(success),
        latency=float(latency),
        tokens=float(tokens),
        reward=float(reward),
        context_text=context_text,
    )
    _save_pipeline(pipeline)
    return {"enabled": True, "agent_ids": agent_ids, "path": route}
