from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[1]
SIM_ROOT = REPO_ROOT / "sim"
DEFAULT_ARTIFACT_PATH = REPO_ROOT / "workspace" / "artifacts" / "finance" / "consensus_latest.json"
DEFAULT_HISTORY_PATH = REPO_ROOT / "workspace" / "artifacts" / "finance" / "consensus_history.jsonl"
DEFAULT_EXTERNAL_SIGNAL_PATH = REPO_ROOT / "workspace" / "state" / "external" / "macbook_sentiment.json"
DEFAULT_EXTERNAL_SIGNAL_STALE_AFTER_SECONDS = 2700

DEFAULTS = {
    "artifact_path": str(DEFAULT_ARTIFACT_PATH),
    "history_path": str(DEFAULT_HISTORY_PATH),
    "external_signal_path": str(DEFAULT_EXTERNAL_SIGNAL_PATH),
    "fingpt_signal_path": str(REPO_ROOT / "workspace" / "state" / "external" / "fingpt_sentiment.json"),
    "sim_root": str(SIM_ROOT),
    "enabled": True,
    "llm_enabled": True,
    "llm_base_url": "http://127.0.0.1:8001/v1",
    "llm_model": "local-assistant",
    "llm_timeout_sec": 6.0,
    "llm_max_tokens": 96,
    "llm_temperature": 0.0,
    "max_live_llm_symbols": 1,
    "retrieval_trade_limit": 24,
    "enter_threshold": 0.28,
    "exit_threshold": -0.12,
    "min_confidence": 0.52,
    "fast_period": 8,
    "slow_period": 21,
}


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _sma(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / float(period)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(ts: Any) -> datetime | None:
    raw = str(ts or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _signal_age_seconds(payload: dict[str, Any], target: Path) -> float | None:
    generated_at = _parse_iso(payload.get("generated_at"))
    if generated_at is not None:
        return max(0.0, (datetime.now(timezone.utc) - generated_at).total_seconds())
    if target.exists():
        return max(0.0, time.time() - target.stat().st_mtime)
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_external_signal(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or DEFAULT_EXTERNAL_SIGNAL_PATH)
    payload = _read_json(target) or {}
    model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
    aggregate = payload.get("aggregate") if isinstance(payload.get("aggregate"), dict) else {}
    poll = payload.get("poll") if isinstance(payload.get("poll"), dict) else {}
    stale_after_seconds = int(
        max(
            0.0,
            _safe_float(poll.get("stale_after_seconds"), DEFAULT_EXTERNAL_SIGNAL_STALE_AFTER_SECONDS),
        )
    )
    age_seconds = _signal_age_seconds(payload, target) if payload else None
    status_raw = str(payload.get("status") or ("missing" if not payload else "unknown"))
    stale = bool(
        payload
        and status_raw == "ok"
        and (age_seconds is None or age_seconds > float(stale_after_seconds))
    )
    return {
        "path": str(target),
        "available": bool(payload),
        "status": "stale" if stale else status_raw,
        "status_raw": status_raw,
        "stale": stale,
        "producer": payload.get("producer"),
        "generated_at": payload.get("generated_at"),
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "stale_after_seconds": stale_after_seconds,
        "model_requested": model.get("requested"),
        "model_resolved": model.get("resolved") or model.get("requested"),
        "model_provider": model.get("provider"),
        "fallback_used": bool(model.get("fallback_used", False)),
        "aggregate": aggregate,
        "sources": payload.get("sources") if isinstance(payload.get("sources"), dict) else {},
    }


def load_external_inputs(
    *,
    external_signal_path: str | Path | None = None,
    fingpt_signal_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    inputs = {
        "macbook_sentiment": load_external_signal(external_signal_path or DEFAULT_EXTERNAL_SIGNAL_PATH),
    }
    fingpt_target = Path(str(fingpt_signal_path or DEFAULTS["fingpt_signal_path"]))
    fingpt = load_external_signal(fingpt_target)
    fingpt["path"] = str(fingpt_target)
    inputs["fingpt_sentiment"] = fingpt
    return inputs


def combine_external_inputs(external_inputs: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    inputs = external_inputs or {}
    combined_sources: dict[str, Any] = {}
    weighted_sentiment = 0.0
    weighted_confidence = 0.0
    weighted_risk_on = 0.0
    weighted_risk_off = 0.0
    total_weight = 0.0
    model_resolved: dict[str, str] = {}
    macbook_ready = bool(
        isinstance(inputs.get("macbook_sentiment"), dict)
        and str((inputs.get("macbook_sentiment") or {}).get("status") or "") == "ok"
    )
    for key, payload in inputs.items():
        if not isinstance(payload, dict):
            continue
        aggregate = payload.get("aggregate") if isinstance(payload.get("aggregate"), dict) else {}
        status = str(payload.get("status") or "missing")
        confidence = max(0.0, min(1.0, _safe_float(aggregate.get("confidence"), 0.0)))
        sentiment = _safe_float(aggregate.get("sentiment"), 0.0)
        risk_on = _safe_float(aggregate.get("risk_on"), 0.0)
        risk_off = _safe_float(aggregate.get("risk_off"), 0.0)
        source_weight = 0.9 if key == "fingpt_sentiment" else 1.0
        if key == "fingpt_sentiment" and macbook_ready:
            effective_weight = 0.0
        else:
            effective_weight = source_weight * confidence if status == "ok" else 0.0
        combined_sources[key] = {
            "status": status,
            "producer": payload.get("producer"),
            "model_resolved": payload.get("model_resolved"),
            "sentiment": round(sentiment, 4),
            "confidence": round(confidence, 4),
            "risk_on": round(risk_on, 4),
            "risk_off": round(risk_off, 4),
            "weight": round(effective_weight, 4),
            "age_seconds": payload.get("age_seconds"),
            "stale_after_seconds": payload.get("stale_after_seconds"),
        }
        if payload.get("model_resolved"):
            model_resolved[key] = str(payload["model_resolved"])
        if effective_weight <= 0.0:
            continue
        total_weight += effective_weight
        weighted_sentiment += sentiment * effective_weight
        weighted_confidence += confidence * effective_weight
        weighted_risk_on += risk_on * effective_weight
        weighted_risk_off += risk_off * effective_weight
    if total_weight <= 0.0:
        fallback_status = "stale" if any(source.get("status") == "stale" for source in combined_sources.values()) else "missing"
        return {
            "status": fallback_status,
            "sentiment": 0.0,
            "confidence": 0.0,
            "risk_on": 0.0,
            "risk_off": 0.0,
            "sources": combined_sources,
            "models_resolved": model_resolved,
        }
    return {
        "status": "ok",
        "sentiment": round(weighted_sentiment / total_weight, 4),
        "confidence": round(weighted_confidence / total_weight, 4),
        "risk_on": round(weighted_risk_on / total_weight, 4),
        "risk_off": round(weighted_risk_off / total_weight, 4),
        "sources": combined_sources,
        "models_resolved": model_resolved,
    }


def build_retrieval_stats(
    symbols: list[str],
    *,
    sim_root: Path = SIM_ROOT,
    limit: int = 24,
    sim_ids: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {
        symbol: {
            "sample_size": 0,
            "win_rate": 0.5,
            "avg_pnl": 0.0,
            "recent_bias": 0.0,
            "last_reasons": [],
        }
        for symbol in symbols
    }
    allowed_sim_ids = {str(sim_id) for sim_id in (sim_ids or []) if str(sim_id)}
    for sim_dir in sorted(sim_root.glob("SIM_*")):
        if allowed_sim_ids and sim_dir.name not in allowed_sim_ids:
            continue
        trades_path = sim_dir / "trades.jsonl"
        if not trades_path.exists():
            continue
        try:
            lines = trades_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for raw in reversed(lines):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            symbol = str(row.get("symbol") or "")
            if symbol not in stats:
                continue
            bucket = stats[symbol]
            if bucket["sample_size"] >= limit:
                continue
            if str(row.get("side") or "") not in {"close_long", "close_short", "close_pair"}:
                continue
            pnl = _safe_float(row.get("pnl"), 0.0)
            bucket["sample_size"] += 1
            bucket["avg_pnl"] += pnl
            if pnl > 0:
                bucket["win_rate"] += 1.0
            reason = str(row.get("reason") or "")
            if reason and len(bucket["last_reasons"]) < 6:
                bucket["last_reasons"].append(reason)

    for symbol, bucket in stats.items():
        sample = int(bucket["sample_size"])
        if sample > 0:
            wins = max(0.0, float(bucket["win_rate"]) - 0.5)
            win_rate = wins / float(sample)
            avg_pnl = float(bucket["avg_pnl"]) / float(sample)
            bucket["win_rate"] = round(win_rate, 4)
            bucket["avg_pnl"] = round(avg_pnl, 6)
            bucket["recent_bias"] = round(_clip(((win_rate - 0.5) * 1.5) + (avg_pnl / 2.0)), 4)
        else:
            bucket["win_rate"] = 0.5
            bucket["avg_pnl"] = 0.0
            bucket["recent_bias"] = 0.0
    return stats


def _technical_agent(closes: list[float], *, fast_period: int, slow_period: int, htf_bullish: bool | None) -> dict[str, Any]:
    fast = _sma(closes, fast_period)
    slow = _sma(closes, slow_period)
    score = 0.0
    rationale: list[str] = []
    if fast is not None and slow not in (None, 0):
        trend_edge = (float(fast) - float(slow)) / float(slow)
        score += trend_edge / 0.008
        rationale.append(f"trend_edge={trend_edge:.4f}")
    if len(closes) >= 20 and closes[-20] > 0:
        swing = (closes[-1] / closes[-20]) - 1.0
        score += swing / 0.02
        rationale.append(f"swing_20={swing:.4f}")
    if htf_bullish is True:
        score += 0.22
        rationale.append("htf=bull")
    elif htf_bullish is False:
        score -= 0.22
        rationale.append("htf=flat_or_bear")
    score = _clip(score)
    return {
        "score": round(score, 4),
        "confidence": round(min(1.0, abs(score) * 0.9 + 0.1), 4),
        "rationale": rationale,
    }


def _microstructure_agent(tick_snapshot: dict[str, Any] | None, cross_exchange_row: dict[str, Any] | None) -> dict[str, Any]:
    snap = tick_snapshot or {}
    raw_score = (
        _safe_float(snap.get("imbalance"), 0.0) * 0.65
        + (_safe_float(snap.get("momentum_1m"), 0.0) / 0.0025)
        + (_safe_float(snap.get("window_return"), 0.0) / 0.0035)
    )
    spread_bps = _safe_float(snap.get("spread_bps"), 999.0)
    trade_count = int(snap.get("trade_count", 0) or 0)
    if trade_count < 40:
        raw_score *= 0.75
    if spread_bps > 5.0:
        raw_score -= min(0.6, spread_bps / 20.0)
    gap_bps = _safe_float((cross_exchange_row or {}).get("mid_gap_bps"), 0.0)
    raw_score += _clip(gap_bps / 6.0) * 0.12
    score = _clip(raw_score / (1.0 + (abs(raw_score) * 0.45)))
    return {
        "score": round(score, 4),
        "confidence": round(min(1.0, 0.15 + (trade_count / 500.0)), 4),
        "trade_count": trade_count,
        "spread_bps": round(spread_bps, 4) if spread_bps < 900 else None,
        "gap_bps": round(gap_bps, 4),
    }


def _sentiment_agent(itc_sentiment: float, external_inputs: dict[str, dict[str, Any]] | None) -> tuple[dict[str, Any], dict[str, float | dict[str, Any]]]:
    combined = combine_external_inputs(external_inputs)
    ext_sent = _safe_float(combined.get("sentiment"), 0.0)
    ext_conf = max(0.0, min(1.0, _safe_float(combined.get("confidence"), 0.0)))
    risk_on = _safe_float(combined.get("risk_on"), 0.0)
    risk_off = _safe_float(combined.get("risk_off"), 0.0)
    ext_component = ext_sent * (0.65 + (ext_conf * 0.35))
    score = _clip((ext_component * 0.8) + (_safe_float(itc_sentiment, 0.0) * 0.55) + ((risk_on - risk_off) * 0.25))
    confidence = min(1.0, 0.2 + (ext_conf * 0.8))
    return (
        {
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "model_resolved": (
                combined.get("models_resolved", {}).get("macbook_sentiment")
                or combined.get("models_resolved", {}).get("fingpt_sentiment")
            ),
            "models_resolved": combined.get("models_resolved", {}),
            "status": combined.get("status", "missing"),
            "risk_on": round(risk_on, 4),
            "risk_off": round(risk_off, 4),
        },
        {
            "macbook_sentiment": round(ext_sent, 4),
            "itc_sentiment": round(_safe_float(itc_sentiment, 0.0), 4),
            "risk_skew": round(risk_on - risk_off, 4),
            "external_sources": combined.get("sources", {}),
        },
    )


def _risk_agent(tick_snapshot: dict[str, Any] | None, funding_row: dict[str, Any] | None, cross_exchange_row: dict[str, Any] | None) -> dict[str, Any]:
    snap = tick_snapshot or {}
    spread_bps = _safe_float(snap.get("spread_bps"), 0.0)
    realized_vol = _safe_float(snap.get("realized_vol"), 0.0)
    funding = _safe_float((funding_row or {}).get("last_funding_rate"), 0.0)
    cross_gap = abs(_safe_float((cross_exchange_row or {}).get("mid_gap_bps"), 0.0))
    penalty = min(1.0, (spread_bps / 8.0) * 0.4 + (realized_vol / 0.0015) * 0.35 + (abs(funding) / 0.0004) * 0.15 + (cross_gap / 8.0) * 0.1)
    score = _clip(0.35 - penalty)
    if penalty >= 0.72:
        risk_state = "elevated"
    elif penalty >= 0.48:
        risk_state = "guarded"
    else:
        risk_state = "normal"
    return {
        "score": round(score, 4),
        "confidence": round(0.5 + min(0.45, penalty), 4),
        "risk_state": risk_state,
        "spread_bps": round(spread_bps, 4),
        "realized_vol": round(realized_vol, 8),
        "funding_rate": round(funding, 8),
        "cross_gap_bps": round(cross_gap, 4),
    }


def _retrieval_agent(retrieval_stats: dict[str, Any] | None) -> dict[str, Any]:
    row = retrieval_stats or {}
    return {
        "score": round(_clip(_safe_float(row.get("recent_bias"), 0.0)), 4),
        "confidence": round(min(1.0, int(row.get("sample_size", 0) or 0) / 10.0), 4),
        "sample_size": int(row.get("sample_size", 0) or 0),
        "win_rate": round(_safe_float(row.get("win_rate"), 0.5), 4),
        "avg_pnl": round(_safe_float(row.get("avg_pnl"), 0.0), 6),
        "last_reasons": list(row.get("last_reasons") or []),
    }


def _heuristic_weights(sentiment: dict[str, Any], technical: dict[str, Any], microstructure: dict[str, Any], risk: dict[str, Any], retrieval: dict[str, Any]) -> dict[str, float]:
    return {
        "sentiment": round(0.8 + (_safe_float(sentiment.get("confidence"), 0.0) * 0.4), 4),
        "technical": round(1.0 + (_safe_float(technical.get("confidence"), 0.0) * 0.25), 4),
        "microstructure": round(0.9 + min(0.35, int(microstructure.get("trade_count", 0) or 0) / 1200.0), 4),
        "risk": round(1.15 if str(risk.get("risk_state")) == "normal" else 0.85, 4),
        "retrieval": round(0.55 + min(0.35, int(retrieval.get("sample_size", 0) or 0) / 20.0), 4),
    }


def _combine_agents(agents: dict[str, dict[str, Any]], learned_weights: dict[str, float]) -> dict[str, Any]:
    total_weight = max(0.0001, sum(float(weight) for weight in learned_weights.values()))
    weighted_sum = 0.0
    confidence_mass = 0.0
    for name, agent in agents.items():
        weight = float(learned_weights.get(name, 1.0))
        weighted_sum += _safe_float(agent.get("score"), 0.0) * weight
        confidence_mass += _safe_float(agent.get("confidence"), 0.0) * weight
    bias = _clip(weighted_sum / total_weight)
    confidence = max(0.0, min(1.0, confidence_mass / total_weight))
    return {
        "bias": round(bias, 4),
        "confidence": round(confidence, 4),
    }


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    trimmed = str(text).strip()
    if "</think>" in trimmed:
        trimmed = trimmed.split("</think>", 1)[1].strip()
    try:
        parsed = json.loads(trimmed)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    start = trimmed.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(trimmed)):
            ch = trimmed[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = trimmed[start : idx + 1]
                    try:
                        parsed = json.loads(candidate)
                    except Exception:
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = trimmed.find("{", start + 1)
    return None


def _call_local_llm(symbol: str, summary: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    start = time.time()
    model_requested = str(cfg.get("llm_model") or DEFAULTS["llm_model"])
    body = {
        "model": model_requested,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return compact JSON only. Decide a micro-edge trading bias for the next 15m bar. "
                    "Schema: {\"bias\":-1..1,\"confidence\":0..1,\"weight_overrides\":{\"sentiment\":number,"
                    "\"technical\":number,\"microstructure\":number,\"risk\":number,\"retrieval\":number},"
                    "\"note\":\"short string\"}."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"symbol": symbol, "summary": summary}, separators=(",", ":"), ensure_ascii=False),
            },
        ],
        "temperature": _safe_float(cfg.get("llm_temperature"), 0.0),
        "max_tokens": int(cfg.get("llm_max_tokens") or DEFAULTS["llm_max_tokens"]),
        "response_format": {"type": "json_object"},
    }
    base_url = str(cfg.get("llm_base_url") or DEFAULTS["llm_base_url"]).rstrip("/")
    req = request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('OPENCLAW_LOCAL_ASSISTANT_API_KEY', 'local')}",
        },
        method="POST",
    )
    timeout = max(0.5, _safe_float(cfg.get("llm_timeout_sec"), DEFAULTS["llm_timeout_sec"]))
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {
            "used": False,
            "reason": f"llm_error:{type(exc).__name__}",
            "latency_ms": round((time.time() - start) * 1000.0, 1),
            "model_requested": model_requested,
            "model_resolved": None,
        }

    try:
        content = payload["choices"][0]["message"]["content"]
        parsed = _extract_json_object(content)
        if not isinstance(parsed, dict):
            reasoning_content = payload["choices"][0]["message"].get("reasoning_content")
            parsed = _extract_json_object(reasoning_content) if isinstance(reasoning_content, str) else None
        if not isinstance(parsed, dict):
            raise ValueError("no_json_object")
    except Exception as exc:
        return {
            "used": False,
            "reason": f"llm_parse_error:{type(exc).__name__}",
            "latency_ms": round((time.time() - start) * 1000.0, 1),
            "model_requested": model_requested,
            "model_resolved": str(payload.get("model") or model_requested),
        }

    overrides = parsed.get("weight_overrides") if isinstance(parsed.get("weight_overrides"), dict) else {}
    clean_overrides = {
        key: round(max(0.25, min(2.0, _safe_float(overrides.get(key), 1.0))), 4)
        for key in ("sentiment", "technical", "microstructure", "risk", "retrieval")
        if key in overrides
    }
    return {
        "used": True,
        "reason": "ok",
        "latency_ms": round((time.time() - start) * 1000.0, 1),
        "model_requested": model_requested,
        "model_resolved": str(payload.get("model") or model_requested),
        "bias": round(_clip(_safe_float(parsed.get("bias"), 0.0)), 4),
        "confidence": round(max(0.0, min(1.0, _safe_float(parsed.get("confidence"), 0.0))), 4),
        "weight_overrides": clean_overrides,
        "note": str(parsed.get("note") or "")[:120],
    }


