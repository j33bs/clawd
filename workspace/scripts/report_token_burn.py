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


def load_session_stats(root: Path):
    stats = defaultdict(lambda: {
        "calls": 0,
        "successes": 0,
        "failures": 0,
        "tokens": 0,
        "failed_tokens": 0,
        "timeout_failures": 0,
        "timeout_waste_tokens": 0,
        "missing_usage_records": 0,
    })
    scanned_files = 0
    scanned_lines = 0
    for path in sorted((root / "agents").glob("*/sessions/*.jsonl")):
        scanned_files += 1
        agent = path.parts[-3] if len(path.parts) >= 3 else "unknown"
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
                    msg = obj.get("message", {})
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


def load_router_stats(root: Path):
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
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
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


def render_markdown(session_stats, router_stats):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = []
    for (agent, provider, model), data in session_stats["rows"].items():
        rows.append((agent, provider, model, data))
    rows.sort(key=lambda x: x[3]["tokens"], reverse=True)

    lines = [
        f"# Token Burn Snapshot {now}",
        "",
        "## Scan Coverage",
        f"- session_files_scanned: {session_stats['scanned_files']}",
        f"- session_lines_scanned: {session_stats['scanned_lines']}",
        f"- router_event_log: {router_stats['events_file']}",
        f"- router_event_log_exists: {str(router_stats['exists']).lower()}",
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
    parser.add_argument("--out", help="Write markdown report to file")
    parser.add_argument("--stdout", action="store_true", help="Print markdown to stdout")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    session_stats = load_session_stats(root)
    router_stats = load_router_stats(root)
    report = render_markdown(session_stats, router_stats)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
    if args.stdout or not args.out:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
