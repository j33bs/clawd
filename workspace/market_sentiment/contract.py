from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import jsonschema
except Exception:  # pragma: no cover
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "workspace" / "market_sentiment" / "schema" / "market_sentiment.schema.json"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "workspace" / "artifacts" / "market_sentiment"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_iso(ts_utc: str) -> datetime:
    return datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _dated_dir(root: Path, ts_utc: str) -> Path:
    dt = _parse_iso(ts_utc)
    return root / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}"


def _ref_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_snapshot(snapshot: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(snapshot, dict):
        return False, "snapshot_not_object"
    required = {
        "schema_version",
        "generated_at",
        "producer",
        "status",
        "poll",
        "model",
        "artifacts",
        "sources",
        "aggregate",
    }
    missing = sorted(required - set(snapshot.keys()))
    if missing:
        return False, f"missing_required:{','.join(missing)}"
    if snapshot.get("schema_version") != 1:
        return False, "schema_version_invalid"
    generated_at = snapshot.get("generated_at")
    try:
        if not isinstance(generated_at, str):
            return False, "generated_at_invalid"
        _parse_iso(generated_at)
    except ValueError:
        return False, "generated_at_invalid"
    status = snapshot.get("status")
    if status not in {"ok", "degraded", "error"}:
        return False, "status_invalid"
    aggregate = snapshot.get("aggregate")
    if not isinstance(aggregate, dict):
        return False, "aggregate_invalid"
    for key in ("sentiment", "confidence", "risk_on", "risk_off", "sources_considered", "source_weights", "regime"):
        if key not in aggregate:
            return False, f"aggregate_missing:{key}"
    try:
        sentiment = float(aggregate["sentiment"])
        confidence = float(aggregate["confidence"])
        risk_on = float(aggregate["risk_on"])
        risk_off = float(aggregate["risk_off"])
    except Exception:
        return False, "aggregate_numeric_invalid"
    if not (-1.0 <= sentiment <= 1.0):
        return False, "aggregate.sentiment_out_of_bounds"
    if not (0.0 <= confidence <= 1.0):
        return False, "aggregate.confidence_out_of_bounds"
    if not (0.0 <= risk_on <= 1.0):
        return False, "aggregate.risk_on_out_of_bounds"
    if not (0.0 <= risk_off <= 1.0):
        return False, "aggregate.risk_off_out_of_bounds"
    if aggregate.get("regime") not in {"risk_on", "risk_off", "neutral", "mixed"}:
        return False, "aggregate.regime_invalid"
    if not isinstance(snapshot.get("sources"), dict) or not snapshot["sources"]:
        return False, "sources_invalid"
    if jsonschema is None:
        return True, "ok_fallback"
    try:
        jsonschema.validate(snapshot, load_schema())
    except jsonschema.ValidationError as exc:  # pragma: no cover - exercised in tests
        path = ".".join(str(part) for part in exc.absolute_path)
        if path:
            return False, f"{path}: {exc.message}"
        return False, exc.message
    return True, "ok"


def emit_event(event_type: str, payload: dict[str, Any], artifact_root: Path = DEFAULT_ARTIFACT_ROOT) -> str:
    events_dir = artifact_root / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    path = events_dir / "market_sentiment_events.jsonl"
    entry = {
        "event_type": event_type,
        "ts_utc": utc_now_iso(),
        "payload": payload,
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return _ref_path(path)


def persist_raw_artifact(
    *,
    source: str,
    ts_utc: str,
    content: bytes,
    extension: str,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
) -> str:
    raw_dir = _dated_dir(artifact_root / "raw", ts_utc)
    raw_dir.mkdir(parents=True, exist_ok=True)
    token = ts_utc.replace("-", "").replace(":", "")
    hash8 = sha256_hex(content)[:8]
    path = raw_dir / f"{source}_{token}_{hash8}.{extension.lstrip('.') or 'txt'}"
    path.write_bytes(content)
    return _ref_path(path)


def persist_snapshot_artifact(snapshot: dict[str, Any], artifact_root: Path = DEFAULT_ARTIFACT_ROOT) -> str:
    ts_utc = str(snapshot["generated_at"])
    norm_dir = _dated_dir(artifact_root / "normalized", ts_utc)
    norm_dir.mkdir(parents=True, exist_ok=True)
    token = ts_utc.replace("-", "").replace(":", "")
    canonical = json.loads(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
    artifacts = canonical.get("artifacts") if isinstance(canonical.get("artifacts"), dict) else {}
    if isinstance(artifacts, dict):
        artifacts["snapshot_ref"] = "__self__"
    serialized = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    hash8 = sha256_hex(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8"))[:8]
    path = norm_dir / f"market_sentiment_{token}_{hash8}.json"
    path.write_bytes(serialized)
    return _ref_path(path)


def write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
