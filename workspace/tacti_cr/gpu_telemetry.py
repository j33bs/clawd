"""GPU telemetry bridge — injects live VRAM/utilization pressure into the arousal system.

Reads nvidia-smi every N seconds and exposes a normalized [0, 1] ``gpu_pressure``
signal that the ArousalOscillator can blend with its circadian baseline.

Design principles
-----------------
- **No hard dependency on nvidia-smi**: if unavailable, pressure = 0.0 (neutral).
- **Process-safe**: uses subprocess, no pynvml / ctypes binding that can conflict
  with the vLLM process already holding the CUDA context.
- **Lightweight**: one subprocess call, cached for ``cache_ttl_s`` seconds.
- **Composable**: callers import ``GpuTelemetry`` and call ``.pressure()`` or
  ``.snapshot()``.  Integration into ArousalOscillator is additive — the oscillator
  already has a ``multiplier()`` method; callers can multiply it by
  ``(1 - gpu_pressure * weight)`` to suppress heavy escalation under VRAM load.

Usage
-----
    from workspace.tacti_cr.gpu_telemetry import GpuTelemetry
    telem = GpuTelemetry()
    snap  = telem.snapshot()        # dict with all fields
    p     = telem.pressure()        # float [0,1], higher = more loaded
    telem.is_critical()             # True if VRAM > critical_vram_pct
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Feature flag — GPU telemetry is infrastructure, not a consciousness feature.
# It defaults to ENABLED regardless of TACTI_CR_ENABLE master gate.
# Disable explicitly with TACTI_CR_GPU_TELEMETRY=0.
# Float knobs are read from TACTI-CR config when available.
# ---------------------------------------------------------------------------
import os as _os

def _gpu_telem_enabled() -> bool:  # noqa: E302
    v = _os.environ.get("TACTI_CR_GPU_TELEMETRY", "1").strip().lower()
    return v not in ("0", "false", "no", "off", "disabled")

try:
    from .config import get_float
    _ENABLED_FN = _gpu_telem_enabled  # noqa: E731
    _VRAM_WEIGHT_FN = lambda: get_float("gpu_vram_pressure_weight", 0.8, clamp=(0.0, 1.0))  # noqa: E731
    _UTIL_WEIGHT_FN = lambda: get_float("gpu_util_pressure_weight", 0.2, clamp=(0.0, 1.0))  # noqa: E731
    _CRITICAL_VRAM_FN = lambda: get_float("gpu_critical_vram_pct", 92.0, clamp=(50.0, 100.0))  # noqa: E731
except Exception:
    _ENABLED_FN = _gpu_telem_enabled  # noqa: E731
    _VRAM_WEIGHT_FN = lambda: 0.8  # noqa: E731
    _UTIL_WEIGHT_FN = lambda: 0.2  # noqa: E731
    _CRITICAL_VRAM_FN = lambda: 92.0  # noqa: E731


@dataclass
class GpuSnapshot:
    """Single-GPU telemetry snapshot."""
    gpu_index: int
    name: str
    vram_used_mib: float
    vram_total_mib: float
    vram_pct: float          # 0–100
    utilization_pct: float   # 0–100
    temperature_c: float
    power_w: float
    power_limit_w: float
    power_pct: float         # 0–100
    # derived
    pressure: float          # weighted composite [0,1]
    timestamp: float


def _parse_nvidia_smi_csv(line: str) -> GpuSnapshot | None:
    """Parse one CSV line from nvidia-smi --query-gpu --format=csv,noheader,nounits."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 7:
        return None
    try:
        idx = int(parts[0])
        name = parts[1]
        vram_used = float(parts[2])
        vram_total = float(parts[3])
        util = float(parts[4])
        temp = float(parts[5])
        power_draw = float(parts[6])
        power_limit = float(parts[7]) if len(parts) > 7 else 350.0

        vram_pct = (vram_used / vram_total * 100.0) if vram_total > 0 else 0.0
        power_pct = (power_draw / power_limit * 100.0) if power_limit > 0 else 0.0

        # Composite pressure: VRAM dominates (it causes OOM), util secondary.
        # Weights must sum to ≥ 1.0 so that 100% VRAM usage maps to pressure = 1.0.
        # Default: vram_w=0.8 means 96% VRAM → 0.768 pressure (above 0.6 suppression threshold).
        vram_w = _VRAM_WEIGHT_FN()
        util_w = _UTIL_WEIGHT_FN()
        pressure = min(1.0, (vram_pct / 100.0) * vram_w + (util / 100.0) * util_w)

        return GpuSnapshot(
            gpu_index=idx,
            name=name,
            vram_used_mib=vram_used,
            vram_total_mib=vram_total,
            vram_pct=round(vram_pct, 2),
            utilization_pct=round(util, 2),
            temperature_c=temp,
            power_w=power_draw,
            power_limit_w=power_limit,
            power_pct=round(power_pct, 2),
            pressure=round(pressure, 4),
            timestamp=time.time(),
        )
    except (ValueError, IndexError):
        return None


