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
SYSTEM_MAP_FILE = BASE_DIR / "workspace" / "policy" / "system_map.json"
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

ALLOWLIST_EXAMPLE = (
    "ALLOWED_CHAT_IDS=-1001369282532,-1001700695156,-1002117631304,-1001445373305"
)


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


def normalize_node_id(raw_value, system_map):
    if not isinstance(system_map, dict):
        return "dali"
    nodes = system_map.get("nodes") or {}
    default_id = str(system_map.get("default_node_id") or "dali")

    if raw_value is None:
        return default_id

    needle = str(raw_value).strip().lower()
    if not needle:
        return default_id

    for node_id, node_cfg in nodes.items():
        aliases = node_cfg.get("aliases") if isinstance(node_cfg, dict) else None
        values = aliases if isinstance(aliases, list) else [node_id]
        for alias in values:
            if str(alias).strip().lower() == needle:
                return node_id
    return default_id


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
        allowlist, source, invalid, warnings_list = resolve_allowlist()
    except AllowlistConfigError as exc:
        fail(str(exc), ["Fix allowlist configuration and retry"], failures)
        return
    for warning in warnings_list:
        warn(warning, warnings)

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
            "Set ALLOWED_CHAT_IDS or add allow_chat_ids to credentials/telegram-allowFrom.json. "
            f"Example: {ALLOWLIST_EXAMPLE}",
            [
                "Set ALLOWED_CHAT_IDS env var",
                "Or update credentials/telegram-allowFrom.json (allow_chat_ids)",
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


def check_node_identity(failures, warnings):
    cfg = load_json(OPENCLAW_FILE) or {}
    system_map = load_json(SYSTEM_MAP_FILE) or {}
    default_node_id = str(system_map.get("default_node_id") or "dali")

    node = cfg.get("node") if isinstance(cfg.get("node"), dict) else {}
    raw_node_id = node.get("id")
    normalized = normalize_node_id(raw_node_id, system_map)

    if not raw_node_id:
        warn(
            f"openclaw.json node.id missing; defaulting to '{default_node_id}' for compatibility",
            warnings,
        )
    elif normalized != str(raw_node_id).strip().lower():
        warn(
            f"openclaw.json node.id alias '{raw_node_id}' normalized to '{normalized}'",
            warnings,
        )


def main():
    failures = []
    warnings = []

    check_requests(failures)
    policy = check_policy(failures)
    if policy:
        check_router(policy, failures)
    check_node_identity(failures, warnings)
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
