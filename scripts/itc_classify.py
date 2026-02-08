#!/usr/bin/env python3
"""
ITC Hybrid Classifier
Two-pass classification:
  1. Rule-based regex (fast, free) — catches obvious trade_signal, spam, and some news
  2. LLM pass — reclassifies anything tagged "noise"

LLM fallback chain (per-call, not per-run) is policy-driven:
  See workspace/policy/llm_policy.json

Budgeting is enforced per day and per run. All events logged to itc/classify_events.jsonl.

Tags: trade_signal, news, noise, spam

Usage:
  python scripts/itc_classify.py              # incremental (new messages only)
  python scripts/itc_classify.py --full       # reprocess all
  python scripts/itc_classify.py --rules-only # skip LLM pass
  python scripts/itc_classify.py --model qwen14b-tools-32k  # use specific Ollama model
"""

import json
import os
import re
import time
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

BASE_DIR = Path("C:/Users/heath/.openclaw")
CANON_IN = BASE_DIR / "itc" / "canon" / "messages.jsonl"
TAGGED_OUT = BASE_DIR / "itc" / "tagged" / "messages.jsonl"
EVENT_LOG = BASE_DIR / "itc" / "classify_events.jsonl"
POLICY_FILE = BASE_DIR / "workspace" / "policy" / "llm_policy.json"
BUDGET_FILE = BASE_DIR / "itc" / "llm_budget.json"

DEFAULT_POLICY = {
    "version": 1,
    "defaults": {
        "allowPaid": False,
        "preferLocal": True,
    },
    "budgets": {
        "itc_classify": {
            "dailyTokenBudget": 25000,
            "dailyCallBudget": 200,
            "maxCallsPerRun": 80,
        }
    },
    "providers": {
        "groq": {"enabled": True, "paid": False},
        "qwen": {"enabled": True, "paid": False},
        "ollama": {"enabled": True, "paid": False},
    },
    "routing": {
        "itc_classify": {
            "order": ["groq", "qwen", "ollama"],
            "preferLocalForShort": True,
            "shortMessageChars": 240,
            "fallbackToRules": True,
        }
    },
}

# ── LLM Backend Config ──────────────────────────────────────────

# Groq (primary — remote, free tier 30K TPM, Llama 4 Scout MoE, OpenAI-compatible)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_TIMEOUT = 15

# Qwen Portal (secondary — remote, OpenAI-compatible, OAuth managed by OpenClaw)
QWEN_PORTAL_URL = "https://portal.qwen.ai/v1/chat/completions"
QWEN_PORTAL_MODEL = "coder-model"
QWEN_PORTAL_TIMEOUT = 15
QWEN_AUTH_FILE = BASE_DIR / "agents" / "main" / "agent" / "auth-profiles.json"

# Ollama (last resort LLM — local, unlimited, smaller model)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen:latest"
OLLAMA_TIMEOUT = 10

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


# ── Policy & Budget ─────────────────────────────────────────────
def _deep_merge(defaults, incoming):
    if not isinstance(defaults, dict) or not isinstance(incoming, dict):
        return incoming if incoming is not None else defaults
    merged = {}
    for key, value in defaults.items():
        if key in incoming:
            merged[key] = _deep_merge(value, incoming[key])
        else:
            merged[key] = value
    for key, value in incoming.items():
        if key not in merged:
            merged[key] = value
    return merged


def load_policy():
    policy = DEFAULT_POLICY
    if POLICY_FILE.exists():
        try:
            raw = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
            policy = _deep_merge(DEFAULT_POLICY, raw)
        except Exception:
            log_event("policy_load_fail", {"path": str(POLICY_FILE)})
    return policy


def _today_key():
    return time.strftime("%Y-%m-%d", time.localtime())


def load_budget_state():
    if BUDGET_FILE.exists():
        try:
            data = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            if data.get("date") == _today_key():
                return data
        except Exception:
            log_event("budget_load_fail", {"path": str(BUDGET_FILE)})
    return {
        "version": 1,
        "date": _today_key(),
        "itc_classify": {"calls": 0, "tokens": 0},
    }