def evaluate_symbol(
    *,
    symbol: str,
    ts: int,
    closes: list[float],
    htf_bullish: bool | None = None,
    itc_sentiment: float = 0.0,
    tick_snapshot: dict[str, Any] | None = None,
    cross_exchange_row: dict[str, Any] | None = None,
    funding_row: dict[str, Any] | None = None,
    external_inputs: dict[str, dict[str, Any]] | None = None,
    retrieval_stats: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    allow_llm: bool = False,
) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if params:
        cfg.update({key: value for key, value in params.items() if value is not None})

    sentiment_agent, incoming_scores = _sentiment_agent(itc_sentiment, external_inputs)
    technical_agent = _technical_agent(
        closes,
        fast_period=int(cfg.get("fast_period") or DEFAULTS["fast_period"]),
        slow_period=int(cfg.get("slow_period") or DEFAULTS["slow_period"]),
        htf_bullish=htf_bullish,
    )
    microstructure_agent = _microstructure_agent(tick_snapshot, cross_exchange_row)
    risk_agent = _risk_agent(tick_snapshot, funding_row, cross_exchange_row)
    retrieval_agent = _retrieval_agent(retrieval_stats)
    agents = {
        "sentiment": sentiment_agent,
        "technical": technical_agent,
        "microstructure": microstructure_agent,
        "risk": risk_agent,
        "retrieval": retrieval_agent,
    }

    learned_weights = _heuristic_weights(sentiment_agent, technical_agent, microstructure_agent, risk_agent, retrieval_agent)
    llm_manager = {
        "used": False,
        "reason": "disabled",
        "latency_ms": 0.0,
        "model_requested": str(cfg.get("llm_model") or DEFAULTS["llm_model"]) if bool(cfg.get("llm_enabled", True)) else None,
        "model_resolved": None,
    }
    if allow_llm and bool(cfg.get("llm_enabled", True)):
        llm_manager = _call_local_llm(
            symbol,
            {
                "incoming_source_scores": incoming_scores,
                "agents": agents,
                "weights": learned_weights,
                "risk_state": risk_agent.get("risk_state"),
            },
            cfg,
        )
        if llm_manager.get("used"):
            for key, value in (llm_manager.get("weight_overrides") or {}).items():
                learned_weights[key] = value

    decision = _combine_agents(agents, learned_weights)
    if llm_manager.get("used"):
        decision["bias"] = round(_clip((decision["bias"] * 0.75) + (_safe_float(llm_manager.get("bias"), 0.0) * 0.25)), 4)
        decision["confidence"] = round(max(decision["confidence"], _safe_float(llm_manager.get("confidence"), 0.0)), 4)
    decision["risk_state"] = str(risk_agent.get("risk_state") or "normal")
    enter_threshold = _safe_float(cfg.get("enter_threshold"), DEFAULTS["enter_threshold"])
    exit_threshold = _safe_float(cfg.get("exit_threshold"), DEFAULTS["exit_threshold"])
    min_confidence = _safe_float(cfg.get("min_confidence"), DEFAULTS["min_confidence"])
    if decision["bias"] >= enter_threshold and decision["confidence"] >= min_confidence and decision["risk_state"] == "normal":
        action = "buy"
    elif decision["bias"] <= exit_threshold or decision["risk_state"] == "elevated":
        action = "flat"
    else:
        action = "hold"
    decision["action"] = action
    decision["ts"] = int(ts)
    decision["model_requested"] = llm_manager.get("model_requested")
    decision["model_resolved"] = llm_manager.get("model_resolved") or llm_manager.get("model_requested")
    decision["analysis_model_requested"] = llm_manager.get("model_requested")
    decision["analysis_model_resolved"] = llm_manager.get("model_resolved") or llm_manager.get("model_requested")
    decision["sentiment_model_resolved"] = sentiment_agent.get("model_resolved")
    decision["sentiment_models_resolved"] = sentiment_agent.get("models_resolved", {})
    decision["models_resolved"] = sentiment_agent.get("models_resolved", {})

    return {
        "symbol": symbol,
        "ts": int(ts),
        "decision": decision,
        "agents": agents,
        "incoming_source_scores": incoming_scores,
        "learned_weights": learned_weights,
        "llm_manager": llm_manager,
    }


