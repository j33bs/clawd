from __future__ import annotations

import json
from typing import Any, Dict, Iterable

DEFAULT_SCORES: Dict[str, float] = {
    "cryptocosm": 1.0,
    "cryptoverse": 1.0,
    "coingecko": 1.0,
    "coindesk": 1.0,
    "whale_alert": 1.0,
    "binance_killers": 1.0,
    "wolfx_signals": 1.0,
    "alt_signals": 1.0,
    "fat_pig_signals": 1.0,
}


def _to_float(val: Any) -> float | None:
    try:
        f = float(val)
    except Exception:
        return None
    if f != f:
        return None
    return f


def validate_scores(scores: Dict[Any, Any], normalize: bool = False) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not isinstance(scores, dict):
        return out

    for k, v in scores.items():
        if not isinstance(k, str):
            continue
        fv = _to_float(v)
        if fv is None:
            continue
        if fv < 0:
            fv = 0.0
        out[k] = fv

    if normalize and out:
        total = sum(out.values())
        if total > 0:
            out = {k: v / total for k, v in out.items()}
    return out


def _list_to_scores(items: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    mapping: Dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        ch = item.get("channel")
        wt = item.get("weight")
        if not isinstance(ch, str):
            continue
        fv = _to_float(wt)
        if fv is None:
            continue
        mapping[ch] = fv
    return mapping


def load_channel_scores(path: str, defaults: Dict[str, float] | None = None) -> Dict[str, float]:
    base = dict(DEFAULT_SCORES)
    if defaults is not None and isinstance(defaults, dict):
        base.update(validate_scores(defaults))

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return base

    if isinstance(raw, dict):
        parsed = validate_scores(raw)
    elif isinstance(raw, list):
        parsed = validate_scores(_list_to_scores(raw))
    else:
        return base

    if not parsed:
        return base
    return parsed
