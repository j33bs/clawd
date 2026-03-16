#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = REPO_ROOT / "workspace" / "state_runtime" / "twitter_api.env"
DEFAULT_BASE_URL = "https://api.x.com/2"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def oauth_percent_encode(value: str) -> str:
    return quote(str(value), safe="~-._")


def build_oauth1_authorization_header(
    *,
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> str:
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    encoded_pairs = "&".join(
        f"{oauth_percent_encode(key)}={oauth_percent_encode(oauth_params[key])}"
        for key in sorted(oauth_params)
    )
    base_string = "&".join(
        [
            method.upper(),
            oauth_percent_encode(url),
            oauth_percent_encode(encoded_pairs),
        ]
    )
    signing_key = f"{oauth_percent_encode(consumer_secret)}&{oauth_percent_encode(access_token_secret)}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    oauth_params["oauth_signature"] = signature
    parts = ", ".join(
        f'{oauth_percent_encode(key)}="{oauth_percent_encode(oauth_params[key])}"'
        for key in sorted(oauth_params)
    )
    return f"OAuth {parts}"


def fetch_user_by_username_with_bearer(*, bearer_token: str, username: str, base_url: str, timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/users/by/username/{quote(username)}"
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "User-Agent": "clawd-twitter-scrape-stub/1.0",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return {
        "status": response.status_code,
        "json": response.json(),
    }


def fetch_user_by_username_with_oauth1(
    *,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    username: str,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/users/by/username/{quote(username)}"
    auth_header = build_oauth1_authorization_header(
        method="GET",
        url=url,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    response = requests.get(
        url,
        headers={
            "Authorization": auth_header,
            "Accept": "application/json",
            "User-Agent": "clawd-twitter-scrape-stub/1.0",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return {
        "status": response.status_code,
        "json": response.json(),
    }


def resolve_auth_mode(env: dict[str, str], requested_mode: str) -> str:
    has_bearer = bool(env.get("X_BEARER_TOKEN"))
    has_oauth1 = all(
        env.get(key)
        for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    )
    if requested_mode == "bearer":
        if not has_bearer:
            raise SystemExit("missing_env:X_BEARER_TOKEN")
        return "bearer"
    if requested_mode == "oauth1":
        if not has_oauth1:
            raise SystemExit("missing_env:oauth1_requires_X_API_KEY,X_API_SECRET,X_ACCESS_TOKEN,X_ACCESS_TOKEN_SECRET")
        return "oauth1"
    if has_oauth1:
        return "oauth1"
    if has_bearer:
        return "bearer"
    raise SystemExit("missing_env:need_X_BEARER_TOKEN_or_full_oauth1_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal X/Twitter scraping stub using bearer auth or OAuth1.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Path to the local env file with X credentials.")
    parser.add_argument("--username", default="x", help="Username to look up for the live check.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="X API base URL.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds.")
    parser.add_argument("--auth-mode", choices=("auto", "bearer", "oauth1"), default="auto", help="Auth mode to use.")
    parser.add_argument("--dump-json", action="store_true", help="Print the full response JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    env_file = Path(args.env_file).expanduser().resolve()
    if not env_file.is_file():
        raise SystemExit(f"missing_env_file:{env_file}")

    env = load_env_file(env_file)
    auth_mode = resolve_auth_mode(env, str(args.auth_mode))

    try:
        if auth_mode == "oauth1":
            result = fetch_user_by_username_with_oauth1(
                consumer_key=env["X_API_KEY"],
                consumer_secret=env["X_API_SECRET"],
                access_token=env["X_ACCESS_TOKEN"],
                access_token_secret=env["X_ACCESS_TOKEN_SECRET"],
                username=str(args.username),
                base_url=str(args.base_url),
                timeout=float(args.timeout),
            )
        else:
            result = fetch_user_by_username_with_bearer(
                bearer_token=env["X_BEARER_TOKEN"],
                username=str(args.username),
                base_url=str(args.base_url),
                timeout=float(args.timeout),
            )
    except requests.HTTPError as exc:
        response = exc.response
        body = response.text if response is not None else ""
        print(json.dumps({"status": "http_error", "code": response.status_code if response is not None else None, "body": body}, ensure_ascii=True))
        return 1
    except requests.RequestException as exc:
        print(json.dumps({"status": "network_error", "reason": str(exc)}, ensure_ascii=True))
        return 1

    payload = result["json"]
    data = payload.get("data") if isinstance(payload, dict) else None
    summary = {
        "status": "ok",
        "auth_mode": auth_mode,
        "http_status": result["status"],
        "username": args.username,
        "user_id": data.get("id") if isinstance(data, dict) else None,
        "name": data.get("name") if isinstance(data, dict) else None,
    }
    print(json.dumps(summary, ensure_ascii=True))
    if args.dump_json:
        print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