def save_budget_state(state):
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def estimate_tokens(text):
    # Rough heuristic: 4 chars per token + prompt overhead
    return max(1, (len(text) + 200) // 4)


def provider_enabled(policy, name):
    provider = policy.get("providers", {}).get(name, {})
    if not provider.get("enabled", True):
        return False
    if provider.get("paid") and not policy.get("defaults", {}).get("allowPaid", False):
        return False
    return True


def provider_max_chars(policy, name, default=500):
    models = policy.get("providers", {}).get(name, {}).get("models", [])
    if models:
        return int(models[0].get("maxInputChars", default))
    return default


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


# ── Shared ──────────────────────────────────────────────────────
def _build_prompt(text, max_chars=500):
    """Build the classification prompt (shared across backends)."""
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


def _read_secrets_key(key_name):
    """Read a key from secrets.env."""
    key = os.environ.get(key_name)
    if key:
        return key
    secrets_file = BASE_DIR / "secrets.env"
    if secrets_file.exists():
        try:
            with open(secrets_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    if k.strip() == key_name and v.strip():
                        return v.strip()
        except Exception:
            pass
    return None


# ── Backend: Groq ───────────────────────────────────────────────
def classify_groq(text, max_chars=500):
    """LLM classification via Groq API (Llama 4 Scout). Returns (tag, 'groq') or (None, error_str)."""
    if requests is None:
        return None, "no_requests_lib"

    api_key = _read_secrets_key("GROQ_API_KEY")
    if not api_key:
        return None, "groq_no_key"

    prompt = _build_prompt(text, max_chars=max_chars)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 10,
    }

    try:
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=GROQ_TIMEOUT)
        if resp.status_code == 429:
            return None, "groq_rate_limited"
        if resp.status_code != 200:
            return None, f"groq_http_{resp.status_code}"
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        tag = _extract_tag(answer)
        if tag:
            return tag, "groq"
        return None, "groq_parse_fail"
    except requests.exceptions.Timeout:
        return None, "groq_timeout"
    except requests.exceptions.ConnectionError:
        return None, "groq_conn_error"
    except Exception as e:
        return None, f"groq_{type(e).__name__}"


# ── Backend: Qwen Portal ───────────────────────────────────────
def _get_qwen_portal_token():
    """Get Qwen Portal OAuth access token from auth-profiles.json."""
    if not QWEN_AUTH_FILE.exists():
        return None
    try:
        with open(QWEN_AUTH_FILE, "r", encoding="utf-8") as f:
            auth = json.load(f)
        profile = auth.get("profiles", {}).get("qwen-portal:default", {})
        token = profile.get("access")
        expires = profile.get("expires", 0)
        # Check if token is expired (with 5 min buffer)
        now_ms = int(time.time() * 1000)
        if token and expires > now_ms + 300_000:
            # Check cooldown
            stats = auth.get("usageStats", {}).get("qwen-portal:default", {})
            cooldown = stats.get("cooldownUntil", 0)
            if now_ms < cooldown:
                return None  # still in cooldown from rate limiting
            return token
    except Exception:
        pass
    return None


def classify_qwen_portal(text, max_chars=500):
    """LLM classification via Qwen Portal API. Returns (tag, 'qwen') or (None, error_str)."""
    if requests is None:
        return None, "no_requests_lib"

    token = _get_qwen_portal_token()
    if not token:
        return None, "qwen_no_token"

    prompt = _build_prompt(text, max_chars=max_chars)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": QWEN_PORTAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 10,
    }

    try:
        resp = requests.post(QWEN_PORTAL_URL, json=payload, headers=headers,
                             timeout=QWEN_PORTAL_TIMEOUT)
        if resp.status_code == 429:
            return None, "qwen_rate_limited"
        if resp.status_code == 401:
            return None, "qwen_auth_expired"
        if resp.status_code != 200:
            return None, f"qwen_http_{resp.status_code}"
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        tag = _extract_tag(answer)
        if tag:
            return tag, "qwen"
        return None, "qwen_parse_fail"
    except requests.exceptions.Timeout:
        return None, "qwen_timeout"
    except requests.exceptions.ConnectionError:
        return None, "qwen_conn_error"
    except Exception as e:
        return None, f"qwen_{type(e).__name__}"


# ── Backend: Ollama ─────────────────────────────────────────────
def classify_ollama(text, model=None, max_chars=500):
    """LLM classification via local Ollama. Returns (tag, 'ollama') or (None, error_str)."""
    if requests is None:
        return None, "no_requests_lib"

    model = model or OLLAMA_MODEL
    prompt = _build_prompt(text, max_chars=max_chars)

    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 10},
        }, timeout=OLLAMA_TIMEOUT)

        if resp.status_code != 200:
            return None, f"ollama_http_{resp.status_code}"
        answer = resp.json().get("response", "")
        tag = _extract_tag(answer)
        if tag:
            return tag, "ollama"
        return None, "ollama_parse_fail"
    except requests.exceptions.Timeout:
        return None, "ollama_timeout"
    except requests.exceptions.ConnectionError:
        return None, "ollama_conn_error"
    except Exception as e:
        return None, f"ollama_{type(e).__name__}"


