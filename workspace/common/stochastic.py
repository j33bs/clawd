#!/usr/bin/env python3
"""Bounded randomness utilities.

Use randomness for delivery and exploration, not for truth/state.
This module provides constrained, inspectable stochastic choices.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable


@dataclass(frozen=True)
class WindowedChoice:
    value: Any
    rationale: dict[str, Any]


def _rng(seed: int | None = None) -> random.Random:
    return random.Random(seed) if seed is not None else random.Random()


def bounded_randint(low: int, high: int, *, seed: int | None = None) -> int:
    if high < low:
        high = low
    return _rng(seed).randint(low, high)


def next_time_in_window(
    *,
    now: datetime,
    min_gap_minutes: int,
    max_gap_minutes: int,
    seed: int | None = None,
) -> WindowedChoice:
    minutes = bounded_randint(min_gap_minutes, max_gap_minutes, seed=seed)
    when = now + timedelta(minutes=minutes)
    return WindowedChoice(
        value=when,
        rationale={
            "kind": "next_time_in_window",
            "min_gap_minutes": min_gap_minutes,
            "max_gap_minutes": max_gap_minutes,
            "selected_gap_minutes": minutes,
            "seed": seed,
        },
    )


def choose_weighted(
    items: Iterable[Any],
    *,
    weight_key: str = "weight",
    default_weight: float = 1.0,
    seed: int | None = None,
) -> WindowedChoice | None:
    rows = list(items)
    if not rows:
        return None
    rng = _rng(seed)
    weights = []
    for row in rows:
        if isinstance(row, dict):
            w = float(row.get(weight_key, default_weight))
        else:
            w = float(default_weight)
        weights.append(max(0.0, w))
    if sum(weights) <= 0:
        weights = [1.0 for _ in rows]
    picked = rng.choices(rows, weights=weights, k=1)[0]
    return WindowedChoice(
        value=picked,
        rationale={
            "kind": "choose_weighted",
            "weight_key": weight_key,
            "seed": seed,
            "population": len(rows),
        },
    )


def pick_with_cooldown(
    items: Iterable[dict[str, Any]],
    *,
    cooldown_ids: set[str] | None = None,
    id_key: str = "id",
    seed: int | None = None,
) -> WindowedChoice | None:
    rows = list(items)
    if not rows:
        return None
    cooldown_ids = cooldown_ids or set()
    eligible = [row for row in rows if str(row.get(id_key)) not in cooldown_ids]
    pool = eligible or rows
    picked = choose_weighted(pool, seed=seed)
    if picked is None:
        return None
    return WindowedChoice(
        value=picked.value,
        rationale={
            "kind": "pick_with_cooldown",
            "seed": seed,
            "cooldown_ids": sorted(cooldown_ids),
            "eligible": len(eligible),
            "fallback_to_full_pool": not bool(eligible),
        },
    )
