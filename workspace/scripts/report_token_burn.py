#!/usr/bin/env python3
"""
Summarize token burn from session and router event logs.
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _parse_since(value: str):
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        num = float(text)
        if num > 1e12:
            return int(num)
        return int(num * 1000)
    except Exception:
        pass
    try:
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def _event_timestamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 1e12:
            return int(value)
        return int(value * 1000)
    if isinstance(value, str):
        return _parse_since(value)
    return None


def _extract_ts(obj, msg):
    for cand in (
        obj.get("timestamp"),
        obj.get("ts"),
        msg.get("timestamp") if isinstance(msg, dict) else None,
    ):
        ts = _event_timestamp(cand)
        if ts is not None:
            return ts
    return None


def load_session_stats(root: Path, since_ms=None, max_files=0):
    stats = defaultdict(
        lambda: {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "tokens": 0,
            "failed_tokens": 0,
            "timeout_failures": 0,
            "timeout_waste_tokens": 0,
            "missing_usage_records": 0,
        }
    )
    scanned_files = 0
    scanned_lines = 0
    files = sorted((root / "agents").glob("*/sessions/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if max_files and max_files > 0:
        files = files[:max_files]
    for path in files:
        scanned_files += 1
        agent = path.parts[-3] if len(path.parts) >= 3 else "unknown"
        file_mtime_ms = int(path.stat().st_mtime * 1000)
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    scanned_lines += 1
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("type") != "message":
                        continue
                    msg = obj.get("message", {}) or {}
                    ts = _extract_ts(obj, msg)
                    if since_ms is not None:
                        if ts is None and file_mtime_ms < since_ms:
                            continue
                        if ts is not None and ts < since_ms:
                            continue
                    provider = msg.get("provider")
                    model = msg.get("model")
                    if not provider or not model:
                        continue
                    usage = msg.get("usage", {}) or {}
                    total_tokens = usage.get("totalTokens")
                    stop_reason = str(msg.get("stopReason", "")).lower()
                    error_text = str(msg.get("errorMessage", "")).lower()
                    key = (agent, provider, model)
                    row = stats[key]
                    row["calls"] += 1
                    if total_tokens is None:
                        row["missing_usage_records"] += 1
                        total_tokens = 0
                    total_tokens = _safe_int(total_tokens, 0)
                    row["tokens"] += total_tokens
                    if stop_reason == "error":
                        row["failures"] += 1
                        row["failed_tokens"] += total_tokens
                        if "timeout" in error_text or "timed out" in error_text:
                            row["timeout_failures"] += 1
                            row["timeout_waste_tokens"] += total_tokens
                    else:
                        row["successes"] += 1
        except Exception:
            continue
    return {
        "rows": stats,
        "scanned_files": scanned_files,
        "scanned_lines": scanned_lines,
    }


def load_router_stats(root: Path, since_ms=None):
    path = root / "itc" / "llm_router_events.jsonl"
    out = {
        "events_file": str(path),
        "exists": path.exists(),
        "escalations_total": 0,
        "escalations_by_reason": defaultdict(int),
        "attempt_failures_by_provider": defaultdict(int),
        "attempt_failures_by_reason": defaultdict(int),
        "timeout_escalations": 0,
    }
    if not path.exists():
        return out
    try:
        file_mtime_ms = int(path.stat().st_mtime * 1000)
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                ts = _event_timestamp(obj.get("ts") or obj.get("timestamp"))
                if since_ms is not None:
                    if ts is None and file_mtime_ms < since_ms:
                        continue
                    if ts is not None and ts < since_ms:
                        continue
                event = obj.get("event")
                detail = obj.get("detail", {}) or {}
                if event == "router_escalate":
                    reason = detail.get("reason_code") or "unknown"
                    out["escalations_total"] += 1
                    out["escalations_by_reason"][reason] += 1
                    if "timeout" in reason:
                        out["timeout_escalations"] += 1
                elif event == "router_attempt":
                    reason = detail.get("reason_code") or "unknown"
                    provider = detail.get("provider") or "unknown"
                    out["attempt_failures_by_provider"][provider] += 1
                    out["attempt_failures_by_reason"][reason] += 1
    except Exception:
        pass
    return out


def aggregate(session_stats):
    agg = {
        "total_calls": 0,
        "total_successes": 0,
        "total_failures": 0,
        "total_tokens": 0,
        "failed_tokens": 0,
        "timeout_failures": 0,
        "timeout_waste_tokens": 0,
        "missing_usage_records": 0,
        "failure_rate_pct": 0.0,
    }
    for data in session_stats["rows"].values():
        agg["total_calls"] += data["calls"]
        agg["total_successes"] += data["successes"]
        agg["total_failures"] += data["failures"]
        agg["total_tokens"] += data["tokens"]
        agg["failed_tokens"] += data["failed_tokens"]
        agg["timeout_failures"] += data["timeout_failures"]
        agg["timeout_waste_tokens"] += data["timeout_waste_tokens"]
        agg["missing_usage_records"] += data["missing_usage_records"]
    if agg["total_calls"]:
        agg["failure_rate_pct"] = round((agg["total_failures"] * 100.0) / agg["total_calls"], 4)
    return agg


def _parse_thresholds(value):
    if not value:
        return {}
    text = value.strip()
    if not text:
        return {}
    path = Path(text)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def evaluate_thresholds(agg, router_stats, thresholds):
    violations = []
    if not thresholds:
        return violations

    max_failure_rate_pct = thresholds.get("max_failure_rate_pct")
    if max_failure_rate_pct is not None and agg["failure_rate_pct"] > float(max_failure_rate_pct):
        violations.append(
            f"failure_rate_pct {agg['failure_rate_pct']} > max_failure_rate_pct {max_failure_rate_pct}"
        )

    max_failed_tokens = thresholds.get("max_failed_tokens")
    if max_failed_tokens is not None and agg["failed_tokens"] > int(max_failed_tokens):
        violations.append(
            f"failed_tokens {agg['failed_tokens']} > max_failed_tokens {max_failed_tokens}"
        )

    max_timeout_waste_tokens = thresholds.get("max_timeout_waste_tokens")
    if max_timeout_waste_tokens is not None and agg["timeout_waste_tokens"] > int(max_timeout_waste_tokens):
        violations.append(
            f"timeout_waste_tokens {agg['timeout_waste_tokens']} > max_timeout_waste_tokens {max_timeout_waste_tokens}"
        )

    max_router_escalations = thresholds.get("max_router_escalations")
    if max_router_escalations is not None and router_stats["escalations_total"] > int(max_router_escalations):
        violations.append(
            f"router_escalations {router_stats['escalations_total']} > max_router_escalations {max_router_escalations}"
        )

    max_missing_usage_records = thresholds.get("max_missing_usage_records")
    if max_missing_usage_records is not None and agg["missing_usage_records"] > int(max_missing_usage_records):
        violations.append(
            f"missing_usage_records {agg['missing_usage_records']} > max_missing_usage_records {max_missing_usage_records}"
        )

    return violations


def render_markdown(session_stats, router_stats, agg, since=None, thresholds=None, violations=None):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = []
    for (agent, provider, model), data in session_stats["rows"].items():
        rows.append((agent, provider, model, data))
    rows.sort(key=lambda x: x[3]["tokens"], reverse=True)

    lines = [
        f"# Token Burn Snapshot {now}",
        "",
        "## Scan Coverage",
        f"- since: {since or 'none'}",
        f"- session_files_scanned: {session_stats['scanned_files']}",
        f"- session_lines_scanned: {session_stats['scanned_lines']}",
        f"- router_event_log: {router_stats['events_file']}",
        f"- router_event_log_exists: {str(router_stats['exists']).lower()}",
        "",
        "## Aggregate",
        f"- total_calls: {agg['total_calls']}",
        f"- total_successes: {agg['total_successes']}",
        f"- total_failures: {agg['total_failures']}",
        f"- failure_rate_pct: {agg['failure_rate_pct']}",
        f"- total_tokens: {agg['total_tokens']}",
        f"- failed_tokens: {agg['failed_tokens']}",
        f"- timeout_failures: {agg['timeout_failures']}",
        f"- timeout_waste_tokens: {agg['timeout_waste_tokens']}",
        f"- missing_usage_records: {agg['missing_usage_records']}",
        "",
        "## By Agent / Provider / Model",
        "| Agent | Provider | Model | Calls | Success | Failure | Tokens | Failed Tokens | Timeout Failures | Timeout Waste | Missing Usage |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if rows:
        for agent, provider, model, data in rows:
            lines.append(
                f"| {agent} | {provider} | {model} | {data['calls']} | {data['successes']} | "
                f"{data['failures']} | {data['tokens']} | {data['failed_tokens']} | "
                f"{data['timeout_failures']} | {data['timeout_waste_tokens']} | {data['missing_usage_records']} |"
            )
    else:
        lines.append("| (none) | - | - | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Retry/Timeout Signals (Router)",
            f"- escalations_total: {router_stats['escalations_total']}",
            f"- timeout_escalations: {router_stats['timeout_escalations']}",
        ]
    )
    if router_stats["escalations_by_reason"]:
        lines.append("- escalations_by_reason:")
        for reason, count in sorted(router_stats["escalations_by_reason"].items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  - {reason}: {count}")
    else:
        lines.append("- escalations_by_reason: none")

    if router_stats["attempt_failures_by_provider"]:
        lines.append("- attempt_failures_by_provider:")
        for provider, count in sorted(router_stats["attempt_failures_by_provider"].items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  - {provider}: {count}")
    else:
        lines.append("- attempt_failures_by_provider: none")

    if router_stats["attempt_failures_by_reason"]:
        lines.append("- attempt_failures_by_reason:")
        for reason, count in sorted(router_stats["attempt_failures_by_reason"].items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  - {reason}: {count}")
    else:
        lines.append("- attempt_failures_by_reason: none")

    if thresholds:
        lines.extend(["", "## Thresholds", f"- config: `{json.dumps(thresholds, sort_keys=True)}`"])
        if violations:
            lines.append("- result: FAIL")
            lines.append("- violations:")
            for v in violations:
                lines.append(f"  - {v}")
        else:
            lines.append("- result: PASS")

    lines.extend(
        [
            "",
            "## Interpretation",
            "- `Failed Tokens` approximates token spend on erroring calls.",
            "- `Timeout Waste` tracks error calls whose message includes timeout indicators.",
            "- `Missing Usage` should remain zero for unified accounting health.",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Report token burn by agent/provider/model")
    parser.add_argument("--since", help="Only include entries at/after ISO timestamp or epoch")
    parser.add_argument("--max-files", type=int, default=0, help="Limit session files scanned (0=all)")
    parser.add_argument("--fail-thresholds", help="JSON string or file with threshold config")
    parser.add_argument("--out", help="Write markdown report to file")
    parser.add_argument("--stdout", action="store_true", help="Print markdown to stdout")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    since_ms = _parse_since(args.since)
    thresholds = _parse_thresholds(args.fail_thresholds)

    session_stats = load_session_stats(root, since_ms=since_ms, max_files=args.max_files)
    router_stats = load_router_stats(root, since_ms=since_ms)
    agg = aggregate(session_stats)
    violations = evaluate_thresholds(agg, router_stats, thresholds)
    report = render_markdown(session_stats, router_stats, agg, since=args.since, thresholds=thresholds, violations=violations)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
    if args.stdout or not args.out:
        print(report, end="")
    return 2 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
