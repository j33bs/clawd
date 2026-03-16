from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .regime_detector import detect_regime
from .strategy_blender import blend_signals
from .volatility_metrics import compute_volatility

_DEFAULTS = {
    "ewma_decay": 0.9,
    "score_scale": 180.0,
    "hit_rate_scale": 0.8,
    "min_weight": 0.35,
    "max_weight": 3.0,
    "flat_signal_threshold": 0.05,
    "enter_threshold": 0.18,
    "exit_threshold": -0.02,
    "risk_exit_threshold": -0.35,
    "trend_fast": 8,
    "trend_slow": 21,
    "pullback_lookback": 12,
    "breakout_lookback": 20,
    "volatility_cap_pct": 0.04,
    "sentiment_signal_scale": 1.5,
    "tick_min_trade_count": 20,
    "tick_imbalance_scale": 0.45,
    "tick_return_scale": 0.0025,
    "tick_momentum_scale": 0.0015,
    "tick_spread_soft_cap_bps": 6.0,
    "regime_params": {
        "lookback": 96,
        "sideways_threshold": 0.002,
        "conf_scale": 0.01,
    },
    "volatility_params": {
        "atr_period": 14,
        "vol_window": 30,
    },
    "strategy_blender": {
        "method": "weighted_mean",
        "tie_break": "flat",
    },
    "forecast_horizons_bars": [4, 16],
}


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / float(period)


def _to_price_list(closes: List[Any]) -> List[float]:
    out: List[float] = []
    for value in closes:
        try:
            fval = float(value)
        except Exception:
            continue
        if fval > 0:
            out.append(fval)
    return out