# ── Fallback Chain ──────────────────────────────────────────────
def classify_llm(text, model=None, chain=None, available=None, limits=None):
    """Try LLM classification with a policy-defined fallback chain."""
    chain = chain or ["groq", "qwen", "ollama"]
    available = available or {}
    limits = limits or {}
    last_result = None

    for backend in chain:
        if not available.get(backend, False):
            continue
        if backend == "groq":
            tag, result = classify_groq(text, max_chars=limits.get("groq", 500))
        elif backend == "qwen":
            tag, result = classify_qwen_portal(text, max_chars=limits.get("qwen", 500))
        elif backend == "ollama":
            tag, result = classify_ollama(text, model=model, max_chars=limits.get("ollama", 500))
        else:
            continue

        if tag:
            if backend == "ollama":
                log_event("ollama_fallback_used")
            return tag, backend
        log_event(f"{backend}_fail", result)
        last_result = result

    log_event("all_llm_fail", last_result)
    return None, None


# ── Backend availability checks ─────────────────────────────────
def check_groq():
    """Quick check if Groq API key is available."""
    return _read_secrets_key("GROQ_API_KEY") is not None


def check_qwen_portal():
    """Quick check if Qwen Portal token is available and not expired/cooled down."""
    return _get_qwen_portal_token() is not None


