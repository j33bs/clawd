from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INBOX = REPO_ROOT / "workspace" / "data" / "itc" / "inbox"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "workspace" / "artifacts" / "itc"
SCHEMA_PATH = REPO_ROOT / "workspace" / "itc" / "schema" / "itc_signal.schema.json"

ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
WINDOW_RE = re.compile(r"^\d+(m|h|d)$")


@dataclass
class RawPayload:
    content: bytes
    extension: str
    metadata: Dict[str, Any]


class IngestAdapter(ABC):
    @abstractmethod
    def fetch_raw(self) -> RawPayload:
        raise NotImplementedError

    @abstractmethod
    def parse_normalize(self, raw: RawPayload) -> Dict[str, Any]:
        raise NotImplementedError


def iso_now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_token(ts_utc: str) -> str:
    return ts_utc.replace("-", "").replace(":", "")


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_iso(ts_utc: str) -> datetime:
    return datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def validate_signal(signal: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(signal, dict):
        return False, "signal_not_object"

    required = ["schema_version", "source", "ts_utc", "window", "metrics", "raw_ref"]
    missing = [k for k in required if k not in signal]
    if missing:
        return False, f"missing_required:{','.join(missing)}"

    if signal.get("schema_version") != 1:
        return False, "schema_version_invalid"

    source = signal.get("source")
    if not isinstance(source, str) or not source:
        return False, "source_invalid"

    ts_utc = signal.get("ts_utc")
    if not isinstance(ts_utc, str) or not ISO_UTC_RE.match(ts_utc):
        return False, "ts_utc_invalid"
    try:
        _parse_iso(ts_utc)
    except ValueError:
        return False, "ts_utc_parse_error"

    window = signal.get("window")
    if not isinstance(window, str) or not WINDOW_RE.match(window):
        return False, "window_invalid"

    metrics = signal.get("metrics")
    if not isinstance(metrics, dict):
        return False, "metrics_invalid"

    for key in ("sentiment", "confidence"):
        if key not in metrics:
            return False, f"metrics_missing_{key}"
        if not isinstance(metrics[key], (int, float)):
            return False, f"metrics_{key}_type"

    regime = metrics.get("regime")
    if regime is not None and not isinstance(regime, str):
        return False, "metrics_regime_type"

    for key in ("risk_on", "risk_off"):
        value = metrics.get(key)
        if value is not None and not isinstance(value, (int, float)):
            return False, f"metrics_{key}_type"

    raw_ref = signal.get("raw_ref")
    if not isinstance(raw_ref, str) or not raw_ref:
        return False, "raw_ref_invalid"

    signature = signal.get("signature")
    if signature is not None:
        if not isinstance(signature, str) or not re.match(r"^sha256:[a-f0-9]{64}$", signature):
            return False, "signature_invalid"

    allowed = {"schema_version", "source", "ts_utc", "window", "metrics", "raw_ref", "signature"}
    extras = set(signal.keys()) - allowed
    if extras:
        return False, f"unknown_top_level_keys:{','.join(sorted(extras))}"

    return True, "ok"


def emit_event(event_type: str, run_id: str, payload: Dict[str, Any], artifact_root: Path = DEFAULT_ARTIFACT_ROOT) -> None:
    events_dir = artifact_root / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "event_type": event_type,
        "ts_utc": iso_now_utc(),
        "run_id": run_id,
        "payload": payload,
    }
    with open(events_dir / "itc_events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")


class FileDropAdapter(IngestAdapter):
    def __init__(self, inbox_dir: Path = DEFAULT_INBOX, input_file: Optional[Path] = None):
        self.inbox_dir = Path(inbox_dir)
        self.input_file = Path(input_file) if input_file else None

    def fetch_raw(self) -> RawPayload:
        selected = self.input_file
        if selected is None:
            if not self.inbox_dir.exists():
                raise FileNotFoundError(f"inbox_not_found:{self.inbox_dir}")
            candidates = sorted(p for p in self.inbox_dir.iterdir() if p.is_file())
            if not candidates:
                raise FileNotFoundError("inbox_empty")
            selected = candidates[0]

        content = selected.read_bytes()
        ext = selected.suffix.lstrip(".") or "json"
        return RawPayload(
            content=content,
            extension=ext,
            metadata={"input_path": str(selected)},
        )

    def parse_normalize(self, raw: RawPayload) -> Dict[str, Any]:
        data = json.loads(raw.content.decode("utf-8"))
        metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
        signal = {
            "schema_version": 1,
            "source": str(data.get("source") or "file"),
            "ts_utc": str(data.get("ts_utc") or iso_now_utc()),
            "window": str(data.get("window") or "1h"),
            "metrics": {
                "risk_on": float(metrics.get("risk_on", 0.0)),
                "risk_off": float(metrics.get("risk_off", 0.0)),
                "sentiment": float(metrics.get("sentiment", 0.0)),
                "regime": str(metrics.get("regime", "unknown")),
                "confidence": float(metrics.get("confidence", 0.0)),
            },
            "raw_ref": "pending://raw_ref",
            "signature": f"sha256:{sha256_hex(raw.content)}",
        }
        return signal


def _dated_dirs(root: Path, ts_utc: str) -> Path:
    dt = _parse_iso(ts_utc)
    return root / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}"


def persist_artifacts(
    raw: RawPayload,
    signal: Dict[str, Any],
    run_id: str,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
) -> Dict[str, str]:
    def _ref_path(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    sig = signal.get("signature")
    if not isinstance(sig, str) or not sig.startswith("sha256:"):
        sig = f"sha256:{sha256_hex(raw.content)}"
        signal["signature"] = sig
    hash8 = sig.split(":", 1)[1][:8]

    raw_dir = _dated_dirs(artifact_root / "raw", signal["ts_utc"])
    norm_dir = _dated_dirs(artifact_root / "normalized", signal["ts_utc"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)

    token = ts_token(signal["ts_utc"])
    raw_name = f"{signal['source']}_{token}_{hash8}.{raw.extension}"
    raw_path = raw_dir / raw_name
    raw_path.write_bytes(raw.content)

    signal["raw_ref"] = _ref_path(raw_path)
    norm_name = f"itc_signal_{token}_{hash8}.json"
    norm_path = norm_dir / norm_name
    with open(norm_path, "w", encoding="utf-8") as f:
        json.dump(signal, f, ensure_ascii=False, indent=2, sort_keys=True)

    emit_event("itc_raw_stored", run_id, {"raw_ref": signal["raw_ref"], "signature": sig}, artifact_root)
    emit_event(
        "itc_normalized_valid",
        run_id,
        {"normalized_ref": _ref_path(norm_path), "signature": sig},
        artifact_root,
    )
    return {
        "raw_path": str(raw_path),
        "normalized_path": str(norm_path),
    }


def ingest_with_adapter(
    adapter: IngestAdapter,
    run_id: str,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
) -> Dict[str, Any]:
    emit_event("itc_ingest_started", run_id, {"adapter": adapter.__class__.__name__}, artifact_root)
    raw = adapter.fetch_raw()
    signal = adapter.parse_normalize(raw)
    ok, reason = validate_signal(signal)
    if not ok:
        emit_event("itc_signal_rejected", run_id, {"reason": reason}, artifact_root)
        raise ValueError(f"invalid_signal:{reason}")

    paths = persist_artifacts(raw, signal, run_id, artifact_root=artifact_root)
    return {
        "signal": signal,
        "paths": paths,
    }