def load_model_state(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded.setdefault("version", 1)
                loaded.setdefault("symbols", {})
                return loaded
        except Exception:
            pass
    return {"version": 1, "symbols": {}}


def save_model_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def ensure_symbol_state(state: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    symbols = state.setdefault("symbols", {})
    sym = symbols.setdefault(symbol, {})
    sym.setdefault("models", {})
    sym.setdefault("last_signals", {})
    sym.setdefault("pending_predictions", [])
    sym.setdefault("prediction_metrics", {"count": 0, "correct": 0, "brier_sum": 0.0, "mae_sum": 0.0, "by_horizon": {}})
    return sym


def _ensure_model_stats(symbol_state: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    models = symbol_state.setdefault("models", {})
    stats = models.setdefault(
        model_id,
        {
            "uses": 0,
            "hits": 0,
            "misses": 0,
            "score_ewma": 0.0,
            "cumulative_reward": 0.0,
            "last_reward": 0.0,
            "last_realized_return": 0.0,
        },
    )
    return stats


def _ensure_horizon_bucket(metrics: Dict[str, Any], horizon_bars: int) -> Dict[str, Any]:
    by_horizon = metrics.setdefault("by_horizon", {})
    bucket = by_horizon.setdefault(
        str(int(horizon_bars)),
        {"count": 0, "correct": 0, "brier_sum": 0.0, "mae_sum": 0.0, "avg_realized_return": 0.0},
    )
    return bucket


def _adaptive_weight(stats: Dict[str, Any], base_weight: float, cfg: Dict[str, Any]) -> float:
    uses = int(stats.get("uses", 0))
    hits = int(stats.get("hits", 0))
    misses = int(stats.get("misses", 0))
    score = float(stats.get("score_ewma", 0.0))
    total = hits + misses
    hit_rate = (hits / total) if total > 0 else 0.5
    if uses < 3:
        multiplier = 1.0
    else:
        skill = (score * float(cfg["score_scale"])) + ((hit_rate - 0.5) * float(cfg["hit_rate_scale"]))
        multiplier = 1.0 + skill
    multiplier = max(float(cfg["min_weight"]), min(float(cfg["max_weight"]), multiplier))
    return max(0.0, float(base_weight) * multiplier)


def update_walk_forward_scores(symbol_state: Dict[str, Any], current_close: float, current_ts: int, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    last_close = symbol_state.get("last_close")
    last_ts = int(symbol_state.get("last_ts", 0) or 0)
    last_signals = symbol_state.get("last_signals") or {}
    if not last_close or current_close <= 0 or current_ts <= last_ts or not last_signals:
        return {"updated": False, "realized_return": 0.0}

    realized_return = (float(current_close) / float(last_close)) - 1.0
    flat_threshold = float(cfg["flat_signal_threshold"])
    decay = float(cfg["ewma_decay"])

    for model_id, payload in last_signals.items():
        stats = _ensure_model_stats(symbol_state, model_id)
        signal = _clip(float(payload.get("signal", 0.0)))
        confidence = max(0.0, min(1.0, float(payload.get("confidence", 1.0))))
        reward = signal * realized_return * confidence

        stats["uses"] = int(stats.get("uses", 0)) + 1
        stats["score_ewma"] = (float(stats.get("score_ewma", 0.0)) * decay) + (reward * (1.0 - decay))
        stats["cumulative_reward"] = float(stats.get("cumulative_reward", 0.0)) + reward
        stats["last_reward"] = reward
        stats["last_realized_return"] = realized_return

        if abs(signal) >= flat_threshold:
            signal_dir = 1 if signal > 0 else -1
            return_dir = 1 if realized_return > 0 else (-1 if realized_return < 0 else 0)
            if signal_dir == return_dir:
                stats["hits"] = int(stats.get("hits", 0)) + 1
            else:
                stats["misses"] = int(stats.get("misses", 0)) + 1

    return {"updated": True, "realized_return": realized_return}


def _build_candidate_items(
    closes: List[float],
    candles: List[Dict[str, Any]],
    sentiment_score: float,
    htf_bullish: Optional[bool],
    include_sentiment: bool,
    tick_snapshot: Optional[Dict[str, Any]],
    symbol_state: Dict[str, Any],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    prices = _to_price_list(closes)
    if not prices:
        return {
            "items": [],
            "leaderboard": [],
            "regime": {"regime": "sideways", "confidence": 0.0},
            "volatility": {"atr_pct": None, "rolling_vol_pct": None},
            "risk_signal": 0.0,
        }

    regime = detect_regime(prices, cfg.get("regime_params"))
    volatility = compute_volatility(candles=candles, prices=prices, params=cfg.get("volatility_params"))
    close = prices[-1]

    items: List[Dict[str, Any]] = []

    trend_fast = int(cfg["trend_fast"])
    trend_slow = int(cfg["trend_slow"])
    fast = _sma(prices, trend_fast)
    slow = _sma(prices, trend_slow)
    if fast is not None and slow not in (None, 0):
        edge = (fast - slow) / slow
        items.append(
            {
                "source": "trend_follow",
                "signal": _clip(edge / 0.01),
                "confidence": min(1.0, abs(edge) / 0.01),
                "weight": 1.2,
                "base_weight": 1.2,
            }
        )

    breakout_lb = int(cfg["breakout_lookback"])
    if len(prices) > breakout_lb:
        hist = prices[-(breakout_lb + 1):-1]
        if hist:
            prior_high = max(hist)
            prior_low = min(hist)
            if prior_high > 0 and prior_low > 0:
                up_edge = (close - prior_high) / prior_high
                down_edge = (close - prior_low) / prior_low
                breakout_signal = 0.0
                if up_edge > 0:
                    breakout_signal = _clip(up_edge / 0.01)
                elif down_edge < 0:
                    breakout_signal = _clip(down_edge / 0.01)
                items.append(
                    {
                        "source": "breakout_confirmation",
                        "signal": breakout_signal,
                        "confidence": min(1.0, abs(breakout_signal)),
                        "weight": 1.0,
                        "base_weight": 1.0,
                    }
                )

    pullback_lb = int(cfg["pullback_lookback"])
    pullback_anchor = _sma(prices, pullback_lb)
    if pullback_anchor not in (None, 0):
        dist = (close - pullback_anchor) / pullback_anchor
        if regime.get("regime") == "bull":
            pullback_signal = _clip((-dist) / 0.015)
        elif regime.get("regime") == "bear":
            pullback_signal = _clip(dist / 0.015)
        else:
            pullback_signal = _clip((-dist) / 0.03)
        items.append(
            {
                "source": "pullback_reversion",
                "signal": pullback_signal,
                "confidence": min(1.0, abs(dist) / 0.02),
                "weight": 0.9,
                "base_weight": 0.9,
            }
        )

    regime_signal = 0.0
    if regime.get("regime") == "bull":
        regime_signal = 0.8
    elif regime.get("regime") == "bear":
        regime_signal = -0.8
    items.append(
        {
            "source": "regime_filter",
            "signal": regime_signal,
            "confidence": float(regime.get("confidence", 0.0)),
            "weight": 1.1,
            "base_weight": 1.1,
        }
    )

    if include_sentiment:
        sentiment_signal = _clip(float(sentiment_score) * float(cfg["sentiment_signal_scale"]))
        items.append(
            {
                "source": "itc_sentiment",
                "signal": sentiment_signal,
                "confidence": min(1.0, abs(float(sentiment_score)) * 2.0),
                "weight": 0.9,
                "base_weight": 0.9,
            }
        )

    risk_signal = 0.0
    if tick_snapshot:
        trade_count = int(tick_snapshot.get("trade_count", 0) or 0)
        if trade_count >= int(cfg["tick_min_trade_count"]):
            imbalance = _clip(float(tick_snapshot.get("imbalance", 0.0) or 0.0))
            window_return = float(tick_snapshot.get("window_return", 0.0) or 0.0)
            momentum_1m = float(tick_snapshot.get("momentum_1m", 0.0) or 0.0)
            spread_bps = tick_snapshot.get("spread_bps")
            spread_penalty = 0.0
            if isinstance(spread_bps, (int, float)) and float(spread_bps) > float(cfg["tick_spread_soft_cap_bps"]):
                spread_penalty = min(0.5, (float(spread_bps) - float(cfg["tick_spread_soft_cap_bps"])) / max(1.0, float(cfg["tick_spread_soft_cap_bps"])))
                risk_signal = min(risk_signal, -spread_penalty)
            micro_signal = (
                imbalance * float(cfg["tick_imbalance_scale"])
                + (window_return / max(1e-9, float(cfg["tick_return_scale"])))
                + (momentum_1m / max(1e-9, float(cfg["tick_momentum_scale"])))
            )
            micro_signal = _clip(micro_signal)
            confidence = min(1.0, (trade_count / 120.0) + abs(imbalance) * 0.5)
            confidence = max(0.0, confidence - spread_penalty)
            items.append(
                {
                    "source": "tick_microstructure",
                    "signal": micro_signal,
                    "confidence": confidence,
                    "weight": 1.25,
                    "base_weight": 1.25,
                }
            )

    atr_pct = volatility.get("atr_pct")
    if atr_pct is not None and float(atr_pct) > float(cfg["volatility_cap_pct"]):
        excess = (float(atr_pct) - float(cfg["volatility_cap_pct"])) / max(float(cfg["volatility_cap_pct"]), 1e-9)
        risk_signal = min(-0.35, _clip(-excess, -1.0, -0.35))
    if htf_bullish is False:
        risk_signal = min(risk_signal, -0.75)
    items.append(
        {
            "source": "risk_guard",
            "signal": risk_signal,
            "confidence": 0.9 if risk_signal < 0 else 0.35,
            "weight": 1.4,
            "base_weight": 1.4,
        }
    )

    leaderboard = []
    for item in items:
        stats = _ensure_model_stats(symbol_state, item["source"])
        adaptive = _adaptive_weight(stats, float(item["weight"]), cfg)
        item["weight"] = adaptive
        leaderboard.append(
            {
                "model": item["source"],
                "adaptive_weight": adaptive,
                "score_ewma": float(stats.get("score_ewma", 0.0)),
                "uses": int(stats.get("uses", 0)),
                "hits": int(stats.get("hits", 0)),
                "misses": int(stats.get("misses", 0)),
            }
        )

    leaderboard.sort(key=lambda row: row["adaptive_weight"], reverse=True)
    return {
        "items": items,
        "leaderboard": leaderboard,
        "regime": regime,
        "volatility": volatility,
        "risk_signal": risk_signal,
    }


def run_competing_models(
    *,
    symbol_state: Dict[str, Any],
    ts: int,
    closes: List[Any],
    candles: List[Dict[str, Any]],
    sentiment_score: float = 0.0,
    htf_bullish: Optional[bool] = None,
    include_sentiment: bool = False,
    tick_snapshot: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    prices = _to_price_list(closes)
    if not prices:
        return {
            "signal": 0.0,
            "confidence": 0.0,
            "enter_long": False,
            "exit_long": False,
            "items": [],
            "leaderboard": [],
            "walk_forward": {"updated": False, "realized_return": 0.0},
            "risk_state": "flat",
        }

    walk_forward = update_walk_forward_scores(symbol_state, prices[-1], int(ts), cfg)
    built = _build_candidate_items(
        prices,
        candles,
        float(sentiment_score),
        htf_bullish,
        include_sentiment,
        tick_snapshot,
        symbol_state,
        cfg,
    )
    blended = blend_signals(built["items"], cfg.get("strategy_blender"))
    signal = float(blended.get("signal", 0.0))
    confidence = float(blended.get("confidence", 0.0))
    risk_signal = float(built.get("risk_signal", 0.0))
    risk_state = "risk_off" if risk_signal <= float(cfg["risk_exit_threshold"]) else "normal"
    ranked_contributors = sorted(
        built["items"],
        key=lambda item: abs(float(item.get("signal", 0.0)) * float(item.get("confidence", 0.0)) * float(item.get("weight", 0.0))),
        reverse=True,
    )
    top_model = "ensemble"
    for item in ranked_contributors:
        contribution = abs(float(item.get("signal", 0.0)) * float(item.get("confidence", 0.0)) * float(item.get("weight", 0.0)))
        if contribution > 0:
            top_model = str(item.get("source", "ensemble"))
            break

    enter_long = signal >= float(cfg["enter_threshold"]) and confidence > 0.0 and risk_state == "normal"
    exit_long = signal <= float(cfg["exit_threshold"]) or risk_state == "risk_off"

    symbol_state["last_close"] = prices[-1]
    symbol_state["last_ts"] = int(ts)
    symbol_state["last_signals"] = {
        item["source"]: {
            "signal": float(item["signal"]),
            "confidence": float(item["confidence"]),
            "weight": float(item["weight"]),
        }
        for item in built["items"]
    }

    return {
        "signal": signal,
        "confidence": confidence,
        "enter_long": enter_long,
        "exit_long": exit_long,
        "risk_state": risk_state,
        "risk_signal": risk_signal,
        "items": built["items"],
        "leaderboard": built["leaderboard"],
        "top_model": top_model,
        "regime": built["regime"],
        "volatility": built["volatility"],
        "walk_forward": walk_forward,
    }


def score_pending_predictions(symbol_state: Dict[str, Any], current_close: float, current_ts: int) -> List[Dict[str, Any]]:
    pending = list(symbol_state.get("pending_predictions") or [])
    remaining = []
    settled = []
    metrics = symbol_state.setdefault(
        "prediction_metrics",
        {"count": 0, "correct": 0, "brier_sum": 0.0, "mae_sum": 0.0, "by_horizon": {}},
    )
    for pred in pending:
        due_ts = int(pred.get("due_ts", 0) or 0)
        base_close = float(pred.get("entry_close", 0.0) or 0.0)
        if due_ts <= 0 or base_close <= 0 or current_ts < due_ts:
            remaining.append(pred)
            continue
        realized_return = (float(current_close) / base_close) - 1.0
        probability_up = max(0.0, min(1.0, float(pred.get("probability_up", 0.5))))
        observed_up = 1.0 if realized_return > 0 else 0.0
        predicted_direction = 1 if probability_up >= 0.5 else -1
        actual_direction = 1 if realized_return > 0 else (-1 if realized_return < 0 else 0)
        correct = int(predicted_direction == actual_direction and actual_direction != 0)
        brier = (probability_up - observed_up) ** 2
        predicted_return = float(pred.get("predicted_return", 0.0) or 0.0)
        mae = abs(predicted_return - realized_return)
        horizon_bars = int(pred.get("horizon_bars", 0) or 0)

        metrics["count"] = int(metrics.get("count", 0)) + 1
        metrics["correct"] = int(metrics.get("correct", 0)) + correct
        metrics["brier_sum"] = float(metrics.get("brier_sum", 0.0)) + brier
        metrics["mae_sum"] = float(metrics.get("mae_sum", 0.0)) + mae
        bucket = _ensure_horizon_bucket(metrics, horizon_bars)
        bucket["count"] = int(bucket.get("count", 0)) + 1
        bucket["correct"] = int(bucket.get("correct", 0)) + correct
        bucket["brier_sum"] = float(bucket.get("brier_sum", 0.0)) + brier
        bucket["mae_sum"] = float(bucket.get("mae_sum", 0.0)) + mae
        prev_avg = float(bucket.get("avg_realized_return", 0.0))
        n = int(bucket["count"])
        bucket["avg_realized_return"] = prev_avg + ((realized_return - prev_avg) / max(1, n))

        settled.append(
            {
                "prediction_id": pred.get("prediction_id"),
                "model": pred.get("model"),
                "issued_ts": int(pred.get("issued_ts", 0) or 0),
                "due_ts": due_ts,
                "horizon_bars": horizon_bars,
                "predicted_return": predicted_return,
                "probability_up": probability_up,
                "realized_return": realized_return,
                "correct": bool(correct),
                "brier": brier,
                "mae": mae,
            }
        )
    symbol_state["pending_predictions"] = remaining
    return settled


def issue_predictions(
    symbol_state: Dict[str, Any],
    *,
    ts: int,
    close: float,
    signal: float,
    confidence: float,
    top_model: str,
    horizon_bars: List[int],
    bar_ms: int = 900000,
) -> List[Dict[str, Any]]:
    pending = symbol_state.setdefault("pending_predictions", [])
    created = []
    probability_up = max(0.0, min(1.0, 0.5 + (float(signal) * float(confidence) * 0.5)))
    predicted_return = float(signal) * 0.01
    for horizon in horizon_bars:
        horizon = int(horizon)
        pred = {
            "prediction_id": f"{top_model}:{int(ts)}:{horizon}",
            "model": str(top_model),
            "issued_ts": int(ts),
            "due_ts": int(ts) + (horizon * int(bar_ms)),
            "horizon_bars": horizon,
            "entry_close": float(close),
            "predicted_return": predicted_return,
            "probability_up": probability_up,
        }
        pending.append(pred)
        created.append(pred)
    return created


def summarize_prediction_metrics(symbol_state: Dict[str, Any]) -> Dict[str, Any]:
    metrics = symbol_state.get("prediction_metrics") or {}
    count = int(metrics.get("count", 0))
    correct = int(metrics.get("correct", 0))
    return {
        "count": count,
        "directional_accuracy": (correct / count) if count else 0.0,
        "mean_brier": (float(metrics.get("brier_sum", 0.0)) / count) if count else 0.0,
        "mean_abs_error": (float(metrics.get("mae_sum", 0.0)) / count) if count else 0.0,
        "by_horizon": metrics.get("by_horizon", {}),
    }
