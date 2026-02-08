#!/usr/bin/env python3
"""
Preflight checks for environment prerequisites.
Fails fast with actionable guidance.
"""
import json
import os
import sys
from pathlib import Path


def _resolve_repo_root(start: Path):
    current = start
    for _ in range(8):
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


_env_root = os.environ.get("OPENCLAW_ROOT")
_file_root = _resolve_repo_root(Path(__file__).resolve())
_cwd_root = _resolve_repo_root(Path.cwd())
BASE_DIR = Path(_env_root) if _env_root else (_file_root or _cwd_root or Path("C:/Users/heath/.openclaw"))
POLICY_FILE = BASE_DIR / "workspace" / "policy" / "llm_policy.json"
OPENCLAW_FILE = BASE_DIR / "openclaw.json"
PAIRING = BASE_DIR / "credentials" / "telegram-pairing.json"

sys.path.insert(0, str((BASE_DIR / "workspace" / "scripts").resolve()))
sys.path.insert(0, str((BASE_DIR / "workspace").resolve()))

try:
    import requests  # noqa: F401
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

try:
    from policy_router import PolicyRouter
except Exception:
    PolicyRouter = None

try:
    from itc_pipeline.allowlist import resolve_allowlist, AllowlistConfigError
except Exception:
    resolve_allowlist = None
    AllowlistConfigError = None


def fail(msg, fixes, failures):
    failures.append({"msg": msg, "fixes": fixes})


def warn(msg, warns):
    warns.append(msg)


def load_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def check_policy(failures):
    data = load_json(POLICY_FILE)
    if not data:
        fail("LLM policy missing or invalid", ["Ensure workspace/policy/llm_policy.json exists and is valid JSON"], failures)
        return None
    if data.get("version") != 2:
        fail("LLM policy version must be 2", ["Update workspace/policy/llm_policy.json to version 2"], failures)
    return data


def check_router(policy, failures):
    if PolicyRouter is None:
        fail("Policy router unavailable", ["Ensure workspace/scripts/policy_router.py is present and importable"], failures)
        return
    router = PolicyRouter()
    for intent in ("itc_classify", "coding"):
        status = router.intent_status(intent)
        if not status.get("available"):
            reasons = status.get("reasons", {})
            reason_text = ", ".join(f"{k}={v}" for k, v in reasons.items()) or "unknown"
            fail(
                f"No available providers for intent: {intent}",
                [
                    "Start Ollama: `ollama serve` and pull a model (e.g., `ollama pull qwen:latest`)",
                    "Ensure free-tier credentials are present (GROQ_API_KEY or Qwen OAuth profile)",
                    f"Provider reasons: {reason_text}",
                ],
                failures,
            )


def check_requests(failures):
    if not REQUESTS_OK:
        fail(
            "Python requests library missing",
            ["Install requests: `python3 -m pip install requests`"],
            failures,
        )


def check_telegram(failures, warnings):
    cfg = load_json(OPENCLAW_FILE) or {}
    tg = cfg.get("channels", {}).get("telegram")
    if not tg:
        return

    if resolve_allowlist is None:
        fail(
            "telegram_not_configured: Allowlist module unavailable",
            ["Ensure workspace/itc_pipeline/allowlist.py exists and is importable"],
            failures,
        )
        return

    try:
        allowlist, source, invalid = resolve_allowlist()
    except AllowlistConfigError as exc:
        fail(str(exc), ["Fix allowlist configuration and retry"], failures)
        return

    if invalid:
        fail(
            "telegram_not_configured: Invalid chat IDs in allowlist",
            [
                "Replace usernames with numeric chat IDs",
                "Run `python workspace/scripts/itc/telegram_list_dialogs.py` to discover IDs",
            ],
            failures,
        )
        return

    if not allowlist:
        fail(
            "telegram_not_configured: No allowed Telegram chat IDs configured. "
            "Set ALLOWED_CHAT_IDS or edit credentials/telegram-allowFrom.json. "
            "Example: ALLOWED_CHAT_IDS=-1001234567890,-1009876543210",
            [
                "Set ALLOWED_CHAT_IDS env var",
                "Or update credentials/telegram-allowFrom.json",
            ],
            failures,
        )
        return

    if tg.get("dmPolicy") == "pairing":
        pairing = load_json(PAIRING) or {}
        if not pairing.get("requests") and not allowlist:
            fail(
                "Telegram pairing is required but no paired users exist",
                [
                    "Start a DM with the bot and send /start",
                    "Verify the bot is added to the target group/channel",
                ],
                failures,
            )

    print(f"Resolved Telegram allowlist ({source}): {sorted(allowlist)}")
    warn(
        "If you see 'chat not found', start a DM with the bot and ensure the numeric chat ID is allowlisted.",
        warnings,
    )


def main():
    failures = []
    warnings = []

    check_requests(failures)
    policy = check_policy(failures)
    if policy:
        check_router(policy, failures)
    check_telegram(failures, warnings)

    if warnings:
        print("WARNINGS:")
        for msg in warnings:
            print(f"- {msg}")
        print("")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"- {f['msg']}")
            for fix in f["fixes"]:
                print(f"  - {fix}")
        sys.exit(1)

    print("ok")


if __name__ == "__main__":
    main()
