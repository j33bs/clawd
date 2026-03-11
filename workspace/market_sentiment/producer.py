from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from .classifier import OllamaMarketClassifier
from .contract import (
    DEFAULT_ARTIFACT_ROOT,
    emit_event,
    persist_raw_artifact,
    persist_snapshot_artifact,
    utc_now_iso,
    validate_snapshot,
    write_atomic_json,
)
from .delivery import deliver_snapshot
from .sources import build_sources


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "workspace" / "config" / "market_sentiment_sources.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "workspace" / "state" / "external" / "macbook_sentiment.json"
OPENCLAW_ENV_CONFIG_PATHS = (
    Path.home() / ".openclaw" / "openclaw.json",
    REPO_ROOT / ".openclaw" / "openclaw.json",
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _load_config(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_openclaw_env_vars() -> None:
    for path in OPENCLAW_ENV_CONFIG_PATHS:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        env_vars = ((data.get("env") or {}).get("vars")) or {}
        if not isinstance(env_vars, dict):
            continue
        for key, value in env_vars.items():
            if isinstance(value, str) and value and key not in os.environ:
                os.environ[key] = value


def _classify_source(classifier: OllamaMarketClassifier, source: dict[str, Any], artifact_root: Path) -> tuple[dict[str, Any], bool]:
    heuristic = source["heuristic"]
    try:
        model_classification, meta = classifier.classify(
            source_name=source["name"],
            summary=source["summary"],
            metrics=source["metrics"],
            heuristic=heuristic,
        )
    except Exception as exc:
        emit_event(
            "market_sentiment_classification_failed",
            {"source": source["name"], "error": str(exc)},
            artifact_root,
        )
        classification = dict(heuristic)
        classification["source"] = "heuristic_fallback"
        classification["latency_ms"] = 0
        return classification, False

    if model_classification is None:
        classification = dict(heuristic)
        classification["source"] = "heuristic_fallback"
        classification["latency_ms"] = 0
        emit_event(
            "market_sentiment_classification_skipped",
            {"source": source["name"], "reason": meta.get("error")},
            artifact_root,
        )
        return classification, False

    classification = dict(model_classification)
    classification["source"] = meta.get("resolved") or meta.get("requested") or "ollama"
    classification["latency_ms"] = int(meta.get("latency_ms") or 0)
    emit_event(
        "market_sentiment_classification_ok",
        {"source": source["name"], "model": classification["source"], "latency_ms": classification["latency_ms"]},
        artifact_root,
    )
    return classification, True


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        row for row in records
        if row["status"] in {"ok", "degraded"} and isinstance(row.get("classification"), dict)
    ]
    if not usable:
        return {
            "sentiment": 0.0,
            "confidence": 0.0,
            "risk_on": 0.0,
            "risk_off": 0.0,
            "regime": "neutral",
            "sources_considered": 0,
            "source_weights": {},
        }
    total_weight = sum(max(0.0, float(row.get("weight_hint", 0.0))) for row in usable) or 1.0
    sentiment = sum(float(row["classification"]["sentiment"]) * float(row["weight_hint"]) for row in usable) / total_weight
    confidence = sum(float(row["classification"]["confidence"]) * float(row["weight_hint"]) for row in usable) / total_weight
    risk_on = sum(float(row["classification"]["risk_on"]) * float(row["weight_hint"]) for row in usable) / total_weight
    risk_off = sum(float(row["classification"]["risk_off"]) * float(row["weight_hint"]) for row in usable) / total_weight
    if sentiment >= 0.2:
        regime = "risk_on"
    elif sentiment <= -0.2:
        regime = "risk_off"
    elif abs(risk_on - risk_off) >= 0.18:
        regime = "mixed"
    else:
        regime = "neutral"
    return {
        "sentiment": round(clamp(sentiment, -1.0, 1.0), 6),
        "confidence": round(clamp(confidence, 0.0, 1.0), 6),
        "risk_on": round(clamp(risk_on, 0.0, 1.0), 6),
        "risk_off": round(clamp(risk_off, 0.0, 1.0), 6),
        "regime": regime,
        "sources_considered": len(usable),
        "source_weights": {row["name"]: round(float(row["weight_hint"]), 6) for row in usable},
    }


def run_market_sentiment(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
) -> dict[str, Any]:
    config = _load_config(config_path)
    _load_openclaw_env_vars()
    generated_at = utc_now_iso()
    sources = build_sources(config)
    classifier_cfg = config.get("model") or {}
    poll_cfg = config.get("poll") or {}
    classifier = OllamaMarketClassifier(
        base_url=str(classifier_cfg.get("base_url") or "http://127.0.0.1:11434"),
        requested_model=str(classifier_cfg.get("requested") or "phi4"),
        fallback_models=[str(item) for item in classifier_cfg.get("fallbacks") or []],
        timeout_seconds=int(classifier_cfg.get("timeout_seconds") or 120),
        temperature=float(classifier_cfg.get("temperature") or 0.0),
        num_predict=int(classifier_cfg.get("num_predict") or 220),
        keep_alive=str(classifier_cfg.get("keep_alive") or "0s"),
        idle_only_patterns=[str(item) for item in classifier_cfg.get("idle_only_patterns") or []] or None,
        idle_max_load_per_cpu=classifier_cfg.get("idle_max_load_per_cpu"),
    )

    emit_event("market_sentiment_run_started", {"config_path": str(config_path)}, artifact_root)
    session = requests.Session()
    session.headers.update({"User-Agent": "openclaw-market-sentiment/1.0", "Accept": "*/*"})

    records: list[dict[str, Any]] = []
    model_used = False
    for source in sources:
        data = source.fetch(session)
        raw_ref = ""
        if data.raw_content:
            raw_ref = persist_raw_artifact(
                source=data.name,
                ts_utc=generated_at,
                content=data.raw_content,
                extension=data.raw_extension,
                artifact_root=artifact_root,
            )
        record = {
            "name": data.name,
            "status": data.status,
            "optional": data.optional,
            "fetched_at": data.fetched_at,
            "stale_after_seconds": int(poll_cfg.get("stale_after_seconds") or 2700),
            "weight_hint": round(float(data.weight_hint), 6),
            "transport": data.transport,
            "raw_ref": raw_ref,
            "summary": data.summary,
            "metrics": data.metrics,
        }
        if data.status == "ok":
            classification, used_model = _classify_source(
                classifier,
                {
                    "name": data.name,
                    "summary": data.summary,
                    "metrics": data.metrics,
                    "heuristic": data.heuristic,
                },
                artifact_root,
            )
            model_used = model_used or used_model
            record["classification"] = classification
            if not used_model:
                record["status"] = "degraded"
        records.append(record)
        emit_event(
            "market_sentiment_source_recorded",
            {"source": data.name, "status": record["status"], "raw_ref": raw_ref},
            artifact_root,
        )

    aggregate = _aggregate(records)
    runtime = classifier.runtime()
    status = "ok"
    if aggregate["sources_considered"] == 0:
        status = "error"
    elif any((not row.get("optional")) and row["status"] in {"error", "stale"} for row in records):
        status = "degraded"
    elif any(row["status"] == "degraded" for row in records):
        status = "degraded"
    elif runtime.status != "ok" or not model_used:
        status = "degraded"

    snapshot = {
        "schema_version": 1,
        "generated_at": generated_at,
        "producer": "c_lawd",
        "status": status,
        "poll": {
            "recommended_interval_seconds": int(poll_cfg.get("recommended_interval_seconds") or 900),
            "stale_after_seconds": int(poll_cfg.get("stale_after_seconds") or 2700),
        },
        "model": {
            "provider": runtime.provider,
            "requested": runtime.requested,
            "resolved": runtime.resolved,
            "fallback_used": runtime.fallback_used,
            "status": runtime.status,
            "error": runtime.error,
        },
        "artifacts": {
            "events_ref": "workspace/artifacts/market_sentiment/events/market_sentiment_events.jsonl",
            "snapshot_ref": "pending://snapshot_ref",
        },
        "sources": {row["name"]: {k: v for k, v in row.items() if k != "name"} for row in records},
        "aggregate": aggregate,
    }
    ok, reason = validate_snapshot(snapshot)
    if not ok:
        emit_event("market_sentiment_snapshot_invalid", {"reason": reason}, artifact_root)
        raise ValueError(f"invalid_market_sentiment_snapshot:{reason}")
    snapshot_ref = persist_snapshot_artifact(snapshot, artifact_root=artifact_root)
    snapshot["artifacts"]["snapshot_ref"] = snapshot_ref
    ok, reason = validate_snapshot(snapshot)
    if not ok:
        emit_event("market_sentiment_snapshot_invalid", {"reason": reason}, artifact_root)
        raise ValueError(f"invalid_market_sentiment_snapshot:{reason}")
    write_atomic_json(Path(output_path), snapshot)
    emit_event(
        "market_sentiment_snapshot_written",
        {"output_path": str(output_path), "status": status, "snapshot_ref": snapshot_ref},
        artifact_root,
    )
    try:
        delivery_result = deliver_snapshot(Path(output_path), config)
    except Exception as exc:
        emit_event(
            "market_sentiment_delivery_failed",
            {"output_path": str(output_path), "error": str(exc)},
            artifact_root,
        )
        raise
    emit_event(
        "market_sentiment_delivery_ok",
        {
            "mode": delivery_result.mode,
            "status": delivery_result.status,
            "target": delivery_result.target,
            "detail": delivery_result.detail,
        },
        artifact_root,
    )
    return snapshot