def check_ollama():
    """Quick check if Ollama is reachable."""
    if requests is None:
        return False
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def list_ollama_models():
    """List available Ollama models."""
    if requests is None:
        return []
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


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

    policy = load_policy()
    budget_state = load_budget_state()
    budget_cfg = policy.get("budgets", {}).get("itc_classify", {})
    daily_token_budget = int(budget_cfg.get("dailyTokenBudget", 0))
    daily_call_budget = int(budget_cfg.get("dailyCallBudget", 0))
    max_calls_per_run = int(budget_cfg.get("maxCallsPerRun", max_llm))
    budget_state.setdefault("itc_classify", {"calls": 0, "tokens": 0})
    calls_used = int(budget_state["itc_classify"].get("calls", 0))
    tokens_used = int(budget_state["itc_classify"].get("tokens", 0))
    remaining_calls = max(0, daily_call_budget - calls_used)
    remaining_tokens = max(0, daily_token_budget - tokens_used)

    if max_calls_per_run > 0:
        max_llm = min(max_llm, max_calls_per_run)
    if remaining_calls > 0:
        max_llm = min(max_llm, remaining_calls)
    else:
        max_llm = 0

    # Check backend availability
    use_llm = False
    active_model = model or OLLAMA_MODEL
    groq_ok = False
    qwen_ok = False
    ollama_ok = False
    ollama_models = []
    policy_ollama = policy.get("providers", {}).get("ollama", {}).get("models", [])
    ollama_limits_by_model = {
        m.get("id"): int(m.get("maxInputChars", 500))
        for m in policy_ollama
        if m.get("id")
    }
    local_short_model = next((m.get("id") for m in policy_ollama if m.get("tier") == "small"), OLLAMA_MODEL)
    local_long_model = next((m.get("id") for m in policy_ollama if m.get("tier") == "large"), OLLAMA_MODEL)
    routing = policy.get("routing", {}).get("itc_classify", {})
    routing_order = routing.get("order", ["groq", "qwen", "ollama"])
    prefer_local_short = bool(routing.get("preferLocalForShort", False))
    short_chars = int(routing.get("shortMessageChars", 240))
    limits = {
        "groq": provider_max_chars(policy, "groq", 500),
        "qwen": provider_max_chars(policy, "qwen", 500),
        "ollama": provider_max_chars(policy, "ollama", 500),
    }

    if not rules_only:
        groq_ok = check_groq() and provider_enabled(policy, "groq")
        qwen_ok = check_qwen_portal() and provider_enabled(policy, "qwen")
        ollama_ok = check_ollama() and provider_enabled(policy, "ollama")

        if (groq_ok or qwen_ok or ollama_ok) and max_llm > 0 and remaining_tokens > 0:
            use_llm = True
        if ollama_ok:
            ollama_models = list_ollama_models()
            if model and model not in ollama_models:
                print(f"  WARNING: requested model '{model}' not found, using {OLLAMA_MODEL}")
                active_model = OLLAMA_MODEL
            if not model:
                if local_short_model not in ollama_models:
                    local_short_model = OLLAMA_MODEL
                if local_long_model not in ollama_models:
                    local_long_model = OLLAMA_MODEL

        # Status display
        groq_s = f"UP ({GROQ_MODEL})" if groq_ok else "NO_KEY"
        qwen_s = "UP" if qwen_ok else "DOWN/COOLDOWN"
        ollama_s = f"UP ({active_model})" if ollama_ok else "DOWN"
        print(f"LLM backends: Groq={groq_s} | Qwen={qwen_s} | Ollama={ollama_s}")

        # Build chain description
        chain = []
        for backend in routing_order:
            if backend == "groq" and groq_ok:
                chain.append("Groq (remote)")
            if backend == "qwen" and qwen_ok:
                chain.append("Qwen Portal")
            if backend == "ollama" and ollama_ok:
                chain.append("Ollama (local)")
        if groq_ok or qwen_ok or ollama_ok:
            chain.append("rules")
        if not chain:
            chain.append("rules")
        print(f"  Chain: {' -> '.join(chain)}")
        print(f"  Max LLM calls: {max_llm}")
        print(f"  Budget remaining: calls={remaining_calls} tokens={remaining_tokens}")

        log_event("classify_start", {
            "policy_version": policy.get("version", 1),
            "groq": "up" if groq_ok else "no_key",
            "qwen": "up" if qwen_ok else "down",
            "ollama": "up" if ollama_ok else "down",
            "model": active_model,
            "max_llm": max_llm,
            "full": full,
            "budget_calls_remaining": remaining_calls,
            "budget_tokens_remaining": remaining_tokens,
            "routing_order": routing_order,
            "prefer_local_short": prefer_local_short,
            "short_chars": short_chars,
            "local_short_model": local_short_model,
            "local_long_model": local_long_model,
        })

        if remaining_calls <= 0 or remaining_tokens <= 0:
            log_event("budget_exhausted", {
                "calls_used": calls_used,
                "tokens_used": tokens_used,
                "daily_call_budget": daily_call_budget,
                "daily_token_budget": daily_token_budget,
            })

    wrote = 0
    mode = "w" if full else "a"
    counts = {"trade_signal": 0, "news": 0, "noise": 0, "spam": 0}
    llm_reclassified = 0
    llm_calls = 0
    backend_counts = {"groq": 0, "qwen": 0, "ollama": 0, "rules": 0}

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
                est_tokens = estimate_tokens(text)
                if tokens_used + est_tokens > daily_token_budget:
                    log_event("budget_exhausted", {
                        "reason": "token",
                        "calls_used": calls_used,
                        "tokens_used": tokens_used,
                        "daily_token_budget": daily_token_budget,
                    })
                else:
                    chain = list(routing_order)
                    available = {"groq": groq_ok, "qwen": qwen_ok, "ollama": ollama_ok}
                    if prefer_local_short and len(text) <= short_chars and ollama_ok:
                        chain = ["ollama"] + [b for b in chain if b != "ollama"]
                    selected_model = active_model
                    if not model:
                        if prefer_local_short and len(text) <= short_chars:
                            selected_model = local_short_model
                        else:
                            selected_model = local_long_model
                    per_call_limits = dict(limits)
                    per_call_limits["ollama"] = ollama_limits_by_model.get(
                        selected_model,
                        per_call_limits.get("ollama", 500),
                    )
                    llm_tag, llm_backend = classify_llm(
                        text,
                        model=selected_model,
                        chain=chain,
                        available=available,
                        limits=per_call_limits,
                    )
                    llm_calls += 1
                    calls_used += 1
                    tokens_used += est_tokens
                    budget_state["itc_classify"]["calls"] = calls_used
                    budget_state["itc_classify"]["tokens"] = tokens_used
                    save_budget_state(budget_state)
                    if llm_tag and llm_tag != "noise":
                        primary = llm_tag
                        all_tags = list(set(all_tags + [llm_tag]))
                        llm_reclassified += 1
                    if llm_backend:
                        backend = llm_backend

            msg["primary_tag"] = primary
            msg["tags"] = all_tags
            msg["classified_at"] = int(time.time() * 1000)
            msg["classifier"] = f"itc_classify.py/hybrid-v3/{backend}"

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
        "budget_calls_used": calls_used,
        "budget_tokens_used": tokens_used,
    })

    return wrote


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ITC hybrid classifier (rules + LLM fallback chain)")
    parser.add_argument("--full", action="store_true", help="Reprocess all canonical messages")
    parser.add_argument("--rules-only", action="store_true", help="Skip LLM pass")
    parser.add_argument("--max-llm", type=int, default=100, help="Max LLM calls per run")
    parser.add_argument("--model", type=str, default=None,
                        help="Ollama model to use (default: qwen:latest). Try qwen14b-tools-32k for better quality.")
    args = parser.parse_args()
    run(full=args.full, rules_only=args.rules_only, max_llm=args.max_llm, model=args.model)
