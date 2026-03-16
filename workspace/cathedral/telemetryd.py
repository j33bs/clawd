from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any

from .io_utils import atomic_write_json, clamp01, safe_float, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import (
    RUNTIME_LOGS,
    SYSTEM_PHYSIOLOGY_MIRROR_PATH,
    SYSTEM_PHYSIOLOGY_PATH,
    ensure_runtime_dirs,
)

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency
    psutil = None


@dataclass
class _RateSnapshot:
    ts: float
    disk_bytes: float
    net_bytes: float


class TelemetryDaemon:
    def __init__(
        self,
        *,
        rate_hz: float = 6.0,
        output_path: Path = SYSTEM_PHYSIOLOGY_PATH,
        mirror_output_path: Path = SYSTEM_PHYSIOLOGY_MIRROR_PATH,
    ):
        ensure_runtime_dirs()
        self.rate_hz = max(5.0, min(10.0, float(rate_hz)))
        self.output_path = output_path
        self.mirror_output_path = mirror_output_path
        self.log = JsonlLogger(RUNTIME_LOGS / "telemetryd.log")
        self._last_rate: _RateSnapshot | None = None

    def _sample_psutil(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "cpu_load": 0.0,
            "ram": 0.0,
            "cpu_temp": None,
            "fan_cpu": None,
            "disk_io": 0.0,
            "network_throughput": 0.0,
        }
        if psutil is None:
            return out

        out["cpu_load"] = clamp01(psutil.cpu_percent(interval=None) / 100.0)
        out["ram"] = clamp01(psutil.virtual_memory().percent / 100.0)

        try:
            temps = psutil.sensors_temperatures(fahrenheit=False)
            for key in ("coretemp", "k10temp", "cpu-thermal", "acpitz"):
                rows = temps.get(key)
                if rows:
                    out["cpu_temp"] = float(rows[0].current)
                    break
        except Exception:
            pass

        try:
            fans = psutil.sensors_fans()
            for key in ("cpu_fan", "nct6775", "asus"):
                rows = fans.get(key)
                if rows:
                    out["fan_cpu"] = int(rows[0].current)
                    break
            if out["fan_cpu"] is None:
                for rows in fans.values():
                    if rows:
                        out["fan_cpu"] = int(rows[0].current)
                        break
        except Exception:
            pass

        try:
            disk = psutil.disk_io_counters()
            net = psutil.net_io_counters()
            now = time.monotonic()
            current = _RateSnapshot(
                ts=now,
                disk_bytes=float((disk.read_bytes if disk else 0) + (disk.write_bytes if disk else 0)),
                net_bytes=float((net.bytes_recv if net else 0) + (net.bytes_sent if net else 0)),
            )
            if self._last_rate is not None:
                dt = max(1e-6, current.ts - self._last_rate.ts)
                disk_rate = max(0.0, current.disk_bytes - self._last_rate.disk_bytes) / dt
                net_rate = max(0.0, current.net_bytes - self._last_rate.net_bytes) / dt
                out["disk_io"] = clamp01(disk_rate / 500_000_000.0)
                out["network_throughput"] = clamp01(net_rate / 250_000_000.0)
            self._last_rate = current
        except Exception:
            pass

        return out

    def _sample_nvidia(self) -> dict[str, Any]:
        out = {
            "gpu_temp": None,
            "gpu_util": 0.0,
            "gpu_vram": 0.0,
            "gpu_vram_used_mb": 0.0,
            "gpu_vram_total_mb": 0.0,
            "fan_gpu": None,
        }
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return out
        cmd = [
            nvidia_smi,
            "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,fan.speed",
            "--format=csv,noheader,nounits",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1.0, check=False)
            if proc.returncode != 0 or not proc.stdout.strip():
                return out
            first = proc.stdout.splitlines()[0].strip()
            parts = [p.strip() for p in first.split(",")]
            if len(parts) >= 4:
                out["gpu_temp"] = safe_float(parts[0], 0.0)
                out["gpu_util"] = clamp01(safe_float(parts[1], 0.0) / 100.0)
                used = max(0.0, safe_float(parts[2], 0.0))
                total = max(1.0, safe_float(parts[3], 1.0))
                out["gpu_vram_used_mb"] = used
                out["gpu_vram_total_mb"] = total
                out["gpu_vram"] = clamp01(used / total)
            if len(parts) >= 5:
                fan_percent = safe_float(parts[4], 0.0)
                out["fan_gpu"] = int(max(0.0, fan_percent) * 45.0)
        except Exception:
            return out
        return out

    def _sample_lm_sensors(self) -> dict[str, Any]:
        out = {"cpu_temp": None, "fan_cpu": None}
        sensors_bin = shutil.which("sensors")
        if not sensors_bin:
            return out
        try:
            proc = subprocess.run([sensors_bin, "-j"], capture_output=True, text=True, timeout=1.0, check=False)
            if proc.returncode != 0:
                return out
            payload = json.loads(proc.stdout)
            if not isinstance(payload, dict):
                return out
            for chip in payload.values():
                if not isinstance(chip, dict):
                    continue
                for name, reading in chip.items():
                    if not isinstance(reading, dict):
                        continue
                    low_name = str(name).lower()
                    if out["cpu_temp"] is None and "temp" in low_name:
                        for key, value in reading.items():
                            if "input" in str(key).lower() and isinstance(value, (int, float)):
                                out["cpu_temp"] = float(value)
                                break
                    if out["fan_cpu"] is None and "fan" in low_name:
                        for key, value in reading.items():
                            if "input" in str(key).lower() and isinstance(value, (int, float)):
                                out["fan_cpu"] = int(value)
                                break
                if out["cpu_temp"] is not None and out["fan_cpu"] is not None:
                    break
        except Exception:
            return out
        return out

    def sample(self) -> dict[str, Any]:
        payload = {
            "ts": utc_now_iso(),
            "cpu_temp": None,
            "cpu_load": 0.0,
            "gpu_temp": None,
            "gpu_util": 0.0,
            "gpu_vram": 0.0,
            "gpu_vram_used_mb": 0.0,
            "gpu_vram_total_mb": 0.0,
            "fan_cpu": None,
            "fan_gpu": None,
            "ram": 0.0,
            "disk_io": 0.0,
            "network_throughput": 0.0,
        }

        psutil_row = self._sample_psutil()
        gpu_row = self._sample_nvidia()
        sensors_row = self._sample_lm_sensors()

        payload.update(psutil_row)
        payload.update(gpu_row)

        if payload.get("cpu_temp") is None and sensors_row.get("cpu_temp") is not None:
            payload["cpu_temp"] = sensors_row["cpu_temp"]
        if payload.get("fan_cpu") is None and sensors_row.get("fan_cpu") is not None:
            payload["fan_cpu"] = sensors_row["fan_cpu"]

        return payload

    def emit_once(self) -> dict[str, Any]:
        payload = self.sample()
        atomic_write_json(self.output_path, payload)
        atomic_write_json(self.mirror_output_path, payload)
        return payload

    def run_forever(self, stop_event: Event | None = None) -> None:
        period = 1.0 / self.rate_hz
        self.log.log("telemetryd_start", rate_hz=self.rate_hz, output=str(self.output_path))
        next_log = time.monotonic()
        while True:
            if stop_event is not None and stop_event.is_set():
                self.log.log("telemetryd_stop")
                return
            t0 = time.monotonic()
            try:
                payload = self.emit_once()
                now = time.monotonic()
                if now >= next_log:
                    self.log.log(
                        "telemetry_sample",
                        cpu_load=payload.get("cpu_load"),
                        gpu_util=payload.get("gpu_util"),
                        ram=payload.get("ram"),
                    )
                    next_log = now + 5.0
            except Exception as exc:
                self.log.log("telemetry_error", error=str(exc))
            elapsed = time.monotonic() - t0
            sleep_for = period - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DALI telemetry daemon")
    parser.add_argument("--rate-hz", type=float, default=6.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    daemon = TelemetryDaemon(rate_hz=args.rate_hz)
    if args.once:
        payload = daemon.emit_once()
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        return 0
    daemon.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
