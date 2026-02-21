"""vLLM Metrics Sink — Prometheus → policy router feedback loop.

Polls the vLLM /metrics endpoint, extracts GPU-side inference health signals,
and writes a JSON artifact that the policy router reads to make routing decisions.

Key signals extracted
---------------------
- queue_depth          : requests waiting (> 4 → spill overflow to cloud)
- kv_cache_usage_pct   : KV cache fill level (> 85 → reduce max_tokens or deflect)
- prefix_cache_hit_rate: token-level prefix cache efficiency (< 30% → warmup needed)
- requests_running     : live inflight count
- throughput_tps        : generation tokens per second (rolling 30s window)
- engine_awake          : whether vLLM engine is active (sleeping = needs wake call)

Output artifact
---------------
  workspace/state/vllm_metrics.json   (written atomically via tmp → rename)

Integration with policy_router.py
----------------------------------
    from workspace.scripts.vllm_metrics_sink import read_metrics_artifact
    m = read_metrics_artifact()
    if m and m.get("queue_depth", 0) > 4:
        # route this request to cloud provider instead
        ...

CLI usage
---------
    python -m workspace.scripts.vllm_metrics_sink          # single poll, write artifact
    python -m workspace.scripts.vllm_metrics_sink --watch  # continuous 5s loop
    python -m workspace.scripts.vllm_metrics_sink --json   # print JSON to stdout
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
METRICS_URL = os.environ.get("OPENCLAW_VLLM_METRICS_URL", "http://127.0.0.1:8001/metrics")
ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "workspace" / "state" / "vllm_metrics.json"
POLL_INTERVAL_S = float(os.environ.get("OPENCLAW_VLLM_METRICS_POLL_S", "5"))

# Routing thresholds (can be overridden via env)
QUEUE_SPILL_THRESHOLD  = int(os.environ.get("OPENCLAW_VLLM_QUEUE_SPILL",   "4"))
KV_WARN_THRESHOLD_PCT  = float(os.environ.get("OPENCLAW_VLLM_KV_WARN_PCT", "85.0"))
PREFIX_WARN_HIT_RATE   = float(os.environ.get("OPENCLAW_VLLM_PREFIX_WARN",  "0.30"))


# ---------------------------------------------------------------------------
# Prometheus text-format parser (minimal, no external deps)
# ---------------------------------------------------------------------------
_METRIC_RE = re.compile(
    r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|NaN|[+-]?Inf)\s*$'
)


def parse_prometheus(text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse Prometheus text exposition format into a dict of metric_name → [sample, ...]."""
    result: dict[str, list[dict]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _METRIC_RE.match(line)
        if not m:
            continue
        name   = m.group("name")
        labels_raw = m.group("labels") or ""
        value_str  = m.group("value")
        try:
            value = float(value_str)
        except ValueError:
            continue

        labels: dict[str, str] = {}
        for part in labels_raw.split(","):
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                labels[k.strip()] = v.strip().strip('"')

        result.setdefault(name, []).append({"labels": labels, "value": value})
    return result


# ---------------------------------------------------------------------------
# Metric extraction helpers
# ---------------------------------------------------------------------------

def _first(samples: list[dict]) -> float | None:
    return samples[0]["value"] if samples else None


def extract_signals(raw: dict[str, list[dict]]) -> dict[str, Any]:
    """Extract the signals we care about from the parsed Prometheus data."""

    queue_depth   = _first(raw.get("vllm:num_requests_waiting", []))    or 0.0
    running       = _first(raw.get("vllm:num_requests_running",  []))    or 0.0
    kv_usage      = (_first(raw.get("vllm:kv_cache_usage_perc",  [])) or 0.0) * 100.0

    # Prefix cache hit rate = cumulative hits / cumulative queries (token-level)
    pc_queries = _first(raw.get("vllm:prefix_cache_queries_total", [])) or 0.0
    pc_hits    = _first(raw.get("vllm:prefix_cache_hits_total",   [])) or 0.0
    prefix_hit_rate = (pc_hits / pc_queries) if pc_queries > 0 else 0.0

    # Throughput proxy: total generation tokens ever / uptime (rough estimate)
    gen_tokens = _first(raw.get("vllm:generation_tokens_total", [])) or 0.0

    # Engine awake state
    awake_samples = raw.get("vllm:engine_sleep_state", [])
    engine_awake  = any(
        s["labels"].get("sleep_state") == "awake" and s["value"] == 1.0
        for s in awake_samples
    )

    # Success/error counts
    success_samples = raw.get("vllm:request_success_total", [])
    total_success   = sum(s["value"] for s in success_samples
                          if s["labels"].get("finished_reason") in ("stop", "length"))
    total_error     = sum(s["value"] for s in success_samples
                          if s["labels"].get("finished_reason") == "error")

    now = time.time()
    signals: dict[str, Any] = {
        "timestamp":            now,
        "timestamp_iso":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "queue_depth":          float(queue_depth),
        "requests_running":     float(running),
        "kv_cache_usage_pct":   round(kv_usage, 2),
        "prefix_cache_queries": float(pc_queries),
        "prefix_cache_hits":    float(pc_hits),
        "prefix_cache_hit_rate": round(prefix_hit_rate, 4),
        "generation_tokens_total": float(gen_tokens),
        "engine_awake":         engine_awake,
        "total_success":        float(total_success),
        "total_errors":         float(total_error),
        # Routing recommendations (computed from thresholds)
        "routing": {
            "spill_to_cloud":     queue_depth >= QUEUE_SPILL_THRESHOLD,
            "kv_cache_pressure":  kv_usage >= KV_WARN_THRESHOLD_PCT,
            "prefix_cache_cold":  prefix_hit_rate < PREFIX_WARN_HIT_RATE and pc_queries > 10,
            "engine_sleeping":    not engine_awake,
        },
    }
    return signals


# ---------------------------------------------------------------------------
# Fetch + parse
# ---------------------------------------------------------------------------

def fetch_metrics(url: str, timeout: float = 4.0) -> dict[str, Any] | None:
    """Fetch and parse vLLM Prometheus metrics.  Returns None on error."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return None

    raw     = parse_prometheus(text)
    signals = extract_signals(raw)
    return signals


# ---------------------------------------------------------------------------
# Artifact write (atomic)
# ---------------------------------------------------------------------------

def write_artifact(signals: dict[str, Any], path: Path = ARTIFACT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(signals, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_metrics_artifact(path: Path = ARTIFACT_PATH) -> dict[str, Any] | None:
    """Read the last-written metrics artifact.  Returns None if missing/stale (>30s)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age  = time.time() - data.get("timestamp", 0)
        if age > 30:
            return None
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(signals: dict[str, Any]) -> None:
    r = signals["routing"]
    print(f"[vllm-metrics] {signals['timestamp_iso']}")
    print(f"  queue={signals['queue_depth']:.0f}  running={signals['requests_running']:.0f}"
          f"  kv_cache={signals['kv_cache_usage_pct']:.1f}%"
          f"  prefix_hit={signals['prefix_cache_hit_rate']:.1%}"
          f"  awake={signals['engine_awake']}")
    if r["spill_to_cloud"]:
        print(f"  ⚠ SPILL: queue depth ≥ {QUEUE_SPILL_THRESHOLD} → route overflow to cloud")
    if r["kv_cache_pressure"]:
        print(f"  ⚠ KV PRESSURE: cache {signals['kv_cache_usage_pct']:.1f}% → reduce max_tokens")
    if r["prefix_cache_cold"]:
        print(f"  ⚠ PREFIX COLD: hit rate {signals['prefix_cache_hit_rate']:.1%} → run prefix warmup")
    if r["engine_sleeping"]:
        print("  ⚠ ENGINE SLEEPING → send wake request before routing")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="vLLM metrics sink")
    parser.add_argument("--watch", action="store_true", help="Continuous polling loop")
    parser.add_argument("--json",  action="store_true", help="Print JSON to stdout, no artifact")
    parser.add_argument("--url",   default=METRICS_URL, help="vLLM metrics URL")
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL_S)
    args = parser.parse_args(argv)

    if args.watch:
        print(f"[vllm-metrics] watching {args.url} every {args.interval}s  (Ctrl+C to stop)")
        while True:
            signals = fetch_metrics(args.url)
            if signals is None:
                print(f"[vllm-metrics] unreachable: {args.url}")
            else:
                write_artifact(signals)
                _print_summary(signals)
            time.sleep(args.interval)
        return 0

    signals = fetch_metrics(args.url)
    if signals is None:
        print(f"[vllm-metrics] ERROR: could not reach {args.url}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(signals, indent=2))
    else:
        write_artifact(signals)
        _print_summary(signals)

    return 0


if __name__ == "__main__":
    sys.exit(main())
