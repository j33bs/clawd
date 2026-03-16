#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_CONFIG_PATH = REPO_ROOT / "workspace" / "config" / "weekly_x_strategy_review.json"
DEFAULT_OUTPUT_PATHS = (
    Path.home() / "Taildrive" / "shared" / "weekly_x_strategy_review.json",
    REPO_ROOT / "workspace" / "runtime" / "weekly_x_strategy_review.json",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    trimmed = str(text or "").strip()
    if not trimmed:
        return None
    try:
        parsed = json.loads(trimmed)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    start = trimmed.find("{")
    end = trimmed.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(trimmed[start : end + 1])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _confidence_value(raw: Any) -> float:
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"high", "strong"}:
            return 0.78
        if normalized in {"medium", "moderate"}:
            return 0.58
        if normalized in {"low", "weak"}:
            return 0.34
    try:
        return float(raw)
    except Exception:
        return 0.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp_path.write_text(serialized, encoding="utf-8")
    try:
        os.replace(tmp_path, path)
    except OSError:
        path.write_text(serialized, encoding="utf-8")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _resolve_output_path(config: dict[str, Any]) -> Path:
    raw_path = str(config.get("output_path") or "").strip()
    if raw_path:
        return Path(raw_path).expanduser()
    for path in DEFAULT_OUTPUT_PATHS:
        parent = path.expanduser().parent
        if parent.exists():
            return path.expanduser()
    return DEFAULT_OUTPUT_PATHS[-1]


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _artifact_is_fresh(path: Path, refresh_after_hours: int) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    generated_at = _parse_iso(payload.get("generated_at")) if isinstance(payload, dict) else None
    if generated_at is None:
        generated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = _now() - generated_at
    return age < timedelta(hours=max(1, int(refresh_after_hours)))


