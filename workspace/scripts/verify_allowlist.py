#!/usr/bin/env python3
"""
Verify Telegram allowlist resolution.
Fails if no IDs or invalid entries are configured.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from itc_pipeline.allowlist import resolve_allowlist, AllowlistConfigError
except Exception as exc:
    print(f"FAIL: allowlist module unavailable: {exc}")
    sys.exit(1)


def main() -> int:
    try:
        allowlist, source, invalid, warnings = resolve_allowlist()
    except AllowlistConfigError as exc:
        print(f"FAIL: {exc}")
        return 1

    if invalid:
        print(f"FAIL: invalid chat IDs: {invalid}")
        return 1
    if not allowlist:
        print(
            "FAIL: no allowed Telegram chat IDs configured. "
            "Set ALLOWED_CHAT_IDS or add allow_chat_ids to credentials/telegram-allowFrom.json."
        )
        return 1

    print(f"OK: allowlist source={source} ids={sorted(allowlist)}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
