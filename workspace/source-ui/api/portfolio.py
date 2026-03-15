"""Canonical dashboard payloads for projects, sims, runtime work, and health."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency in some environments
    yaml = None

from .boundary_state import (
    build_inference_boundary,
    build_memory_source_boundary,
    build_preference_packet_boundary,
    build_research_boundary,
)
from .discord_bridge import bridge_payload as discord_bridge_payload
from .research_promotions import list_research_items
from .sim_review import load_or_build_sim_strategy_review
from .task_store import load_all_tasks
from .user_inference import build_user_context_packet

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
PROJECTS_CONFIG_PATH = SOURCE_UI_ROOT / "config" / "projects.json"
EXTERNAL_SIGNALS_CONFIG_PATH = SOURCE_UI_ROOT / "config" / "external_signals.json"
SIM_CATALOG_PATH = SOURCE_UI_ROOT / "config" / "sim_catalog.json"
SOURCE_MISSION_PATH = SOURCE_UI_ROOT / "config" / "source_mission.json"
TEAMCHAT_ROOT = REPO_ROOT / "workspace" / "teamchat"
SIM_ROOT = REPO_ROOT / "sim"
TRADING_PIPELINE_PATH = REPO_ROOT / "pipelines" / "system1_trading.yaml"
LOCAL_EXEC_LEDGER = REPO_ROOT / "workspace" / "local_exec" / "state" / "jobs.jsonl"
PHASE1_STATUS_PATH = REPO_ROOT / "workspace" / "runtime" / "phase1_idle_status.json"
OPENCLAW_LOG_ROOT = Path.home() / ".local" / "state" / "openclaw"
ITC_CYCLE_LOG = OPENCLAW_LOG_ROOT / "itc-cycle.log"
FINANCE_BRAIN_PATH = REPO_ROOT / "workspace" / "artifacts" / "finance" / "consensus_latest.json"
COMMAND_HISTORY_PATH = SOURCE_UI_ROOT / "state" / "command_history.json"
DISCORD_MEMORY_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "discord_messages.jsonl"
DISCORD_RESEARCH_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "discord_research_messages.jsonl"
TELEGRAM_MEMORY_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "telegram_messages.jsonl"
USER_INFERENCES_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "user_inferences.jsonl"
PREFERENCE_PROFILE_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "preference_profile.json"
ASSISTANT_MODELS_URL = "http://127.0.0.1:8001/v1/models"
TRADING_STRATEGY_REPORT_PATHS = (
    Path.home() / "Taildrive" / "shared" / "openclaw_trading_strategy_report_v2.md",
    REPO_ROOT / "docs" / "openclaw_trading_strategy_report_v2.md",
)
TRADING_BLUEPRINT_CONFIGS = (
    REPO_ROOT / "configs" / "base.yaml",
    REPO_ROOT / "configs" / "live.au.yaml",
    REPO_ROOT / "configs" / "universes" / "equities.yaml",
    REPO_ROOT / "configs" / "universes" / "etfs.yaml",
    REPO_ROOT / "configs" / "universes" / "crypto.yaml",
)

COMPONENT_UNITS = [
    ("gateway", "Gateway", "openclaw-gateway.service"),
    ("assistant", "Assistant LLM", "openclaw-vllm.service"),
    ("market_stream", "Market Stream", "openclaw-market-stream.service"),
    ("itc_cycle", "ITC Cycle Timer", "openclaw-itc-cycle.timer"),
    ("dali", "DALI Fishtank", "dali-fishtank.service"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, int(limit)) :]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _tail_lines(path: Path, limit: int = 80) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, int(limit)) :]


def _format_ts(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for parser in (
        lambda item: datetime.fromisoformat(item.replace("Z", "+00:00")),
        lambda item: datetime.strptime(item, "%a %Y-%m-%d %H:%M GMT%z"),
    ):
        try:
            parsed = parser(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _iso_from_any(value: Any) -> str | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def _excerpt(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _strip_markdown(text: str) -> str:
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", str(text or ""))
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    return " ".join(cleaned.strip().split())


def _markdown_section(text: str, heading: str) -> str:
    lines = str(text or "").splitlines()
    start = None
    level = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        hash_count = len(stripped) - len(stripped.lstrip("#"))
        title = stripped[hash_count:].strip()
        if title == heading:
            start = idx + 1
            level = hash_count
            break
    if start is None or level is None:
        return ""
    end = len(lines)
    for idx in range(start, len(lines)):
        stripped = lines[idx].strip()
        if not stripped.startswith("#"):
            continue
        hash_count = len(stripped) - len(stripped.lstrip("#"))
        if hash_count <= level:
            end = idx
            break
    return "\n".join(lines[start:end]).strip()


def _markdown_items(section: str, *, ordered: bool | None = None) -> list[str]:
    rows: list[str] = []
    for raw_line in str(section or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        is_bullet = line.startswith("- ")
        is_ordered = bool(re.match(r"^\d+\.\s+", line))
        if ordered is True and not is_ordered:
            continue
        if ordered is False and not is_bullet:
            continue
        if not is_bullet and not is_ordered:
            continue
        line = re.sub(r"^-\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        rows.append(_strip_markdown(line))
    return rows


def _first_heading_title(text: str) -> str | None:
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            return _strip_markdown(line[2:])
    return None


def _parse_strategy_titles(text: str) -> list[str]:
    rows: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        match = re.match(r"^##\s+Strategy\s+\d+\s+[—-]\s+(.+)$", line)
        if match:
            rows.append(_strip_markdown(match.group(1)))
    return rows


def _load_trading_pipeline_snapshot() -> dict[str, Any]:
    if yaml is None or not TRADING_PIPELINE_PATH.exists():
        return {
            "status": "offline",
            "enabled_sims": [],
            "enabled_universe": [],
            "path": str(TRADING_PIPELINE_PATH),
        }
    try:
        payload = yaml.safe_load(TRADING_PIPELINE_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {
            "status": "warning",
            "enabled_sims": [],
            "enabled_universe": [],
            "path": str(TRADING_PIPELINE_PATH),
        }
    sims = payload.get("sims") if isinstance(payload, dict) else None
    enabled_rows: list[dict[str, Any]] = []
    universe: list[str] = []
    if isinstance(sims, list):
        for entry in sims:
            if not isinstance(entry, dict) or not bool(entry.get("enabled", False)):
                continue
            symbols = [str(symbol) for symbol in entry.get("universe", []) if str(symbol).strip()]
            enabled_rows.append(
                {
                    "id": str(entry.get("id", "")),
                    "display_name": str(entry.get("display_name", entry.get("id", "sim"))),
                    "strategy": str(entry.get("strategy", "")),
                    "runtime_strategy": str(entry.get("runtime_strategy", entry.get("strategy", ""))),
                    "bucket": str(entry.get("bucket", "")),
                    "target_venue": str(entry.get("target_venue", "")),
                    "universe": symbols,
                }
            )
            universe.extend(symbols)
    return {
        "status": "active" if enabled_rows else "warning",
        "enabled_sims": enabled_rows,
        "enabled_universe": sorted({symbol for symbol in universe if symbol}),
        "path": str(TRADING_PIPELINE_PATH),
    }


def _classify_trading_alignment(sim: dict[str, Any]) -> tuple[str, str]:
    strategy = str(sim.get("strategy") or "").strip().lower()
    runtime_strategy = str(sim.get("runtime_strategy") or sim.get("strategy") or "").strip().lower()
    universe = [str(symbol).strip() for symbol in list(sim.get("universe") or []) if str(symbol).strip()]
    target_venue = str(sim.get("target_venue") or "").strip()
    if strategy == "us_equity_event_impulse":
        return "partial", f"Report-aligned Alpaca event sleeve is paper-live on public equity bars, but it still needs local {target_venue or 'Alpaca'} credentials and richer event/news ingestion."
    if strategy == "etf_narrative_spillover":
        return "partial", f"Report-aligned Alpaca ETF spillover sleeve is paper-live on public ETF bars, but local {target_venue or 'Alpaca'} market data remains the preferred upgrade."
    if strategy == "crypto_sentiment_breakout":
        if any(symbol.endswith("USDT") for symbol in universe):
            return "partial", "Report-aligned crypto sleeve is active, but it still runs on legacy USDT paper symbols instead of Kraken spot pairs."
        return "aligned", "Report-aligned crypto sleeve is mapped to the intended spot venue."
    if strategy == "perp_funding_carry":
        return "blocked", "Perp funding carry conflicts with the AU phase-1 no-derivatives rule."
    if runtime_strategy in {"cross_exchange_spread_arbitrage", "tick_crypto_scalping"}:
        return "research_only", "Keep as AU paper research only until venue, legality, and fee controls are stable."
    if runtime_strategy == "tick_grid_reversion":
        return "research_only", "Useful as an AU paper crypto lane, but keep it out of the initial live brief until Kraken mapping is explicit."
    if runtime_strategy == "latency_consensus_long_flat":
        return "partial", "Useful as an AU-portable bias layer, but the brief wants it feeding venue-specific sleeves rather than standing alone."
    if runtime_strategy in {
        "regime_gated_long_flat",
        "itc_sentiment_tilt_long_flat",
        "ensemble_competing_models_long_flat",
    }:
        return "legacy", "Legacy bar-cadence sim; keep as AU-portable research/support, not the final live sleeve."
    if not strategy:
        return "unknown", "No strategy name found in the current trading config."
    return "partial", "Strategy is not explicitly covered by the current AU live brief."


def _build_trading_strategy_integration(pipeline_snapshot: dict[str, Any]) -> dict[str, Any]:
    enabled = list(pipeline_snapshot.get("enabled_sims") or [])
    enabled_universe = [str(symbol) for symbol in pipeline_snapshot.get("enabled_universe", []) if str(symbol).strip()]
    alignment_rows: list[dict[str, Any]] = []
    notes: list[str] = []
    has_blocked = False
    has_research_only = False
    has_partial = False
    has_staged = False
    has_aligned = False

    for sim in enabled:
        status, note = _classify_trading_alignment(sim)
        has_blocked = has_blocked or status == "blocked"
        has_research_only = has_research_only or status == "research_only"
        has_partial = has_partial or status in {"partial", "legacy", "unknown"}
        has_staged = has_staged or status == "staged"
        has_aligned = has_aligned or status == "aligned"
        alignment_rows.append(
            {
                "id": str(sim.get("id", "")),
                "display_name": str(sim.get("display_name", sim.get("id", "sim"))),
                "strategy": str(sim.get("strategy", "")),
                "runtime_strategy": str(sim.get("runtime_strategy", sim.get("strategy", ""))),
                "status": status,
                "note": note,
            }
        )

    legacy_symbol_feed = any(symbol.endswith("USDT") for symbol in enabled_universe)
    missing_equity_sleeve = enabled and not any(
        str(sim.get("strategy") or "").strip().lower() in {"us_equity_event_impulse", "etf_narrative_spillover"}
        for sim in enabled
    )
    if has_staged:
        notes.append("UEEI and ETNS are configured but still gated behind local venue/data wiring.")
    if any(str(sim.get("strategy") or "").strip().lower() in {"us_equity_event_impulse", "etf_narrative_spillover"} for sim in enabled):
        notes.append("UEEI and ETNS can now run on public equity/ETF bars, but Alpaca credentials and higher-quality event/news ingestion remain the preferred upgrade path.")
    if legacy_symbol_feed:
        notes.append("Enabled paper lanes still read Binance-style USDT symbols; map them to Kraken spot USD/AUD pairs before treating them as AU-live.")
    if missing_equity_sleeve:
        notes.append("No Alpaca equity/ETF sleeve is configured yet; the report wants Alpaca event and ETF spillover lanes in the initial live scope.")
    if any(str(row.get("status") or "") == "legacy" for row in alignment_rows):
        notes.append("Legacy control lanes remain enabled as comparative benchmarks while the report-aligned sleeves self-calibrate.")
    if has_blocked:
        notes.append("At least one enabled sim violates the report's Australia-operable phase-1 constraints and should stay retired.")
    elif enabled and (has_research_only or has_partial or has_staged):
        notes.append("The remaining enabled sims are AU-viable paper compute lanes, not the final live deployment shape.")
    if not enabled:
        notes.append("No sims are currently enabled in the runtime trading config.")

    if has_blocked:
        status = "misaligned"
        summary = "Active runtime still includes a non-AU-operable sleeve and is not ready for the Australia-only brief."
    elif has_staged and (has_partial or legacy_symbol_feed):
        status = "partial"
        summary = "Report-aligned sleeves are configured beside the control lanes, but Alpaca/Kraken cutover and local feeds are still incomplete."
    elif has_research_only or has_partial or has_staged or legacy_symbol_feed or missing_equity_sleeve:
        status = "partial"
        summary = "AU-viable paper lanes are retained, but the live stack still needs Alpaca/Kraken venue cutover."
    elif has_aligned:
        status = "aligned"
        summary = "Report-aligned trading sleeves are present and mapped to the intended venues."
    else:
        status = "aligned"
        summary = "Current enabled trading paths are aligned with the AU live brief."

    return {
        "status": status,
        "summary": summary,
        "enabled_sims": alignment_rows,
        "enabled_universe": enabled_universe,
        "notes": notes,
        "pipeline_path": pipeline_snapshot.get("path"),
    }


def _load_trading_strategy() -> dict[str, Any]:
    report_path = next((path for path in TRADING_STRATEGY_REPORT_PATHS if path.exists()), None)
    if report_path is None:
        return {
            "status": "offline",
            "title": "Trading strategy report unavailable",
            "summary": "No trading strategy report was found on the shared Taildrive surface.",
            "path": None,
            "updated_at": None,
            "live_scope": [],
            "research_scope": [],
            "excluded_scope": [],
            "hard_limits": [],
            "strategy_stack": [],
            "next_steps": [],
            "config_paths": [
                {
                    "label": path.name,
                    "path": str(path),
                    "exists": path.exists(),
                }
                for path in TRADING_BLUEPRINT_CONFIGS
            ],
            "integration": _build_trading_strategy_integration(_load_trading_pipeline_snapshot()),
        }

    text = _read_text(report_path) or ""
    executive_section = _markdown_section(text, "Executive Summary")
    live_scope = _markdown_items(_markdown_section(executive_section, "Recommended live scope"), ordered=True)
    research_scope = _markdown_items(_markdown_section(executive_section, "Supported but not initially live"), ordered=True)
    excluded_scope = _markdown_items(_markdown_section(executive_section, "Explicitly excluded for Australia"), ordered=True)
    hard_limits = _markdown_items(_markdown_section(text, "Hard portfolio limits"), ordered=False)
    next_steps = _markdown_items(_markdown_section(text, "What Another Model Should Do Next in the Repo"), ordered=True)
    pipeline_snapshot = _load_trading_pipeline_snapshot()
    title = _first_heading_title(text) or "OpenClaw Trading System Strategy Report"

    return {
        "status": "active",
        "title": title,
        "summary": "AU semantic-latency trading brief: Alpaca equities/ETFs + Kraken spot, deterministic risk, OpenClaw as control plane only.",
        "path": str(report_path),
        "updated_at": _format_ts(report_path),
        "live_scope": live_scope[:4],
        "research_scope": research_scope[:3],
        "excluded_scope": excluded_scope[:4],
        "hard_limits": hard_limits[:6],
        "strategy_stack": _parse_strategy_titles(text)[:4],
        "next_steps": next_steps[:6],
        "config_paths": [
            {
                "label": path.name,
                "path": str(path),
                "exists": path.exists(),
            }
            for path in TRADING_BLUEPRINT_CONFIGS
        ],
        "integration": _build_trading_strategy_integration(pipeline_snapshot),
    }


def _run_command(args: list[str], timeout: float = 1.5) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return 1, "", str(exc)
    return completed.returncode, completed.stdout, completed.stderr


def _assistant_model_snapshot() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(ASSISTANT_MODELS_URL, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {"reachable": False, "model_ids": []}
    data_rows = payload.get("data") if isinstance(payload, dict) else None
    model_ids: list[str] = []
    if isinstance(data_rows, list):
        for item in data_rows:
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item["id"]))
    return {"reachable": True, "model_ids": model_ids}


def _load_agent_inventory() -> list[dict[str, Any]]:
    code, stdout, _stderr = _run_command(
        [
            "node",
            str(REPO_ROOT / ".runtime" / "openclaw" / "openclaw.mjs"),
            "agents",
            "list",
            "--json",
        ],
        timeout=20.0,
    )
    if code != 0:
        return []
    try:
        payload = json.loads(stdout)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _systemctl_show(unit: str) -> dict[str, str]:
    code, stdout, stderr = _run_command(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "--property=ActiveState,SubState,UnitFileState,ExecMainPID",
        ]
    )
    if code != 0:
        return {
            "ActiveState": "unknown",
            "SubState": "unknown",
            "UnitFileState": "unknown",
            "ExecMainPID": "",
            "Error": stderr.strip() or f"exit={code}",
        }
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key] = value
    return out


def _component_status(active_state: str, sub_state: str) -> str:
    active = str(active_state or "").strip()
    sub = str(sub_state or "").strip()
    if active == "active":
        return "healthy"
    if active == "activating":
        return "warning"
    if active == "failed":
        return "error"
    if active == "inactive" and sub == "dead":
        return "warning"
    return "warning" if active else "error"


def _load_components() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for component_id, name, unit in COMPONENT_UNITS:
        payload = _systemctl_show(unit)
        active_state = payload.get("ActiveState", "unknown")
        sub_state = payload.get("SubState", "unknown")
        detail = f"{unit}: {active_state}/{sub_state}"
        if payload.get("ExecMainPID") and payload["ExecMainPID"] != "0":
            detail = f"{detail} pid={payload['ExecMainPID']}"
        if payload.get("Error"):
            detail = f"{detail} ({payload['Error']})"
        items.append(
            {
                "id": component_id,
                "name": name,
                "status": _component_status(active_state, sub_state),
                "details": detail,
                "unit": unit,
                "active_state": active_state,
                "sub_state": sub_state,
            }
        )
    return items


def _load_health_metrics() -> dict[str, float]:
    cpu_percent = 0.0
    try:
        load_avg = os.getloadavg()[0]
        cores = max(1, os.cpu_count() or 1)
        cpu_percent = min(100.0, round((load_avg / cores) * 100.0, 1))
    except Exception:
        cpu_percent = 0.0

    memory_percent = 0.0
    try:
        meminfo: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meminfo[key] = int(value.strip().split()[0])
        total = float(meminfo.get("MemTotal", 0))
        available = float(meminfo.get("MemAvailable", 0))
        if total > 0:
            memory_percent = round(((total - available) / total) * 100.0, 1)
    except Exception:
        memory_percent = 0.0

    disk_percent = 0.0
    try:
        usage = shutil.disk_usage(REPO_ROOT)
        if usage.total > 0:
            disk_percent = round((usage.used / usage.total) * 100.0, 1)
    except Exception:
        disk_percent = 0.0

    gpu_percent = 0.0
    code, stdout, _ = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ],
        timeout=2.0,
    )
    if code == 0:
        line = stdout.strip().splitlines()[0] if stdout.strip() else ""
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            try:
                util = float(parts[0])
                memory_used = float(parts[1])
                memory_total = float(parts[2])
                memory_pressure = (memory_used / memory_total) * 100.0 if memory_total > 0 else 0.0
                gpu_percent = round(max(util, memory_pressure), 1)
            except ValueError:
                gpu_percent = 0.0

    return {
        "cpu": cpu_percent,
        "memory": memory_percent,
        "disk": disk_percent,
        "gpu": gpu_percent,
    }


def _load_projects() -> list[dict[str, Any]]:
    payload = _read_json(PROJECTS_CONFIG_PATH)
    if not isinstance(payload, list):
        return []

    projects: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        rel_path = str(entry.get("path", "."))
        abs_path = (REPO_ROOT / rel_path).resolve()
        signal_paths = []
        for rel_signal in entry.get("signal_files", []):
            signal_path = (REPO_ROOT / str(rel_signal)).resolve()
            if signal_path.exists():
                signal_paths.append(signal_path)
        latest_signal = max(signal_paths, key=lambda item: item.stat().st_mtime, default=None)
        units = [str(unit) for unit in entry.get("units", [])]
        unit_states = [_systemctl_show(unit) for unit in units]

        status = "idle"
        if any(state.get("ActiveState") == "failed" for state in unit_states):
            status = "error"
        elif any(state.get("ActiveState") == "activating" for state in unit_states):
            status = "busy"
        elif any(state.get("ActiveState") == "active" for state in unit_states):
            status = "active"
        elif latest_signal is not None:
            age_seconds = max(
                0.0,
                (datetime.now(timezone.utc) - datetime.fromtimestamp(latest_signal.stat().st_mtime, tz=timezone.utc)).total_seconds(),
            )
            status = "active" if age_seconds < 86400 else "idle"

        projects.append(
            {
                "id": str(entry.get("id", "")),
                "name": str(entry.get("name", rel_path)),
                "summary": str(entry.get("summary", "")),
                "kind": str(entry.get("kind", "project")),
                "path": str(abs_path),
                "exists": abs_path.exists(),
                "status": status,
                "last_activity": _format_ts(latest_signal),
                "signals": len(signal_paths),
                "units": units,
                "tags": [str(tag) for tag in entry.get("tags", [])],
            }
        )
    return projects


def _load_source_mission(
    *,
    tasks: list[dict[str, Any]],
    memory_ops: dict[str, Any],
    model_ops: dict[str, Any],
    work_items: list[dict[str, Any]],
    teamchat: dict[str, Any],
    context_packet: dict[str, Any],
) -> dict[str, Any]:
    payload = _read_json(SOURCE_MISSION_PATH)
    if not isinstance(payload, dict):
        return {
            "status": "offline",
            "statement": None,
            "tagline": None,
            "north_star": None,
            "pillars": [],
            "operating_commitments": [],
            "tasks": [],
            "signals": [],
            "summary": "No Source mission config found.",
            "path": str(SOURCE_MISSION_PATH),
        }

    pillars = payload.get("pillars") if isinstance(payload.get("pillars"), list) else []
    pillar_map = {
        str(item.get("id", "")).strip(): item
        for item in pillars
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }

    live_task_map = {
        str(task.get("mission_task_id") or task.get("id") or "").strip(): task
        for task in tasks
        if isinstance(task, dict) and str(task.get("origin") or "").strip() == "source_mission_config"
    }
    task_rows: list[dict[str, Any]] = []
    raw_tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    for index, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("id", f"source-{index:03d}"))
        pillar_id = str(item.get("pillar", "")).strip()
        pillar = pillar_map.get(pillar_id, {})
        live_task = live_task_map.get(source_id, {})
        task_rows.append(
            {
                "id": source_id,
                "sequence": index,
                "title": str(item.get("title", "Untitled task")),
                "pillar": pillar_id,
                "pillar_label": str(pillar.get("label", pillar_id or "mission")),
                "priority": str(item.get("priority", "medium")),
                "summary": str(item.get("summary", "")),
                "definition_of_done": str(item.get("definition_of_done", "")),
                "status": str(live_task.get("status", "")),
                "assignee": str(live_task.get("assignee", "")),
                "status_reason": str(live_task.get("status_reason") or live_task.get("fix_instructions") or ""),
            }
        )

    open_tasks = sum(1 for task in tasks if str(task.get("status", "")).lower() != "done")
    in_progress = sum(1 for task in tasks if str(task.get("status", "")).lower() == "in_progress")
    memory_totals = memory_ops.get("totals", {}) if isinstance(memory_ops, dict) else {}
    model_summary = model_ops.get("summary", {}) if isinstance(model_ops, dict) else {}
    signals = [
        {
            "label": "Context Packet",
            "value": str(len(context_packet.get("summary_lines") or [])),
            "detail": "Recency markers, open work, active models, and preference lines",
        },
        {
            "label": "Shared Surfaces",
            "value": "4",
            "detail": "Source UI, Discord, Telegram, local agent",
        },
        {
            "label": "Memory Rows",
            "value": str(int(memory_totals.get("rows", 0) or 0)),
            "detail": "Indexed evidence across Discord and Telegram",
        },
        {
            "label": "Routed Models",
            "value": str(int(model_summary.get("distinct_models", 0) or 0)),
            "detail": "Distinct model lanes visible to the operator plane",
        },
        {
            "label": "Coordination Loops",
            "value": str(len(work_items) + int(teamchat.get("active_count", 0) or 0)),
            "detail": "Live work items plus active TeamChat sessions",
        },
        {
            "label": "Mission Tasks",
            "value": str(len(task_rows)),
            "detail": f"{open_tasks} current operator tasks live, {in_progress} in progress",
        },
    ]

    return {
        "status": "active" if task_rows else "warning",
        "statement": str(payload.get("statement", "")),
        "tagline": str(payload.get("tagline", "")),
        "north_star": str(payload.get("north_star", "")),
        "operating_commitments": [
            str(item) for item in payload.get("operating_commitments", []) if str(item).strip()
        ],
        "pillars": [
            {
                "id": str(item.get("id", "")),
                "label": str(item.get("label", "")),
                "summary": str(item.get("summary", "")),
            }
            for item in pillars
            if isinstance(item, dict)
        ],
        "tasks": task_rows,
        "signals": signals,
        "context_packet": context_packet,
        "summary": f"{len(task_rows)} mission tasks across {len(pillar_map)} pillars",
        "path": str(SOURCE_MISSION_PATH),
    }


def _load_external_signals() -> list[dict[str, Any]]:
    payload = _read_json(EXTERNAL_SIGNALS_CONFIG_PATH)
    if not isinstance(payload, list):
        return []

    signals: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        rel_path = str(entry.get("path", ""))
        signal_path = (REPO_ROOT / rel_path).resolve() if rel_path else None
        exists = bool(signal_path and signal_path.exists())
        signal_payload = _read_json(signal_path) if exists and signal_path is not None else None
        last_seen = _format_ts(signal_path) if exists else None
        status = "optional_offline"
        age_seconds = None
        stale_after_seconds = None
        model = {}
        aggregate = {}
        sources = {}
        if exists and signal_path is not None:
            age_seconds = max(0.0, (now - datetime.fromtimestamp(signal_path.stat().st_mtime, tz=timezone.utc)).total_seconds())
            if isinstance(signal_payload, dict):
                stale_after_seconds = signal_payload.get("poll", {}).get("stale_after_seconds")
                model = signal_payload.get("model", {}) if isinstance(signal_payload.get("model"), dict) else {}
                aggregate = signal_payload.get("aggregate", {}) if isinstance(signal_payload.get("aggregate"), dict) else {}
                sources = signal_payload.get("sources", {}) if isinstance(signal_payload.get("sources"), dict) else {}
                status = str(signal_payload.get("status") or "healthy")
            if stale_after_seconds is None:
                stale_after_seconds = 1800
            if age_seconds > float(stale_after_seconds):
                status = "warning"

        source_rows: list[dict[str, Any]] = []
        for source_id, source_payload in sources.items():
            if not isinstance(source_payload, dict):
                continue
            source_rows.append(
                {
                    "id": str(source_id),
                    "status": str(source_payload.get("status", "unknown")),
                    "optional": bool(source_payload.get("optional", False)),
                    "summary": str(source_payload.get("summary", "")),
                    "weight_hint": source_payload.get("weight_hint"),
                    "classification_source": (
                        source_payload.get("classification", {}).get("source")
                        if isinstance(source_payload.get("classification"), dict)
                        else None
                    ),
                }
            )

        signals.append(
            {
                "id": str(entry.get("id", "")),
                "name": str(entry.get("name", rel_path or "external_signal")),
                "kind": str(entry.get("kind", "signal")),
                "required": bool(entry.get("required", False)),
                "mode": str(entry.get("mode", "poll_json")),
                "summary": str(entry.get("summary", "")),
                "path": str(signal_path) if signal_path is not None else None,
                "status": status,
                "last_seen": last_seen,
                "age_seconds": round(age_seconds, 2) if age_seconds is not None else None,
                "exists": exists,
                "producer": signal_payload.get("producer") if isinstance(signal_payload, dict) else None,
                "schema_version": signal_payload.get("schema_version") if isinstance(signal_payload, dict) else None,
                "signal_status": signal_payload.get("status") if isinstance(signal_payload, dict) else None,
                "model_requested": model.get("requested"),
                "model_resolved": model.get("resolved") or model.get("requested"),
                "model_provider": model.get("provider"),
                "model_status": model.get("status"),
                "model_fallback_used": model.get("fallback_used"),
                "generated_at": signal_payload.get("generated_at") if isinstance(signal_payload, dict) else None,
                "stale_after_seconds": stale_after_seconds,
                "aggregate": {
                    "sentiment": aggregate.get("sentiment"),
                    "confidence": aggregate.get("confidence"),
                    "regime": aggregate.get("regime"),
                    "risk_on": aggregate.get("risk_on"),
                    "risk_off": aggregate.get("risk_off"),
                    "source_weights": aggregate.get("source_weights"),
                    "sources_considered": aggregate.get("sources_considered"),
                },
                "sources": source_rows,
            }
        )
    return signals


def _sim_status(net_return_pct: float) -> str:
    if net_return_pct <= -8.0:
        return "critical"
    if net_return_pct < 0.0:
        return "warning"
    return "healthy"


def _load_sim_catalog() -> dict[str, dict[str, Any]]:
    payload = _read_json(SIM_CATALOG_PATH)
    if not isinstance(payload, dict):
        return {}
    sims = payload.get("sims")
    if not isinstance(sims, list):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for entry in sims:
        if not isinstance(entry, dict):
            continue
        sim_id = str(entry.get("id", "")).strip()
        if sim_id:
            rows[sim_id] = entry
    return rows


def _load_sims() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    catalog = _load_sim_catalog()
    for sim_dir in sorted(SIM_ROOT.glob("SIM_*")):
        perf_path = sim_dir / "performance.json"
        state_path = sim_dir / "state.json"
        perf = _read_json(perf_path)
        state = _read_json(state_path)
        if not isinstance(perf, dict):
            continue
        sim_meta = catalog.get(sim_dir.name, {})
        net_return_pct = float(perf.get("net_return_pct", 0.0))
        realized_pnl = float(perf.get("realized_pnl", 0.0))
        total_fees = float(perf.get("total_fees_usd", 0.0))
        initial_capital = float(perf.get("initial_capital", 0.0) or 0.0)
        final_equity_raw = float(perf.get("final_equity", 0.0) or 0.0)
        mark_equity_raw = float(perf.get("mark_equity", final_equity_raw) or final_equity_raw)
        open_positions = int(perf.get("open_positions", 0) or 0)
        live_equity_raw = mark_equity_raw if open_positions > 0 else final_equity_raw
        live_equity_change_raw = live_equity_raw - initial_capital
        live_return_pct = (live_equity_change_raw / initial_capital * 100.0) if initial_capital > 0 else 0.0
        unrealized_pnl = mark_equity_raw - final_equity_raw
        fee_drag = total_fees > abs(realized_pnl) and total_fees > 1.0
        halted = bool(state.get("halted")) if isinstance(state, dict) else False
        updated_candidates = [path for path in (perf_path, state_path) if path.exists()]
        updated_at = _format_ts(max(updated_candidates, key=lambda item: item.stat().st_mtime)) if updated_candidates else None
        rows.append(
            {
                "id": sim_dir.name,
                "display_name": str(sim_meta.get("display_name", sim_dir.name)),
                "bucket": str(sim_meta.get("bucket", "Unclassified")),
                "thesis": str(sim_meta.get("thesis", "")),
                "active_book": bool(sim_meta.get("active_book", True)),
                "status_note": str(sim_meta.get("status_note", "")),
                "strategy_role": str(sim_meta.get("strategy_role", "candidate" if bool(sim_meta.get("active_book", True)) else "research")),
                "stage": str(sim_meta.get("stage", "paper_live" if bool(sim_meta.get("active_book", True)) else "research")),
                "report_strategy": str(sim_meta.get("report_strategy", sim_meta.get("display_name", sim_dir.name))),
                "target_venue": str(sim_meta.get("target_venue", "")),
                "runtime_engine": str(sim_meta.get("runtime_engine", "")),
                "continuous_improvement": bool(sim_meta.get("continuous_improvement", bool(sim_meta.get("active_book", True)))),
                "control_lane": bool(sim_meta.get("control_lane", False)),
                "data_dependency": str(sim_meta.get("data_dependency", "")),
                "improvement_focus": str(sim_meta.get("improvement_focus", "")),
                "status": _sim_status(net_return_pct),
                "initial_capital": round(initial_capital, 2),
                "net_equity_change": round(float(perf.get("net_equity_change", 0.0)), 2),
                "net_return_pct": round(net_return_pct, 3),
                "final_equity": round(final_equity_raw, 2),
                "mark_equity": round(mark_equity_raw, 2),
                "live_equity": round(live_equity_raw, 2),
                "live_equity_change": round(live_equity_change_raw, 2),
                "live_return_pct": round(live_return_pct, 3),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "win_rate": round(float(perf.get("win_rate", 0.0)) * 100.0, 1),
                "round_trips": int(perf.get("round_trips", 0)),
                "open_positions": open_positions,
                "fees_usd": round(total_fees, 3),
                "turnover_usd": round(float(perf.get("turnover_usd", 0.0)), 2),
                "avg_hold_hours": round(float(perf.get("avg_hold_hours", 0.0) or 0.0), 2),
                "halted": halted,
                "fee_drag": fee_drag,
                "updated_at": updated_at,
                "path": str(sim_dir),
            }
        )
    return rows


def _load_command_history(limit: int = 16) -> list[dict[str, Any]]:
    payload = _read_json(COMMAND_HISTORY_PATH)
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload[: max(1, int(limit))]:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _load_memory_ops(*, tasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    source_defs = [
        ("discord_chat", "Discord Chat", DISCORD_MEMORY_PATH),
        ("discord_research", "Discord Research", DISCORD_RESEARCH_PATH),
        ("telegram_main", "Telegram Main", TELEGRAM_MEMORY_PATH),
    ]
    sources: list[dict[str, Any]] = []
    latest_events: list[dict[str, Any]] = []
    total_rows = 0
    for source_id, label, path in source_defs:
        rows = _read_jsonl(path, limit=5000)
        total_rows += len(rows)
        latest_row = rows[-1] if rows else {}
        latest_at = (
            _iso_from_any(latest_row.get("stored_at") or latest_row.get("created_at"))
            if isinstance(latest_row, dict)
            else None
        )
        latest_excerpt = _excerpt(latest_row.get("content")) if isinstance(latest_row, dict) else ""
        user_rows = [row for row in rows if isinstance(row, dict) and str(row.get("role")) == "user"]
        sources.append(
            {
                "id": source_id,
                "label": label,
                "count": len(rows),
                "user_count": len(user_rows),
                "updated_at": latest_at or _format_ts(path),
                "latest_excerpt": latest_excerpt,
                "path": str(path),
                "boundary": build_memory_source_boundary(source_id, label, latest_row if isinstance(latest_row, dict) else None),
            }
        )
        if latest_at:
            latest_events.append(
                {
                    "id": f"{source_id}-latest",
                    "timestamp": latest_at,
                    "kind": "memory",
                    "title": f"{label} ingest",
                    "detail": latest_excerpt or f"{len(rows)} rows indexed",
                    "tone": "neutral",
                }
            )

    inference_rows = _read_jsonl(USER_INFERENCES_PATH, limit=200)
    active_inferences = [
        row for row in inference_rows if isinstance(row, dict) and str(row.get("status", "active")) == "active"
    ]
    rendered_inferences: list[dict[str, Any]] = []
    for row in active_inferences[:6]:
        item = {
            "id": str(row.get("id", "")),
            "statement": str(row.get("statement", "")),
            "confidence": float(row.get("confidence", 0.0) or 0.0),
            "profile_section": str(row.get("profile_section", "")),
            "review_state": str(row.get("review_state", "")),
            "contradiction_state": str(row.get("contradiction_state", "")),
            "review_notes": str(row.get("review_notes", "")),
            "reviewed_by": str(row.get("reviewed_by", "")),
            "reviewed_at": _iso_from_any(row.get("reviewed_at")) or row.get("reviewed_at"),
            "evidence_refs": [
                str(ref) for ref in (row.get("evidence_refs") or []) if str(ref).strip()
            ][:3],
            "evidence_count": len([ref for ref in (row.get("evidence_refs") or []) if str(ref).strip()]),
            "operator_actions": [
                str(action)
                for action in (row.get("operator_actions") or [])
                if str(action).strip()
            ],
        }
        item["boundary"] = build_inference_boundary(item)
        rendered_inferences.append(item)

    profile = _read_json(PREFERENCE_PROFILE_PATH)
    profile_updated_at = profile.get("updated_at") if isinstance(profile, dict) else None
    top_prompt_lines = [
        str(row.get("prompt_line"))
        for row in active_inferences
        if isinstance(row, dict) and row.get("prompt_line")
    ][:4]
    research_rows = [
        row
        for row in _read_jsonl(DISCORD_RESEARCH_PATH, limit=40)
        if isinstance(row, dict) and str(row.get("role")) == "user" and row.get("content")
    ]
    research_topics = [_excerpt(row.get("content"), limit=88) for row in research_rows][:4]
    research_items = list_research_items(limit=6, tasks=tasks or [], research_path=DISCORD_RESEARCH_PATH)

    if profile_updated_at:
        latest_events.append(
            {
                "id": "preference-profile",
                "timestamp": _iso_from_any(profile_updated_at) or profile_updated_at,
                "kind": "memory",
                "title": "Preference profile distilled",
                "detail": f"{len(active_inferences)} active inferences",
                "tone": "healthy",
            }
        )

    return {
        "status": "active" if total_rows else "warning",
        "summary": f"{total_rows} total memory rows | {len(active_inferences)} active inferences",
        "totals": {
            "rows": total_rows,
            "discord_chat": next((row["count"] for row in sources if row["id"] == "discord_chat"), 0),
            "discord_research": next((row["count"] for row in sources if row["id"] == "discord_research"), 0),
            "telegram_main": next((row["count"] for row in sources if row["id"] == "telegram_main"), 0),
            "inferences": len(active_inferences),
        },
        "sources": sources,
        "active_inferences": rendered_inferences,
        "preference_profile": {
            "updated_at": _iso_from_any(profile_updated_at) or profile_updated_at,
            "top_prompt_lines": top_prompt_lines,
            "boundary": build_preference_packet_boundary(rendered_inferences),
        },
        "research_topics": research_topics,
        "research_items": research_items,
        "research_boundary": build_research_boundary(len(research_rows)),
        "events": latest_events,
    }


def build_source_context_packet(
    *,
    tasks: list[dict[str, Any]],
    memory_ops: dict[str, Any],
    model_ops: dict[str, Any],
    work_items: list[dict[str, Any]],
    teamchat: dict[str, Any],
) -> dict[str, Any]:
    board_tasks = [
        task
        for task in tasks
        if isinstance(task, dict) and not str(task.get("id") or "").startswith("runtime:")
    ]
    status_counts = {
        "backlog": sum(1 for task in board_tasks if str(task.get("status") or "").lower() == "backlog"),
        "in_progress": sum(1 for task in board_tasks if str(task.get("status") or "").lower() == "in_progress"),
        "review": sum(1 for task in board_tasks if str(task.get("status") or "").lower() == "review"),
        "done": sum(1 for task in board_tasks if str(task.get("status") or "").lower() == "done"),
    }
    preference_lines = [
        str(line).strip()
        for line in list(((memory_ops.get("preference_profile") or {}).get("top_prompt_lines") or []))
        if str(line).strip()
    ]
    if not preference_lines:
        preference_lines = [str(line).strip() for line in build_user_context_packet(limit=4) if str(line).strip()]

    memory_sources = memory_ops.get("sources") if isinstance(memory_ops, dict) else []
    latest_memory_at = next(
        (
            str(row.get("updated_at"))
            for row in memory_sources
            if isinstance(row, dict) and str(row.get("updated_at") or "").strip()
        ),
        None,
    )
    latest_teamchat_at = next(
        (
            str(row.get("updated_at"))
            for row in list(teamchat.get("sessions") or [])
            if isinstance(row, dict) and str(row.get("updated_at") or "").strip()
        ),
        None,
    )
    latest_runtime_at = next(
        (
            str(row.get("updated_at") or row.get("started_at"))
            for row in work_items
            if isinstance(row, dict) and str(row.get("updated_at") or row.get("started_at") or "").strip()
        ),
        None,
    )
    model_summary = model_ops.get("summary", {}) if isinstance(model_ops, dict) else {}
    distinct_models = int(model_summary.get("distinct_models", 0) or 0)
    default_model = str(model_summary.get("default_model") or "").strip() or "unset"
    summary_lines = [
        f"Open work {sum(status_counts[key] for key in ('backlog', 'in_progress', 'review'))}: {status_counts['backlog']} backlog, {status_counts['in_progress']} in progress, {status_counts['review']} review.",
        f"Active models: {distinct_models} routed, default {default_model}.",
        f"Human preference lines: {len(preference_lines)} available.",
        f"Recency markers: memory {latest_memory_at or 'n/a'} | teamchat {latest_teamchat_at or 'n/a'} | runtime {latest_runtime_at or 'n/a'}.",
    ]
    return {
        "generated_at": now_iso(),
        "open_work": status_counts,
        "active_models": {
            "distinct": distinct_models,
            "default_model": default_model,
        },
        "recency_markers": {
            "memory_updated_at": latest_memory_at,
            "teamchat_updated_at": latest_teamchat_at,
            "runtime_updated_at": latest_runtime_at,
        },
        "preference_lines": preference_lines,
        "summary_lines": summary_lines,
    }


def _load_model_ops(
    *,
    components: list[dict[str, Any]],
    external_signals: list[dict[str, Any]],
    finance_brain: dict[str, Any],
) -> dict[str, Any]:
    assistant_snapshot = _assistant_model_snapshot()
    inventory = _load_agent_inventory()
    external_models = sorted(
        {
            str(signal.get("model_resolved") or signal.get("model_requested"))
            for signal in external_signals
            if signal.get("model_resolved") or signal.get("model_requested")
        }
    )
    finance_models = sorted(
        {
            str(row.get("model_resolved"))
            for row in finance_brain.get("symbols", [])
            if isinstance(row, dict) and row.get("model_resolved")
        }
    )
    assistant_component = next((component for component in components if component.get("id") == "assistant"), {})
    agents = [
        {
            "id": str(item.get("id", "")),
            "model": str(item.get("model", "unknown")),
            "workspace": str(item.get("workspace", "")),
            "bindings": int(item.get("bindings", 0) or 0),
            "is_default": bool(item.get("isDefault", False)),
            "routes": item.get("routes") if isinstance(item.get("routes"), list) else [],
        }
        for item in inventory
        if isinstance(item, dict)
    ]
    model_counts: dict[str, int] = {}
    for agent in agents:
        model_name = agent["model"]
        model_counts[model_name] = model_counts.get(model_name, 0) + 1

    return {
        "status": "active" if assistant_snapshot.get("reachable") else "warning",
        "assistant": {
            "status": str(assistant_component.get("status", "unknown")),
            "details": str(assistant_component.get("details", "")),
            "model_ids": assistant_snapshot.get("model_ids", []),
            "reachable": bool(assistant_snapshot.get("reachable")),
        },
        "agents": agents,
        "summary": {
            "agent_count": len(agents),
            "distinct_models": len(model_counts),
            "default_model": next((agent["model"] for agent in agents if agent["is_default"]), None),
            "external_models": external_models,
            "finance_models": finance_models,
        },
        "model_counts": [
            {"model": model, "count": count}
            for model, count in sorted(model_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def _load_sim_ops(sims: list[dict[str, Any]]) -> dict[str, Any]:
    active_book = sorted(
        [sim for sim in sims if bool(sim.get("active_book", False))],
        key=lambda item: float(item.get("live_return_pct", item.get("net_return_pct", 0.0)) or 0.0),
        reverse=True,
    )
    frozen = [sim for sim in sims if not bool(sim.get("active_book", False))]
    attention: list[dict[str, Any]] = []
    for sim in active_book:
        live_return_pct = float(sim.get("live_return_pct", sim.get("net_return_pct", 0.0)) or 0.0)
        stage = str(sim.get("stage", "") or "").strip().lower()
        flags: list[str] = []
        if sim.get("halted"):
            flags.append("halted")
        if sim.get("fee_drag"):
            flags.append("fee drag")
        if live_return_pct <= -1.0:
            flags.append("underwater")
        if int(sim.get("open_positions", 0) or 0) > 0:
            flags.append(f"{sim.get('open_positions', 0)} open")
        if stage == "staged":
            flags.append("feed pending")
        tone = "healthy"
        if sim.get("halted") or live_return_pct <= -3.0:
            tone = "error"
        elif stage == "staged" and int(sim.get("round_trips", 0) or 0) == 0:
            tone = "warning"
        elif flags:
            tone = "warning"
        attention.append(
            {
                "id": sim.get("id"),
                "display_name": sim.get("display_name", sim.get("id")),
                "bucket": sim.get("bucket"),
                "strategy_role": sim.get("strategy_role", "candidate"),
                "stage": sim.get("stage", ""),
                "report_strategy": sim.get("report_strategy", sim.get("display_name", sim.get("id"))),
                "target_venue": sim.get("target_venue", ""),
                "continuous_improvement": bool(sim.get("continuous_improvement", False)),
                "control_lane": bool(sim.get("control_lane", False)),
                "improvement_focus": sim.get("improvement_focus", ""),
                "tone": tone,
                "initial_capital": sim.get("initial_capital", 0.0),
                "net_equity_change": sim.get("net_equity_change", 0.0),
                "net_return_pct": sim.get("net_return_pct", 0.0),
                "final_equity": sim.get("final_equity", 0.0),
                "mark_equity": sim.get("mark_equity", sim.get("final_equity", 0.0)),
                "live_equity": sim.get("live_equity", sim.get("final_equity", 0.0)),
                "live_equity_change": sim.get("live_equity_change", sim.get("net_equity_change", 0.0)),
                "live_return_pct": sim.get("live_return_pct", sim.get("net_return_pct", 0.0)),
                "unrealized_pnl": sim.get("unrealized_pnl", 0.0),
                "fees_usd": sim.get("fees_usd", 0.0),
                "win_rate": sim.get("win_rate", 0.0),
                "round_trips": sim.get("round_trips", 0),
                "open_positions": sim.get("open_positions", 0),
                "avg_hold_hours": sim.get("avg_hold_hours", 0.0),
                "flags": flags,
                "status_note": sim.get("status_note", ""),
                "updated_at": sim.get("updated_at"),
            }
        )

    frozen_rows = [
        {
            "id": sim.get("id"),
            "display_name": sim.get("display_name", sim.get("id")),
            "bucket": sim.get("bucket"),
            "net_return_pct": sim.get("net_return_pct", 0.0),
            "status_note": sim.get("status_note", ""),
        }
        for sim in frozen
    ]
    return {
        "status": "active" if active_book else "warning",
        "summary": {
            "active_count": len(active_book),
            "growing_count": sum(
                1 for sim in active_book if float(sim.get("live_return_pct", sim.get("net_return_pct", 0.0)) or 0.0) > 0.0
            ),
            "frozen_count": len(frozen_rows),
            "attention_count": sum(1 for row in attention if row["tone"] != "healthy"),
            "trade_count": sum(int(sim.get("round_trips", 0) or 0) for sim in active_book),
            "book_equity": round(sum(float(sim.get("final_equity", 0.0) or 0.0) for sim in active_book), 2),
            "live_equity": round(
                sum(float(sim.get("live_equity", sim.get("final_equity", 0.0)) or 0.0) for sim in active_book), 2
            ),
            "book_pnl": round(sum(float(sim.get("net_equity_change", 0.0) or 0.0) for sim in active_book), 2),
            "live_pnl": round(
                sum(float(sim.get("live_equity_change", sim.get("net_equity_change", 0.0)) or 0.0) for sim in active_book),
                2,
            ),
            "live_return_pct": round(
                (
                    sum(float(sim.get("live_equity_change", sim.get("net_equity_change", 0.0)) or 0.0) for sim in active_book)
                    / sum(float(sim.get("initial_capital", 0.0) or 0.0) for sim in active_book)
                    * 100.0
                )
                if sum(float(sim.get("initial_capital", 0.0) or 0.0) for sim in active_book) > 0.0
                else 0.0,
                2,
            ),
            "open_positions": sum(int(sim.get("open_positions", 0) or 0) for sim in active_book),
        },
        "active": attention,
        "frozen": frozen_rows,
    }


def _build_operator_timeline(
    *,
    commands: list[dict[str, Any]],
    work_items: list[dict[str, Any]],
    finance_brain: dict[str, Any],
    memory_ops: dict[str, Any],
    sim_ops: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in commands[:8]:
        timestamp = _iso_from_any(event.get("timestamp")) or event.get("timestamp")
        if not timestamp:
            continue
        rows.append(
            {
                "id": str(event.get("id", "")) or f"command-{timestamp}",
                "timestamp": timestamp,
                "kind": "command",
                "title": str(event.get("action") or event.get("command") or "command"),
                "detail": str(event.get("summary") or ""),
                "tone": "healthy" if bool(event.get("ok", False)) else "error",
            }
        )
    for item in work_items[:6]:
        tone = "warning" if str(item.get("status", "")).lower() in {"queued", "running"} else "neutral"
        rows.append(
            {
                "id": f"work-{item.get('id', item.get('title', 'work'))}",
                "timestamp": now_iso(),
                "kind": "runtime",
                "title": str(item.get("title") or item.get("id") or "runtime work"),
                "detail": str(item.get("detail") or item.get("status") or ""),
                "tone": tone,
            }
        )
    for event in memory_ops.get("events", [])[:6]:
        if isinstance(event, dict) and event.get("timestamp"):
            rows.append(event)
    generated_at = finance_brain.get("generated_at")
    if generated_at:
        rows.append(
            {
                "id": "finance-brain",
                "timestamp": _iso_from_any(generated_at) or generated_at,
                "kind": "finance",
                "title": "Finance consensus refreshed",
                "detail": str(finance_brain.get("summary") or ""),
                "tone": "healthy",
            }
        )
    for sim in sim_ops.get("active", [])[:4]:
        if sim.get("updated_at"):
            detail_bits = [f"{float(sim.get('net_return_pct', 0.0) or 0.0):+.2f}%"]
            if sim.get("flags"):
                detail_bits.append(", ".join(str(flag) for flag in sim["flags"]))
            rows.append(
                {
                    "id": f"sim-{sim.get('id')}",
                    "timestamp": str(sim.get("updated_at")),
                    "kind": "sim",
                    "title": str(sim.get("display_name") or sim.get("id") or "sim"),
                    "detail": " | ".join(detail_bits),
                    "tone": str(sim.get("tone", "neutral")),
                }
            )
    rows.sort(
        key=lambda item: _parse_timestamp(item.get("timestamp")) or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return rows[:16]


def _load_finance_brain() -> dict[str, Any]:
    payload = _read_json(FINANCE_BRAIN_PATH)
    if not isinstance(payload, dict):
        return {
            "status": "offline",
            "summary": "No finance brain snapshot yet.",
            "generated_at": None,
            "symbols": [],
            "path": str(FINANCE_BRAIN_PATH),
        }
    rows: list[dict[str, Any]] = []
    symbols = payload.get("symbols") if isinstance(payload.get("symbols"), dict) else {}
    for symbol, row in symbols.items():
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        llm_manager = row.get("llm_manager") if isinstance(row.get("llm_manager"), dict) else {}
        analysis_model_resolved = (
            decision.get("analysis_model_resolved")
            or decision.get("model_resolved")
            or llm_manager.get("model_resolved")
        )
        analysis_model_requested = (
            decision.get("analysis_model_requested")
            or decision.get("model_requested")
            or llm_manager.get("model_requested")
        )
        sentiment_models = (
            decision.get("sentiment_models_resolved")
            if isinstance(decision.get("sentiment_models_resolved"), dict)
            else (decision.get("models_resolved") if isinstance(decision.get("models_resolved"), dict) else {})
        )
        rows.append(
            {
                "symbol": str(symbol),
                "action": str(decision.get("action", "hold")),
                "bias": round(float(decision.get("bias", 0.0)), 4),
                "confidence": round(float(decision.get("confidence", 0.0)), 4),
                "risk_state": str(decision.get("risk_state", "normal")),
                "model_resolved": analysis_model_resolved or analysis_model_requested,
                "analysis_model_resolved": analysis_model_resolved,
                "analysis_model_requested": analysis_model_requested,
                "sentiment_model_resolved": decision.get("sentiment_model_resolved"),
                "models_resolved": sentiment_models,
                "llm_used": bool(llm_manager.get("used", False)),
                "llm_reason": llm_manager.get("reason"),
                "llm_latency_ms": llm_manager.get("latency_ms"),
                "weights": row.get("learned_weights") if isinstance(row.get("learned_weights"), dict) else {},
                "incoming_source_scores": row.get("incoming_source_scores") if isinstance(row.get("incoming_source_scores"), dict) else {},
            }
        )
    status = "active" if rows else "warning"
    summary = f"{len(rows)} symbols with live consensus" if rows else "Snapshot present but no symbol rows"
    external = payload.get("external_signal") if isinstance(payload.get("external_signal"), dict) else {}
    analysis_models = sorted(
        {
            str(row.get("analysis_model_resolved") or row.get("analysis_model_requested"))
            for row in rows
            if row.get("analysis_model_resolved") or row.get("analysis_model_requested")
        }
    )
    if analysis_models:
        summary = f"{summary} | analysis={analysis_models[0]}"
    external_inputs = external.get("inputs") if isinstance(external.get("inputs"), dict) else {}
    macbook = external_inputs.get("macbook_sentiment") if isinstance(external_inputs.get("macbook_sentiment"), dict) else {}
    fallback = external_inputs.get("fingpt_sentiment") if isinstance(external_inputs.get("fingpt_sentiment"), dict) else {}
    sentiment_model = None
    if str(macbook.get("status") or "") == "ok" and macbook.get("model_resolved"):
        sentiment_model = macbook.get("model_resolved")
    elif str(fallback.get("status") or "") == "ok" and fallback.get("model_resolved"):
        sentiment_model = fallback.get("model_resolved")
    elif macbook.get("model_resolved"):
        sentiment_model = macbook.get("model_resolved")
    elif fallback.get("model_resolved"):
        sentiment_model = fallback.get("model_resolved")
    if sentiment_model:
        summary = f"{summary} | sentiment={sentiment_model}"
    return {
        "status": status,
        "summary": summary,
        "generated_at": payload.get("generated_at"),
        "external_signal": external,
        "symbols": rows,
        "path": str(FINANCE_BRAIN_PATH),
    }


def _extract_itc_work_items() -> list[dict[str, Any]]:
    lines = _tail_lines(ITC_CYCLE_LOG, 120)
    if not lines:
        return []

    items: list[dict[str, Any]] = []
    recent = [line.strip() for line in lines if line.strip()]
    for marker in ("WAIT_OK local_vllm", "==> classify", "==> sim", "==> market"):
        for line in reversed(recent):
            if marker in line:
                items.append(
                    {
                        "id": marker.lower().replace(" ", "_").replace(">", "").replace("=", ""),
                        "title": marker.replace("==> ", "").replace("WAIT_OK ", ""),
                        "status": "running",
                        "detail": line,
                        "source": str(ITC_CYCLE_LOG),
                    }
                )
                break

    sim_lines = [line for line in recent if line.startswith("[SIM_") or line.startswith("  [SIM_")]
    for line in sim_lines[-3:]:
        items.append(
            {
                "id": line.strip().split("|", 1)[0].strip(" []"),
                "title": "Sim update",
                "status": "running",
                "detail": line.strip(),
                "source": str(ITC_CYCLE_LOG),
            }
        )
    return items


def _extract_local_exec_items() -> list[dict[str, Any]]:
    rows = _read_jsonl(LOCAL_EXEC_LEDGER, limit=100)
    items: list[dict[str, Any]] = []
    for row in reversed(rows):
        status = str(row.get("status", "")).lower()
        if status not in {"queued", "claimed", "running"}:
            continue
        items.append(
            {
                "id": str(row.get("job_id", row.get("id", "local_exec"))),
                "title": str(row.get("job_type", "Local exec job")),
                "status": "running" if status in {"claimed", "running"} else "queued",
                "detail": str(row.get("summary") or row.get("intent") or row.get("description") or status),
                "source": str(LOCAL_EXEC_LEDGER),
            }
        )
    return items[:5]


def _extract_phase1_item() -> list[dict[str, Any]]:
    payload = _read_json(PHASE1_STATUS_PATH)
    if not isinstance(payload, dict):
        return []
    status = str(payload.get("status", "")).strip().lower()
    if not status:
        return []
    detail = f"{payload.get('commandlet_name', 'Phase One')} status={status}"
    if payload.get("started_at"):
        detail = f"{detail} started={payload['started_at']}"
    return [
        {
            "id": "dali_phase1",
            "title": "DALI Phase One",
            "status": "running" if status == "running" else "idle",
            "detail": detail,
            "source": str(PHASE1_STATUS_PATH),
        }
    ]


def _load_work_items() -> list[dict[str, Any]]:
    items = _extract_itc_work_items() + _extract_local_exec_items() + _extract_phase1_item()
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = f"{item.get('title')}::{item.get('detail')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:12]


def _load_teamchat_sessions(limit: int = 4) -> dict[str, Any]:
    state_root = TEAMCHAT_ROOT / "state"
    session_root = TEAMCHAT_ROOT / "sessions"
    if not state_root.exists():
        return {
            "status": "offline",
            "summary": "No teamchat state directory found.",
            "sessions": [],
            "active_count": 0,
        }

    session_rows: list[dict[str, Any]] = []
    for path in sorted(state_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        session_id = str(payload.get("session_id") or path.stem)
        session_log = session_root / f"{session_id}.jsonl"
        session_rows.append(
            {
                "id": session_id,
                "task": str(payload.get("task", "")).strip(),
                "status": str(payload.get("status", "unknown")).strip() or "unknown",
                "cycle": int(payload.get("cycle", 0) or 0),
                "updated_at": _format_ts(path),
                "live": bool(payload.get("live", False)),
                "accepted_reports": int(payload.get("accepted_reports", 0) or 0),
                "session_log": str(session_log) if session_log.exists() else None,
            }
        )
        if len(session_rows) >= limit:
            break

    active = [item for item in session_rows if item.get("status") not in {"accepted", "completed", "failed"}]
    latest = session_rows[0] if session_rows else None
    summary = "No recorded teamchat sessions."
    if latest:
        summary = f"{latest['id']} is {latest['status']}"
        if latest.get("task"):
            summary = f"{summary}: {latest['task']}"

    return {
        "status": "active" if active else ("history" if session_rows else "offline"),
        "summary": summary,
        "sessions": session_rows,
        "active_count": len(active),
    }


def portfolio_payload() -> dict[str, Any]:
    tasks = load_all_tasks()
    external_signals = _load_external_signals()
    finance_brain = _load_finance_brain()
    trading_strategy = _load_trading_strategy()
    sims = _load_sims()
    work_items = _load_work_items()
    components = _load_components()
    command_history = _load_command_history()
    memory_ops = _load_memory_ops(tasks=tasks)
    sim_ops = _load_sim_ops(sims)
    sim_strategy_review = load_or_build_sim_strategy_review(sims, finance_brain, trading_strategy)
    teamchat = _load_teamchat_sessions()
    model_ops = _load_model_ops(
        components=components,
        external_signals=external_signals,
        finance_brain=finance_brain,
    )
    context_packet = build_source_context_packet(
        tasks=tasks,
        memory_ops=memory_ops,
        model_ops=model_ops,
        work_items=work_items,
        teamchat=teamchat,
    )
    payload = {
        "generated_at": now_iso(),
        "projects": _load_projects(),
        "external_signals": external_signals,
        "finance_brain": finance_brain,
        "trading_strategy": trading_strategy,
        "sims": sims,
        "sim_ops": sim_ops,
        "sim_strategy_review": sim_strategy_review,
        "tasks": tasks,
        "work_items": work_items,
        "components": components,
        "health_metrics": _load_health_metrics(),
        "teamchat": teamchat,
        "command_history": command_history,
        "memory_ops": memory_ops,
        "model_ops": model_ops,
        "context_packet": context_packet,
    }
    payload["source_mission"] = _load_source_mission(
        tasks=tasks,
        memory_ops=memory_ops,
        model_ops=model_ops,
        work_items=work_items,
        teamchat=teamchat,
        context_packet=context_packet,
    )
    payload["operator_timeline"] = _build_operator_timeline(
        commands=command_history,
        work_items=work_items,
        finance_brain=finance_brain,
        memory_ops=memory_ops,
        sim_ops=sim_ops,
    )
    payload["discord_bridge"] = discord_bridge_payload(payload, tasks)
    return payload
