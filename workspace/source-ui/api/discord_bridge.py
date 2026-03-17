"""Discord bridge previews for project and runtime state.

This module keeps Discord downstream of canonical repo/runtime state.
It can render channel-specific payload previews locally and optionally
deliver them via webhooks when explicitly invoked by an operator.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request
from zoneinfo import ZoneInfo

from .boundary_state import build_discord_channel_boundary

SOURCE_UI_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = SOURCE_UI_ROOT / "config" / "discord_bridge.json"
STATUS_PATH = SOURCE_UI_ROOT / "state" / "discord_bridge_status.json"
ENV_FILE = Path.home() / ".config" / "openclaw" / "discord-bridge.env"
_ENV_LOADED = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(ts: str | None) -> datetime | None:
    raw = str(ts or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_env_file_once(path: Path = ENV_FILE) -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _truncate(text: str, limit: int = 1900) -> str:
    if len(text) <= limit:
        return text
    if limit <= 1:
        return "…"
    return f"{text[: limit - 1]}…"


def _preview_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bullet_lines(title: str, lines: list[str], footer: str | None = None) -> str:
    body = "\n".join(f"- {line}" for line in lines if str(line).strip()) or "- No items."
    text = f"**{title}**\n{body}"
    if footer:
        text = f"{text}\n\n{footer}"
    return _truncate(text)


def _format_component_line(component: dict[str, Any]) -> str:
    return f"{component.get('name', component.get('id', 'component'))}: {component.get('status', 'unknown')} ({component.get('details', 'no detail')})"


def _format_signed_currency(value: Any) -> str:
    amount = float(value or 0.0)
    return f"{'+' if amount >= 0 else '-'}${abs(amount):.2f}"


def _format_signed_percent(value: Any) -> str:
    return f"{float(value or 0.0):+.2f}%"


def _format_sim_totals_line(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Active book: 0 sims"
    sim_count = len(rows)
    trade_count = sum(int(row.get("round_trips", 0) or 0) for row in rows)
    open_positions = sum(int(row.get("open_positions", 0) or 0) for row in rows)
    initial_capital = sum(float(row.get("initial_capital", 0.0) or 0.0) for row in rows)
    live_equity = sum(float(row.get("live_equity", row.get("final_equity", 0.0)) or 0.0) for row in rows)
    live_pnl = sum(float(row.get("live_equity_change", row.get("net_equity_change", 0.0)) or 0.0) for row in rows)
    booked_pnl = sum(float(row.get("net_equity_change", 0.0) or 0.0) for row in rows)
    live_return_pct = (live_pnl / initial_capital * 100.0) if initial_capital > 0.0 else 0.0
    bits = [
        f"Active book: {sim_count} sims",
        f"{trade_count} trades",
        f"live capital ${live_equity:.2f}",
        f"live P/L {_format_signed_currency(live_pnl)} ({_format_signed_percent(live_return_pct)})",
    ]
    if abs(live_pnl - booked_pnl) >= 0.01:
        bits.append(f"booked {_format_signed_currency(booked_pnl)}")
    if open_positions > 0:
        bits.append(f"{open_positions} open")
    return " | ".join(bits)


def _format_review_summary_line(review: dict[str, Any]) -> str | None:
    if not isinstance(review, dict):
        return None
    summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
    active_count = int(summary.get("active_count", 0) or 0)
    if active_count <= 0:
        return None
    interval_hours = int(review.get("review_interval_hours", 0) or 0)
    free_signal = review.get("free_realtime_signal") if isinstance(review.get("free_realtime_signal"), dict) else {}
    weekly_x = review.get("weekly_x_review") if isinstance(review.get("weekly_x_review"), dict) else {}
    bits = [
        f"Review {interval_hours or '?'}h",
        f"keep {int(summary.get('keep_count', 0) or 0)}",
        f"retune {int(summary.get('retune_count', 0) or 0)}",
        f"retire {int(summary.get('retire_count', 0) or 0)}",
    ]
    weekly_status = str(weekly_x.get("status") or "missing")
    free_status = str(free_signal.get("status") or "missing")
    if free_status != "fresh":
        bits.append(f"free sentiment {free_status}")
    if weekly_status == "stale":
        bits.append("weekly X stale")
    elif weekly_status != "fresh":
        bits.append("weekly X pending")
    return " | ".join(bits)


def _format_sim_line(sim: dict[str, Any]) -> str:
    label = str(sim.get("display_name") or sim.get("id") or "SIM")
    live_equity = float(sim.get("live_equity", sim.get("final_equity", 0.0)) or 0.0)
    live_pnl = float(sim.get("live_equity_change", sim.get("net_equity_change", 0.0)) or 0.0)
    live_return_pct = float(sim.get("live_return_pct", sim.get("net_return_pct", 0.0)) or 0.0)
    open_positions = int(sim.get("open_positions", 0) or 0)
    stage = str(sim.get("stage") or "").strip().lower()
    bits = [
        f"capital ${live_equity:.2f}",
        f"P/L {_format_signed_currency(live_pnl)} ({_format_signed_percent(live_return_pct)})",
        f"trades {int(sim.get('round_trips', 0) or 0)}",
        f"win {float(sim.get('win_rate', 0.0) or 0.0):.1f}%",
    ]
    if sim.get("halted"):
        bits.append("HALTED")
    if open_positions > 0:
        bits.append(f"{open_positions} open")
    if sim.get("fee_drag"):
        bits.append("fee drag")
    if stage == "staged":
        bits.append("awaiting feed")
    elif bool(sim.get("control_lane")):
        bits.append("control")
    if live_return_pct > 0.0:
        bits.append("growing")
    return f"{label}: " + " | ".join(bits)


def _format_review_action_line(review: dict[str, Any]) -> str | None:
    if not isinstance(review, dict):
        return None
    rows = [item for item in list(review.get("recommendations") or []) if isinstance(item, dict)]
    retune = [str(item.get("display_name") or item.get("id") or "sim") for item in rows if str(item.get("recommendation") or "") == "retune"]
    retire = [str(item.get("display_name") or item.get("id") or "sim") for item in rows if str(item.get("recommendation") or "") == "retire"]
    keep = [str(item.get("display_name") or item.get("id") or "sim") for item in rows if str(item.get("recommendation") or "") == "keep"]
    bits: list[str] = []
    if retune:
        bits.append("Retune: " + ", ".join(retune[:2]))
    if retire:
        bits.append("Retire: " + ", ".join(retire[:2]))
    if not bits and keep:
        bits.append("Stable: " + ", ".join(keep[:2]))
    return " | ".join(bits) if bits else None


def _age_minutes(ts: str | None) -> float | None:
    parsed = _parse_iso(ts)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60.0)


def _format_finance_line(row: dict[str, Any]) -> str:
    return (
        f"{row.get('symbol', 'symbol')}: {row.get('action', 'hold')}"
        f" bias {float(row.get('bias', 0.0)):+.2f}"
        f", conf {float(row.get('confidence', 0.0)):.2f}"
        f", risk {row.get('risk_state', 'unknown')}"
    )


def _parse_clock_time(raw: str) -> dt_time | None:
    text = str(raw or "").strip()
    if not text or ":" not in text:
        return None
    parts = text.split(":", 1)
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except Exception:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return dt_time(hour=hour, minute=minute)


def _current_schedule_slot(channel: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
    raw_times = channel.get("schedule_local_times")
    if not isinstance(raw_times, list) or not raw_times:
        return None
    tz_name = str(channel.get("schedule_timezone") or "Australia/Brisbane").strip() or "Australia/Brisbane"
    try:
        zone = ZoneInfo(tz_name)
    except Exception:
        zone = timezone.utc
        tz_name = "UTC"
    local_now = (now or datetime.now(timezone.utc)).astimezone(zone)
    candidates: list[dict[str, Any]] = []
    for day_offset in (0, -1):
        target_date = local_now.date() + timedelta(days=day_offset)
        for label in raw_times:
            clock = _parse_clock_time(str(label))
            if clock is None:
                continue
            slot_dt = datetime.combine(target_date, clock, tzinfo=zone)
            if slot_dt <= local_now:
                candidates.append(
                    {
                        "slot_id": slot_dt.strftime("%Y-%m-%d@%H:%M"),
                        "slot_label": slot_dt.strftime("%H:%M"),
                        "slot_ts": slot_dt.isoformat(),
                        "timezone": tz_name,
                    }
                )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item["slot_ts"])


def _round_float(value: Any, digits: int = 3) -> float:
    try:
        return round(float(value), digits)
    except Exception:
        return round(float(0.0), digits)


def _sim_watch_state_snapshot(portfolio: dict[str, Any]) -> dict[str, Any]:
    sims = list(portfolio.get("sims") or [])
    active_book_sims = [item for item in sims if bool(item.get("active_book"))]
    finance_brain = portfolio.get("finance_brain") if isinstance(portfolio.get("finance_brain"), dict) else {}
    finance_rows = list(finance_brain.get("symbols") or [])
    external_inputs = (
        finance_brain.get("external_signal", {}).get("inputs", {})
        if isinstance(finance_brain.get("external_signal"), dict)
        else {}
    )

    sim_snapshot: dict[str, Any] = {}
    for sim in active_book_sims:
        sim_id = str(sim.get("id") or "")
        if not sim_id:
            continue
        age_minutes = _age_minutes(sim.get("updated_at"))
        sim_snapshot[sim_id] = {
            "display_name": str(sim.get("display_name") or sim_id),
            "bucket": str(sim.get("bucket") or ""),
            "strategy_type": str(sim.get("bucket") or sim.get("strategy_type") or ""),
            "strategy_role": str(sim.get("strategy_role") or ""),
            "stage": str(sim.get("stage") or ""),
            "target_venue": str(sim.get("target_venue") or ""),
            "control_lane": bool(sim.get("control_lane")),
            "status": str(sim.get("status") or "unknown"),
            "halted": bool(sim.get("halted")),
            "fee_drag": bool(sim.get("fee_drag")),
            "open_positions": int(sim.get("open_positions", 0) or 0),
            "round_trips": int(sim.get("round_trips", 0) or 0),
            "win_rate": _round_float(sim.get("win_rate", 0.0), 1),
            "initial_capital": _round_float(sim.get("initial_capital", 0.0), 2),
            "net_equity_change": _round_float(sim.get("net_equity_change", 0.0), 2),
            "net_return_pct": _round_float(sim.get("net_return_pct", 0.0), 2),
            "final_equity": _round_float(sim.get("final_equity", 0.0), 2),
            "mark_equity": _round_float(sim.get("mark_equity", sim.get("final_equity", 0.0)), 2),
            "live_equity": _round_float(sim.get("live_equity", sim.get("final_equity", 0.0)), 2),
            "live_equity_change": _round_float(sim.get("live_equity_change", sim.get("net_equity_change", 0.0)), 2),
            "live_return_pct": _round_float(sim.get("live_return_pct", sim.get("net_return_pct", 0.0)), 2),
            "unrealized_pnl": _round_float(sim.get("unrealized_pnl", 0.0), 2),
            "fees_usd": _round_float(sim.get("fees_usd", 0.0), 2),
            "avg_hold_hours": _round_float(sim.get("avg_hold_hours", 0.0), 2),
            "stale": bool(age_minutes is not None and age_minutes > 10.0),
        }

    finance_snapshot: dict[str, Any] = {}
    for row in finance_rows[:4]:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        finance_snapshot[symbol] = {
            "action": str(row.get("action", "hold")),
            "risk_state": str(row.get("risk_state", "unknown")),
            "bias": _round_float(row.get("bias", 0.0), 2),
            "confidence": _round_float(row.get("confidence", 0.0), 2),
        }

    sentiment_model = None
    fingpt_status = None
    macbook_status = None
    if isinstance(external_inputs, dict):
        macbook = external_inputs.get("macbook_sentiment")
        if isinstance(macbook, dict):
            sentiment_model = macbook.get("model_resolved")
            macbook_status = macbook.get("status")
        fingpt = external_inputs.get("fingpt_sentiment")
        if isinstance(fingpt, dict):
            fingpt_status = fingpt.get("status")

    return {
        "sims": sim_snapshot,
        "finance": finance_snapshot,
        "feeds": {
            "macbook_status": str(macbook_status or "unknown"),
            "fingpt_status": str(fingpt_status or "unknown"),
            "sentiment_model": str(sentiment_model or ""),
        },
    }


def _build_ops_status_lines(portfolio: dict[str, Any]) -> tuple[list[str], str]:
    components = [item for item in list(portfolio.get("components") or []) if isinstance(item, dict)]
    work_items = [item for item in list(portfolio.get("work_items") or []) if isinstance(item, dict)]
    health = portfolio.get("health_metrics") if isinstance(portfolio.get("health_metrics"), dict) else {}
    finance = portfolio.get("finance_brain") if isinstance(portfolio.get("finance_brain"), dict) else {}
    external_signals = [item for item in list(portfolio.get("external_signals") or []) if isinstance(item, dict)]

    healthy = sum(1 for item in components if str(item.get("status") or "").lower() == "healthy")
    warnings = [item.get("name", item.get("id", "component")) for item in components if str(item.get("status") or "").lower() not in {"healthy"}]
    lines = [
        f"Core services: {healthy}/{len(components) or 0} healthy"
        + (f"; attention: {', '.join(str(item) for item in warnings[:3])}" if warnings else "; attention: none")
    ]
    if components:
        lines.append(
            "Services: "
            + "; ".join(
                f"{item.get('name', item.get('id', 'component'))} {item.get('status', 'unknown')}"
                for item in components[:4]
            )
        )

    if health:
        lines.append(
            "Host load: "
            f"CPU {float(health.get('cpu', 0.0)):.1f}%, "
            f"RAM {float(health.get('memory', 0.0)):.1f}%, "
            f"GPU {float(health.get('gpu', 0.0)):.1f}%, "
            f"Disk {float(health.get('disk', 0.0)):.1f}%"
        )

    if work_items:
        summary = "; ".join(
            f"{str(item.get('title', item.get('id', 'work')))} ({str(item.get('status', 'idle'))})"
            for item in work_items[:3]
        )
        lines.append(f"Current work: {summary}")

    finance_rows = [item for item in list(finance.get("symbols") or []) if isinstance(item, dict)]
    if finance_rows:
        finance_summary = " | ".join(
            f"{row.get('symbol', 'symbol')} {row.get('action', 'hold')} conf {float(row.get('confidence', 0.0)):.2f}"
            for row in finance_rows[:2]
        )
        lines.append(f"Finance bias: {finance_summary}")

    macbook = next((item for item in external_signals if str(item.get("id") or "") == "macbook_sentiment"), None)
    fingpt = next((item for item in external_signals if str(item.get("id") or "") == "fingpt_sentiment"), None)
    if macbook or fingpt:
        signal_bits: list[str] = []
        if isinstance(macbook, dict):
            model = str(macbook.get("model_resolved") or "unknown")
            signal_bits.append(f"MacBook sentiment {macbook.get('status', 'unknown')} ({model})")
        if isinstance(fingpt, dict):
            signal_bits.append(f"Dali fallback {fingpt.get('status', 'unknown')}")
        lines.append("Signals: " + "; ".join(signal_bits))

    footer = "Daily operating summary from Dali."
    return lines[:6], footer


def _build_sim_watch_summary(portfolio: dict[str, Any]) -> tuple[list[str], str, dict[str, Any]]:
    snapshot = _sim_watch_state_snapshot(portfolio)
    sim_snapshot = snapshot.get("sims", {})
    feeds = snapshot.get("feeds", {})
    strategy_review = portfolio.get("sim_strategy_review") if isinstance(portfolio.get("sim_strategy_review"), dict) else {}
    sim_rows = list(sim_snapshot.values())
    halted = sum(1 for item in sim_rows if bool(item.get("halted")))
    growing = sum(1 for item in sim_rows if float(item.get("live_return_pct", item.get("net_return_pct", 0.0)) or 0.0) > 0.0)
    flagged = sum(
        1
        for item in sim_rows
        if bool(item.get("halted"))
        or bool(item.get("fee_drag"))
        or float(item.get("live_return_pct", item.get("net_return_pct", 0.0)) or 0.0) <= -1.0
    )
    lines: list[str] = []
    if sim_rows:
        lines.append(_format_sim_totals_line(sim_rows))
        review_line = _format_review_summary_line(strategy_review)
        if review_line:
            lines.append(review_line)
        review_actions = _format_review_action_line(strategy_review)
        if review_actions:
            lines.append(review_actions)
        lines.extend(_format_sim_line(current) for current in sim_rows[:6])
    signal_bits: list[str] = []
    if str(feeds.get("macbook_status") or "") not in {"ok", "healthy", "unknown"}:
        signal_bits.append(f"macbook {feeds.get('macbook_status')}")
    if str(feeds.get("fingpt_status") or "") not in {"ok", "healthy", "missing", "optional_offline", "unknown"}:
        signal_bits.append(f"dali fallback {feeds.get('fingpt_status')}")
    footer = f"Nightly AU paper trading summary from Dali. Active book {len(sim_snapshot)} strategies, {growing} growing, {halted} halted, {flagged} flagged."
    if signal_bits:
        footer = f"{footer} " + "; ".join(signal_bits[:3]) + "."
    return lines[:10], footer, snapshot


def _build_sim_watch_lines(portfolio: dict[str, Any], previous_state: dict[str, Any] | None = None) -> tuple[list[str], str, dict[str, Any]]:
    snapshot = _sim_watch_state_snapshot(portfolio)
    prev = previous_state if isinstance(previous_state, dict) else {}
    prev_sims = prev.get("sims") if isinstance(prev.get("sims"), dict) else {}
    prev_finance = prev.get("finance") if isinstance(prev.get("finance"), dict) else {}
    prev_feeds = prev.get("feeds") if isinstance(prev.get("feeds"), dict) else {}

    sim_snapshot = snapshot.get("sims", {})
    sim_rows = list(sim_snapshot.values())
    lines: list[str] = []
    if sim_rows:
        lines.append(_format_sim_totals_line(sim_rows))
        review_line = _format_review_summary_line(
            portfolio.get("sim_strategy_review") if isinstance(portfolio.get("sim_strategy_review"), dict) else {}
        )
        if review_line:
            lines.append(review_line)
        review_actions = _format_review_action_line(
            portfolio.get("sim_strategy_review") if isinstance(portfolio.get("sim_strategy_review"), dict) else {}
        )
        if review_actions:
            lines.append(review_actions)
        lines.extend(_format_sim_line(current) for current in sim_rows[:6])
    alerts: list[str] = []
    baseline = not bool(prev_sims or prev_finance or prev_feeds)

    for sim_id, current in sim_snapshot.items():
        previous = prev_sims.get(sim_id) if isinstance(prev_sims, dict) else None
        label = str(current.get("display_name") or sim_id)
        if baseline or not isinstance(previous, dict):
            continue
        if bool(previous.get("halted")) != bool(current.get("halted")):
            alerts.append(f"{label} {'halted' if current.get('halted') else 'resumed'}")
        if int(previous.get("open_positions", 0) or 0) != int(current.get("open_positions", 0) or 0):
            alerts.append(
                f"{label} open positions {int(previous.get('open_positions', 0) or 0)} -> {int(current.get('open_positions', 0) or 0)}"
            )
            alerts.append(f"{label} exposure changed")
        if str(previous.get("status") or "") != str(current.get("status") or ""):
            alerts.append(f"{label} status changed")
        if bool(previous.get("fee_drag")) != bool(current.get("fee_drag")):
            alerts.append(f"{label} fee drag {'on' if current.get('fee_drag') else 'cleared'}")
        prev_low_win = int(previous.get("round_trips", 0) or 0) >= 3 and float(previous.get("win_rate", 0.0) or 0.0) < 40.0
        curr_low_win = int(current.get("round_trips", 0) or 0) >= 3 and float(current.get("win_rate", 0.0) or 0.0) < 40.0
        if prev_low_win != curr_low_win:
            alerts.append(f"{label} win-rate {'degraded' if curr_low_win else 'recovered'} to {float(current.get('win_rate', 0.0)):.1f}%")
        if bool(previous.get("stale")) != bool(current.get("stale")):
            alerts.append(f"{label} {'stale' if current.get('stale') else 'fresh again'}")

    finance_snapshot = snapshot.get("finance", {})
    for symbol, current in finance_snapshot.items():
        previous = prev_finance.get(symbol) if isinstance(prev_finance, dict) else None
        if baseline or not isinstance(previous, dict):
            continue
        if str(previous.get("action")) != str(current.get("action")):
            alerts.append(f"{symbol} action flip")
            alerts.append(f"{symbol}: action {previous.get('action', 'hold')} -> {current.get('action', 'hold')}")
        if str(previous.get("risk_state")) != str(current.get("risk_state")):
            alerts.append(f"{symbol}: risk {previous.get('risk_state', 'unknown')} -> {current.get('risk_state', 'unknown')}")

    feeds = snapshot.get("feeds", {})
    if not baseline:
        if str(prev_feeds.get("fingpt_status") or "") != str(feeds.get("fingpt_status") or ""):
            alerts.append("Dali fallback feed changed")
            alerts.append(f"Dali fallback feed: {prev_feeds.get('fingpt_status', 'unknown')} -> {feeds.get('fingpt_status', 'unknown')}")
        if str(prev_feeds.get("macbook_status") or "") != str(feeds.get("macbook_status") or ""):
            alerts.append(f"MacBook sentiment: {prev_feeds.get('macbook_status', 'unknown')} -> {feeds.get('macbook_status', 'unknown')}")

    if baseline:
        summary = "Transition baseline captured. Future sim-watch posts only fire on state changes."
    elif alerts:
        summary = "Attention: " + "; ".join(alerts[:8])
    else:
        summary = "No new sim-watch transitions."
    return lines[:8], summary, snapshot


def _format_task_line(task: dict[str, Any]) -> str:
    project = str(task.get("project", "")).strip() or "unscoped"
    assignee = str(task.get("assignee", "")).strip() or "unassigned"
    priority = str(task.get("priority", "medium")).strip() or "medium"
    return f"#{task.get('id')} [{project}] {task.get('title', 'task')} ({task.get('status', 'backlog')}, {priority}, {assignee})"


def _format_work_item_line(item: dict[str, Any]) -> str:
    return f"{item.get('title', item.get('id', 'work'))}: {item.get('status', 'idle')} :: {item.get('detail', '')}"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    _load_env_file_once()
    payload = _read_json(path)
    if isinstance(payload, dict):
        return payload
    return {
        "enabled": False,
        "dry_run": True,
        "channels": [],
    }


def _channel_previews(
    portfolio: dict[str, Any],
    tasks: list[dict[str, Any]],
    config: dict[str, Any],
    previous_channels: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    components = list(portfolio.get("components") or [])
    sims = list(portfolio.get("sims") or [])
    work_items = list(portfolio.get("work_items") or [])
    projects = list(portfolio.get("projects") or [])
    active_components = [item for item in components if str(item.get("status", "")).lower() in {"healthy", "warning", "active"}]
    active_book_sims = [item for item in sims if bool(item.get("active_book"))]
    flagged_sims = [item for item in active_book_sims if str(item.get("status", "")).lower() in {"critical", "warning"}]
    open_tasks = [item for item in tasks if str(item.get("status", "")).lower() != "done"]
    active_projects = [item for item in projects if str(item.get("status", "")).lower() in {"active", "busy"}]

    sim_watch_previous = None
    if isinstance(previous_channels, dict):
        sim_watch_previous = previous_channels.get("sim_watch", {}).get("state")
    ops_status_lines, ops_status_footer = _build_ops_status_lines(portfolio)
    sim_watch_summary_lines, sim_watch_summary_footer, sim_watch_summary_state = _build_sim_watch_summary(portfolio)
    sim_watch_lines, sim_watch_footer, sim_watch_state = _build_sim_watch_lines(portfolio, sim_watch_previous)

    previews_by_id = {
        "ops_status": _bullet_lines(
            "Ops Status",
            ops_status_lines or [_format_component_line(item) for item in active_components[:6]],
            footer=ops_status_footer,
        ),
        "sim_watch": _bullet_lines(
            "Sim Watch",
            sim_watch_lines
            or [_format_sim_line(item) for item in flagged_sims[:6]]
            or [_format_sim_line(item) for item in active_book_sims[:6]]
            or [_format_sim_line(item) for item in sims[:6]],
            footer=sim_watch_footer,
        ),
        "project_intake": _bullet_lines(
            "Project Intake",
            [f"{item.get('name', item.get('id', 'project'))}: {item.get('status', 'idle')}" for item in active_projects[:5]]
            + [_format_task_line(item) for item in open_tasks[:5]],
            footer="Discord is a collaboration surface only. Canonical state remains local.",
        ),
    }

    channels = []
    for entry in config.get("channels", []):
        if not isinstance(entry, dict):
            continue
        channel_id = str(entry.get("id", "")).strip()
        env_var = str(entry.get("webhook_env", "")).strip()
        if channel_id == "sim_watch" and str(entry.get("report_mode") or "").strip() == "scheduled_summary":
            preview = _bullet_lines("Sim Watch", sim_watch_summary_lines, footer=sim_watch_summary_footer)
            state = sim_watch_summary_state
        else:
            preview = previews_by_id.get(
                channel_id,
                _bullet_lines(
                    entry.get("title") or entry.get("label") or channel_id or "Bridge Preview",
                    [entry.get("description", "No preview formatter configured.")],
                ),
            )
            state = sim_watch_state if channel_id == "sim_watch" else {}
        label = str(entry.get("label", channel_id))
        enabled = bool(entry.get("enabled", False))
        delivery = str(entry.get("delivery", "webhook"))
        has_webhook = bool(env_var and os.environ.get(env_var))
        auto_post = bool(entry.get("auto_post", True))
        report_mode = str(entry.get("report_mode") or "")
        channels.append(
            {
                "id": channel_id,
                "label": label,
                "title": str(entry.get("title", entry.get("label", channel_id))),
                "enabled": enabled,
                "delivery": delivery,
                "webhook_env": env_var or None,
                "has_webhook": has_webhook,
                "auto_post": auto_post,
                "preview": preview,
                "preview_length": len(preview),
                "preview_hash": _preview_hash(preview),
                "description": str(entry.get("description", "")),
                "min_resend_minutes": max(0, int(entry.get("min_resend_minutes", 0) or 0)),
                "schedule_timezone": str(entry.get("schedule_timezone") or "Australia/Brisbane"),
                "schedule_local_times": list(entry.get("schedule_local_times") or []),
                "report_mode": report_mode,
                "state": state,
                "boundary": build_discord_channel_boundary(
                    label=label,
                    enabled=enabled,
                    has_webhook=has_webhook,
                    auto_post=auto_post,
                    delivery=delivery,
                    report_mode=report_mode,
                ),
            }
        )
    return channels


def bridge_payload(
    portfolio: dict[str, Any],
    tasks: list[dict[str, Any]],
    config_path: Path = CONFIG_PATH,
    previous_channels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    channels = _channel_previews(portfolio, tasks, config, previous_channels=previous_channels)
    return {
        "generated_at": _now_iso(),
        "enabled": bool(config.get("enabled", False)),
        "dry_run": bool(config.get("dry_run", True)),
        "status": "dry_run" if bool(config.get("dry_run", True)) else ("configured" if bool(config.get("enabled", False)) else "disabled"),
        "channels": channels,
        "channel_count": len(channels),
        "active_channels": sum(1 for item in channels if item.get("enabled")),
    }


def render_bridge_state(portfolio: dict[str, Any], tasks: list[dict[str, Any]], status_path: Path = STATUS_PATH) -> dict[str, Any]:
    existing = _read_json(status_path)
    previous_channels = existing.get("last_delivery", {}).get("channels") if isinstance(existing, dict) else {}
    payload = bridge_payload(portfolio, tasks, previous_channels=previous_channels if isinstance(previous_channels, dict) else None)
    if isinstance(existing, dict) and isinstance(existing.get("last_delivery"), dict):
        payload["last_delivery"] = existing["last_delivery"]
    payload["rendered_at"] = _now_iso()
    _write_json_atomic(status_path, payload)
    return payload


def post_bridge_webhooks(
    payload: dict[str, Any],
    timeout: float = 10.0,
    status_path: Path = STATUS_PATH,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Deliver pre-rendered bridge messages.

    This performs outbound network requests and should only be invoked
    explicitly by an operator-approved command.
    """

    existing = _read_json(status_path)
    previous_delivery = existing.get("last_delivery") if isinstance(existing, dict) else {}
    previous_channels = previous_delivery.get("channels") if isinstance(previous_delivery, dict) else {}
    previous_attempted_at = previous_delivery.get("attempted_at") if isinstance(previous_delivery, dict) else None
    if not isinstance(previous_channels, dict):
        previous_channels = {}

    results: list[dict[str, Any]] = []
    delivery_channels: dict[str, Any] = {}
    for channel in payload.get("channels", []):
        if not isinstance(channel, dict) or not channel.get("enabled"):
            continue
        channel_id = str(channel.get("id") or "")
        if not force and not bool(channel.get("auto_post", True)):
            result = {
                "id": channel_id,
                "status": "manual_only",
                "preview_hash": str(channel.get("preview_hash") or ""),
                "state": {},
            }
            results.append(result)
            delivery_channels[channel_id] = result
            continue
        previous_channel = previous_channels.get(channel_id) if isinstance(previous_channels, dict) else None
        previous_hash = previous_channel.get("preview_hash") if isinstance(previous_channel, dict) else None
        current_hash = str(channel.get("preview_hash") or "")
        schedule_slot = _current_schedule_slot(channel)
        previous_slot_id = previous_channel.get("sent_slot_id") if isinstance(previous_channel, dict) else None
        scheduled_due = False
        if isinstance(channel.get("schedule_local_times"), list) and channel.get("schedule_local_times"):
            if schedule_slot is None:
                result = {
                    "id": channel_id,
                    "status": "not_scheduled",
                    "preview_hash": current_hash,
                    "state": previous_channel.get("state", {}) if isinstance(previous_channel, dict) else {},
                }
                results.append(result)
                delivery_channels[channel_id] = result
                continue
            scheduled_due = bool(force or previous_slot_id != schedule_slot.get("slot_id"))
        min_resend_minutes = max(0, int(channel.get("min_resend_minutes", 0) or 0))
        if isinstance(previous_channel, dict):
            sent_at_raw = previous_channel.get("sent_at")
            if not sent_at_raw and previous_channel.get("status") == "sent":
                sent_at_raw = previous_attempted_at
        else:
            sent_at_raw = None
        last_sent_at = _parse_iso(sent_at_raw)
        if not force and not scheduled_due and last_sent_at is not None and min_resend_minutes > 0:
            elapsed_minutes = (datetime.now(timezone.utc) - last_sent_at).total_seconds() / 60.0
            if elapsed_minutes < float(min_resend_minutes):
                result = {
                    "id": channel_id,
                    "status": "rate_limited",
                    "preview_hash": current_hash,
                    "min_resend_minutes": min_resend_minutes,
                    "last_sent_at": last_sent_at.isoformat().replace("+00:00", "Z"),
                }
                results.append(result)
                delivery_channels[channel_id] = {
                    **result,
                    "preview_hash": previous_hash or current_hash,
                    "sent_at": last_sent_at.isoformat().replace("+00:00", "Z"),
                    "sent_slot_id": previous_slot_id,
                    "state": previous_channel.get("state", {}) if isinstance(previous_channel, dict) else {},
                }
                continue
        if not force and not scheduled_due and previous_hash and previous_hash == current_hash:
            result = {
                "id": channel_id,
                "status": "unchanged",
                "preview_hash": current_hash,
                "sent_slot_id": previous_slot_id,
                "state": previous_channel.get("state", {}) if isinstance(previous_channel, dict) else {},
            }
            results.append(result)
            delivery_channels[channel_id] = result
            continue
        env_var = str(channel.get("webhook_env") or "").strip()
        webhook_url = os.environ.get(env_var) if env_var else None
        if not webhook_url:
            result = {
                "id": channel_id,
                "status": "skipped",
                "reason": "missing_webhook_env",
                "preview_hash": current_hash,
                "state": previous_channel.get("state", {}) if isinstance(previous_channel, dict) else {},
            }
            results.append(result)
            delivery_channels[channel_id] = result
            continue
        body = json.dumps({"content": str(channel.get("preview", ""))}).encode("utf-8")
        req = request.Request(
            webhook_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "openclaw-discord-bridge/1.0",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                result = {
                    "id": channel_id,
                    "status": "sent",
                    "http_status": int(getattr(response, "status", 200)),
                    "preview_hash": current_hash,
                    "sent_at": _now_iso(),
                    "sent_slot_id": schedule_slot.get("slot_id") if isinstance(schedule_slot, dict) else None,
                    "state": channel.get("state", {}) if isinstance(channel.get("state"), dict) else {},
                }
        except error.HTTPError as exc:
            result = {
                "id": channel_id,
                "status": "error",
                "http_status": int(exc.code),
                "reason": str(exc),
                "preview_hash": current_hash,
                "sent_slot_id": previous_slot_id,
                "state": previous_channel.get("state", {}) if isinstance(previous_channel, dict) else {},
            }
        except Exception as exc:
            result = {
                "id": channel_id,
                "status": "error",
                "reason": str(exc),
                "preview_hash": current_hash,
                "sent_slot_id": previous_slot_id,
                "state": previous_channel.get("state", {}) if isinstance(previous_channel, dict) else {},
            }
        results.append(result)
        delivery_channels[channel_id] = result

    payload["last_delivery"] = {
        "attempted_at": _now_iso(),
        "force": bool(force),
        "channels": delivery_channels,
        "results": results,
    }
    payload["rendered_at"] = _now_iso()
    _write_json_atomic(status_path, payload)
    return results
