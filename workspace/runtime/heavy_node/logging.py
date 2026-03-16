#!/usr/bin/env python3
"""Structured telemetry for DALI heavy node."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


class HeavyNodeTelemetry:
    def __init__(
        self,
        log_path: Path = Path("workspace/logs/heavy_node_calls.jsonl"),
        metrics_path: Path = Path("workspace/metrics/heavy_node_rollup.json"),
    ) -> None:
        self.log_path = Path(log_path)
        self.metrics_path = Path(metrics_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, row: Dict[str, Any]) -> None:
        # Explicitly avoid raw prompt/message payloads.
        row.pop("prompt", None)
        row.pop("messages", None)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        self._rollup(row)

    def _rollup(self, row: Dict[str, Any]) -> None:
        data: Dict[str, Any] = {
            "calls_total": 0,
            "errors_total": 0,
            "latency_avg_ms": 0.0,
            "tokens_in_total": 0,
            "tokens_out_total": 0,
            "by_endpoint": {},
            "last_updated_utc": None,
        }
        if self.metrics_path.exists():
            try:
                data.update(json.loads(self.metrics_path.read_text(encoding="utf-8")))
            except Exception:
                pass

        prev_calls = int(data.get("calls_total") or 0)
        prev_avg = float(data.get("latency_avg_ms") or 0.0)
        latency = float(row.get("latency_ms") or 0.0)
        calls = prev_calls + 1

        data["calls_total"] = calls
        data["latency_avg_ms"] = round(((prev_avg * prev_calls) + latency) / max(1, calls), 3)
        data["tokens_in_total"] = int(data.get("tokens_in_total") or 0) + int(row.get("tokens_in") or 0)
        data["tokens_out_total"] = int(data.get("tokens_out_total") or 0) + int(row.get("tokens_out") or 0)
        if str(row.get("status", "ok")) != "ok":
            data["errors_total"] = int(data.get("errors_total") or 0) + 1

        endpoint = str(row.get("endpoint") or "unknown")
        by_ep = data.get("by_endpoint") or {}
        current = by_ep.get(endpoint) or {}
        prev_count = int(current.get("count") or 0)
        prev_avg = float(current.get("latency_avg_ms") or 0.0)
        current["count"] = prev_count + 1
        current["latency_avg_ms"] = round(((prev_avg * prev_count) + latency) / max(1, current["count"]), 3)
        current["tokens_in_total"] = int(current.get("tokens_in_total") or 0) + int(row.get("tokens_in") or 0)
        current["tokens_out_total"] = int(current.get("tokens_out_total") or 0) + int(row.get("tokens_out") or 0)
        if str(row.get("status", "ok")) != "ok":
            current["errors_total"] = int(current.get("errors_total") or 0) + 1
        else:
            current["errors_total"] = int(current.get("errors_total") or 0)
        current["last_status"] = str(row.get("status", "ok"))
        by_ep[endpoint] = current
        data["by_endpoint"] = by_ep
        data["last_updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        current["last_updated_utc"] = data["last_updated_utc"]

        self.metrics_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
