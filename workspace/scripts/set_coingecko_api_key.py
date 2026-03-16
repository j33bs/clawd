#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOME_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_REPO_CONFIG = REPO_ROOT / ".openclaw" / "openclaw.json"
DEFAULT_MARKET_CONFIG = REPO_ROOT / "workspace" / "config" / "market_sentiment_sources.json"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _backup(path: Path) -> Path:
    backup_path = path.with_name(f"{path.name}.bak.{_utc_stamp()}")
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def _update_openclaw_env(path: Path, key: str) -> Path:
    payload = _load_json(path)
    env = payload.setdefault("env", {})
    env_vars = env.setdefault("vars", {})
    if not isinstance(env_vars, dict):
        raise ValueError(f"invalid_env_vars:{path}")
    backup_path = _backup(path)
    env_vars["COINGECKO_API_KEY"] = key
    _write_json(path, payload)
    return backup_path


def _update_market_config(path: Path, *, mode: str | None) -> tuple[Path, str]:
    payload = _load_json(path)
    source_cfg = ((payload.get("sources") or {}).get("coingecko")) or {}
    if not isinstance(source_cfg, dict):
        raise ValueError("invalid_coingecko_source_config")
    backup_path = _backup(path)
    source_cfg["api_key_env"] = "COINGECKO_API_KEY"
    if mode == "pro":
        source_cfg["base_url"] = "https://pro-api.coingecko.com/api/v3"
    elif mode == "demo":
        source_cfg["base_url"] = "https://api.coingecko.com/api/v3"
    _write_json(path, payload)
    return backup_path, str(source_cfg.get("base_url") or "")


def _test_key(*, base_url: str, key: str, timeout_seconds: int = 10) -> int:
    headers = {"Accept": "application/json"}
    header_name = "x-cg-pro-api-key" if "pro-api.coingecko.com" in base_url else "x-cg-demo-api-key"
    headers[header_name] = key
    response = requests.get(f"{base_url.rstrip('/')}/ping", headers=headers, timeout=timeout_seconds)
    return response.status_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Store a CoinGecko API key in local OpenClaw config.")
    parser.add_argument("--key", help="CoinGecko API key. If omitted, prompts securely.")
    parser.add_argument("--pro", action="store_true", help="Switch market sentiment CoinGecko base_url to pro API.")
    parser.add_argument("--demo", action="store_true", help="Switch market sentiment CoinGecko base_url to demo/public API.")
    parser.add_argument("--skip-test", action="store_true", help="Skip ping validation after writing config.")
    parser.add_argument("--home-config", default=str(DEFAULT_HOME_CONFIG))
    parser.add_argument("--repo-config", default=str(DEFAULT_REPO_CONFIG))
    parser.add_argument("--market-config", default=str(DEFAULT_MARKET_CONFIG))
    args = parser.parse_args()

    if args.pro and args.demo:
        raise SystemExit("choose_only_one_of:--pro,--demo")

    key = args.key or getpass.getpass("CoinGecko API key: ").strip()
    if not key:
        raise SystemExit("empty_api_key")

    mode = "pro" if args.pro else "demo" if args.demo else None
    home_config = Path(args.home_config).expanduser()
    repo_config = Path(args.repo_config).expanduser()
    market_config = Path(args.market_config).expanduser()

    for path in (home_config, repo_config, market_config):
        if not path.is_file():
            raise SystemExit(f"missing_config:{path}")

    home_backup = _update_openclaw_env(home_config, key)
    repo_backup = _update_openclaw_env(repo_config, key)
    market_backup, base_url = _update_market_config(market_config, mode=mode)

    print(f"updated={home_config}")
    print(f"backup={home_backup}")
    print(f"updated={repo_config}")
    print(f"backup={repo_backup}")
    print(f"updated={market_config}")
    print(f"backup={market_backup}")
    print(f"coingecko_base_url={base_url}")

    if args.skip_test:
        print("test=skipped")
        return 0

    status_code = _test_key(base_url=base_url, key=key)
    print(f"ping_status={status_code}")
    return 0 if 200 <= status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