_NVIDIA_SMI_QUERY = (
    "index,"
    "name,"
    "memory.used,"
    "memory.total,"
    "utilization.gpu,"
    "temperature.gpu,"
    "power.draw,"
    "power.limit"
)

_NVIDIA_SMI_CMD = [
    "nvidia-smi",
    f"--query-gpu={_NVIDIA_SMI_QUERY}",
    "--format=csv,noheader,nounits",
]


class GpuTelemetry:
    """
    Lightweight GPU telemetry reader with time-based caching.

    Parameters
    ----------
    cache_ttl_s : float
        How long (seconds) to reuse the last snapshot before querying
        nvidia-smi again.  Default 2 s — fine for arousal modulation
        without hammering the driver.
    gpu_index : int | None
        Which GPU to report pressure for.  ``None`` → GPU 0.
    """

    def __init__(self, *, cache_ttl_s: float = 2.0, gpu_index: int = 0):
        self._cache_ttl = cache_ttl_s
        self._gpu_index = gpu_index
        self._last_snapshot: GpuSnapshot | None = None
        self._last_fetch: float = 0.0

    # ------------------------------------------------------------------
    def _fetch(self) -> list[GpuSnapshot]:
        """Run nvidia-smi and return parsed snapshots (may be empty on error)."""
        try:
            result = subprocess.run(
                _NVIDIA_SMI_CMD,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode != 0:
                return []
            snaps: list[GpuSnapshot] = []
            for line in result.stdout.strip().splitlines():
                s = _parse_nvidia_smi_csv(line)
                if s is not None:
                    snaps.append(s)
            return snaps
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return []

    def _get_cached(self) -> GpuSnapshot | None:
        now = time.time()
        if self._last_snapshot is not None and (now - self._last_fetch) < self._cache_ttl:
            return self._last_snapshot

        snaps = self._fetch()
        target = next((s for s in snaps if s.gpu_index == self._gpu_index), None)
        if target is None and snaps:
            target = snaps[0]

        self._last_snapshot = target
        self._last_fetch = now
        return target

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return the current GPU snapshot as a plain dict (JSON-serializable).
        Returns an empty-pressure stub when nvidia-smi is unavailable."""
        if not _ENABLED_FN():
            return {"pressure": 0.0, "available": False}

        snap = self._get_cached()
        if snap is None:
            return {"pressure": 0.0, "available": False}

        return {**asdict(snap), "available": True}

    def pressure(self) -> float:
        """Normalized GPU pressure in [0, 1].  0 = idle, 1 = fully saturated.
        Returns 0.0 when telemetry is unavailable (fail-open / don't suppress)."""
        snap = self._get_cached()
        if snap is None or not _ENABLED_FN():
            return 0.0
        return snap.pressure

    def is_critical(self) -> bool:
        """True when VRAM usage exceeds the configured critical threshold."""
        snap = self._get_cached()
        if snap is None:
            return False
        return snap.vram_pct >= _CRITICAL_VRAM_FN()

    def arousal_suppression_factor(self) -> float:
        """
        Factor [0, 1] to multiply against the arousal oscillator multiplier.

        When GPU is idle  → 1.0 (no suppression, full arousal).
        When GPU is near  → tapers toward (1 - vram_weight).
        When GPU critical → floor of ~0.3 to prevent zero-arousal lockout.

        Integrate as::

            final_multiplier = osc.multiplier() * telem.arousal_suppression_factor()
        """
        p = self.pressure()
        # Smooth sigmoid-like suppression: starts biting at p > 0.6
        if p < 0.6:
            return 1.0
        # linear ramp from 1.0 at p=0.6 down to 0.3 at p=1.0
        factor = 1.0 - 0.7 * ((p - 0.6) / 0.4)
        return max(0.3, round(factor, 4))


# ---------------------------------------------------------------------------
# Module-level singleton (optional convenience)
# ---------------------------------------------------------------------------
_DEFAULT_TELEMETRY: GpuTelemetry | None = None


def get_default() -> GpuTelemetry:
    global _DEFAULT_TELEMETRY
    if _DEFAULT_TELEMETRY is None:
        _DEFAULT_TELEMETRY = GpuTelemetry()
    return _DEFAULT_TELEMETRY


__all__ = ["GpuSnapshot", "GpuTelemetry", "get_default"]
