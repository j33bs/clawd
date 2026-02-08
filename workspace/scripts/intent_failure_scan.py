#!/usr/bin/env python3
"""
Scan agent session logs for intent-level failures and produce a remediation report.
"""
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ERROR_PATTERNS = [
    {
        "id": "qwen_quota",
        "match": re.compile(r"429 .*quota exceeded", re.I),
        "intent": "LLM response (Qwen Portal)",
        "fixes": [
            "Reduce remote usage via policy: workspace/policy/llm_policy.json",
            "Prefer local for short messages; ensure Ollama is running",
            "Wait for quota reset or upgrade plan",
        ],
    },
    {
        "id": "groq_tpm",
        "match": re.compile(r"Request too large|TPM", re.I),
        "intent": "LLM response (Groq)",
        "fixes": [
            "Keep Groq out of agent routing (use for classifier only)",
            "Reduce prompt size or max input chars in policy",
        ],
    },
    {
        "id": "anthropic_404",
        "match": re.compile(r"not_found_error|404.*anthropic", re.I),
        "intent": "LLM response (Anthropic)",
        "fixes": [
            "Verify ANTHROPIC_API_KEY in secrets.env",
            "Confirm Anthropic baseUrl and model ID in workspace/policy/llm_policy.json",
            "Check network connectivity",
        ],
    },
    {
        "id": "ollama_404",
        "match": re.compile(r"404 page not found|ollama_http_404", re.I),
        "intent": "LLM response (Ollama)",
        "fixes": [
            "Ensure Ollama baseUrl is reachable (default http://localhost:11434)",
            "Start Ollama: `ollama serve`",
            "Confirm model pulled: `ollama list`",
        ],
    },
    {
        "id": "telegram_not_configured",
        "match": re.compile(r"telegram_not_configured|No allowed Telegram chat IDs configured", re.I),
        "intent": "Telegram config",
        "fixes": [
            "Set ALLOWED_CHAT_IDS env var with numeric chat IDs",
            "Or update credentials/telegram-allowFrom.json with allow_chat_ids",
            "Run workspace/scripts/itc/telegram_list_dialogs.py to discover IDs",
        ],
    },
    {
        "id": "telegram_chat_not_allowed",
        "match": re.compile(r"telegram_chat_not_allowed|not in allowlist", re.I),
        "intent": "Telegram allowlist",
        "fixes": [
            "Ensure target chat ID is in ALLOWED_CHAT_IDS",
            "Use numeric chat IDs from `workspace/scripts/itc/telegram_list_dialogs.py`",
        ],
    },
    {
        "id": "telegram_chat_not_found",
        "match": re.compile(r"telegram_chat_not_found|chat not found", re.I),
        "intent": "Telegram send/resolve",
        "fixes": [
            "Start bot in DM or add to target group/channel",
            "Use numeric chat IDs from `workspace/scripts/itc/telegram_list_dialogs.py`",
            "Verify allowlist in credentials/telegram-allowFrom.json",
        ],
    },
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"gsk_[A-Za-z0-9_-]{10,}"),
]
ROUTER_EVENT_LOG = Path("itc/llm_router_events.jsonl")
ROUTER_REASON_FIXES = {
    "request_http_429": [
        "Reduce prompt size or max input chars in policy",
        "Lower per-run call caps or wait for rate limit reset",
    ],
    "request_http_404": [
        "Verify provider baseUrl and model ID in workspace/policy/llm_policy.json",
    ],
    "request_timeout": [
        "Check network connectivity and provider status",
        "Increase timeout if consistently slow",
    ],
    "request_conn_error": [
        "Check network connectivity and provider status",
    ],
    "missing_api_key": [
        "Set the required API key env var in secrets.env",
    ],
    "auth_login_required": [
        "Complete auth login and set OPENAI_AUTH_READY/CLAUDE_AUTH_READY",
    ],
    "ollama_unreachable": [
        "Start Ollama: `ollama serve` and verify baseUrl",
    ],
    "request_token_cap_exceeded": [
        "Lower prompt size or raise maxTokensPerRequest in policy",
    ],
}


def redact(text: str) -> str:
    if not text:
        return text
    redacted = text
    for pat in SECRET_PATTERNS:
        redacted = pat.sub("***", redacted)
    return redacted


def find_pattern(error_text: str):
    for pat in ERROR_PATTERNS:
        if pat["match"].search(error_text):
            return pat
    return None


