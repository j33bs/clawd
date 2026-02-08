#!/usr/bin/env python3
"""
ITC Hybrid Classifier
Two-pass classification:
  1. Rule-based regex (fast, free) — catches obvious trade_signal, spam, and some news
  2. LLM pass — reclassifies anything tagged "noise"

LLM routing is centralized via the policy router:
  workspace/scripts/policy_router.py

Tags: trade_signal, news, noise, spam

Usage:
  python scripts/itc_classify.py              # incremental (new messages only)
  python scripts/itc_classify.py --full       # reprocess all
  python scripts/itc_classify.py --rules-only # skip LLM pass
  python scripts/itc_classify.py --model qwen14b-tools-32k  # override Ollama model
"""

import argparse
import json
import os
import re
import sys
import time
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
CANON_IN = BASE_DIR / "itc" / "canon" / "messages.jsonl"
TAGGED_OUT = BASE_DIR / "itc" / "tagged" / "messages.jsonl"
EVENT_LOG = BASE_DIR / "itc" / "classify_events.jsonl"

POLICY_ROUTER_DIR = BASE_DIR / "workspace" / "scripts"
if str(POLICY_ROUTER_DIR) not in sys.path:
    sys.path.insert(0, str(POLICY_ROUTER_DIR))

try:
    from policy_router import PolicyRouter, build_chat_payload
except Exception:
    PolicyRouter = None
    build_chat_payload = None

VALID_TAGS = {"trade_signal", "news", "noise", "spam"}

# ── Rule definitions ────────────────────────────────────────────
TRADE_SIGNAL_PATTERNS = [
    re.compile(r'\b(buy|sell|long|short)\b.*\b(entry|target|stop\s?loss|tp|sl)\b', re.I),
    re.compile(r'\b(entry|target|sl|tp)\s*[:=]\s*\$?[\d,.]+', re.I),
    re.compile(r'\b(leverage|margin)\s*[:=]?\s*\d+x\b', re.I),
    re.compile(r'\b(call|put)\s+\$?\w+\s+\d', re.I),
    re.compile(r'(?:.*entry.*target|.*target.*entry)', re.I),
]

NEWS_PATTERNS = [
    re.compile(r'\b(breaking|just in|report|announce|launch|partner|list|delist|hack|exploit|sec |regulation)\b', re.I),
    re.compile(r'\b(according to|sources say|confirmed|official)\b', re.I),
    re.compile(r'\b(SEC|ETF|FOMC|CPI|Fed|treasury|congress)\b'),
    re.compile(r'\b(acquisition|merger|bankrupt|lawsuit|indictment)\b', re.I),
]

SPAM_PATTERNS = [
    re.compile(r'\b(airdrop|free|giveaway|claim now|guaranteed|100x|1000x)\b', re.I),
    re.compile(r'\b(dm me|join now|limited spots|whatsapp|t\.me/\S+bot)\b', re.I),
    re.compile(r'(.)\1{5,}', re.I),
]


# ── Event Logging ───────────────────────────────────────────────
def log_event(event_type, detail=None):
    """Append an event to classify_events.jsonl for observability."""
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": int(time.time() * 1000),
        "event": event_type,
    }
    if detail:
        entry["detail"] = detail
    try:
        with open(EVENT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging should never crash the classifier


# ── Classification Functions ────────────────────────────────────
def classify_rules(text):
    """Rule-based first pass. Returns (primary_tag, all_tags)."""
    tags = []

    for pat in TRADE_SIGNAL_PATTERNS:
        if pat.search(text):
            tags.append("trade_signal")
            break

    for pat in SPAM_PATTERNS:
        if pat.search(text):
            tags.append("spam")
            break

    for pat in NEWS_PATTERNS:
        if pat.search(text):
            tags.append("news")
            break

    if not tags:
        tags.append("noise")

    return tags[0], list(set(tags))


def _build_prompt(text, max_chars=500):
    """Build the classification prompt."""
    text_trunc = text[:max_chars] if len(text) > max_chars else text
    return (
        "Classify this crypto Telegram message into exactly ONE category:\n"
        "- trade_signal: contains specific trade setup (entry price, targets, stop loss, leverage, buy/sell calls with numbers)\n"
        "- news: reports events, announcements, partnerships, regulatory actions, market milestones\n"
        "- noise: casual chat, memes, opinions without actionable content, reactions\n"
        "- spam: promotions, airdrops, scams, referral links, bot spam\n"
        f'\nMessage: "{text_trunc}"\n\n'
        "Reply with ONLY the category name (trade_signal, news, noise, or spam). Nothing else."
    )


def _extract_tag(answer):
    """Extract a valid tag from LLM response text."""
    answer = answer.strip().lower()
    for tag in VALID_TAGS:
        if tag in answer:
            return tag
    return None


def classify_llm(router, text, model_override=None):
    """LLM classification via policy router. Returns (tag, provider_or_reason)."""
    if router is None or build_chat_payload is None:
        return None, "router_unavailable"
    prompt = _build_prompt(text)
    payload = build_chat_payload(prompt, temperature=0.0, max_tokens=10)
    context = {"input_text": text}
    if model_override:
        context["override_model"] = model_override
    result = router.execute_with_escalation(
        "itc_classify",
        payload,
        context_metadata=context,
        validate_fn=_extract_tag,
    )
    if result.get("ok"):
        tag = result.get("parsed") or _extract_tag(result.get("text", ""))
        return tag, result.get("provider")
    return None, result.get("reason_code")


def load_seen_hashes():
    """Load hashes already in tagged output."""
    seen = set()
    if TAGGED_OUT.exists():
        with open(TAGGED_OUT, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line).get("hash", ""))
                except json.JSONDecodeError:
                    continue
    return seen


