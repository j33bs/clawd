"""Periodic strategy review for AU-legal paper trading lanes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_ARTIFACT_PATH = REPO_ROOT / "workspace" / "runtime" / "sim_strategy_review.json"
WEEKLY_X_STRATEGY_PATHS = (
    Path.home() / "Taildrive" / "shared" / "weekly_x_strategy_review.json",
    REPO_ROOT / "workspace" / "runtime" / "weekly_x_strategy_review.json",
)
DEFAULT_REVIEW_INTERVAL_HOURS = 6
DEFAULT_WEEKLY_X_MAX_AGE_HOURS = 8 * 24
DEFAULT_FREE_SIGNAL_MAX_AGE_MINUTES = 180


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace("+00:00", "Z")


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


def _age_minutes(ts: Any) -> float | None:
    parsed = _parse_iso(ts)
    if parsed is None:
        return None
    return max(0.0, (_now_utc() - parsed).total_seconds() / 60.0)


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _free_realtime_signal_snapshot(finance_brain: dict[str, Any]) -> dict[str, Any]:
    external = finance_brain.get("external_signal") if isinstance(finance_brain.get("external_signal"), dict) else {}
    inputs = external.get("inputs") if isinstance(external, dict) else {}
    macbook = inputs.get("macbook_sentiment") if isinstance(inputs, dict) else {}
    fingpt = inputs.get("fingpt_sentiment") if isinstance(inputs, dict) else {}
    if not isinstance(macbook, dict):
        macbook = {}
    if not isinstance(fingpt, dict):
        fingpt = {}
    primary_status = str(macbook.get("status") or "missing")
    secondary_status = str(fingpt.get("status") or "missing")
    primary_generated_at = macbook.get("generated_at")
    secondary_generated_at = fingpt.get("generated_at")
    primary_age_minutes = _age_minutes(primary_generated_at)
    secondary_age_minutes = _age_minutes(secondary_generated_at)
    primary_stale = bool(
        primary_status == "stale"
        or (
            primary_status == "ok"
            and (primary_age_minutes is None or primary_age_minutes > DEFAULT_FREE_SIGNAL_MAX_AGE_MINUTES)
        )
    )
    secondary_stale = bool(
        secondary_status == "stale"
        or (
            secondary_status == "ok"
            and (secondary_age_minutes is None or secondary_age_minutes > DEFAULT_FREE_SIGNAL_MAX_AGE_MINUTES)
        )
    )
    primary_ready = primary_status == "ok" and not primary_stale
    secondary_ready = secondary_status == "ok" and not secondary_stale
    ready = primary_ready or secondary_ready
    active_source_id = "macbook_sentiment"
    active_source_label = "MacBook realtime sentiment"
    active_payload = macbook
    if secondary_ready and not primary_ready:
        active_source_id = "fingpt_sentiment"
        active_source_label = "Dali fallback sentiment"
        active_payload = fingpt
    if ready:
        status = "fresh"
        if active_source_id == "fingpt_sentiment":
            summary = "Free realtime sentiment is fresh enough to guide the day-to-day crypto paper lanes via the Dali fallback while the MacBook feed is stale."
        else:
            summary = "Free realtime sentiment is fresh enough to guide the day-to-day crypto paper lanes."
    elif primary_status in {"ok", "stale"} or secondary_status in {"ok", "stale"}:
        status = "stale"
        summary = "Free realtime sentiment is present but stale, so treat it as context only until refreshed."
    else:
        status = "missing"
        summary = "Free realtime sentiment is missing."
    return {
        "ready": ready,
        "status": status,
        "source": "free realtime sentiment",
        "active_source_id": active_source_id,
        "active_source_label": active_source_label,
        "primary_status": primary_status,
        "secondary_status": secondary_status,
        "producer": active_payload.get("producer"),
        "model_resolved": active_payload.get("model_resolved"),
        "generated_at": active_payload.get("generated_at"),
        "primary_age_minutes": round(primary_age_minutes, 1) if primary_age_minutes is not None else None,
        "secondary_age_minutes": round(secondary_age_minutes, 1) if secondary_age_minutes is not None else None,
        "max_age_minutes": DEFAULT_FREE_SIGNAL_MAX_AGE_MINUTES,
        "stale": status == "stale",
        "summary": summary,
    }


def _weekly_x_strategy_snapshot() -> dict[str, Any]:
    review_path = next((path for path in WEEKLY_X_STRATEGY_PATHS if path.exists()), None)
    default_path = str(WEEKLY_X_STRATEGY_PATHS[0])
    if review_path is None:
        return {
            "status": "missing",
            "source": "c_lawd weekly X strategy review",
            "path": default_path,
            "updated_at": None,
            "summary": "Waiting for a weekly X-guided strategy note from c_lawd.",
        }
    payload = _read_json(review_path)
    generated_at = None
    summary = ""
    producer = None
    if isinstance(payload, dict):
        generated_at = payload.get("generated_at")
        summary = str(payload.get("summary") or payload.get("thesis") or payload.get("focus") or "").strip()
        producer = payload.get("producer")
    if not generated_at:
        generated_at = _iso(datetime.fromtimestamp(review_path.stat().st_mtime, tz=timezone.utc))
    age_minutes = _age_minutes(generated_at)
    stale = bool(age_minutes is not None and age_minutes > (DEFAULT_WEEKLY_X_MAX_AGE_HOURS * 60))
    return {
        "status": "stale" if stale else "fresh",
        "source": "c_lawd weekly X strategy review",
        "path": str(review_path),
        "updated_at": generated_at,
        "summary": summary or "Weekly X-guided strategic note available.",
        "producer": producer,
    }


def _review_priority(recommendation: str) -> int:
    return {"retire": 0, "retune": 1, "keep": 2}.get(str(recommendation or "").strip().lower(), 3)


def _strategy_semantic_profile(sim: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(sim.get("display_name") or ""),
            str(sim.get("bucket") or ""),
            str(sim.get("thesis") or ""),
            str(sim.get("status_note") or ""),
        ]
    ).lower()
    if any(term in text for term in ("sentiment", "itc", "consensus", "bias", "event")):
        return "high"
    if any(term in text for term in ("reversion", "crypto", "impulse", "breakout")):
        return "medium"
    return "low"


def _review_row(
    sim: dict[str, Any],
    *,
    free_signal: dict[str, Any],
    weekly_x_review: dict[str, Any],
) -> dict[str, Any]:
    live_return_pct = float(sim.get("live_return_pct", sim.get("net_return_pct", 0.0)) or 0.0)
    live_pnl = float(sim.get("live_equity_change", sim.get("net_equity_change", 0.0)) or 0.0)
    fees = float(sim.get("fees_usd", 0.0) or 0.0)
    trades = int(sim.get("round_trips", 0) or 0)
    win_rate = float(sim.get("win_rate", 0.0) or 0.0)
    open_positions = int(sim.get("open_positions", 0) or 0)
    stage = str(sim.get("stage") or "").strip().lower()
    strategy_role = str(sim.get("strategy_role") or "").strip().lower()
    continuous_improvement = bool(sim.get("continuous_improvement", False))
    improvement_focus = str(sim.get("improvement_focus") or "").strip()
    target_venue = str(sim.get("target_venue") or "").strip()
    data_dependency = str(sim.get("data_dependency") or "").strip()
    updated_age = _age_minutes(sim.get("updated_at"))
    stale = bool(updated_age is not None and updated_age > 180.0)
    fee_drag = bool(sim.get("fee_drag"))
    semantic_profile = _strategy_semantic_profile(sim)

    score = 0
    reasons: list[str] = []
    actions: list[str] = []

    if live_return_pct > 0.15:
        score += 2
        reasons.append("positive live P/L")
    elif live_return_pct > 0.0:
        score += 1
        reasons.append("slightly positive live P/L")
    elif live_return_pct <= -3.0:
        score -= 3
        reasons.append("deep drawdown")
    elif live_return_pct <= -1.0:
        score -= 2
        reasons.append("material negative live P/L")
    elif live_return_pct < 0.0:
        score -= 1
        reasons.append("slightly negative live P/L")

    if fee_drag:
        score -= 2
        reasons.append("fee drag active")
        actions.append("reduce churn and require wider expected edge")
    elif trades >= 40 and fees >= 2.0 and live_return_pct <= 0.0:
        score -= 1
        reasons.append("fees large relative to current edge")
        actions.append("tighten turnover budget or widen entry threshold")

    if trades >= 12 and win_rate < 35.0:
        score -= 1
        reasons.append("weak hit rate on live sample")
        actions.append("recalibrate sizing and stop/exit policy")
    elif trades <= 10:
        reasons.append("sample still small")

    if trades == 0:
        reasons.append("no closed trades yet")
        if stage == "staged":
            actions.append("seed the first shadow sample once the required feed is live")
        else:
            actions.append("loosen the trigger budget until the lane produces a meaningful sample")

    if stale:
        score -= 1
        reasons.append("review data stale")
        actions.append("refresh upstream state before trusting the lane")

    if stage == "staged":
        reasons.append("candidate lane is staged behind venue/data wiring")
        if data_dependency:
            actions.append(f"bring {data_dependency.replace('_', ' ')} online before promotion")
        elif target_venue:
            actions.append(f"bring the {target_venue} feed online before promotion")
    elif strategy_role == "candidate" and str(data_dependency or "").startswith("alpaca_"):
        reasons.append("candidate lane is running on fallback market data")
        actions.append(f"upgrade to {data_dependency.replace('_', ' ')} once credentials and collectors are live")
    elif strategy_role == "control":
        reasons.append("control lane is retained for comparative benchmarking")

    if free_signal.get("ready") and semantic_profile == "high":
        score += 1
        reasons.append("free realtime sentiment is available")
        actions.append("compare live triggers against the free sentiment stack")
    elif free_signal.get("ready") and semantic_profile == "medium":
        reasons.append("free realtime sentiment is available as a context layer")
    elif not free_signal.get("ready") and semantic_profile in {"high", "medium"}:
        reasons.append("realtime sentiment context is missing")
        actions.append("treat the lane as control-only until realtime sentiment returns")

    if weekly_x_review.get("status") == "fresh" and semantic_profile in {"high", "medium"}:
        reasons.append("weekly X strategy note is available")
        actions.append("apply the next weekly X-guided ranking adjustment sparingly")
    elif weekly_x_review.get("status") == "missing" and semantic_profile in {"high", "medium"}:
        actions.append("prepare a weekly X-guided sleeve review on c_lawd")

    if continuous_improvement and improvement_focus:
        actions.append(f"keep retuning against {improvement_focus}")

    if live_return_pct <= -4.0:
        recommendation = "retire"
    elif fee_drag or score <= -2 or (trades >= 40 and live_return_pct < 0.0):
        recommendation = "retune"
    else:
        recommendation = "keep"

    if recommendation == "keep" and not actions:
        actions.append("keep as the current AU paper control lane")
    elif recommendation == "retire":
        actions.append("move budget to a stronger AU-legal sleeve")

    summary = "; ".join(reasons[:3]) if reasons else "stable"
    if recommendation == "retune":
        summary = f"retune around {summary}"
    elif recommendation == "retire":
        summary = f"retire because {summary}"
    else:
        summary = f"keep because {summary}"

    return {
        "id": str(sim.get("id") or ""),
        "display_name": str(sim.get("display_name") or sim.get("id") or "sim"),
        "bucket": str(sim.get("bucket") or ""),
        "recommendation": recommendation,
        "score": score,
        "semantic_profile": semantic_profile,
        "stage": stage or "paper_live",
        "strategy_role": strategy_role or "candidate",
        "continuous_improvement": continuous_improvement,
        "improvement_focus": improvement_focus,
        "target_venue": target_venue,
        "summary": summary,
        "actions": actions[:3],
        "live_equity_change": round(live_pnl, 2),
        "live_return_pct": round(live_return_pct, 3),
        "fees_usd": round(fees, 2),
        "round_trips": trades,
        "win_rate": round(win_rate, 1),
        "open_positions": open_positions,
        "stale": stale,
    }


def build_sim_strategy_review(
    sims: list[dict[str, Any]],
    finance_brain: dict[str, Any],
    trading_strategy: dict[str, Any] | None = None,
    *,
    review_interval_hours: int = DEFAULT_REVIEW_INTERVAL_HOURS,
) -> dict[str, Any]:
    generated_at = _now_utc()
    active_book = [sim for sim in sims if bool(sim.get("active_book"))]
    free_signal = _free_realtime_signal_snapshot(finance_brain if isinstance(finance_brain, dict) else {})
    weekly_x_review = _weekly_x_strategy_snapshot()
    review_rows = [
        _review_row(
            sim,
            free_signal=free_signal,
            weekly_x_review=weekly_x_review,
        )
        for sim in active_book
    ]
    review_rows.sort(
        key=lambda item: (_review_priority(item.get("recommendation", "")), float(item.get("live_return_pct", 0.0)), str(item.get("id", "")))
    )
    integration = trading_strategy.get("integration") if isinstance(trading_strategy, dict) and isinstance(trading_strategy.get("integration"), dict) else {}
    pipeline_notes = list(integration.get("notes") or [])[:2] if isinstance(integration, dict) else []

    keep_count = sum(1 for row in review_rows if row.get("recommendation") == "keep")
    retune_count = sum(1 for row in review_rows if row.get("recommendation") == "retune")
    retire_count = sum(1 for row in review_rows if row.get("recommendation") == "retire")

    focus = (
        "Free realtime sentiment should drive the day-to-day crypto paper lanes. "
        "The paid X API should only adjust overall sleeve ranking on a weekly cadence."
    )

    return {
        "status": "active" if review_rows else "warning",
        "generated_at": _iso(generated_at),
        "next_review_at": _iso(generated_at + timedelta(hours=max(1, int(review_interval_hours)))),
        "review_interval_hours": max(1, int(review_interval_hours)),
        "artifact_path": str(REVIEW_ARTIFACT_PATH),
        "focus": focus,
        "free_realtime_signal": free_signal,
        "weekly_x_review": weekly_x_review,
        "summary": {
            "active_count": len(review_rows),
            "keep_count": keep_count,
            "retune_count": retune_count,
            "retire_count": retire_count,
        },
        "recommendations": review_rows,
        "pipeline_notes": pipeline_notes,
    }


def write_sim_strategy_review(
    sims: list[dict[str, Any]],
    finance_brain: dict[str, Any],
    trading_strategy: dict[str, Any] | None = None,
    *,
    artifact_path: Path = REVIEW_ARTIFACT_PATH,
    review_interval_hours: int = DEFAULT_REVIEW_INTERVAL_HOURS,
) -> dict[str, Any]:
    payload = build_sim_strategy_review(
        sims,
        finance_brain,
        trading_strategy,
        review_interval_hours=review_interval_hours,
    )
    _write_json_atomic(artifact_path, payload)
    return payload


def load_or_build_sim_strategy_review(
    sims: list[dict[str, Any]],
    finance_brain: dict[str, Any],
    trading_strategy: dict[str, Any] | None = None,
    *,
    artifact_path: Path = REVIEW_ARTIFACT_PATH,
    review_interval_hours: int = DEFAULT_REVIEW_INTERVAL_HOURS,
) -> dict[str, Any]:
    payload = _read_json(artifact_path)
    if isinstance(payload, dict):
        age_minutes = _age_minutes(payload.get("generated_at"))
        max_age = max(60.0, float(review_interval_hours) * 120.0)
        if age_minutes is not None and age_minutes <= max_age:
            return payload
    built = build_sim_strategy_review(
        sims,
        finance_brain,
        trading_strategy,
        review_interval_hours=review_interval_hours,
    )
    built["status"] = "ephemeral" if built.get("status") == "active" else built.get("status")
    return built


__all__ = [
    "DEFAULT_REVIEW_INTERVAL_HOURS",
    "REVIEW_ARTIFACT_PATH",
    "WEEKLY_X_STRATEGY_PATHS",
    "build_sim_strategy_review",
    "load_or_build_sim_strategy_review",
    "write_sim_strategy_review",
]