def load_recent_session_files(max_files: int):
    base = Path("agents")
    files = list(base.glob("*/sessions/*.jsonl"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:max_files]

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


def _event_timestamp(obj):
    ts = obj.get("timestamp") or obj.get("ts")
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        if ts > 1e12:
            return int(ts)
        return int(ts * 1000)
    if isinstance(ts, str):
        return _parse_since(ts)
    return None


def scan_files(files, max_errors, since_ms=None):
    findings = []
    for path in files:
        try:
            file_mtime_ms = int(path.stat().st_mtime * 1000)
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if len(findings) >= max_errors:
                        return findings
                    if "errorMessage" not in line and "chat not found" not in line and "telegram_" not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        obj = {}
                    if since_ms is not None:
                        event_ts = _event_timestamp(obj)
                        if event_ts is None:
                            if file_mtime_ms < since_ms:
                                continue
                        elif event_ts < since_ms:
                            continue
                    err = obj.get("errorMessage")
                    if not err and "chat not found" in line:
                        err = line.strip()
                    if not err:
                        continue
                    err = redact(err)
                    pat = find_pattern(err)
                    findings.append({
                        "timestamp": obj.get("timestamp"),
                        "file": str(path),
                        "error": err,
                        "pattern": pat,
                    })
        except Exception:
            continue
    return findings


def scan_router_events(path: Path):
    counts = {}
    total = 0
    if not path.exists():
        return {"total": 0, "by_reason": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("event") not in ("router_fail", "router_escalate"):
                    continue
                detail = obj.get("detail", {})
                reason = detail.get("reason_code")
                if not reason:
                    continue
                counts[reason] = counts.get(reason, 0) + 1
                total += 1
    except Exception:
        return {"total": 0, "by_reason": {}}
    return {"total": total, "by_reason": counts}


def format_report(findings, since=None):
    date = time.strftime("%Y-%m-%d", time.localtime())
    lines = [f"# Intent Failure Report {date}", "", "## Summary"]
    if since:
        lines.append(f"- since: {since}")
    lines.append(f"- total_errors: {len(findings)}")
    categories = {}
    for f in findings:
        pid = f.get("pattern", {}).get("id", "unknown") if f.get("pattern") else "unknown"
        categories[pid] = categories.get(pid, 0) + 1
    if categories:
        lines.append("- categories:")
        for k, v in sorted(categories.items(), key=lambda x: -x[1]):
            lines.append(f"  - {k}: {v}")
    else:
        lines.append("- categories: none")

    router_stats = scan_router_events(ROUTER_EVENT_LOG)
    lines.append(f"- router_failures: {router_stats.get('total', 0)}")
    if router_stats.get("by_reason"):
        lines.append("- router_failure_reasons:")
        for k, v in sorted(router_stats["by_reason"].items(), key=lambda x: -x[1]):
            lines.append(f"  - {k}: {v}")
    else:
        lines.append("- router_failure_reasons: none")

    lines.append("")
    lines.append("## Router Failures")
    if router_stats.get("total", 0) > 0:
        for k, v in sorted(router_stats.get("by_reason", {}).items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")
            fixes = ROUTER_REASON_FIXES.get(k, [])
            if fixes:
                for fix in fixes:
                    lines.append(f"  - {fix}")
    else:
        lines.append("No router failures recorded.")

    lines.append("")
    lines.append("## Findings")
    if not findings:
        lines.append("No errors found in recent session logs.")
        return "\n".join(lines)

    for idx, f in enumerate(findings, 1):
        pat = f.get("pattern")
        intent = pat.get("intent") if pat else "Unknown intent"
        lines.append(f"{idx}. Intent: {intent}")
        lines.append(f"   Error: {f.get('error')}")
        if pat:
            lines.append("   Suggested fixes:")
            for fix in pat.get("fixes", []):
                lines.append(f"   - {fix}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Scan logs for intent-level failures")
    parser.add_argument("--max-files", type=int, default=20, help="Max session files to scan")
    parser.add_argument("--max-errors", type=int, default=50, help="Max errors to report")
    parser.add_argument("--out", type=str, default=None, help="Write report to file")
    parser.add_argument("--stdout", action="store_true", help="Print report to stdout")
    parser.add_argument("--since", type=str, default=None, help="Only include events at/after this time (ISO or epoch)")
    args = parser.parse_args()

    files = load_recent_session_files(args.max_files)
    since_ms = _parse_since(args.since) if args.since else None
    findings = scan_files(files, args.max_errors, since_ms=since_ms)
    report = format_report(findings, since=args.since)

    if args.stdout or not args.out:
        print(report)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