def _fetch_recent_search(
    *,
    bearer_token: str,
    base_url: str,
    query: str,
    max_results: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    response = requests.get(
        f"{base_url.rstrip('/')}/tweets/search/recent",
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "User-Agent": "openclaw-weekly-x-review/1.0",
        },
        params={
            "query": query,
            "max_results": max(10, min(100, int(max_results))),
            "tweet.fields": "created_at,lang,public_metrics",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _tweet_engagement(tweet: dict[str, Any]) -> int:
    metrics = tweet.get("public_metrics") if isinstance(tweet.get("public_metrics"), dict) else {}
    return int(metrics.get("like_count", 0) or 0) + (2 * int(metrics.get("retweet_count", 0) or 0))


def _summarize_queries(payloads: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query_rows: list[dict[str, Any]] = []
    sample_posts: list[dict[str, Any]] = []
    for item in payloads:
        query_id = str(item.get("id") or "query")
        weight = float(item.get("weight") or 1.0)
        tweets = [row for row in list(item.get("tweets") or []) if isinstance(row, dict)]
        tweets.sort(key=_tweet_engagement, reverse=True)
        top_posts: list[dict[str, Any]] = []
        for tweet in tweets[:4]:
            metrics = tweet.get("public_metrics") if isinstance(tweet.get("public_metrics"), dict) else {}
            top_posts.append(
                {
                    "created_at": tweet.get("created_at"),
                    "text": " ".join(str(tweet.get("text") or "").split())[:280],
                    "likes": int(metrics.get("like_count", 0) or 0),
                    "retweets": int(metrics.get("retweet_count", 0) or 0),
                    "replies": int(metrics.get("reply_count", 0) or 0),
                }
            )
        query_rows.append(
            {
                "id": query_id,
                "query": str(item.get("query") or ""),
                "weight": weight,
                "tweet_count": len(tweets),
                "top_posts": top_posts,
            }
        )
        for tweet in top_posts[:3]:
            sample_posts.append({"query_id": query_id, **tweet})
    sample_posts.sort(key=lambda row: (row.get("likes", 0) + (2 * row.get("retweets", 0))), reverse=True)
    return query_rows, sample_posts[:10]


def _heuristic_note(query_rows: list[dict[str, Any]], sample_posts: list[dict[str, Any]]) -> dict[str, Any]:
    dominant = max(query_rows, key=lambda row: row.get("tweet_count", 0), default=None)
    dominant_id = dominant.get("id") if isinstance(dominant, dict) else "crypto_market"
    top_sample = sample_posts[0]["text"] if sample_posts else "No usable X samples."
    return {
        "summary": f"X sampled {sum(int(row.get('tweet_count', 0) or 0) for row in query_rows)} posts across {len(query_rows)} weekly themes.",
        "thesis": f"Treat {dominant_id} as the main slow-moving context lane and keep X as ranking input only, not an execution trigger.",
        "focus": "Retune crypto paper lanes around regime shifts, sentiment persistence, and drawdown control rather than chasing isolated X spikes.",
        "actions": [
            "review crypto paper sleeves once this note lands",
            "treat X context as a weekly ranking overlay only",
            "prefer smaller sizing or hold decisions when X sentiment conflicts with fresh market structure",
        ],
        "risk_flags": [
            "X can shift asynchronously to tape action",
            "engagement-weighted posts can overstate crowded views",
            top_sample[:140],
        ],
        "confidence": 0.42,
    }


def _run_analysis(config: dict[str, Any], query_rows: list[dict[str, Any]], sample_posts: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    analysis_cfg = config.get("analysis") if isinstance(config.get("analysis"), dict) else {}
    model = str(analysis_cfg.get("model") or "local-assistant")
    base_url = str(analysis_cfg.get("base_url") or "http://100.113.160.1:8001/v1").rstrip("/")
    api_key = os.environ.get(str(analysis_cfg.get("api_key_env") or "OPENCLAW_LOCAL_ASSISTANT_API_KEY"), "local")
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return terse JSON only with keys: summary, thesis, focus, actions, risk_flags, confidence. "
                    "This is a weekly strategy note for an AU-legal crypto paper-trading system. "
                    "Use X as slow context only, not as a trade trigger. "
                    "If X conflicts with realtime tape or liquidity, prefer throttling or hold decisions over forced trades. "
                    "Keep summary <= 180 chars, thesis <= 220 chars, focus <= 140 chars, "
                    "actions <= 3 short items, risk_flags <= 3 short items."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "query_rows": query_rows,
                        "sample_posts": sample_posts,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "temperature": float(analysis_cfg.get("temperature") or 0.0),
        "max_tokens": int(analysis_cfg.get("max_tokens") or 420),
        "response_format": {"type": "json_object"},
    }
    start = time.time()
    response = requests.post(
        f"{base_url}/chat/completions",
        json=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=float(analysis_cfg.get("timeout_seconds") or 30),
    )
    response.raise_for_status()
    payload = response.json()
    message = ((payload.get("choices") or [{}])[0] or {}).get("message") or {}
    content = str(message.get("content") or message.get("reasoning_content") or "")
    parsed = _extract_json_object(content)
    if not isinstance(parsed, dict):
        raise ValueError("analysis_json_missing")
    parsed["confidence"] = max(0.0, min(1.0, _confidence_value(parsed.get("confidence", 0.0))))
    focus = parsed.get("focus")
    if isinstance(focus, list):
        parsed["focus"] = " | ".join(str(item).strip() for item in focus if str(item).strip())[:180]
    else:
        parsed["focus"] = str(focus or "").strip()[:180]
    parsed["actions"] = [str(item).strip() for item in list(parsed.get("actions") or []) if str(item).strip()][:3]
    parsed["risk_flags"] = [str(item).strip() for item in list(parsed.get("risk_flags") or []) if str(item).strip()][:3]
    parsed["latency_ms"] = int((time.time() - start) * 1000.0)
    resolved_model = str(payload.get("model") or model)
    return parsed, resolved_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a weekly X-guided strategy note for Dali.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", default="", help="Override output path.")
    parser.add_argument("--force", action="store_true", help="Ignore refresh cadence and run now.")
    parser.add_argument("--analysis-only", action="store_true", help="Reuse the saved X digest and rerun only the analysis stage.")
    parser.add_argument("--print-json", action="store_true", help="Print the full artifact JSON.")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    config = _read_json(config_path)
    output_path = Path(args.output).expanduser() if str(args.output).strip() else _resolve_output_path(config)
    refresh_after_hours = int(config.get("refresh_after_hours") or 144)
    if not args.force and _artifact_is_fresh(output_path, refresh_after_hours):
        print("status=skipped reason=artifact_fresh")
        return 0

    x_api_cfg = config.get("x_api") if isinstance(config.get("x_api"), dict) else {}
    env_path = Path(str(x_api_cfg.get("env_file") or "workspace/state_runtime/twitter_api.env"))
    if not env_path.is_absolute():
        env_path = (REPO_ROOT / env_path).resolve()
    if not env_path.exists():
        print(f"status=error error=missing_env_file:{env_path}", file=sys.stderr)
        return 1
    env = _load_env_file(env_path)
    bearer_token = str(env.get("X_BEARER_TOKEN") or "").strip()
    if not bearer_token:
        print("status=error error=missing_env:X_BEARER_TOKEN", file=sys.stderr)
        return 1

    if args.analysis_only:
        existing_payload = _read_json(output_path)
        query_rows = [row for row in list(existing_payload.get("queries") or []) if isinstance(row, dict)]
        sample_posts = [row for row in list(existing_payload.get("sample_posts") or []) if isinstance(row, dict)]
        if not query_rows or not sample_posts:
            print("status=error error=missing_saved_x_digest", file=sys.stderr)
            return 1
    else:
        query_defs = [row for row in list(config.get("queries") or []) if isinstance(row, dict)]
        timeout_seconds = float(x_api_cfg.get("timeout_seconds") or 20)
        results_per_query = int(x_api_cfg.get("results_per_query") or 10)
        base_url = str(x_api_cfg.get("base_url") or "https://api.x.com/2")

        query_payloads: list[dict[str, Any]] = []
        for query_row in query_defs:
            query = str(query_row.get("query") or "").strip()
            if not query:
                continue
            raw = _fetch_recent_search(
                bearer_token=bearer_token,
                base_url=base_url,
                query=query,
                max_results=results_per_query,
                timeout_seconds=timeout_seconds,
            )
            query_payloads.append(
                {
                    "id": str(query_row.get("id") or "query"),
                    "query": query,
                    "weight": float(query_row.get("weight") or 1.0),
                    "tweets": list(raw.get("data") or []),
                    "meta": raw.get("meta") if isinstance(raw.get("meta"), dict) else {},
                }
            )

        query_rows, sample_posts = _summarize_queries(query_payloads)
    analysis_status = "ok"
    analysis_model_resolved = ""
    try:
        note, analysis_model_resolved = _run_analysis(config, query_rows, sample_posts)
    except Exception:
        analysis_status = "degraded"
        note = _heuristic_note(query_rows, sample_posts)
        analysis_model_resolved = "heuristic_fallback"

    artifact = {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "producer": "c_lawd",
        "status": analysis_status,
        "source": "weekly_x_recent_search",
        "window_days": 7,
        "summary": str(note.get("summary") or "").strip(),
        "thesis": str(note.get("thesis") or "").strip(),
        "focus": str(note.get("focus") or "").strip(),
        "actions": [str(item) for item in list(note.get("actions") or []) if str(item).strip()][:5],
        "risk_flags": [str(item) for item in list(note.get("risk_flags") or []) if str(item).strip()][:5],
        "confidence": max(0.0, min(1.0, float(note.get("confidence", 0.0) or 0.0))),
        "analysis_model_requested": str((config.get("analysis") or {}).get("model") or "local-assistant"),
        "analysis_model_resolved": analysis_model_resolved,
        "x_query_count": len(query_rows),
        "x_post_count": sum(int(row.get("tweet_count", 0) or 0) for row in query_rows),
        "queries": query_rows,
        "sample_posts": sample_posts,
    }
    _write_json_atomic(output_path, artifact)

    if args.print_json:
        print(json.dumps(artifact, indent=2, ensure_ascii=False))
    else:
        print(
            f"status={artifact['status']} "
            f"posts={artifact['x_post_count']} "
            f"model={artifact['analysis_model_resolved']} "
            f"output={output_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
