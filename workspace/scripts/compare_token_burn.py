#!/usr/bin/env python3
"""
Compare two token burn snapshots and detect drift.
"""
import argparse
import json
from pathlib import Path


DEFAULT_THRESHOLDS = {
    "max_failure_rate_pp": 1.0,
    "max_timeout_waste_delta_tokens": 5000,
    "max_failed_tokens_delta": 50000,
    "max_model_failure_rate_pp": 5.0,
    "min_calls_for_model_rate": 20,
}


def _to_int(text, default=0):
    try:
        return int(str(text).strip())
    except Exception:
        return default


def _to_float(text, default=0.0):
    try:
        return float(str(text).strip())
    except Exception:
        return default


def _parse_thresholds(value):
    if not value:
        return dict(DEFAULT_THRESHOLDS)
    text = value.strip()
    if not text:
        return dict(DEFAULT_THRESHOLDS)
    path = Path(text)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        try:
            data = json.loads(text)
        except Exception:
            data = {}
    merged = dict(DEFAULT_THRESHOLDS)
    merged.update(data)
    return merged


def parse_snapshot(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    aggregate = {}
    per_model = {}

    for line in lines:
        line = line.strip()
        if line.startswith("- ") and ": " in line:
            key, value = line[2:].split(": ", 1)
            aggregate[key.strip()] = value.strip()

    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        if "|---" in s:
            continue
        parts = [p.strip() for p in s.strip("|").split("|")]
        if len(parts) != 11:
            continue
        if parts[0] == "Agent" or parts[0] == "(none)":
            continue
        provider = parts[1]
        model = parts[2]
        key = (provider, model)
        row = per_model.setdefault(
            key,
            {
                "calls": 0,
                "success": 0,
                "failure": 0,
                "tokens": 0,
                "failed_tokens": 0,
                "timeout_failures": 0,
                "timeout_waste": 0,
            },
        )
        row["calls"] += _to_int(parts[3])
        row["success"] += _to_int(parts[4])
        row["failure"] += _to_int(parts[5])
        row["tokens"] += _to_int(parts[6])
        row["failed_tokens"] += _to_int(parts[7])
        row["timeout_failures"] += _to_int(parts[8])
        row["timeout_waste"] += _to_int(parts[9])

    parsed = {
        "aggregate": {
            "total_calls": _to_int(aggregate.get("total_calls", 0)),
            "total_failures": _to_int(aggregate.get("total_failures", 0)),
            "total_tokens": _to_int(aggregate.get("total_tokens", 0)),
            "failed_tokens": _to_int(aggregate.get("failed_tokens", 0)),
            "timeout_waste_tokens": _to_int(aggregate.get("timeout_waste_tokens", 0)),
            "failure_rate_pct": _to_float(aggregate.get("failure_rate_pct", 0.0)),
        },
        "per_model": per_model,
    }
    return parsed


def compare(old_data, new_data):
    old_agg = old_data["aggregate"]
    new_agg = new_data["aggregate"]

    delta = {
        "calls": new_agg["total_calls"] - old_agg["total_calls"],
        "failures": new_agg["total_failures"] - old_agg["total_failures"],
        "tokens": new_agg["total_tokens"] - old_agg["total_tokens"],
        "failed_tokens": new_agg["failed_tokens"] - old_agg["failed_tokens"],
        "timeout_waste_tokens": new_agg["timeout_waste_tokens"] - old_agg["timeout_waste_tokens"],
        "failure_rate_pp": round(new_agg["failure_rate_pct"] - old_agg["failure_rate_pct"], 4),
    }

    model_deltas = []
    keys = set(old_data["per_model"].keys()) | set(new_data["per_model"].keys())
    for key in sorted(keys):
        o = old_data["per_model"].get(key, {})
        n = new_data["per_model"].get(key, {})
        ocalls = _to_int(o.get("calls", 0))
        nfails = _to_int(n.get("failure", 0))
        ncalls = _to_int(n.get("calls", 0))
        ofails = _to_int(o.get("failure", 0))
        orate = (ofails * 100.0 / ocalls) if ocalls else 0.0
        nrate = (nfails * 100.0 / ncalls) if ncalls else 0.0
        model_deltas.append(
            {
                "provider": key[0],
                "model": key[1],
                "delta_calls": _to_int(n.get("calls", 0)) - _to_int(o.get("calls", 0)),
                "delta_tokens": _to_int(n.get("tokens", 0)) - _to_int(o.get("tokens", 0)),
                "delta_failures": _to_int(n.get("failure", 0)) - _to_int(o.get("failure", 0)),
                "delta_failed_tokens": _to_int(n.get("failed_tokens", 0)) - _to_int(o.get("failed_tokens", 0)),
                "delta_timeout_waste": _to_int(n.get("timeout_waste", 0)) - _to_int(o.get("timeout_waste", 0)),
                "failure_rate_pp": round(nrate - orate, 4),
                "new_calls": ncalls,
            }
        )

    model_deltas.sort(key=lambda x: abs(x["delta_failed_tokens"]) + abs(x["delta_timeout_waste"]), reverse=True)
    return delta, model_deltas


def evaluate_drift(delta, model_deltas, thresholds):
    violations = []
    if abs(delta["failure_rate_pp"]) > float(thresholds["max_failure_rate_pp"]):
        violations.append(
            f"failure_rate_pp drift {delta['failure_rate_pp']} exceeds {thresholds['max_failure_rate_pp']}"
        )
    if delta["timeout_waste_tokens"] > int(thresholds["max_timeout_waste_delta_tokens"]):
        violations.append(
            f"timeout_waste_tokens delta {delta['timeout_waste_tokens']} exceeds {thresholds['max_timeout_waste_delta_tokens']}"
        )
    if delta["failed_tokens"] > int(thresholds["max_failed_tokens_delta"]):
        violations.append(
            f"failed_tokens delta {delta['failed_tokens']} exceeds {thresholds['max_failed_tokens_delta']}"
        )

    min_calls = int(thresholds["min_calls_for_model_rate"])
    max_model_pp = float(thresholds["max_model_failure_rate_pp"])
    for row in model_deltas:
        if row["new_calls"] < min_calls:
            continue
        if abs(row["failure_rate_pp"]) > max_model_pp:
            violations.append(
                f"{row['provider']}/{row['model']} failure_rate_pp {row['failure_rate_pp']} exceeds {max_model_pp}"
            )
    return violations


def render(old_file, new_file, delta, model_deltas, thresholds, violations):
    lines = [
        "# Token Burn Drift Report",
        "",
        "## Inputs",
        f"- baseline: `{old_file}`",
        f"- current: `{new_file}`",
        "",
        "## Aggregate Drift",
        f"- delta_calls: {delta['calls']}",
        f"- delta_failures: {delta['failures']}",
        f"- delta_tokens: {delta['tokens']}",
        f"- delta_failed_tokens: {delta['failed_tokens']}",
        f"- delta_timeout_waste_tokens: {delta['timeout_waste_tokens']}",
        f"- failure_rate_pp: {delta['failure_rate_pp']}",
        "",
        "## Top Waste Sources (Provider/Model)",
        "| Provider | Model | ΔCalls | ΔTokens | ΔFailures | ΔFailedTokens | ΔTimeoutWaste | FailureRateΔpp |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    if model_deltas:
        for row in model_deltas[:10]:
            lines.append(
                f"| {row['provider']} | {row['model']} | {row['delta_calls']} | {row['delta_tokens']} | "
                f"{row['delta_failures']} | {row['delta_failed_tokens']} | {row['delta_timeout_waste']} | {row['failure_rate_pp']} |"
            )
    else:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Thresholds",
            f"- config: `{json.dumps(thresholds, sort_keys=True)}`",
        ]
    )
    if violations:
        lines.append("- result: FAIL")
        lines.append("- violations:")
        for v in violations:
            lines.append(f"  - {v}")
    else:
        lines.append("- result: PASS")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Compare token burn snapshots")
    parser.add_argument("baseline", help="Baseline snapshot markdown path")
    parser.add_argument("current", help="Current snapshot markdown path")
    parser.add_argument("--thresholds", help="JSON string or file for drift thresholds")
    parser.add_argument("--out", help="Write report to file")
    parser.add_argument("--stdout", action="store_true", help="Print report")
    args = parser.parse_args()

    thresholds = _parse_thresholds(args.thresholds)
    old_data = parse_snapshot(Path(args.baseline))
    new_data = parse_snapshot(Path(args.current))
    delta, model_deltas = compare(old_data, new_data)
    violations = evaluate_drift(delta, model_deltas, thresholds)
    report = render(args.baseline, args.current, delta, model_deltas, thresholds, violations)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
    if args.stdout or not args.out:
        print(report, end="")
    return 2 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