# ── Main ────────────────────────────────────────────────────────
def run(full=False, rules_only=False, max_llm=100, model=None):
    if not CANON_IN.exists():
        print(f"No canonical input at {CANON_IN}")
        print("Run: python scripts/itc_normalize.py first")
        return 0

    seen = set() if full else load_seen_hashes()
    TAGGED_OUT.parent.mkdir(parents=True, exist_ok=True)

    router = None
    status = {"order": [], "available": [], "reasons": {}}
    if not rules_only and PolicyRouter is not None:
        router = PolicyRouter()
        status = router.intent_status("itc_classify")

    use_llm = bool(router and status["available"])
    max_calls_cfg = 0
    if router:
        max_calls_cfg = int(
            router.policy.get("budgets", {})
            .get("intents", {})
            .get("itc_classify", {})
            .get("maxCallsPerRun", 0)
        )

    if max_calls_cfg > 0:
        max_llm = min(max_llm, max_calls_cfg)
    if rules_only or not use_llm:
        max_llm = 0

    if router:
        print(f"LLM routing order: {', '.join(status['order']) or 'none'}")
        if status["available"]:
            print(f"LLM available: {', '.join(status['available'])}")
        else:
            print("LLM available: none")
        if status["reasons"]:
            reasons = ", ".join(f"{k}={v}" for k, v in status["reasons"].items())
            print(f"LLM unavailable reasons: {reasons}")
        print(f"Max LLM calls: {max_llm}")
    else:
        print("LLM routing: disabled (router unavailable or rules-only)")

    log_event("classify_start", {
        "router_ready": bool(router),
        "full": full,
        "rules_only": rules_only,
        "max_llm": max_llm,
        "routing_order": status.get("order", []),
        "routing_available": status.get("available", []),
        "routing_reasons": status.get("reasons", {}),
        "model_override": model,
    })

    wrote = 0
    mode = "w" if full else "a"
    counts = {"trade_signal": 0, "news": 0, "noise": 0, "spam": 0}
    llm_reclassified = 0
    llm_calls = 0
    backend_counts = {"rules": 0}

    with open(CANON_IN, "r", encoding="utf-8") as fin, \
         open(TAGGED_OUT, mode, encoding="utf-8") as fout:
        for line in fin:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            h = msg.get("hash", "")
            if h in seen:
                continue

            text = msg.get("text", "")
            primary, all_tags = classify_rules(text)

            # LLM second pass: reclassify noise-tagged messages (capped)
            backend = "rules"
            if use_llm and primary == "noise" and len(text) > 10 and llm_calls < max_llm:
                llm_tag, llm_backend = classify_llm(router, text, model_override=model)
                llm_calls += 1
                if llm_tag and llm_tag != "noise":
                    primary = llm_tag
                    all_tags = list(set(all_tags + [llm_tag]))
                    llm_reclassified += 1
                if llm_backend:
                    backend = llm_backend
                if not llm_tag:
                    log_event("llm_router_fail", {"reason_code": llm_backend})

            msg["primary_tag"] = primary
            msg["tags"] = all_tags
            msg["classified_at"] = int(time.time() * 1000)
            msg["classifier"] = f"itc_classify.py/hybrid-v4/{backend}"

            fout.write(json.dumps(msg, ensure_ascii=False) + "\n")
            seen.add(h)
            counts[primary] = counts.get(primary, 0) + 1
            backend_counts[backend] = backend_counts.get(backend, 0) + 1
            wrote += 1

    # Summary
    print(f"Classified: {wrote} messages")
    for tag, n in sorted(counts.items(), key=lambda x: -x[1]):
        if n > 0:
            print(f"  {tag}: {n}")
    if llm_calls > 0:
        print(f"  LLM: {llm_calls} calls, {llm_reclassified} reclassified")
        active = {k: v for k, v in backend_counts.items() if v > 0}
        print(f"  Backends used: {', '.join(f'{k}={v}' for k, v in active.items())}")

    log_event("classify_done", {
        "wrote": wrote,
        "counts": counts,
        "llm_calls": llm_calls,
        "llm_reclassified": llm_reclassified,
        "backends": backend_counts,
    })

    return wrote


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ITC hybrid classifier (rules + LLM fallback chain)")
    parser.add_argument("--full", action="store_true", help="Reprocess all canonical messages")
    parser.add_argument("--rules-only", action="store_true", help="Skip LLM pass")
    parser.add_argument("--max-llm", type=int, default=100, help="Max LLM calls per run")
    parser.add_argument("--model", type=str, default=None,
                        help="Ollama model override (default from policy).")
    args = parser.parse_args()
    run(full=args.full, rules_only=args.rules_only, max_llm=args.max_llm, model=args.model)
