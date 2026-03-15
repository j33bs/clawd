#!/usr/bin/env python3
"""
Trading Sim Runner
Reads market candles + ITC signals, runs paper-trade strategies, writes trade log.

Two strategies (from pipeline config):
  SIM_A: regime_gated_long_flat     — pure price-action regime detection
  SIM_B: itc_sentiment_tilt_long_flat — SIM_A + ITC sentiment tilt
  SIM_C: ensemble_competing_models_long_flat — adaptive competing models with walk-forward weighting
  SIM_H: latency_consensus_long_flat — local finance brain consensus over sentiment, technicals, risk, and microstructure

Signal timeframes:
  Primary: 15m candles — SMA crossover for regime detection
  Confirmation: 1h candles — SMA crossover for higher-timeframe filter
  Minimum hold: 4 bars (1 hour on 15m) to prevent whipsaw exits

Governance constraints (per config):
  - dd_kill: halt sim if max drawdown exceeded
  - daily_loss: halt trading for the day if daily loss exceeded
  - max_trades_per_day: hard cap on trades per calendar day

No real money. No exchange keys.

Usage:
  python scripts/sim_runner.py              # run all sims on new candles
  python scripts/sim_runner.py --full       # reprocess all candles from scratch
  python scripts/sim_runner.py --sim SIM_A  # run only one sim
"""

import json
import time
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_infra.regime_detector import detect_regime
from core_infra.volatility_metrics import compute_volatility
from core_infra.channel_scoring import load_channel_scores
from core_infra.competing_models import (
    issue_predictions,
    load_model_state,
    run_competing_models,
    save_model_state,
    score_pending_predictions,
    summarize_prediction_metrics,
)
from core_infra.finance_brain import build_live_snapshot, build_retrieval_stats, evaluate_symbol, load_external_inputs
from core_infra.strategy_blender import blend_signals
from core_infra.econ_log import append_jsonl
from core_infra.fill_simulator import estimate_liquidation_price, limit_fill_price, market_fill_price
from core_infra.tick_microstructure import load_tick_feature_snapshot, prune_trade_window, summarize_trade_window
try:
    from workspace.itc.api import get_itc_signal
except Exception:
    get_itc_signal = None
BASE_DIR = REPO_ROOT
DEFAULT_CONFIG_PATH = REPO_ROOT / "pipelines" / "system1_trading.yaml"
DEFAULT_FEATURES_CONFIG_PATH = REPO_ROOT / "pipelines" / "system1_trading.features.yaml"
CONFIG_ENV = "OPENCLAW_CONFIG_PATH"
FEATURES_ENV = "OPENCLAW_FEATURES_CONFIG_PATH"
CANDLES_15M = BASE_DIR / "market" / "candles_15m.jsonl"
CANDLES_1H = BASE_DIR / "market" / "candles_1h.jsonl"
TICK_FEATURES = BASE_DIR / "market" / "tick_features.json"
TICKS_FILE = BASE_DIR / "market" / "ticks.jsonl"
VENUE_QUOTES_FILE = BASE_DIR / "market" / "venue_quotes.jsonl"
CROSS_EXCHANGE_FILE = BASE_DIR / "market" / "cross_exchange_features.json"
FUNDING_HISTORY_FILE = BASE_DIR / "market" / "funding_rates.jsonl"
FUNDING_SNAPSHOT_FILE = BASE_DIR / "market" / "funding_snapshot.json"
TAGGED_FILE = BASE_DIR / "itc" / "tagged" / "messages.jsonl"
DEFAULT_TICK_TAIL_BYTES = 32 * 1024 * 1024
DEFAULT_VENUE_QUOTE_TAIL_BYTES = 8 * 1024 * 1024
DEFAULT_FUNDING_TAIL_BYTES = 2 * 1024 * 1024

# ── Strategy parameters ─────────────────────────────────────────
# SMA crossover for regime detection (15m timeframe)
FAST_PERIOD = 8
SLOW_PERIOD = 21
# HTF regime confirmation (1h timeframe)
HTF_FAST = 8
HTF_SLOW = 21
# Minimum hold period in bars (15m bars → 4 bars = 1 hour)
MIN_HOLD_BARS = 4
# Position sizing: fraction of equity per trade
POSITION_SIZE = 0.05
# Simulated trading costs (round-trip)
FEE_RATE = 0.001  # 0.1% taker fee each side (Binance default)
SLIPPAGE_BPS = 2  # 2 basis points simulated slippage

DEFAULT_FEATURES = {
    "regime_detector": False,
    "volatility_metrics": False,
    "channel_scoring": False,
    "strategy_blender": False,
    "competing_models": True,
    "finance_brain": True,
    "econ_logging": False,
}

DEFAULT_EXECUTION_MODEL = {
    "fee_rate": 0.001,
    "maker_fee_rate": 0.0002,
    "taker_fee_rate": 0.001,
    "slippage_bps": 2.0,
    "spread_bps": 1.0,
    "market_impact_bps_per_10k": 0.5,
    "max_notional_pct": 0.05,
    "max_margin_utilization": 0.5,
    "leverage": 1.0,
    "maintenance_margin_pct": 0.005,
    "funding_bps_8h": 1.0,
    "borrow_bps_daily": 0.0,
    "short_borrow_bps_daily": 0.0,
    "bar_ms": 900000,
    "tick_min_interval_ms": 5000,
    "max_hold_ms": 900000,
    "stop_loss_pct": 0.003,
    "take_profit_pct": 0.004,
    "queue_buffer_bps": 0.25,
}

DEFAULT_FEATURE_PARAMS = {
    "regime_detector": {
        "fast": 13,
        "slow": 47,
        "threshold": 0.001,
    },
    "volatility_metrics": {
        "atr_period": 14,
        "vol_period": 20,
    },
    "channel_scoring": {
        "default_weight": 1.0,
    },
    "strategy_blender": {
        "method": "weighted_mean",
        "min_confidence": 0.0,
        "tie_break": "flat",
    },
    "competing_models": {
        "ewma_decay": 0.9,
        "score_scale": 180.0,
        "hit_rate_scale": 0.8,
        "min_weight": 0.35,
        "max_weight": 3.0,
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
    },
    "execution_model": {
        "fee_rate": 0.001,
        "maker_fee_rate": 0.0002,
        "taker_fee_rate": 0.001,
        "slippage_bps": 2.0,
        "spread_bps": 1.0,
        "market_impact_bps_per_10k": 0.5,
        "max_notional_pct": 0.05,
        "max_margin_utilization": 0.5,
        "leverage": 1.0,
        "maintenance_margin_pct": 0.005,
        "funding_bps_8h": 1.0,
        "borrow_bps_daily": 0.0,
        "short_borrow_bps_daily": 0.0,
        "bar_ms": 900000,
        "tick_min_interval_ms": 5000,
        "max_hold_ms": 900000,
        "stop_loss_pct": 0.003,
        "take_profit_pct": 0.004,
        "queue_buffer_bps": 0.25,
    },
    "finance_brain": {
        "enabled": True,
        "llm_enabled": True,
        "llm_base_url": "http://127.0.0.1:8001/v1",
        "llm_model": "local-assistant",
        "llm_timeout_sec": 6.0,
        "llm_max_tokens": 96,
        "max_live_llm_symbols": 1,
        "retrieval_trade_limit": 24,
        "enter_threshold": 0.28,
        "exit_threshold": -0.12,
        "min_confidence": 0.52,
        "artifact_path": "workspace/artifacts/finance/consensus_latest.json",
        "history_path": "workspace/artifacts/finance/consensus_history.jsonl",
        "external_signal_path": "workspace/state/external/macbook_sentiment.json",
        "fingpt_signal_path": "workspace/state/external/fingpt_sentiment.json",
        "sim_root": "sim",
        "fast_period": 8,
        "slow_period": 21,
    },
    "econ_logging": {
        "observe_path": ".openclaw/economics/observe.jsonl",
    },
}

STRATEGY_RUNTIME_ALIASES = {
    "us_equity_event_impulse": "itc_sentiment_tilt_long_flat",
    "etf_narrative_spillover": "ensemble_competing_models_long_flat",
    "crypto_sentiment_breakout": "latency_consensus_long_flat",
}


def resolve_runtime_strategy(cfg_or_strategy):
    if isinstance(cfg_or_strategy, dict):
        runtime = str(cfg_or_strategy.get("runtime_strategy", "") or "").strip()
        strategy = str(cfg_or_strategy.get("strategy", "") or "").strip()
        return runtime or STRATEGY_RUNTIME_ALIASES.get(strategy, strategy)
    strategy = str(cfg_or_strategy or "").strip()
    return STRATEGY_RUNTIME_ALIASES.get(strategy, strategy)


def deep_merge(base, overlay):
    """Deep-merge overlay into base without mutating inputs."""
    if overlay is None:
        return base
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, val in overlay.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], val)
            else:
                merged[key] = val
        return merged
    return overlay