def build_live_snapshot(
    *,
    candles_15m: dict[str, list[dict[str, Any]]],
    htf_regime: dict[str, dict[int, bool]],
    tick_features: dict[str, dict[str, Any]],
    cross_exchange_snapshot: dict[str, Any] | None,
    funding_snapshot: dict[str, Any] | None,
    symbols: list[str],
    itc_sentiment_by_hour: dict[int, float],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if params:
        cfg.update({key: value for key, value in params.items() if value is not None})
    external_inputs = load_external_inputs(
        external_signal_path=cfg.get("external_signal_path"),
        fingpt_signal_path=cfg.get("fingpt_signal_path"),
    )
    retrieval = build_retrieval_stats(
        symbols,
        sim_root=Path(str(cfg.get("sim_root") or SIM_ROOT)),
        limit=int(cfg.get("retrieval_trade_limit") or DEFAULTS["retrieval_trade_limit"]),
        sim_ids=list(cfg.get("retrieval_sim_ids") or []),
    )
    cross_symbols = ((cross_exchange_snapshot or {}).get("symbols") or {}) if isinstance(cross_exchange_snapshot, dict) else {}
    funding_symbols = ((funding_snapshot or {}).get("symbols") or {}) if isinstance(funding_snapshot, dict) else {}
    max_live_llm_symbols = max(0, int(cfg.get("max_live_llm_symbols") or DEFAULTS["max_live_llm_symbols"]))
    llm_budget = max_live_llm_symbols

    rows: dict[str, Any] = {}
    for symbol in symbols:
        bars = candles_15m.get(symbol) or []
        if not bars:
            continue
        closes = [_safe_float(bar.get("c"), 0.0) for bar in bars[-128:] if _safe_float(bar.get("c"), 0.0) > 0]
        if len(closes) < 24:
            continue
        latest_bar = bars[-1]
        bar_ts = int(latest_bar.get("ts", 0) or 0)
        hour_ts = (bar_ts // 3_600_000) * 3_600_000
        htf_bullish = (htf_regime.get(symbol) or {}).get(hour_ts)
        allow_llm = llm_budget > 0 and bool(cfg.get("llm_enabled", True))
        row = evaluate_symbol(
            symbol=symbol,
            ts=bar_ts,
            closes=closes,
            htf_bullish=htf_bullish,
            itc_sentiment=_safe_float(itc_sentiment_by_hour.get(hour_ts), 0.0),
            tick_snapshot=tick_features.get(symbol),
            cross_exchange_row=cross_symbols.get(symbol) if isinstance(cross_symbols, dict) else None,
            funding_row=funding_symbols.get(symbol) if isinstance(funding_symbols, dict) else None,
            external_inputs=external_inputs,
            retrieval_stats=retrieval.get(symbol),
            params=cfg,
            allow_llm=allow_llm,
        )
        if allow_llm:
            llm_budget -= 1
        rows[symbol] = row

    payload = {
        "version": 1,
        "generated_at": _now_iso(),
        "external_signal": {
            "status": combine_external_inputs(external_inputs).get("status"),
            "inputs": {
                key: {
                    "status": value.get("status"),
                    "producer": value.get("producer"),
                    "model_resolved": value.get("model_resolved"),
                    "generated_at": value.get("generated_at"),
                }
                for key, value in external_inputs.items()
            },
        },
        "symbols": rows,
    }
    artifact_path = Path(str(cfg.get("artifact_path") or DEFAULT_ARTIFACT_PATH))
    history_path = Path(str(cfg.get("history_path") or DEFAULT_HISTORY_PATH))
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _append_jsonl(history_path, payload)
    return payload
