#!/usr/bin/env python3
"""
Trading Sim Runner
Reads market candles + ITC signals, runs paper-trade strategies, writes trade log.

Two strategies (from pipeline config):
  SIM_A: regime_gated_long_flat     — pure price-action regime detection
  SIM_B: itc_sentiment_tilt_long_flat — SIM_A + ITC sentiment tilt

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
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    raise SystemExit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_infra.regime_detector import detect_regime
from core_infra.volatility_metrics import compute_volatility
from core_infra.channel_scoring import load_channel_scores
from core_infra.strategy_blender import blend_signals
from core_infra.econ_log import append_jsonl
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
TAGGED_FILE = BASE_DIR / "itc" / "tagged" / "messages.jsonl"

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
    "econ_logging": False,
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
    "econ_logging": {
        "observe_path": ".openclaw/economics/observe.jsonl",
    },
}


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


def sma(prices, period):
    """Simple moving average of last `period` values."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


class Sim:
    def __init__(self, cfg):
        self.id = cfg["id"]
        self.strategy = cfg["strategy"]
        self.universe = cfg["universe"]
        self.dd_kill = cfg["dd_kill"]
        self.daily_loss = cfg["daily_loss"]
        self.max_trades_per_day = cfg["max_trades_per_day"]
        self.sim_dir = BASE_DIR / "sim" / self.id

        saved = load_sim_state(self.sim_dir)
        if saved:
            self.equity = saved["equity"]
            self.peak_equity = saved["peak_equity"]
            self.last_ts = saved.get("last_ts", 0)
            self.total_trades = saved.get("total_trades", 0)
            self.halted = saved.get("halted", False)
        else:
            self.equity = float(cfg["capital"])
            self.peak_equity = self.equity
            self.last_ts = 0
            self.total_trades = 0
            self.halted = False

        self.initial_capital = float(cfg["capital"])
        self.position = {}  # symbol -> {"side", "entry", "size", "cost", "open_ts"}
        self.day_start_equity = self.equity
        self.trades_today = 0
        self.current_day = None
        self.bars_since_entry = {}  # symbol -> int (count of bars since position opened)

    def _new_day(self, ts):
        """Reset daily counters if we've crossed into a new UTC day."""
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if day != self.current_day:
            self.current_day = day
            self.day_start_equity = self.equity
            self.trades_today = 0

    def _check_halt(self):
        """Check governance kill switches. Returns True if halted."""
        dd = (self.peak_equity - self.equity) / self.peak_equity if self.peak_equity > 0 else 0
        if dd >= self.dd_kill:
            self.halted = True
            return True
        daily_ret = (self.equity - self.day_start_equity) / self.day_start_equity if self.day_start_equity > 0 else 0
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

    def _execute(self, symbol, side, price, ts, reason):
        """Paper-execute a trade. Returns trade record or None."""
        if not self._can_trade():
            return None

        size_usd = self.equity * POSITION_SIZE
        if size_usd < 1.0:
            return None

        cost = size_usd * FEE_RATE + size_usd * (SLIPPAGE_BPS / 10000)

        if side == "open_long":
            units = size_usd / price
            self.position[symbol] = {"side": "long", "entry": price, "size": units, "cost": cost, "open_ts": ts}
            self.equity -= cost
            self.bars_since_entry[symbol] = 0
        elif side == "close_long" and symbol in self.position:
            pos = self.position.pop(symbol)
            pnl = (price - pos["entry"]) * pos["size"] - pos["cost"] - cost
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
            "price": float(price),
            "size_usd": float(size_usd),
            "cost": float(cost),
            "equity_after": float(self.equity),
            "reason": reason,
        }
        if side == "close_long":
            record["pnl"] = float(pnl)
        return record

    def run_bar(self, symbol, bar, closes, sentiment_score, htf_bullish=None):
        """Process one 15m candle bar. Returns list of trade records.
        htf_bullish: True/False/None from 1h regime lookup. None = no data (ignored)."""
        trades = []
        ts = bar["ts"]
        close = bar["c"]
        self._new_day(ts)

        # Track bars since entry for minimum hold
        if symbol in self.position:
            self.bars_since_entry[symbol] = self.bars_since_entry.get(symbol, 0) + 1

        if self._check_halt():
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

    def save(self):
        """Persist state."""
        save_sim_state(self.sim_dir, {
            "sim_id": self.id,
            "strategy": self.strategy,
            "initial_capital": self.initial_capital,
            "equity": self.equity,
            "peak_equity": self.peak_equity,
            "last_ts": self.last_ts,
            "total_trades": self.total_trades,
            "halted": self.halted,
            "pnl": self.equity - self.initial_capital,
            "pnl_pct": ((self.equity - self.initial_capital) / self.initial_capital) * 100,
            "updated_at": int(time.time() * 1000),
        })


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
    f_log = get_feature(config, "econ_logging")
    econ_path = os.path.join("economics", "observe.jsonl")
    meta_features = {
        "regime_detector": f_regime,
        "volatility_metrics": f_vol,
        "channel_scoring": f_chan,
        "strategy_blender": f_blend,
        "econ_logging": f_log,
    }

    sims_cfg = config["sims"]
    if sim_filter:
        sims_cfg = [s for s in sims_cfg if s["id"] == sim_filter]
        if not sims_cfg:
            print(f"No sim found with id={sim_filter}")
            return

    all_symbols = set()
    for s in sims_cfg:
        all_symbols.update(s["universe"])

    # Primary signal: 15m candles
    candles_15m = load_candles(list(all_symbols), CANDLES_15M)
    # HTF confirmation: 1h candles
    candles_1h = load_candles(list(all_symbols), CANDLES_1H)
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

    for cfg in sims_cfg:
        sim = Sim(cfg)
        if full:
            sim.equity = float(cfg["capital"])
            sim.peak_equity = sim.equity
            sim.last_ts = 0
            sim.total_trades = 0
            sim.halted = False

        trades_out = sim.sim_dir / "trades.jsonl"
        sim.sim_dir.mkdir(parents=True, exist_ok=True)

        mode = "w" if full else "a"
        trade_count = 0

        with open(trades_out, mode, encoding="utf-8") as fout:
            for symbol in sim.universe:
                closes = []
                bars = candles_15m.get(symbol, [])

                for bar in bars:
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
                    if sim.strategy == "itc_sentiment_tilt_long_flat" and get_itc_signal is not None:
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