def load_config(base_path, overlay_path=None):
    """Load base config and optional overlay config, deep-merged."""
    if yaml is None:
        raise RuntimeError("pyyaml is required for load_config(); install with: pip install pyyaml")
    base_path = Path(base_path)
    with open(base_path, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f) or {}

    overlay = {}
    if overlay_path is not None:
        overlay_path = Path(overlay_path)
    if overlay_path is not None and overlay_path.exists():
        with open(overlay_path, "r", encoding="utf-8") as f:
            overlay = yaml.safe_load(f) or {}

    return deep_merge(base, overlay)


def get_feature(cfg, name):
    features = cfg.get("features", {}) if isinstance(cfg, dict) else {}
    if not isinstance(features, dict):
        features = {}
    return bool(features.get(name, DEFAULT_FEATURES.get(name, False)))


def get_feature_params(cfg):
    params = cfg.get("features_params", {}) if isinstance(cfg, dict) else {}
    if not isinstance(params, dict):
        params = {}
    return deep_merge(DEFAULT_FEATURE_PARAMS, params)


def _econ_log(enabled, path, obj):
    if not enabled:
        return
    append_jsonl(path, obj)


def load_candles(symbols, candle_file):
    """Load candles from JSONL, grouped by symbol, sorted by timestamp."""
    by_symbol = {s: [] for s in symbols}
    if not candle_file.exists():
        return by_symbol
    with open(candle_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            sym = c.get("symbol")
            if sym in by_symbol:
                by_symbol[sym].append(c)
    for sym in by_symbol:
        by_symbol[sym].sort(key=lambda x: x["ts"])
    return by_symbol


def _iter_jsonl_tail(path: Path, *, tail_bytes: int | None = None):
    if tail_bytes is None or tail_bytes <= 0:
        with open(path, "r", encoding="utf-8") as handle:
            yield from handle
        return

    size = path.stat().st_size
    with open(path, "rb") as handle:
        if size > tail_bytes:
            handle.seek(size - tail_bytes)
            # Drop the partial first line from the seek position.
            handle.readline()
        for raw in handle:
            try:
                yield raw.decode("utf-8")
            except UnicodeDecodeError:
                yield raw.decode("utf-8", errors="ignore")


def load_ticks(symbols, ticks_file, *, tail_bytes: int | None = DEFAULT_TICK_TAIL_BYTES):
    by_symbol = {s: [] for s in symbols}
    if not ticks_file.exists():
        return by_symbol
    for line in _iter_jsonl_tail(Path(ticks_file), tail_bytes=tail_bytes):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            symbol = row.get("symbol")
            if symbol in by_symbol:
                by_symbol[symbol].append(row)
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda item: int(item.get("ts", 0) or 0))
    return by_symbol


def load_venue_quotes(symbols, quotes_file, *, tail_bytes: int | None = DEFAULT_VENUE_QUOTE_TAIL_BYTES):
    by_symbol = {s: [] for s in symbols}
    if not quotes_file.exists():
        return by_symbol
    for line in _iter_jsonl_tail(Path(quotes_file), tail_bytes=tail_bytes):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            symbol = row.get("symbol")
            if symbol in by_symbol:
                by_symbol[symbol].append(row)
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda item: int(item.get("ts", 0) or 0))
    return by_symbol


def load_funding_history(symbols, funding_file, *, tail_bytes: int | None = DEFAULT_FUNDING_TAIL_BYTES):
    by_symbol = {s: [] for s in symbols}
    if not funding_file.exists():
        return by_symbol
    for line in _iter_jsonl_tail(Path(funding_file), tail_bytes=tail_bytes):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            symbol = row.get("symbol")
            if symbol in by_symbol:
                by_symbol[symbol].append(row)
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda item: int(item.get("ts", 0) or 0))
    return by_symbol


def load_snapshot_file(path):
    if not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def latest_at_or_before(rows, ts):
    latest = None
    for row in rows:
        row_ts = int(row.get("ts", 0) or 0)
        if row_ts > int(ts):
            break
        latest = row
    return latest


def build_cross_exchange_events(quotes):
    by_symbol = {}
    for symbol, rows in quotes.items():
        latest = {}
        events = []
        for row in rows:
            venue = str(row.get("venue") or "")
            latest[venue] = row
            binance = latest.get("binance_spot")
            bybit = latest.get("bybit_spot")
            if not binance or not bybit:
                continue
            binance_mid = binance.get("mid_price")
            bybit_mid = bybit.get("mid_price")
            if not isinstance(binance_mid, (int, float)) or not isinstance(bybit_mid, (int, float)) or float(binance_mid) <= 0:
                continue
            gap_bps = ((float(bybit_mid) / float(binance_mid)) - 1.0) * 10000.0
            events.append(
                {
                    "symbol": symbol,
                    "ts": max(int(binance.get("ts", 0) or 0), int(bybit.get("ts", 0) or 0)),
                    "binance_mid": float(binance_mid),
                    "bybit_mid": float(bybit_mid),
                    "mid_gap_bps": gap_bps,
                    "buy_venue": "binance_spot" if gap_bps > 0 else "bybit_spot",
                    "sell_venue": "bybit_spot" if gap_bps > 0 else "binance_spot",
                }
            )
        by_symbol[symbol] = events
    return by_symbol


def build_htf_regime(candles_1h, symbols):
    """Build a lookup: {symbol: {hour_ts: bool(bullish)}} from 1h candles.
    Used for higher-timeframe regime confirmation."""
    regime = {}
    for sym in symbols:
        bars = candles_1h.get(sym, [])
        regime[sym] = {}
        closes = []
        for bar in bars:
            closes.append(bar["c"])
            if len(closes) > HTF_SLOW + 5:
                closes = closes[-(HTF_SLOW + 5):]
            fast = sma(closes, HTF_FAST) if len(closes) >= HTF_FAST else None
            slow = sma(closes, HTF_SLOW) if len(closes) >= HTF_SLOW else None
            if fast is not None and slow is not None:
                regime[sym][bar["ts"]] = fast > slow
    return regime


