#!/usr/bin/env python3
"""
Scan agent session logs for intent-level failures and produce a remediation report.
"""
import argparse
import json
import re
import time
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
            "Confirm Anthropic baseUrl and model ID",
            "Check network connectivity",
        ],
    },
    {
        "id": "ollama_404",
        "match": re.compile(r"404 page not found|ollama_http_404", re.I),
        "intent": "LLM response (Ollama)",
        "fixes": [
            "Ensure Ollama baseUrl ends with /v1",
            "Start Ollama: `ollama serve`",
            "Confirm model pulled: `ollama list`",
        ],
    },
    {
        "id": "telegram_chat_not_found",
        "match": re.compile(r"chat not found", re.I),
        "intent": "Telegram send",
        "fixes": [
            "Start bot in DM or add to target group",
            "Use correct chat ID from sessions_list",
            "Verify bot token and allowlist",
        ],
    },
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"gsk_[A-Za-z0-9_-]{10,}"),
]


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


def scan_files(files, max_errors):
    findings = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if len(findings) >= max_errors:
                        return findings
                    if "errorMessage" not in line and "chat not found" not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        obj = {}
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


def format_report(findings):
    date = time.strftime("%Y-%m-%d", time.localtime())
    lines = [f"# Intent Failure Report {date}", "", "## Summary"]
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
    args = parser.parse_args()

    files = load_recent_session_files(args.max_files)
    findings = scan_files(files, args.max_errors)
    report = format_report(findings)

    if args.stdout or not args.out:
        print(report)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
