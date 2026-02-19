#!/usr/bin/env python3
"""
Audit skill files for suspicious supply-chain patterns.

Designed for pre-install gating:
  python3 workspace/scripts/audit_skills.py --path /path/to/skill
  python3 workspace/scripts/audit_skills.py --preinstall skill-name
  python3 workspace/scripts/audit_skills.py --scan
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from urllib.parse import urlparse


SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class PatternRule:
    rule_id: str
    severity: str
    description: str
    pattern: str
    flags: int = re.IGNORECASE | re.MULTILINE


PATTERN_RULES: Sequence[PatternRule] = (
    PatternRule(
        "child_process_exec",
        "high",
        "Node child process execution primitive",
        r"\bchild_process\.exec(?:Sync)?\s*\(",
    ),
    PatternRule(
        "subprocess_exec",
        "medium",
        "Python subprocess execution primitive",
        r"\bsubprocess\.(?:run|Popen|call|check_output)\s*\(",
    ),
    PatternRule(
        "curl_pipe_shell",
        "high",
        "Pipe-from-network shell execution",
        r"\bcurl\b[^\n|]{0,300}\|\s*(?:bash|sh)\b",
    ),
    PatternRule(
        "eval_call",
        "high",
        "Dynamic eval execution",
        r"\beval\s*\(",
    ),
    PatternRule(
        "generic_exec_call",
        "medium",
        "Generic exec invocation",
        r"(?<!child_process\.)\bexec(?:Sync|File)?\s*\(",
    ),
    PatternRule(
        "fetch_auth_token",
        "high",
        "HTTP fetch with auth/token-like material",
        r"\bfetch\s*\(.{0,400}\b(?:authorization|api[_-]?key|bearer|token)\b",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
    PatternRule(
        "post_auth_token",
        "high",
        "HTTP POST with auth/token-like material",
        r"\b(?:requests\.)?post\s*\(.{0,400}\b(?:authorization|api[_-]?key|bearer|token)\b",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
    PatternRule(
        "read_dot_env",
        "high",
        "Reads .env content from filesystem",
        r"\breadFile(?:Sync)?\s*\(.{0,200}(?:~\/\.env|\.env\b)",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
    PatternRule(
        "read_clawdbot_home",
        "high",
        "Reads ~/.clawdbot content",
        r"(?:readFile(?:Sync)?\s*\(.{0,200}~\/\.clawdbot|~\/\.clawdbot)",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
    PatternRule(
        "webhook_reference",
        "medium",
        "Webhook usage reference",
        r"\bwebhook\b",
    ),
    PatternRule(
        "base64_payload",
        "medium",
        "Base64 payload construction/decoding",
        r"\b(?:atob|btoa|base64|Buffer\.from\s*\(.{0,120}['\"]base64['\"])\b",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
)


URL_PATTERN = re.compile(r"https?://[^\s)\"'>]+", re.IGNORECASE)

SUSPICIOUS_DOMAIN_MARKERS = (
    "webhook.site",
    "discord.com/api/webhooks",
    "requestbin",
    "ngrok",
    "pastebin.",
    "transfer.sh",
    "0x0.st",
    "hookdeck",
)

TEXT_FILE_EXTS = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".bash",
    ".zsh",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}


def _default_skills_root() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    return codex_home / "skills"


def _is_private_ip(host: str) -> bool:
    if not host:
        return False
    parts = host.split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts):
        return False
    a, b, _, _ = [int(x) for x in parts]
    if a == 10:
        return True
    if a == 127:
        return True
    if a == 192 and b == 168:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    return False


def _iter_scan_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if not path.exists() or not path.is_dir():
        return
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        if item.suffix.lower() in TEXT_FILE_EXTS or item.name.lower() in {"skill.md", "readme.md"}:
            yield item


def _to_line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _snippet(text: str, start: int, end: int, max_len: int = 220) -> str:
    raw = text[start:end].replace("\n", " ").strip()
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def _scan_rule_matches(file_path: Path, text: str, compiled_rules: Sequence[tuple[PatternRule, re.Pattern]]) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    seen = set()
    for rule, rgx in compiled_rules:
        for match in rgx.finditer(text):
            line = _to_line_number(text, match.start())
            key = (rule.rule_id, str(file_path), line, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "severity": rule.severity,
                    "rule": rule.rule_id,
                    "description": rule.description,
                    "file": str(file_path),
                    "line": line,
                    "evidence": _snippet(text, match.start(), match.end()),
                }
            )
    return findings


def _scan_urls(file_path: Path, text: str) -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    for match in URL_PATTERN.finditer(text):
        url = match.group(0).strip().rstrip(".,;")
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            continue
        severity = None
        rule = None
        description = None
        low_url = url.lower()

        if any(marker in low_url for marker in SUSPICIOUS_DOMAIN_MARKERS):
            severity = "high"
            rule = "suspicious_url_webhook_or_exfil"
            description = "Potential exfiltration/webhook endpoint"
        elif host not in {"localhost"} and not _is_private_ip(host) and parsed.scheme == "http":
            severity = "medium"
            rule = "unencrypted_external_http_url"
            description = "External HTTP URL without TLS"
        elif re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", host) and not _is_private_ip(host):
            severity = "medium"
            rule = "external_ip_url"
            description = "External raw IP URL"

        if severity is None:
            continue

        findings.append(
            {
                "severity": severity,
                "rule": rule,
                "description": description,
                "file": str(file_path),
                "line": _to_line_number(text, match.start()),
                "evidence": url,
            }
        )
    return findings


def _risk_level(findings: Sequence[Dict[str, object]]) -> str:
    if any(f.get("severity") == "high" for f in findings):
        return "high"
    if any(f.get("severity") == "medium" for f in findings):
        return "medium"
    return "low"


def _recommendation(level: str) -> str:
    if level == "high":
        return "reject"
    if level == "medium":
        return "review"
    return "install"


def audit_skill_path(path: Path) -> Dict[str, object]:
    scan_root = path.resolve()
    if not scan_root.exists():
        raise FileNotFoundError(f"path not found: {scan_root}")

    if scan_root.is_dir():
        skill_name = scan_root.name
    else:
        skill_name = scan_root.parent.name

    compiled_rules = [(rule, re.compile(rule.pattern, rule.flags)) for rule in PATTERN_RULES]
    findings: List[Dict[str, object]] = []
    scanned_files = 0
    skipped_files: List[str] = []

    for file_path in _iter_scan_files(scan_root):
        scanned_files += 1
        try:
            raw = file_path.read_bytes()
        except Exception:
            skipped_files.append(str(file_path))
            continue

        if b"\x00" in raw:
            skipped_files.append(str(file_path))
            continue

        text = raw.decode("utf-8", errors="ignore")
        findings.extend(_scan_rule_matches(file_path, text, compiled_rules))
        findings.extend(_scan_urls(file_path, text))

    # Stable sort for deterministic outputs.
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(str(f.get("severity")), 0), str(f.get("file")), int(f.get("line", 0))), reverse=True)
    level = _risk_level(findings)
    report: Dict[str, object] = {
        "skill_name": skill_name,
        "skill_path": str(scan_root),
        "risk_level": level,
        "recommendation": _recommendation(level),
        "files_scanned": scanned_files,
        "files_skipped": skipped_files,
        "findings": findings,
    }
    return report


def _discover_installed_skill_paths(skills_root: Path) -> List[Path]:
    if not skills_root.exists() or not skills_root.is_dir():
        return []
    skill_files = sorted(list(skills_root.rglob("SKILL.md")) + list(skills_root.rglob("skill.md")))
    parents = []
    seen = set()
    for file_path in skill_files:
        parent = file_path.parent.resolve()
        if parent in seen:
            continue
        seen.add(parent)
        parents.append(parent)
    return parents


def audit_installed_skills(skills_root: Path) -> List[Dict[str, object]]:
    reports = []
    for skill_path in _discover_installed_skill_paths(skills_root):
        reports.append(audit_skill_path(skill_path))
    return reports


def summarize_reports(reports: Sequence[Dict[str, object]]) -> Dict[str, int]:
    summary = {"high": 0, "medium": 0, "low": 0, "total": 0}
    for report in reports:
        level = str(report.get("risk_level", "low"))
        if level not in summary:
            continue
        summary[level] += 1
        summary["total"] += 1
    return summary


def _should_fail(report: Dict[str, object], fail_threshold: str) -> bool:
    if fail_threshold == "none":
        return False
    threshold_rank = SEVERITY_ORDER[fail_threshold]
    level = str(report.get("risk_level", "low"))
    return SEVERITY_ORDER.get(level, 0) >= threshold_rank


def _resolve_preinstall_target(preinstall_arg: str, skills_root: Path) -> Path:
    candidate = Path(preinstall_arg).expanduser()
    if candidate.exists():
        return candidate.resolve()
    return (skills_root / preinstall_arg).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit skills for malicious/suspicious patterns")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--path", help="Path to a skill directory or file to audit")
    mode.add_argument("--preinstall", help="Skill name/path to audit before installation")
    mode.add_argument("--scan", action="store_true", help="Scan installed skills under CODEX_HOME/skills")
    parser.add_argument("--skills-root", help="Override skills root (default: $CODEX_HOME/skills or ~/.codex/skills)")
    parser.add_argument(
        "--fail-threshold",
        choices=["none", "low", "medium", "high"],
        default="high",
        help="Exit non-zero when risk level is at or above this threshold (default: high)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    skills_root = Path(args.skills_root).expanduser().resolve() if args.skills_root else _default_skills_root().resolve()

    try:
        if args.path:
            report = audit_skill_path(Path(args.path).expanduser())
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1 if _should_fail(report, args.fail_threshold) else 0

        if args.preinstall:
            target = _resolve_preinstall_target(args.preinstall, skills_root)
            report = audit_skill_path(target)
            report["mode"] = "preinstall"
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1 if _should_fail(report, args.fail_threshold) else 0

        reports = audit_installed_skills(skills_root)
        payload = {
            "mode": "scan",
            "skills_root": str(skills_root),
            "skills": reports,
            "summary": summarize_reports(reports),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1 if any(_should_fail(r, args.fail_threshold) for r in reports) else 0
    except FileNotFoundError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"ERROR: audit failed: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