def load_itc_sentiment():
    """Load ITC tagged messages and compute a simple sentiment score.
    Returns dict keyed by hour-bucket (ts floored to hour) with score in [-1, 1].
    trade_signal -> +1, news -> +0.3, noise -> 0, spam -> -0.2
    Averaged per hour bucket."""
    TAG_WEIGHT = {"trade_signal": 1.0, "news": 0.3, "noise": 0.0, "spam": -0.2}
    buckets = {}

    if not TAGGED_FILE.exists():
        return buckets

    with open(TAGGED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = msg.get("ts", 0)
            hour_ts = (ts // 3_600_000) * 3_600_000
            tag = msg.get("primary_tag", "noise")
            score = TAG_WEIGHT.get(tag, 0.0)
            buckets.setdefault(hour_ts, []).append(score)

    return {k: sum(v) / len(v) for k, v in buckets.items()}


def ms_to_utc_iso(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_sim_b_tilt(sentiment_score, scale=0.005, max_abs_tilt=0.02):
    """Bounded sentiment tilt for SIM_B sizing/risk threshold adjustment."""
    raw = float(sentiment_score) * float(scale)
    cap = abs(float(max_abs_tilt))
    if raw > cap:
        return cap
    if raw < -cap:
        return -cap
    return raw


def load_sim_state(sim_dir):
    """Load persisted sim state or return None for fresh start."""
    state_file = sim_dir / "state.json"
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_sim_state(sim_dir, state):
    """Persist sim state."""
    sim_dir.mkdir(parents=True, exist_ok=True)
    with open(sim_dir / "state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def summarize_trade_log(trades_path, initial_capital, final_equity, mark_equity=None):
    """Aggregate realized trading outcomes from the persisted trade log."""
    summary = {
        "version": 1,
        "initial_capital": float(initial_capital),
        "final_equity": float(final_equity),
        "mark_equity": float(mark_equity if mark_equity is not None else final_equity),
        "net_equity_change": float(final_equity - initial_capital),
        "net_return_pct": ((float(final_equity) - float(initial_capital)) / float(initial_capital) * 100.0)
        if float(initial_capital) > 0
        else 0.0,
        "realized_pnl": 0.0,
        "round_trips": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "turnover_usd": 0.0,
        "total_fees_usd": 0.0,
        "total_funding_usd": 0.0,
        "total_borrow_usd": 0.0,
        "avg_hold_hours": 0.0,
        "open_positions": 0,
    }
    if not trades_path.exists():
        return summary

    open_positions = {}
    total_hold_hours = 0.0
    with open(trades_path, "r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            symbol = row.get("symbol")
            side = row.get("side")
            ts = int(row.get("ts", 0) or 0)
            summary["turnover_usd"] += float(row.get("size_usd", 0.0) or 0.0)
            fees = float((row.get("cost_components") or {}).get("fee_usd", row.get("cost", 0.0)) or 0.0)
            summary["total_fees_usd"] += fees

            if side == "open_long":
                open_positions[symbol] = {"ts": ts}
                continue

            if side != "close_long":
                continue

            pnl = float(row.get("pnl", 0.0) or 0.0)
            summary["realized_pnl"] += pnl
            summary["round_trips"] += 1
            summary["total_funding_usd"] += float(row.get("funding_cost", 0.0) or 0.0)
            summary["total_borrow_usd"] += float(row.get("borrow_cost", 0.0) or 0.0)
            if pnl > 0:
                summary["wins"] += 1
            elif pnl < 0:
                summary["losses"] += 1

            opened = open_positions.pop(symbol, None)
            if opened is not None and ts > int(opened.get("ts", 0) or 0):
                total_hold_hours += (ts - int(opened["ts"])) / 3_600_000.0

    if summary["round_trips"] > 0:
        summary["win_rate"] = summary["wins"] / summary["round_trips"]
        summary["avg_hold_hours"] = total_hold_hours / summary["round_trips"]
    summary["open_positions"] = len(open_positions)
    return summary


def sma(prices, period):
    """Simple moving average of last `period` values."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


class Sim:
    def __init__(self, cfg):
        self.id = cfg["id"]
        self.strategy_profile = str(cfg["strategy"])
        self.runtime_strategy = resolve_runtime_strategy(cfg)
        self.strategy = self.runtime_strategy
        self.universe = cfg["universe"]
        self.mode = str(cfg.get("mode", "bar"))
        self.dd_kill = cfg["dd_kill"]
        self.daily_loss = cfg["daily_loss"]
        self.max_trades_per_day = cfg["max_trades_per_day"]
        self.sim_dir = BASE_DIR / "sim" / self.id
        self.model_state_path = self.sim_dir / "model_state.json"
        self.metrics_path = self.sim_dir / "metrics.json"
        self.performance_path = self.sim_dir / "performance.json"
        self.prediction_events_path = self.sim_dir / "prediction_events.jsonl"
        self.model_state = load_model_state(self.model_state_path)
        self.execution = deep_merge(DEFAULT_EXECUTION_MODEL, cfg.get("execution") or {})

        saved = load_sim_state(self.sim_dir)
        if saved:
            self.equity = saved["equity"]
            self.peak_equity = saved["peak_equity"]
            self.last_ts = saved.get("last_ts", 0)
            self.total_trades = saved.get("total_trades", 0)
            self.halted = saved.get("halted", False)
            self.position = saved.get("positions", {}) or {}
            self.synthetic_pairs = saved.get("synthetic_pairs", {}) or {}
            self.bars_since_entry = saved.get("bars_since_entry", {}) or {}
            self.last_tick_ts = saved.get("last_tick_ts", {}) or {}
            self.last_marks = saved.get("last_marks", {}) or {}
        else:
            self.equity = float(cfg["capital"])
            self.peak_equity = self.equity
            self.last_ts = 0
            self.total_trades = 0
            self.halted = False
            self.position = {}
            self.synthetic_pairs = {}
            self.bars_since_entry = {}
            self.last_tick_ts = {}
            self.last_marks = {}

        self.initial_capital = float(cfg["capital"])
        self.day_start_equity = self.equity
        self.trades_today = 0
        self.current_day = None

    def _new_day(self, ts):
        """Reset daily counters if we've crossed into a new UTC day."""
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if day != self.current_day:
            self.current_day = day
            self.day_start_equity = self.equity
            self.trades_today = 0

    def _estimate_close_components(self, position, price, ts):
        direction = int(position.get("direction", 1) or 1)
        side = "sell" if direction > 0 else "buy"
        exit_notional_pre = float(position.get("size", 0.0)) * float(price)
        fill = market_fill_price(
            side=side,
            reference_price=float(price),
            best_bid=position.get("best_bid"),
            best_ask=position.get("best_ask"),
            slippage_bps=float(self.execution.get("slippage_bps", SLIPPAGE_BPS)),
            spread_bps=float(self.execution.get("spread_bps", 0.0)),
            impact_bps_per_10k=float(self.execution.get("market_impact_bps_per_10k", 0.0)),
            notional_usd=exit_notional_pre,
        )
        execution_price = float(fill["price"])
        exit_notional = float(position.get("size", 0.0)) * execution_price
        fee_rate = float(self.execution.get("taker_fee_rate", self.execution.get("fee_rate", FEE_RATE)))
        exit_fee = exit_notional * fee_rate
        hold_ms = max(0, int(ts) - int(position.get("open_ts", ts)))
        avg_notional = (float(position.get("entry_notional_usd", 0.0)) + exit_notional) / 2.0
        funding_periods = hold_ms / float(8 * 60 * 60 * 1000)
        borrow_days = hold_ms / float(24 * 60 * 60 * 1000)
        funding_cost = avg_notional * (float(self.execution.get("funding_bps_8h", 0.0)) / 10000.0) * funding_periods * direction
        borrow_daily = float(self.execution.get("borrow_bps_daily", 0.0)) if direction > 0 else float(self.execution.get("short_borrow_bps_daily", self.execution.get("borrow_bps_daily", 0.0)))
        borrow_cost = avg_notional * (borrow_daily / 10000.0) * borrow_days
        cost_components = {
            "fee_usd": exit_fee,
            "slippage_bps": float(fill["slippage_bps"]),
            "spread_bps": float(fill["spread_bps"]),
            "impact_bps": float(fill["impact_bps"]),
            "fill_role": "taker",
        }
        return {
            "price": execution_price,
            "size_usd": exit_notional,
            "cost": exit_fee,
            "cost_components": cost_components,
            "funding_cost": funding_cost,
            "borrow_cost": borrow_cost,
        }

    def _margin_in_use(self):
        total = 0.0
        for position in self.position.values():
            leverage = max(1.0, float(position.get("leverage", 1.0) or 1.0))
            total += float(position.get("entry_notional_usd", 0.0) or 0.0) / leverage
        return total

    def _mark_to_market_equity(self, mark_ts=None, price_overrides=None):
        effective_equity = float(self.equity)
        price_overrides = price_overrides or {}
        for symbol, position in self.position.items():
            price = price_overrides.get(symbol)
            if price is None:
                mark = self.last_marks.get(symbol) or {}
                price = mark.get("price")
            if price in (None, 0):
                continue
            estimate = self._estimate_close_components(position, price, mark_ts or position.get("open_ts", 0))
            direction = int(position.get("direction", 1) or 1)
            unrealized = (
                direction * (float(estimate["price"]) - float(position["entry"])) * float(position["size"])
                - float(estimate["cost"])
                - float(estimate["funding_cost"])
                - float(estimate["borrow_cost"])
            )
            effective_equity += unrealized
        return effective_equity

    def _check_halt(self, mark_equity=None):
        """Check governance kill switches. Returns True if halted."""
        effective_equity = float(mark_equity if mark_equity is not None else self.equity)
        if effective_equity > self.peak_equity:
            self.peak_equity = effective_equity
        dd = (self.peak_equity - effective_equity) / self.peak_equity if self.peak_equity > 0 else 0
        if dd >= self.dd_kill:
            self.halted = True
            return True
        daily_ret = (effective_equity - self.day_start_equity) / self.day_start_equity if self.day_start_equity > 0 else 0
        if daily_ret <= -self.daily_loss:
            return True
        return False

    def _can_trade(self):
        """Check if trade limits allow another trade."""
        if self.halted:
            return False
        if self.trades_today >= self.max_trades_per_day:
            return False
        return True

    def _can_exit(self, symbol):
        """Check if minimum hold period has elapsed."""
        bars = self.bars_since_entry.get(symbol, 0)
        return bars >= MIN_HOLD_BARS

    def _execute(self, symbol, side, price, ts, reason, *, quote=None, order_type="market", limit_price=None, leverage=None, metadata=None):
        """Paper-execute a trade. Returns trade record or None."""
        quote = quote or {}
        best_bid = quote.get("best_bid")
        best_ask = quote.get("best_ask")
        max_notional_pct = float(self.execution.get("max_notional_pct", POSITION_SIZE))
        leverage = max(1.0, float(leverage if leverage is not None else self.execution.get("leverage", 1.0)))
        maintenance_margin_pct = float(self.execution.get("maintenance_margin_pct", 0.005))
        max_margin_utilization = float(self.execution.get("max_margin_utilization", 0.5))

        is_open = side in {"open_long", "open_short"}
        is_close = side in {"close_long", "close_short"}
        if not (is_open or is_close):
            return None
        if is_open and not self._can_trade():
            return None

        direction = 1 if side.endswith("long") else -1

        if is_open:
            margin_budget = self.equity * max_notional_pct
            if (self._margin_in_use() + margin_budget) > (self.equity * max_margin_utilization):
                return None
            size_usd = margin_budget * leverage
            if size_usd < 1.0:
                return None
            fill = None
            if order_type == "limit" and limit_price is not None:
                fill = limit_fill_price(
                    side="buy" if direction > 0 else "sell",
                    limit_price=float(limit_price),
                    trade_price=float(price),
                    queue_buffer_bps=float(self.execution.get("queue_buffer_bps", 0.0)),
                )
            if fill is None:
                fill = market_fill_price(
                    side="buy" if direction > 0 else "sell",
                    reference_price=float(price),
                    best_bid=best_bid,
                    best_ask=best_ask,
                    slippage_bps=float(self.execution.get("slippage_bps", SLIPPAGE_BPS)),
                    spread_bps=float(self.execution.get("spread_bps", 0.0)),
                    impact_bps_per_10k=float(self.execution.get("market_impact_bps_per_10k", 0.0)),
                    notional_usd=size_usd,
                )
                order_type = "market"
            execution_price = float(fill["price"])
            fee_rate = float(
                self.execution.get(
                    "maker_fee_rate" if fill["role"] == "maker" else "taker_fee_rate",
                    self.execution.get("fee_rate", FEE_RATE),
                )
            )
            cost = size_usd * fee_rate
            cost_components = {
                "fee_usd": size_usd * fee_rate,
                "slippage_bps": float(fill["slippage_bps"]),
                "spread_bps": float(fill["spread_bps"]),
                "impact_bps": float(fill["impact_bps"]),
                "fill_role": fill["role"],
            }
            units = size_usd / execution_price
            self.position[symbol] = {
                "side": "long" if direction > 0 else "short",
                "direction": direction,
                "entry": execution_price,
                "size": units,
                "cost": cost,
                "open_ts": ts,
                "entry_price_raw": price,
                "entry_notional_usd": size_usd,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "leverage": leverage,
                "liquidation_price": estimate_liquidation_price(execution_price, direction, leverage, maintenance_margin_pct),
                "metadata": dict(metadata or {}),
            }
            self.equity -= cost
            self.bars_since_entry[symbol] = 0
            funding_cost = 0.0
            borrow_cost = 0.0
        elif symbol in self.position:
            pos = self.position.get(symbol)
            if (direction > 0 and int(pos.get("direction", 1)) <= 0) or (direction < 0 and int(pos.get("direction", 1)) >= 0):
                return None
            pos = self.position.pop(symbol)
            if order_type == "limit" and limit_price is not None:
                fill = limit_fill_price(
                    side="sell" if int(pos.get("direction", 1)) > 0 else "buy",
                    limit_price=float(limit_price),
                    trade_price=float(price),
                    queue_buffer_bps=float(self.execution.get("queue_buffer_bps", 0.0)),
                )
            else:
                fill = None
            if fill is None:
                close_estimate = self._estimate_close_components({**pos, "best_bid": best_bid, "best_ask": best_ask}, price, ts)
            else:
                execution_price = float(fill["price"])
                size_usd = float(pos.get("size", 0.0)) * execution_price
                fee_rate = float(self.execution.get("maker_fee_rate", self.execution.get("fee_rate", FEE_RATE)))
                cost = size_usd * fee_rate
                hold_ms = max(0, int(ts) - int(pos.get("open_ts", ts)))
                avg_notional = (float(pos.get("entry_notional_usd", 0.0)) + size_usd) / 2.0
                funding_periods = hold_ms / float(8 * 60 * 60 * 1000)
                borrow_days = hold_ms / float(24 * 60 * 60 * 1000)
                direction_open = int(pos.get("direction", 1) or 1)
                funding_cost = avg_notional * (float(self.execution.get("funding_bps_8h", 0.0)) / 10000.0) * funding_periods * direction_open
                borrow_daily = float(self.execution.get("borrow_bps_daily", 0.0)) if direction_open > 0 else float(self.execution.get("short_borrow_bps_daily", self.execution.get("borrow_bps_daily", 0.0)))
                borrow_cost = avg_notional * (borrow_daily / 10000.0) * borrow_days
                close_estimate = {
                    "price": execution_price,
                    "size_usd": size_usd,
                    "cost": cost,
                    "cost_components": {
                        "fee_usd": cost,
                        "slippage_bps": 0.0,
                        "spread_bps": 0.0,
                        "impact_bps": 0.0,
                        "fill_role": "maker",
                    },
                    "funding_cost": funding_cost,
                    "borrow_cost": borrow_cost,
                }
            execution_price = float(close_estimate["price"])
            size_usd = float(close_estimate["size_usd"])
            cost = float(close_estimate["cost"])
            cost_components = dict(close_estimate["cost_components"])
            funding_cost = float(close_estimate["funding_cost"])
            borrow_cost = float(close_estimate["borrow_cost"])
            direction_open = int(pos.get("direction", 1) or 1)
            pnl = direction_open * (execution_price - pos["entry"]) * pos["size"] - pos["cost"] - cost - funding_cost - borrow_cost
            self.equity += pnl
            self.bars_since_entry.pop(symbol, None)
        else:
            return None

        self.trades_today += 1
        self.total_trades += 1
        self.peak_equity = max(self.peak_equity, self.equity)

        record = {
            "ts": ts,
            "sim": self.id,
            "symbol": symbol,
            "side": side,
            "price": float(execution_price),
            "price_raw": float(price),
            "size_usd": float(size_usd),
            "cost": float(cost),
            "cost_components": cost_components,
            "equity_after": float(self.equity),
            "reason": reason,
        }
        if side == "close_long":
            record["pnl"] = float(pnl)
            record["funding_cost"] = float(funding_cost)
            record["borrow_cost"] = float(borrow_cost)
        if side == "close_short":
            record["pnl"] = float(pnl)
            record["funding_cost"] = float(funding_cost)
            record["borrow_cost"] = float(borrow_cost)
        if is_open:
            record["leverage"] = float(leverage)
            record["order_type"] = str(order_type)
        if metadata:
            record["meta"] = dict(metadata)
        return record

    def _append_prediction_event(self, event: dict):
        self.sim_dir.mkdir(parents=True, exist_ok=True)
        with open(self.prediction_events_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def run_bar(self, symbol, bar, closes, sentiment_score, htf_bullish=None):
        """Process one 15m candle bar. Returns list of trade records.
        htf_bullish: True/False/None from 1h regime lookup. None = no data (ignored)."""
        trades = []
        ts = bar["ts"]
        close = bar["c"]
        self._new_day(ts)
        self.last_marks[symbol] = {"price": close, "ts": ts}

        # Track bars since entry for minimum hold
        if symbol in self.position:
            self.bars_since_entry[symbol] = self.bars_since_entry.get(symbol, 0) + 1

        mark_equity = self._mark_to_market_equity(mark_ts=ts, price_overrides={symbol: close})
        if self._check_halt(mark_equity=mark_equity):
            if symbol in self.position:
                t = self._execute(symbol, "close_long", close, ts, "halt_exit")
                if t:
                    trades.append(t)
            return trades

        fast = sma(closes, FAST_PERIOD)
        slow = sma(closes, SLOW_PERIOD)

        if fast is None or slow is None:
            return trades

        regime_bullish = fast > slow
        htf_confirms = htf_bullish if htf_bullish is not None else True

        if self.strategy == "regime_gated_long_flat":
            confirmed_bull = regime_bullish and htf_confirms

            if confirmed_bull and symbol not in self.position:
                reason = "regime_bull+htf" if htf_bullish is not None else "regime_bull"
                t = self._execute(symbol, "open_long", close, ts, reason)
                if t:
                    trades.append(t)
            elif not confirmed_bull and symbol in self.position and self._can_exit(symbol):
                reason = "regime_flat" if not regime_bullish else "htf_flat"
                t = self._execute(symbol, "close_long", close, ts, reason)
                if t:
                    trades.append(t)

        elif self.strategy == "itc_sentiment_tilt_long_flat":
            tilt = compute_sim_b_tilt(sentiment_score)
            adjusted_bullish = (fast - slow) / slow > (-0.001 + tilt) if slow > 0 else False
            confirmed_bull = adjusted_bullish and htf_confirms

            if confirmed_bull and symbol not in self.position:
                reason = f"itc_tilt({sentiment_score:.2f})+htf" if htf_bullish is not None else f"itc_tilt({sentiment_score:.2f})"
                t = self._execute(symbol, "open_long", close, ts, reason)
                if t:
                    trades.append(t)
            elif not confirmed_bull and symbol in self.position and self._can_exit(symbol):
                reason = f"itc_flat({sentiment_score:.2f})" if not adjusted_bullish else "htf_flat"
                t = self._execute(symbol, "close_long", close, ts, reason)
                if t:
                    trades.append(t)

        return trades

    def run_bar_with_competing_models(self, symbol, bar, closes, sentiment_score, candles_window, htf_bullish=None, tick_snapshot=None, params=None):
        """Process one 15m candle using adaptive competing models."""
        trades = []
        ts = bar["ts"]
        close = bar["c"]
        self._new_day(ts)
        self.last_marks[symbol] = {"price": close, "ts": ts}

        if symbol in self.position:
            self.bars_since_entry[symbol] = self.bars_since_entry.get(symbol, 0) + 1

        mark_equity = self._mark_to_market_equity(mark_ts=ts, price_overrides={symbol: close})
        if self._check_halt(mark_equity=mark_equity):
            if symbol in self.position:
                t = self._execute(symbol, "close_long", close, ts, "halt_exit")
                if t:
                    trades.append(t)
            return trades, None

        symbol_state = self.model_state.setdefault("symbols", {}).setdefault(symbol, {})
        settled = score_pending_predictions(symbol_state, current_close=close, current_ts=ts)
        for row in settled:
            self._append_prediction_event(
                {
                    "event": "forecast_scored",
                    "sim": self.id,
                    "symbol": symbol,
                    **row,
                }
            )
        decision = run_competing_models(
            symbol_state=symbol_state,
            ts=ts,
            closes=closes,
            candles=candles_window,
            sentiment_score=sentiment_score,
            htf_bullish=htf_bullish,
            include_sentiment=True,
            tick_snapshot=tick_snapshot,
            params=params,
        )
        issued = issue_predictions(
            symbol_state,
            ts=ts,
            close=close,
            signal=decision["signal"],
            confidence=decision["confidence"],
            top_model=str(decision.get("top_model") or "ensemble"),
            horizon_bars=list((params or {}).get("forecast_horizons_bars", [4, 16])),
            bar_ms=int(self.execution.get("bar_ms", 900000)),
        )
        for row in issued:
            self._append_prediction_event(
                {
                    "event": "forecast_issued",
                    "sim": self.id,
                    "symbol": symbol,
                    **row,
                }
            )

        if decision["enter_long"] and symbol not in self.position:
            leader = str(decision.get("top_model") or "ensemble")
            reason = f"ensemble_long({decision['signal']:.2f},{decision['confidence']:.2f})/{leader}"
            t = self._execute(symbol, "open_long", close, ts, reason)
            if t:
                trades.append(t)
        elif decision["exit_long"] and symbol in self.position and self._can_exit(symbol):
            reason = f"ensemble_flat({decision['signal']:.2f},{decision['risk_state']})"
            t = self._execute(symbol, "close_long", close, ts, reason)
            if t:
                trades.append(t)

        return trades, decision

    def run_bar_with_finance_brain(
        self,
        symbol,
        bar,
        closes,
        sentiment_score,
        *,
        htf_bullish=None,
        tick_snapshot=None,
        cross_exchange_row=None,
        funding_row=None,
        external_inputs=None,
        retrieval_stats=None,
        params=None,
        allow_llm=False,
    ):
        trades = []
        ts = bar["ts"]
        close = bar["c"]
        self._new_day(ts)
        self.last_marks[symbol] = {"price": close, "ts": ts}

        if symbol in self.position:
            self.bars_since_entry[symbol] = self.bars_since_entry.get(symbol, 0) + 1

        mark_equity = self._mark_to_market_equity(mark_ts=ts, price_overrides={symbol: close})
        if self._check_halt(mark_equity=mark_equity):
            if symbol in self.position:
                t = self._execute(symbol, "close_long", close, ts, "halt_exit")
                if t:
                    trades.append(t)
            return trades, None

        decision = evaluate_symbol(
            symbol=symbol,
            ts=ts,
            closes=closes,
            htf_bullish=htf_bullish,
            itc_sentiment=sentiment_score,
            tick_snapshot=tick_snapshot,
            cross_exchange_row=cross_exchange_row,
            funding_row=funding_row,
            external_inputs=external_inputs,
            retrieval_stats=retrieval_stats,
            params=params,
            allow_llm=allow_llm,
        )

        bias = float(decision["decision"]["bias"])
        confidence = float(decision["decision"]["confidence"])
        risk_state = str(decision["decision"].get("risk_state") or "normal")
        action = str(decision["decision"].get("action") or "hold")

        if symbol in self.position:
            if (action == "flat" or risk_state == "elevated" or bias <= float((params or {}).get("exit_threshold", -0.12))) and self._can_exit(symbol):
                t = self._execute(symbol, "close_long", close, ts, f"finance_flat({bias:.2f},{risk_state})")
                if t:
                    trades.append(t)
            return trades, decision

        if action == "buy" and confidence >= float((params or {}).get("min_confidence", 0.52)):
            t = self._execute(symbol, "open_long", close, ts, f"finance_buy({bias:.2f},{confidence:.2f})")
            if t:
                trades.append(t)
        return trades, decision

    def _maybe_force_liquidation(self, symbol, price, ts, quote=None):
        position = self.position.get(symbol)
        if not position:
            return None
        liq = position.get("liquidation_price")
        if liq in (None, 0):
            return None
        direction = int(position.get("direction", 1) or 1)
        if (direction > 0 and float(price) <= float(liq)) or (direction < 0 and float(price) >= float(liq)):
            side = "close_long" if direction > 0 else "close_short"
            return self._execute(symbol, side, price, ts, "liquidation", quote=quote, order_type="market")
        return None

    def _current_return_pct(self, symbol, price):
        position = self.position.get(symbol)
        if not position or float(position.get("entry", 0.0) or 0.0) <= 0:
            return 0.0
        direction = int(position.get("direction", 1) or 1)
        return direction * ((float(price) / float(position["entry"])) - 1.0)

    def run_tick_scalper(self, symbol, tick, *, tick_snapshot, sentiment_score=0.0, htf_bullish=None):
        trades = []
        ts = int(tick["ts"])
        price = float(tick["price"])
        quote = {"best_bid": tick_snapshot.get("best_bid"), "best_ask": tick_snapshot.get("best_ask")}
        self._new_day(ts)
        self.last_marks[symbol] = {"price": price, "ts": ts}
        if ts - int(self.last_tick_ts.get(symbol, 0) or 0) < int(self.execution.get("tick_min_interval_ms", 5000)):
            return trades
        self.last_tick_ts[symbol] = ts

        liquidation = self._maybe_force_liquidation(symbol, price, ts, quote=quote)
        if liquidation:
            trades.append(liquidation)
            return trades

        trade_count = int(tick_snapshot.get("trade_count", 0) or 0)
        spread_bps = float(tick_snapshot.get("spread_bps", 9999.0) or 9999.0)
        if trade_count < 20 or spread_bps > 8.0:
            return trades

        signal = (
            float(tick_snapshot.get("imbalance", 0.0) or 0.0) * 0.8
            + (float(tick_snapshot.get("momentum_1m", 0.0) or 0.0) / 0.0015)
            + (float(sentiment_score) * 0.35)
        )
        if htf_bullish is False:
            signal = min(signal, 0.0)
        position = self.position.get(symbol)
        if position:
            ret = self._current_return_pct(symbol, price)
            hold_ms = ts - int(position.get("open_ts", ts))
            if (
                ret >= float(self.execution.get("take_profit_pct", 0.004))
                or ret <= -float(self.execution.get("stop_loss_pct", 0.003))
                or hold_ms >= int(self.execution.get("max_hold_ms", 900000))
                or signal * int(position.get("direction", 1) or 1) < -0.4
            ):
                side = "close_long" if int(position.get("direction", 1) or 1) > 0 else "close_short"
                trade = self._execute(symbol, side, price, ts, "tick_scalper_exit", quote=quote, order_type="market")
                if trade:
                    trades.append(trade)
            return trades

        if signal >= 0.9:
            trade = self._execute(symbol, "open_long", price, ts, "tick_scalper_long", quote=quote, order_type="market", leverage=3.0)
            if trade:
                trades.append(trade)
        elif signal <= -0.9 and htf_bullish is not True:
            trade = self._execute(symbol, "open_short", price, ts, "tick_scalper_short", quote=quote, order_type="market", leverage=3.0)
            if trade:
                trades.append(trade)
        return trades

    def run_tick_grid(self, symbol, tick, *, tick_snapshot):
        trades = []
        ts = int(tick["ts"])
        price = float(tick["price"])
        quote = {"best_bid": tick_snapshot.get("best_bid"), "best_ask": tick_snapshot.get("best_ask")}
        self._new_day(ts)
        self.last_marks[symbol] = {"price": price, "ts": ts}
        if ts - int(self.last_tick_ts.get(symbol, 0) or 0) < int(self.execution.get("tick_min_interval_ms", 5000)):
            return trades
        self.last_tick_ts[symbol] = ts

        trade_count = int(tick_snapshot.get("trade_count", 0) or 0)
        vwap = float(tick_snapshot.get("vwap", 0.0) or 0.0)
        realized_vol = float(tick_snapshot.get("realized_vol", 0.0) or 0.0)
        momentum = float(tick_snapshot.get("momentum_1m", 0.0) or 0.0)
        if trade_count < 20 or vwap <= 0 or realized_vol > 0.0015:
            return trades
        grid_step = max(0.0006, min(0.0035, abs(momentum) * 2.0 + realized_vol * 8.0))
        long_entry = vwap * (1.0 - grid_step)
        long_exit = vwap * (1.0 + (grid_step * 0.7))
        position = self.position.get(symbol)
        if position:
            ret = self._current_return_pct(symbol, price)
            if price >= long_exit or ret <= -float(self.execution.get("stop_loss_pct", 0.003)):
                trade = self._execute(symbol, "close_long", price, ts, "grid_exit", quote=quote, order_type="limit", limit_price=max(long_exit, price))
                if trade:
                    trades.append(trade)
            return trades
        if price <= long_entry:
            trade = self._execute(symbol, "open_long", price, ts, "grid_entry", quote=quote, order_type="limit", limit_price=long_entry, leverage=1.0)
            if trade:
                trades.append(trade)
        return trades

    def run_tick_funding_carry(self, symbol, tick, *, tick_snapshot, funding_row):
        trades = []
        if funding_row is None:
            return trades
        ts = int(tick["ts"])
        price = float(tick["price"])
        quote = {"best_bid": tick_snapshot.get("best_bid"), "best_ask": tick_snapshot.get("best_ask")}
        self._new_day(ts)
        self.last_marks[symbol] = {"price": price, "ts": ts}
        if ts - int(self.last_tick_ts.get(symbol, 0) or 0) < max(60_000, int(self.execution.get("tick_min_interval_ms", 5000))):
            return trades
        self.last_tick_ts[symbol] = ts

        liquidation = self._maybe_force_liquidation(symbol, price, ts, quote=quote)
        if liquidation:
            trades.append(liquidation)
            return trades

        funding_rate = float(funding_row.get("last_funding_rate", 0.0) or 0.0)
        realized_vol = float(tick_snapshot.get("realized_vol", 0.0) or 0.0)
        spread_bps = float(tick_snapshot.get("spread_bps", 9999.0) or 9999.0)
        position = self.position.get(symbol)
        entry_min_abs_funding_rate = max(0.0, float(self.execution.get("entry_min_abs_funding_rate", 0.0001) or 0.0001))
        exit_min_abs_funding_rate = max(0.0, float(self.execution.get("exit_min_abs_funding_rate", entry_min_abs_funding_rate * 0.5) or (entry_min_abs_funding_rate * 0.5)))
        if position:
            ret = self._current_return_pct(symbol, price)
            if (
                abs(funding_rate) < exit_min_abs_funding_rate
                or realized_vol > 0.0016
                or ret >= float(self.execution.get("take_profit_pct", 0.004))
                or ret <= -float(self.execution.get("stop_loss_pct", 0.003))
            ):
                side = "close_long" if int(position.get("direction", 1) or 1) > 0 else "close_short"
                trade = self._execute(symbol, side, price, ts, "funding_carry_exit", quote=quote, order_type="market")
                if trade:
                    trades.append(trade)
            return trades

        if spread_bps > 10.0 or realized_vol > 0.0012:
            return trades
        if funding_rate >= entry_min_abs_funding_rate:
            trade = self._execute(symbol, "open_short", price, ts, "funding_carry_short", quote=quote, order_type="market", leverage=2.0)
            if trade:
                trades.append(trade)
        elif funding_rate <= -entry_min_abs_funding_rate:
            trade = self._execute(symbol, "open_long", price, ts, "funding_carry_long", quote=quote, order_type="market", leverage=2.0)
            if trade:
                trades.append(trade)
        return trades

    def run_quote_arb(self, symbol, event):
        trades = []
        ts = int(event["ts"])
        gap_bps = float(event.get("mid_gap_bps", 0.0) or 0.0)
        self._new_day(ts)
        mark_price = float(event.get("binance_mid", 0.0) or event.get("bybit_mid", 0.0) or 0.0)
        if mark_price > 0:
            self.last_marks[symbol] = {"price": mark_price, "ts": ts}
        if self._check_halt(mark_equity=self._mark_to_market_equity(mark_ts=ts)):
            if symbol in self.synthetic_pairs:
                position = self.synthetic_pairs.pop(symbol)
                close_cost = float(position["notional"]) * float(self.execution.get("taker_fee_rate", self.execution.get("fee_rate", FEE_RATE))) * 2.0
                self.equity -= close_cost
                self.trades_today += 1
                self.total_trades += 1
                trades.append(
                    {
                        "ts": ts,
                        "sim": self.id,
                        "symbol": symbol,
                        "side": "close_pair",
                        "price": float(event.get("binance_mid", 0.0) or 0.0),
                        "price_raw": float(event.get("bybit_mid", 0.0) or 0.0),
                        "size_usd": float(position["notional"]),
                        "cost": close_cost,
                        "cost_components": {"fee_usd": close_cost, "fill_role": "taker_pair"},
                        "equity_after": float(self.equity),
                        "reason": "halt_exit",
                        "pnl": -(float(position.get("cost_open", 0.0)) + close_cost),
                    }
                )
            return trades
        position = self.synthetic_pairs.get(symbol)
        entry_threshold = 3.0
        exit_threshold = 0.8
        max_margin_pct = float(self.execution.get("max_notional_pct", POSITION_SIZE))
        leverage = max(1.0, float(self.execution.get("leverage", 1.0)))
        leg_fee = float(self.execution.get("taker_fee_rate", self.execution.get("fee_rate", FEE_RATE)))
        notional = self.equity * max_margin_pct * leverage
        if position:
            pnl = ((position["entry_gap_bps"] - gap_bps) / 10000.0) * float(position["notional"])
            if abs(gap_bps) <= exit_threshold or pnl <= -(float(self.execution.get("stop_loss_pct", 0.003)) * float(position["notional"])) or pnl >= float(self.execution.get("take_profit_pct", 0.004)) * float(position["notional"]):
                close_cost = float(position["notional"]) * leg_fee * 2.0
                net_pnl = pnl - float(position["cost_open"]) - close_cost
                self.equity += net_pnl
                record = {
                    "ts": ts,
                    "sim": self.id,
                    "symbol": symbol,
                    "side": "close_pair",
                    "price": float(event.get("binance_mid", 0.0) or 0.0),
                    "price_raw": float(event.get("bybit_mid", 0.0) or 0.0),
                    "size_usd": float(position["notional"]),
                    "cost": close_cost,
                    "cost_components": {"fee_usd": close_cost, "fill_role": "taker_pair"},
                    "equity_after": float(self.equity),
                    "reason": "arb_exit",
                    "pnl": net_pnl,
                }
                self.synthetic_pairs.pop(symbol, None)
                self.trades_today += 1
                self.total_trades += 1
                trades.append(record)
            return trades
        if abs(gap_bps) < entry_threshold or notional < 1.0:
            return trades
        open_cost = notional * leg_fee * 2.0
        self.equity -= open_cost
        self.synthetic_pairs[symbol] = {
            "entry_gap_bps": gap_bps,
            "notional": notional,
            "open_ts": ts,
            "cost_open": open_cost,
        }
        self.trades_today += 1
        self.total_trades += 1
        trades.append(
            {
                "ts": ts,
                "sim": self.id,
                "symbol": symbol,
                "side": "open_pair",
                "price": float(event.get("binance_mid", 0.0) or 0.0),
                "price_raw": float(event.get("bybit_mid", 0.0) or 0.0),
                "size_usd": float(notional),
                "cost": open_cost,
                "cost_components": {"fee_usd": open_cost, "fill_role": "taker_pair"},
                "equity_after": float(self.equity),
                "reason": "arb_entry",
                "meta": {"gap_bps": gap_bps, "buy_venue": event.get("buy_venue"), "sell_venue": event.get("sell_venue")},
            }
        )
        return trades

    def save(self):
        """Persist state."""
        mark_ts = max([self.last_ts] + [int((mark or {}).get("ts", 0) or 0) for mark in self.last_marks.values()])
        mark_equity = self._mark_to_market_equity(mark_ts=mark_ts)
        save_sim_state(self.sim_dir, {
            "sim_id": self.id,
            "strategy": self.strategy_profile,
            "runtime_strategy": self.runtime_strategy,
            "initial_capital": self.initial_capital,
            "dd_kill": self.dd_kill,
            "daily_loss": self.daily_loss,
            "equity": self.equity,
            "mark_equity": mark_equity,
            "peak_equity": self.peak_equity,
            "last_ts": self.last_ts,
            "total_trades": self.total_trades,
            "halted": self.halted,
            "open_positions": len(self.position) + len(self.synthetic_pairs),
            "positions": self.position,
            "synthetic_pairs": self.synthetic_pairs,
            "bars_since_entry": self.bars_since_entry,
            "last_tick_ts": self.last_tick_ts,
            "last_marks": self.last_marks,
            "pnl": self.equity - self.initial_capital,
            "pnl_pct": ((self.equity - self.initial_capital) / self.initial_capital) * 100,
            "updated_at": int(time.time() * 1000),
        })
        save_model_state(self.model_state_path, self.model_state)
        metrics = {"version": 1, "symbols": {}}
        for symbol, symbol_state in (self.model_state.get("symbols") or {}).items():
            metrics["symbols"][symbol] = summarize_prediction_metrics(symbol_state)
        self.metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        performance = summarize_trade_log(
            self.sim_dir / "trades.jsonl",
            initial_capital=self.initial_capital,
            final_equity=self.equity,
            mark_equity=mark_equity,
        )
        self.performance_path.write_text(json.dumps(performance, indent=2) + "\n", encoding="utf-8")


def resolve_path(cli_value, env_var, default_path):
    if cli_value:
        return Path(cli_value)
    env_val = os.getenv(env_var)
    if env_val:
        return Path(env_val)
    return Path(default_path)


def run(sim_filter=None, full=False, config_path=None, features_path=None):
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    if not Path(config_path).exists():
        print(f"ERROR: config not found at {config_path}. Use --config to override.")
        return

    config = load_config(config_path, features_path)
    feature_params = get_feature_params(config)
    f_regime = get_feature(config, "regime_detector")
    f_vol = get_feature(config, "volatility_metrics")
    f_chan = get_feature(config, "channel_scoring")
    f_blend = get_feature(config, "strategy_blender")
    f_competing = get_feature(config, "competing_models")
    f_finance = get_feature(config, "finance_brain")
    f_log = get_feature(config, "econ_logging")
    econ_path = os.path.join("economics", "observe.jsonl")
    meta_features = {
        "regime_detector": f_regime,
        "volatility_metrics": f_vol,
        "channel_scoring": f_chan,
        "strategy_blender": f_blend,
        "competing_models": f_competing,
        "finance_brain": f_finance,
        "econ_logging": f_log,
    }
    competing_params = feature_params.get("competing_models", {})
    execution_params = feature_params.get("execution_model", {})
    finance_params = feature_params.get("finance_brain", {})

    sims_cfg = config["sims"]
    if sim_filter:
        sims_cfg = [s for s in sims_cfg if s["id"] == sim_filter]
        if not sims_cfg:
            print(f"No sim found with id={sim_filter}")
            return
    else:
        sims_cfg = [s for s in sims_cfg if bool(s.get("enabled", True))]

    all_symbols = set()
    for s in sims_cfg:
        all_symbols.update(s["universe"])

    tick_strategies = {"tick_crypto_scalping", "tick_grid_reversion", "perp_funding_carry"}
    quote_strategies = {"cross_exchange_spread_arbitrage"}
    active_strategies = {resolve_runtime_strategy(cfg) for cfg in sims_cfg}
    need_ticks = bool(active_strategies.intersection(tick_strategies))
    need_quote_events = bool(active_strategies.intersection(quote_strategies))
    # Only the tick scalper currently consumes historical venue quotes for best bid/ask.
    need_tick_quotes = "tick_crypto_scalping" in active_strategies
    need_venue_quotes = need_quote_events or need_tick_quotes
    need_funding_history = "perp_funding_carry" in active_strategies

    # Primary signal: 15m candles
    candles_15m = load_candles(list(all_symbols), CANDLES_15M)
    # HTF confirmation: 1h candles
    candles_1h = load_candles(list(all_symbols), CANDLES_1H)
    ticks = load_ticks(list(all_symbols), TICKS_FILE) if need_ticks else {s: [] for s in all_symbols}
    venue_quotes = load_venue_quotes(list(all_symbols), VENUE_QUOTES_FILE) if need_venue_quotes else {s: [] for s in all_symbols}
    funding_history = load_funding_history(list(all_symbols), FUNDING_HISTORY_FILE) if need_funding_history else {s: [] for s in all_symbols}
    tick_features = load_tick_feature_snapshot(TICK_FEATURES)
    cross_exchange_snapshot = load_snapshot_file(CROSS_EXCHANGE_FILE)
    funding_snapshot = load_snapshot_file(FUNDING_SNAPSHOT_FILE)
    sentiment = load_itc_sentiment()
    itc_artifact_root = REPO_ROOT / "workspace" / "artifacts" / "itc"
    itc_lookback = os.getenv("OPENCLAW_ITC_LOOKBACK", "8h")

    htf_regime = build_htf_regime(candles_1h, list(all_symbols))

    total_15m = sum(len(v) for v in candles_15m.values())
    htf_count = sum(len(v) for v in candles_1h.values())
    if total_15m == 0:
        print("No 15m candle data. Run: python scripts/market_stream.py first")
        return

    print(f"Loaded {total_15m} candles (15m) + {htf_count} (1h) across {len(all_symbols)} symbols")
    print(f"Loaded {len(sentiment)} sentiment buckets from ITC")
    total_ticks = sum(len(v) for v in ticks.values())
    total_quotes = sum(len(v) for v in venue_quotes.values())
    total_funding = sum(len(v) for v in funding_history.values())
    if total_ticks:
        print(f"Loaded {total_ticks} ticks across {len([s for s, rows in ticks.items() if rows])} symbols")
    if total_quotes:
        print(f"Loaded {total_quotes} venue quote updates")
    if total_funding:
        print(f"Loaded {total_funding} funding updates")
    if tick_features:
        print(f"Loaded tick feature snapshots for {len(tick_features)} symbols")
    if (cross_exchange_snapshot.get("symbols") or {}):
        print(f"Loaded cross-exchange snapshot for {len(cross_exchange_snapshot.get('symbols', {}))} symbols")
    if (funding_snapshot.get("symbols") or {}):
        print(f"Loaded funding snapshot for {len(funding_snapshot.get('symbols', {}))} symbols")
    finance_external_inputs = (
        load_external_inputs(
            external_signal_path=finance_params.get("external_signal_path"),
            fingpt_signal_path=finance_params.get("fingpt_signal_path"),
        )
        if f_finance
        else {}
    )
    active_sim_ids = [str(cfg.get("id") or "").strip() for cfg in sims_cfg if str(cfg.get("id") or "").strip() and bool(cfg.get("enabled", True))]
    finance_params = deep_merge(finance_params, {"retrieval_sim_ids": active_sim_ids}) if f_finance else finance_params
    finance_retrieval = (
        build_retrieval_stats(
            sorted(all_symbols),
            sim_root=BASE_DIR / "sim",
            limit=int(finance_params.get("retrieval_trade_limit", 24)),
            sim_ids=active_sim_ids,
        )
        if f_finance
        else {}
    )
    if f_finance and bool(finance_params.get("enabled", True)):
        try:
            finance_live = build_live_snapshot(
                candles_15m=candles_15m,
                htf_regime=htf_regime,
                tick_features=tick_features,
                cross_exchange_snapshot=cross_exchange_snapshot,
                funding_snapshot=funding_snapshot,
                symbols=sorted(all_symbols),
                itc_sentiment_by_hour=sentiment,
                params=finance_params,
            )
            print(f"Built finance brain snapshot for {len(finance_live.get('symbols', {}))} symbols")
        except Exception as exc:
            print(f"WARN: finance brain snapshot failed: {exc}")

    for cfg in sims_cfg:
        sim_cfg = deep_merge(dict(cfg), {"execution": execution_params})
        sim = Sim(sim_cfg)
        if full:
            sim.equity = float(sim_cfg["capital"])
            sim.peak_equity = sim.equity
            sim.last_ts = 0
            sim.total_trades = 0
            sim.halted = False
            sim.model_state = {"version": 1, "symbols": {}}
            sim.position = {}
            sim.synthetic_pairs = {}
            sim.bars_since_entry = {}
            sim.last_tick_ts = {}
            sim.last_marks = {}
            if sim.prediction_events_path.exists():
                sim.prediction_events_path.unlink()

        trades_out = sim.sim_dir / "trades.jsonl"
        sim.sim_dir.mkdir(parents=True, exist_ok=True)

        mode = "w" if full else "a"
        trade_count = 0
        with open(trades_out, mode, encoding="utf-8") as fout:
            if sim.strategy in tick_strategies:
                for symbol in sim.universe:
                    symbol_ticks = ticks.get(symbol, [])
                    htf_rows = htf_regime.get(symbol, {})
                    funding_rows = funding_history.get(symbol, [])
                    symbol_quotes = (
                        [row for row in venue_quotes.get(symbol, []) if str(row.get("venue") or "") == "binance_spot"]
                        if sim.strategy == "tick_crypto_scalping"
                        else []
                    )
                    if not symbol_ticks:
                        continue
                    window_trades = []
                    quote_idx = 0
                    current_quote = None
                    for tick in symbol_ticks:
                        if not full and int(tick["ts"]) <= int(sim.last_ts):
                            continue
                        ts = int(tick["ts"])
                        hour_ts = (ts // 3_600_000) * 3_600_000
                        sent = sentiment.get(hour_ts, 0.0)
                        htf_bull = htf_rows.get(hour_ts)
                        if htf_bull is None and htf_rows:
                            earlier = [t for t in htf_rows if t <= ts]
                            if earlier:
                                htf_bull = htf_rows[max(earlier)]
                        while quote_idx < len(symbol_quotes) and int(symbol_quotes[quote_idx].get("ts", 0) or 0) <= ts:
                            current_quote = symbol_quotes[quote_idx]
                            quote_idx += 1
                        window_trades.append(tick)
                        prune_trade_window(window_trades, now_ts=ts, lookback_ms=300000)
                        latest_snapshot = summarize_trade_window(
                            symbol,
                            window_trades,
                            best_bid=(current_quote or {}).get("best_bid", (tick_features.get(symbol) or {}).get("best_bid")),
                            best_ask=(current_quote or {}).get("best_ask", (tick_features.get(symbol) or {}).get("best_ask")),
                            lookback_ms=300000,
                        )
                        funding_row = latest_at_or_before(funding_rows, ts)
                        if sim.strategy == "tick_crypto_scalping":
                            bar_trades = sim.run_tick_scalper(symbol, tick, tick_snapshot=latest_snapshot, sentiment_score=sent, htf_bullish=htf_bull)
                        elif sim.strategy == "tick_grid_reversion":
                            bar_trades = sim.run_tick_grid(symbol, tick, tick_snapshot=latest_snapshot)
                        else:
                            bar_trades = sim.run_tick_funding_carry(symbol, tick, tick_snapshot=latest_snapshot, funding_row=funding_row)
                        for t in bar_trades:
                            fout.write(json.dumps(t, ensure_ascii=False) + "\n")
                            trade_count += 1
                        sim.last_ts = max(sim.last_ts, ts)
            elif sim.strategy in quote_strategies:
                quote_events = build_cross_exchange_events(venue_quotes)
                for symbol in sim.universe:
                    events = quote_events.get(symbol, [])
                    for event in events:
                        if not full and int(event["ts"]) <= int(sim.last_ts):
                            continue
                        bar_trades = sim.run_quote_arb(symbol, event)
                        for t in bar_trades:
                            fout.write(json.dumps(t, ensure_ascii=False) + "\n")
                            trade_count += 1
                        sim.last_ts = max(sim.last_ts, int(event["ts"]))
            for symbol in ([] if sim.strategy in tick_strategies.union(quote_strategies) else sim.universe):
                closes = []
                bars = candles_15m.get(symbol, [])

                for bar_idx, bar in enumerate(bars):
                    if not full and bar["ts"] <= sim.last_ts:
                        closes.append(bar["c"])
                        if len(closes) > SLOW_PERIOD + 5:
                            closes = closes[-(SLOW_PERIOD + 5):]
                        continue

                    closes.append(bar["c"])
                    if len(closes) > SLOW_PERIOD + 5:
                        closes = closes[-(SLOW_PERIOD + 5):]

                    # Get sentiment for this hour
                    hour_ts = (bar["ts"] // 3_600_000) * 3_600_000
                    sent = sentiment.get(hour_ts, 0.0)
                    sentiment_source = "legacy_tagged"
                    sentiment_reason = "ok_legacy"
                    if sim.strategy in {"itc_sentiment_tilt_long_flat", "ensemble_competing_models_long_flat"} and get_itc_signal is not None:
                        selected = get_itc_signal(
                            ts_utc=ms_to_utc_iso(bar["ts"]),
                            lookback=itc_lookback,
                            policy={
                                "artifacts_root": str(itc_artifact_root),
                                "run_id": f"sim_{sim.id}",
                            },
                        )
                        if selected.get("reason") == "ok" and selected.get("signal"):
                            metrics = selected["signal"].get("metrics", {})
                            sent = float(metrics.get("sentiment", 0.0))
                            sentiment_source = str(selected["signal"].get("source", "contract"))
                            sentiment_reason = "ok"
                        else:
                            sentiment_reason = str(selected.get("reason", "missing"))

                    # Get HTF regime: find the most recent 1h bar at or before this 15m bar
                    htf_bull = None
                    sym_htf = htf_regime.get(symbol, {})
                    if sym_htf:
                        htf_bull = sym_htf.get(hour_ts)
                        if htf_bull is None:
                            earlier = [t for t in sym_htf if t <= bar["ts"]]
                            if earlier:
                                htf_bull = sym_htf[max(earlier)]

                    model_decision = None
                    finance_decision = None
                    if sim.strategy == "ensemble_competing_models_long_flat" and f_competing:
                        candles_window = bars[max(0, (bar_idx + 1) - 128):bar_idx + 1]
                        tick_snapshot = tick_features.get(symbol)
                        bar_trades, model_decision = sim.run_bar_with_competing_models(
                            symbol,
                            bar,
                            closes,
                            sent,
                            candles_window,
                            htf_bullish=htf_bull,
                            tick_snapshot=tick_snapshot,
                            params=competing_params,
                        )
                    elif sim.strategy == "latency_consensus_long_flat" and f_finance:
                        cross_symbols = cross_exchange_snapshot.get("symbols") if isinstance(cross_exchange_snapshot, dict) else {}
                        funding_symbols = funding_snapshot.get("symbols") if isinstance(funding_snapshot, dict) else {}
                        allow_live_llm = (not full) and (bar_idx >= (len(bars) - 1))
                        bar_trades, finance_decision = sim.run_bar_with_finance_brain(
                            symbol,
                            bar,
                            closes,
                            sent,
                            htf_bullish=htf_bull,
                            tick_snapshot=tick_features.get(symbol),
                            cross_exchange_row=(cross_symbols or {}).get(symbol) if isinstance(cross_symbols, dict) else None,
                            funding_row=(funding_symbols or {}).get(symbol) if isinstance(funding_symbols, dict) else None,
                            external_inputs=finance_external_inputs,
                            retrieval_stats=finance_retrieval.get(symbol),
                            params=finance_params,
                            allow_llm=allow_live_llm,
                        )
                    else:
                        bar_trades = sim.run_bar(symbol, bar, closes, sent, htf_bullish=htf_bull)
                    if sim.strategy == "itc_sentiment_tilt_long_flat":
                        _econ_log(f_log, econ_path, {
                            "ts": ms_to_utc_iso(bar["ts"]),
                            "sim": sim.id,
                            "symbol": symbol,
                            "type": "sim_b_tilt_applied",
                            "payload": {
                                "sentiment": float(sent),
                                "tilt": compute_sim_b_tilt(sent),
                                "reason": sentiment_reason,
                                "source": sentiment_source,
                            },
                            "meta": {"features": meta_features},
                        })
                    if sim.strategy == "ensemble_competing_models_long_flat" and model_decision is not None:
                        _econ_log(f_log, econ_path, {
                            "ts": ms_to_utc_iso(bar["ts"]),
                            "sim": sim.id,
                            "symbol": symbol,
                            "type": "sim_c_ensemble_signal",
                            "payload": {
                                "signal": float(model_decision["signal"]),
                                "confidence": float(model_decision["confidence"]),
                                "risk_state": str(model_decision["risk_state"]),
                                "risk_signal": float(model_decision["risk_signal"]),
                                "walk_forward": dict(model_decision["walk_forward"]),
                                "leaderboard": list(model_decision.get("leaderboard", []))[:5],
                                "tick_snapshot": dict(tick_features.get(symbol, {})) if tick_features.get(symbol) else None,
                            },
                            "meta": {"features": meta_features},
                        })
                    if sim.strategy == "latency_consensus_long_flat" and finance_decision is not None:
                        _econ_log(f_log, econ_path, {
                            "ts": ms_to_utc_iso(bar["ts"]),
                            "sim": sim.id,
                            "symbol": symbol,
                            "type": "finance_brain_signal",
                            "payload": {
                                "decision": dict(finance_decision.get("decision") or {}),
                                "agents": dict(finance_decision.get("agents") or {}),
                                "incoming_source_scores": dict(finance_decision.get("incoming_source_scores") or {}),
                                "learned_weights": dict(finance_decision.get("learned_weights") or {}),
                                "llm_manager": dict(finance_decision.get("llm_manager") or {}),
                            },
                            "meta": {"features": meta_features},
                        })
                    for t in bar_trades:
                        fout.write(json.dumps(t, ensure_ascii=False) + "\n")
                        trade_count += 1

                    sim.last_ts = max(sim.last_ts, bar["ts"])

        sim.save()

        if f_regime or f_vol or f_chan or f_blend:
            ts_iso = datetime.now(timezone.utc).isoformat()

            if f_chan:
                score_path = os.path.join("itc", "channel_scores.json")
                scores = load_channel_scores(score_path, defaults=None)
                _econ_log(f_log, econ_path, {
                    "ts": ts_iso,
                    "sim": sim.id,
                    "type": "channel_scores",
                    "payload": {
                        "channels": list(scores.keys()),
                        "weights": scores,
                    },
                    "meta": {"features": meta_features},
                })

            for symbol in sim.universe:
                bars = candles_15m.get(symbol, [])

                if f_regime:
                    prices = [b.get("c") for b in bars]
                    regime_out = detect_regime(prices, feature_params.get("regime_detector", {}))
                    _econ_log(f_log, econ_path, {
                        "ts": ts_iso,
                        "sim": sim.id,
                        "symbol": symbol,
                        "type": "regime",
                        "payload": regime_out,
                        "meta": {"features": meta_features},
                    })

                if f_vol:
                    vol_out = compute_volatility(
                        candles=bars,
                        prices=None,
                        params=feature_params.get("volatility_metrics", {}),
                    )
                    _econ_log(f_log, econ_path, {
                        "ts": ts_iso,
                        "sim": sim.id,
                        "symbol": symbol,
                        "type": "volatility",
                        "payload": vol_out,
                        "meta": {"features": meta_features},
                    })

            # Blender demo intentionally skipped unless a clean signal list exists.

        pnl = sim.equity - sim.initial_capital
        pnl_pct = (pnl / sim.initial_capital) * 100
        dd = ((sim.peak_equity - sim.equity) / sim.peak_equity * 100) if sim.peak_equity > 0 else 0

        status = "HALTED" if sim.halted else "ACTIVE"
        print(f"  [{sim.id}] {status} | equity=${sim.equity:.2f} | pnl={pnl_pct:+.2f}% | dd={dd:.2f}% | trades={trade_count} new, {sim.total_trades} total")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading sim runner")
    parser.add_argument("--full", action="store_true", help="Reprocess all candles from scratch")
    parser.add_argument("--sim", type=str, default=None, help="Run only this sim ID")
    parser.add_argument("--config", type=str, default=None, help="Override base config path")
    parser.add_argument("--features-config", type=str, default=None, help="Override features overlay path")
    args = parser.parse_args()
    cfg_path = resolve_path(args.config, CONFIG_ENV, DEFAULT_CONFIG_PATH)
    feat_path = resolve_path(args.features_config, FEATURES_ENV, DEFAULT_FEATURES_CONFIG_PATH)
    run(sim_filter=args.sim, full=args.full, config_path=cfg_path, features_path=feat_path)
