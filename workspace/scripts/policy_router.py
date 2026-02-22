#!/usr/bin/env python3
"""
Policy Router
- Centralized routing, budgeting, and circuit-breaking for all LLM calls.
"""

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

try:
    from proprioception import ProprioceptiveSampler
except Exception:  # pragma: no cover - optional integration
    ProprioceptiveSampler = None

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
BUDGET_FILE = BASE_DIR / "itc" / "llm_budget.json"
CIRCUIT_FILE = BASE_DIR / "itc" / "llm_circuit.json"
EVENT_LOG = BASE_DIR / "itc" / "llm_router_events.jsonl"
QWEN_AUTH_FILE = BASE_DIR / "agents" / "main" / "agent" / "auth-profiles.json"
TACTI_EVENT_LOG = BASE_DIR / "workspace" / "state" / "tacti_cr" / "events.jsonl"
ACTIVE_INFERENCE_STATE_PATH = BASE_DIR / "workspace" / "state" / "active_inference_state.json"
WITNESS_LEDGER_PATH = BASE_DIR / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"

TACTI_ROOT = BASE_DIR / "workspace"
if str(TACTI_ROOT) not in sys.path:
    sys.path.insert(0, str(TACTI_ROOT))

try:
    from tacti_cr.arousal_oscillator import ArousalOscillator
    from tacti_cr.config import is_enabled as tacti_enabled
    from tacti_cr.expression import compute_expression
    from tacti_cr.collapse import emit_recommendation as collapse_emit_recommendation
    from tacti_cr.valence import routing_bias as tacti_routing_bias
    from tacti_cr.events import emit as tacti_emit
except Exception:  # pragma: no cover - optional integration
    ArousalOscillator = None
    tacti_enabled = None
    compute_expression = None
    collapse_emit_recommendation = None
    tacti_routing_bias = None
    tacti_emit = None

DEFAULT_POLICY = {
    "version": 2,
    "defaults": {
        "allowPaid": False,
        "preferLocal": True,
        "maxTokensPerRequest": 1024,
        "circuitBreaker": {
            "failureThreshold": 3,
            "cooldownSec": 900,
            "windowSec": 600,
            "failOn": [
                "request_http_429",
                "request_http_5xx",
                "request_timeout",
                "request_conn_error",
            ],
        },
    },
    "budgets": {
        "intents": {
            "itc_classify": {
                "dailyTokenBudget": 25000,
                "dailyCallBudget": 200,
                "maxCallsPerRun": 80,
            },
            "coding": {
                "dailyTokenBudget": 50000,
                "dailyCallBudget": 200,
                "maxCallsPerRun": 50,
            },
        },
        "tiers": {
            "free": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000},
            "auth": {"dailyTokenBudget": 50000, "dailyCallBudget": 200},
            "paid": {"dailyTokenBudget": 50000, "dailyCallBudget": 200},
        },
    },
    "providers": {
        "ollama": {
            "enabled": True,
            "paid": False,
            "tier": "free",
            "type": "ollama",
            "baseUrl": "http://localhost:11434",
            "models": [
                {"id": "qwen:latest", "maxInputChars": 800, "tier": "small"},
                {"id": "qwen14b-tools-32k", "maxInputChars": 4000, "tier": "large"},
            ],
        },
        "groq": {
            "enabled": True,
            "paid": False,
            "tier": "free",
            "type": "openai_compatible",
            "baseUrl": "https://api.groq.com/openai/v1",
            "apiKeyEnv": "GROQ_API_KEY",
            "models": [
                {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "maxInputChars": 4000}
            ],
        },
        "qwen": {
            "enabled": True,
            "paid": False,
            "tier": "free",
            "type": "openai_compatible",
            "baseUrl": "https://portal.qwen.ai/v1",
            "auth": "qwen_oauth",
            "models": [
                {"id": "coder-model", "maxInputChars": 4000}
            ],
        },
        "openai_auth": {
            "enabled": True,
            "paid": False,
            "tier": "auth",
            "type": "openai_auth",
            "readyEnv": "OPENAI_AUTH_READY",
        },
        "claude_auth": {
            "enabled": True,
            "paid": False,
            "tier": "auth",
            "type": "anthropic_auth",
            "readyEnv": "CLAUDE_AUTH_READY",
        },
        "grok_api": {
            "enabled": True,
            "paid": True,
            "tier": "paid",
            "type": "openai_compatible",
            "baseUrl": "https://api.x.ai/v1",
            "apiKeyEnv": "GROK_API_KEY",
            "models": [
                {"id": "grok-2", "maxInputChars": 6000}
            ],
        },
        "openai_api": {
            "enabled": True,
            "paid": True,
            "tier": "paid",
            "type": "openai_compatible",
            "baseUrl": "https://api.openai.com/v1",
            "apiKeyEnv": "OPENAI_API_KEY",
            "models": [
                {"id": "gpt-4o-mini", "maxInputChars": 6000}
            ],
        },
        "claude_api": {
            "enabled": True,
            "paid": True,
            "tier": "paid",
            "type": "anthropic",
            "baseUrl": "https://api.anthropic.com/v1",
            "apiKeyEnv": "ANTHROPIC_API_KEY",
            "models": [
                {"id": "claude-3-5-sonnet", "maxInputChars": 6000}
            ],
        },
    },
    "routing": {
        "free_order": ["ollama", "groq", "qwen"],
        "intents": {
            "itc_classify": {
                "order": ["free"],
                "fallback": "rules",
                "preferLocalForShort": True,
                "shortMessageChars": 240,
            },
            "coding": {
                "order": [
                    "free",
                    "openai_auth",
                    "claude_auth",
                    "grok_api",
                    "openai_api",
                    "claude_api",
                ],
                "allowPaid": True,
            },
            "governance": {
                "order": ["claude_auth", "claude_api"],
                "allowPaid": True,
            },
            "security": {
                "order": ["claude_auth", "claude_api"],
                "allowPaid": True,
            },
        },
        "capability_router": {
            "enabled": True,
            "subagentProvider": "local_vllm_assistant",
            "mechanicalProvider": "local_vllm_assistant",
            "planningProvider": "claude_auth",
            "reasoningProvider": "claude_auth",
            "codeProvider": "local_vllm_assistant",
            "smallCodeProvider": "local_vllm_assistant",
            "explicitTriggers": {},
        },
    },
}

# Alias normalization to reconcile invariant/policy strings with registry IDs.
PROVIDER_ID_ALIASES = {
    "google-gemini-cli": "google-gemini-cli",
    "qwen-portal": "qwen_alibaba",
    "minimax-portal": "minimax-portal",
    "gemini": "gemini",
    "qwen_alibaba": "qwen_alibaba",
    "groq": "groq",
    "ollama": "ollama",
}

# Back-compat bridge from normalized registry IDs to policy provider keys.
PROVIDER_ID_TO_POLICY_PROVIDER = {
    "qwen_alibaba": "qwen",
}


class PolicyValidationError(Exception):
    pass


def normalize_provider_id(value):
    if not isinstance(value, str):
        return value
    key = value.strip()
    if not key:
        return key
    return PROVIDER_ID_ALIASES.get(key, key)


def denormalize_provider_ids(value):
    out = []
    for raw, norm in PROVIDER_ID_ALIASES.items():
        if norm == value:
            out.append(raw)
    return out


def canonical_intent(intent):
    raw = str(intent or "")
    if raw.startswith("teamchat:"):
        return "coding"
    return raw


def _normalize_provider_order(items):
    if not isinstance(items, list):
        return []
    return [normalize_provider_id(item) for item in items if isinstance(item, str)]


def _normalize_policy_routing(policy):
    routing = policy.get("routing", {})
    if not isinstance(routing, dict):
        return
    routing["free_order"] = _normalize_provider_order(routing.get("free_order", []))
    intents = routing.get("intents", {})
    if isinstance(intents, dict):
        for cfg in intents.values():
            if isinstance(cfg, dict):
                cfg["order"] = _normalize_provider_order(cfg.get("order", []))
    rules = routing.get("rules", [])
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict) and isinstance(rule.get("provider"), str):
                rule["provider"] = normalize_provider_id(rule.get("provider"))


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


def _policy_strict_enabled():
    value = str(os.environ.get("OPENCLAW_POLICY_STRICT", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


_SECRET_VALUE_PATTERNS = [
    re.compile(r"(authorization\s*:\s*bearer\s+)[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+\-/=]{8,}\b"),
    re.compile(r"\b(sk|gsk|xoxb|xoxp)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"((?:api[_-]?key|token|secret|password)\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
]


def _redact_text(value):
    text = str(value or "")
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.pattern.startswith("((?:api"):
            text = pattern.sub(r"\1<redacted>", text)
        elif "authorization" in pattern.pattern.lower():
            text = pattern.sub(r"\1<redacted>", text)
        else:
            text = pattern.sub("<redacted-token>", text)
    text = re.sub(r"(cookie\s*:\s*)([^\r\n]+)", r"\1<redacted>", text, flags=re.IGNORECASE)
    text = re.sub(r"(set-cookie\s*:\s*)([^\r\n]+)", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text


def _redact_detail(value):
    if isinstance(value, str):
        return _redact_text(value)
    if value is None:
        return None
    if isinstance(value, list):
        return [_redact_detail(item) for item in value]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if re.search(r"authorization|cookie|token|secret|password|api[_-]?key", str(key), re.IGNORECASE):
                out[str(key)] = "<redacted>"
            else:
                out[str(key)] = _redact_detail(item)
        return out
    return value


def _new_request_id(prefix="req"):
    pfx = re.sub(r"[^a-z0-9_-]", "", str(prefix or "req").lower()) or "req"
    return f"{pfx}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:8]}"


def _outcome_class_from_reason(reason_code):
    code = str(reason_code or "").lower()
    if code in {"success", "ok"}:
        return "success"
    if "timeout" in code:
        return "timeout"
    if "429" in code or "rate" in code:
        return "rate_limit"
    if "auth" in code or "missing_api_key" in code:
        return "auth_error"
    if "circuit" in code:
        return "circuit_open"
    return "failure"


def _budget_intent_key(intent):
    if isinstance(intent, str) and intent.startswith("teamchat:"):
        return "coding"
    return intent


def _validate_policy_schema(raw):
    errors = []
    budget_intent_keys = {"dailyTokenBudget", "dailyCallBudget", "maxCallsPerRun"}
    provider_keys = {
        "enabled",
        "paid",
        "tier",
        "type",
        "baseUrl",
        "apiKeyEnv",
        "models",
        "auth",
        "readyEnv",
        "provider_id",
        "capabilities",
        "model",
    }

    for intent, cfg in (raw.get("budgets", {}).get("intents", {}) or {}).items():
        if not isinstance(cfg, dict):
            continue
        unknown = sorted(set(cfg.keys()) - budget_intent_keys)
        if unknown:
            errors.append(f"budgets.intents.{intent} unknown keys: {', '.join(unknown)}")

    for provider, cfg in (raw.get("providers", {}) or {}).items():
        if not isinstance(cfg, dict):
            continue
        unknown = sorted(set(cfg.keys()) - provider_keys)
        if unknown:
            errors.append(f"providers.{provider} unknown keys: {', '.join(unknown)}")

    if errors:
        raise PolicyValidationError("; ".join(errors))


def load_policy(path=POLICY_FILE):
    policy = DEFAULT_POLICY
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if _policy_strict_enabled():
                _validate_policy_schema(raw)
            policy = _deep_merge(DEFAULT_POLICY, raw)
        except PolicyValidationError:
            raise
        except Exception:
            log_event("policy_load_fail", {"path": str(path)})
    _normalize_policy_routing(policy)
    return policy


def _today_key():
    return time.strftime("%Y-%m-%d", time.localtime())


def load_budget_state(path=BUDGET_FILE):
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("date") == _today_key():
                return data
        except Exception:
            log_event("budget_load_fail", {"path": str(path)})
    return {
        "version": 1,
        "date": _today_key(),
        "intents": {},
        "tiers": {},
    }


def save_budget_state(state, path=BUDGET_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def load_circuit_state(path=CIRCUIT_FILE):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            log_event("circuit_load_fail", {"path": str(path)})
    return {"version": 1, "providers": {}}


def save_circuit_state(state, path=CIRCUIT_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def log_event(event_type, detail=None, path=EVENT_LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": int(time.time() * 1000),
        "event": event_type,
    }
    if detail:
        entry["detail"] = _redact_detail(detail)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _tacti_event(event_type, detail):
    if callable(tacti_emit):
        try:
            tacti_emit(str(event_type), detail if isinstance(detail, dict) else {"detail": detail})
            return
        except Exception:
            pass
    log_event(event_type, detail=detail, path=TACTI_EVENT_LOG)


def _flag_enabled(name):
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def tacti_features_from_proprioception(snapshot):
    snap = dict(snapshot or {})
    arousal = 0.05
    if snap.get("error_rate", 0.0) and float(snap.get("error_rate", 0.0)) > 0.2:
        arousal = 0.2
    return {"arousal": float(arousal)}


def _legacy_tacti_flags_enabled():
    return any(
        _flag_enabled(name)
        for name in (
            "ENABLE_MURMURATION",
            "ENABLE_RESERVOIR",
            "ENABLE_PHYSARUM_ROUTER",
            "ENABLE_TRAIL_MEMORY",
        )
    )


def tacti_enhance_plan(plan, *, context_metadata=None, intent=None):
    plan_dict = dict(plan or {})
    plan_dict["enabled"] = bool(plan_dict.get("enabled", True))
    agent_ids = list(plan_dict.get("agent_ids") or [])
    if not agent_ids:
        maybe_agent = (context_metadata or {}).get("agent_id")
        if maybe_agent:
            agent_ids = [str(maybe_agent)]
    plan_dict["agent_ids"] = [str(a) for a in agent_ids if str(a).strip()]
    if intent and "intent" not in plan_dict:
        plan_dict["intent"] = intent
    return plan_dict


def _load_active_inference_state(path):
    state_path = Path(path)
    if state_path.exists():
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return {"version": 1, "runs": 0}


def _save_active_inference_state(state, path):
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _active_inference_payload(context_metadata):
    state = _load_active_inference_state(ACTIVE_INFERENCE_STATE_PATH)
    text = str((context_metadata or {}).get("input_text", "")).lower()
    concise_hint = "concise" in text or "brief" in text
    runs = int(state.get("runs", 0))
    confidence = min(0.95, 0.5 + (runs * 0.05))
    preference_params = {
        "style": "concise" if concise_hint else "balanced",
        "conciseness": 0.8 if concise_hint else 0.5,
    }
    state["runs"] = runs + 1
    state["lastPreference"] = preference_params
    _save_active_inference_state(state, ACTIVE_INFERENCE_STATE_PATH)
    return {
        "preference_params": preference_params,
        "confidence": round(confidence, 3),
    }


def read_env_or_secrets(key_name):
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


def get_qwen_token():
    if not QWEN_AUTH_FILE.exists():
        return None, "qwen_auth_missing"
    try:
        auth = json.loads(QWEN_AUTH_FILE.read_text(encoding="utf-8"))
        profile = auth.get("profiles", {}).get("qwen-portal:default", {})
        token = profile.get("access")
        expires = profile.get("expires", 0)
        now_ms = int(time.time() * 1000)
        if token and expires > now_ms + 300_000:
            stats = auth.get("usageStats", {}).get("qwen-portal:default", {})
            cooldown = stats.get("cooldownUntil", 0)
            if now_ms < cooldown:
                return None, "qwen_cooldown"
            return token, None
    except Exception:
        return None, "qwen_auth_error"
    return None, "qwen_no_token"


def estimate_tokens(text):
    return max(1, (len(text) + 200) // 4)


def _extract_text_from_payload(payload):
    if not payload:
        return ""
    if isinstance(payload, dict):
        if "prompt" in payload and isinstance(payload["prompt"], str):
            return payload["prompt"]
        if "messages" in payload and isinstance(payload["messages"], list):
            parts = []
            for msg in payload["messages"]:
                content = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(content, str):
                    parts.append(content)
            return "\n".join(parts)
    return ""


def _truncate_text(text, max_chars):
    if max_chars and len(text) > max_chars:
        return text[:max_chars]
    return text


def _coerce_positive_int(value, fallback):
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except Exception:
        pass
    return fallback


def _contains_phrase(text, phrase):
    if not text or not phrase:
        return False
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    pattern = rf"(?<!\w){escaped}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _is_subagent_context(context):
    if not isinstance(context, dict):
        return False
    if context.get("subagent") or context.get("is_subagent"):
        return True
    for key in ("agent_class", "node_role", "role"):
        value = str(context.get(key, "")).strip().lower()
        if value in {"subagent", "worker", "tool", "tool_agent", "child_agent"}:
            return True
    return False


def _count_bullets(text):
    if not text:
        return 0
    count = 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^[-*+]\s+", s) or re.match(r"^\d+\.\s+", s):
            count += 1
    return count


def _count_file_paths(text):
    if not text:
        return 0
    pattern = r"(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+|[A-Za-z0-9._-]+\.[A-Za-z0-9]{1,8}"
    return len(set(re.findall(pattern, text)))


_INTENT_ACTION_WORD = re.compile(
    r"\b(write|apply|run|execute|edit|modify|update|add|remove|refactor|rewrite|fix|debug|test|lint|format|implement)\b",
    re.IGNORECASE,
)
_INTENT_MECHANICAL_STRONG = [
    re.compile(r"\b(write\s+code|apply\s+(this\s+)?patch)\b", re.IGNORECASE),
    re.compile(r"\b(run|execute)\s+(the\s+)?(tests?|test suite|ci|pipeline)\b", re.IGNORECASE),
    re.compile(r"\b(implement)\s+(this\s+)?(feature|function|method|module|class|api|endpoint)\b", re.IGNORECASE),
    re.compile(r"\b(refactor|rename|fix|debug)\b.*\b(function|class|method|module|file|repo|tests?)\b", re.IGNORECASE),
    re.compile(r"\b(pytest|npm\s+test|pnpm\s+test|go\s+test|cargo\s+test|python\s+-m\s+unittest|git\s+diff|git\s+status|rg\s+-n|sed\s+-n)\b", re.IGNORECASE),
]
_INTENT_WORK_NOUN = (
    r"(code|function|method|class|module|file|repo(?:sitory)?|feature|bug|issue|tests?|pipeline|ci|script|diff|patch|log(?:\s+file)?)"
)
_INTENT_CONTEXTUAL_MECHANICAL = [
    re.compile(
        rf"\b(write|apply|run|execute|edit|modify|update|add|remove|refactor|rewrite|fix|debug|test|lint|format|implement)\b(?:\W+\w+){{0,6}}\W+\b{_INTENT_WORK_NOUN}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b{_INTENT_WORK_NOUN}\b(?:\W+\w+){{0,6}}\W+\b(write|apply|run|execute|edit|modify|update|add|remove|refactor|rewrite|fix|debug|test|lint|format|implement)\b",
        re.IGNORECASE,
    ),
]
_INTENT_NEGATIVE_GUARDS = [
    re.compile(r"\bcode of ethics\b", re.IGNORECASE),
    re.compile(r"\berror code\b", re.IGNORECASE),
    re.compile(r"\bzip code\b", re.IGNORECASE),
    re.compile(r"\bpostal code\b", re.IGNORECASE),
    re.compile(r"\bpatch schedule\b", re.IGNORECASE),
    re.compile(r"\bpatch notes\b", re.IGNORECASE),
    re.compile(r"\b(what is|what's|explain|discuss|describe|define)\b.*\b(code|patch|implementation)\b", re.IGNORECASE),
]
_INTENT_PLANNING_CUES = [
    re.compile(r"\b(plan|planning|design|architecture|roadmap|strategy|proposal|brainstorm|trade[- ]?offs?|synthesis)\b", re.IGNORECASE),
    re.compile(r"\b(explain|discuss|describe|summari[sz]e|compare|evaluate|reason|why|what is|how does)\b", re.IGNORECASE),
]


def classify_intent(text: str) -> str:
    """Ordered classifier: negative guards, strong mechanical, contextual mechanical, planning cues, then planning."""
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return "planning_synthesis"

    has_action_word = _INTENT_ACTION_WORD.search(normalized) is not None

    if any(rx.search(normalized) for rx in _INTENT_NEGATIVE_GUARDS) and not has_action_word:
        return "planning_synthesis"

    if any(rx.search(normalized) for rx in _INTENT_MECHANICAL_STRONG):
        return "mechanical_execution"

    if any(rx.search(normalized) for rx in _INTENT_CONTEXTUAL_MECHANICAL):
        return "mechanical_execution"

    if any(rx.search(normalized) for rx in _INTENT_PLANNING_CUES):
        return "planning_synthesis"

    return "planning_synthesis"


def _has_strong_planning_signal(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return False
    if any(rx.search(normalized) for rx in _INTENT_PLANNING_CUES):
        return True
    has_action_word = _INTENT_ACTION_WORD.search(normalized) is not None
    if any(rx.search(normalized) for rx in _INTENT_NEGATIVE_GUARDS) and not has_action_word:
        return True
    return False


def build_chat_payload(prompt, temperature=0.0, max_tokens=256):
    return {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _provider_auth_type(provider):
    auth = provider.get("auth")
    if isinstance(auth, dict):
        return auth.get("type")
    return None


def _provider_api_key_env(provider):
    if provider.get("apiKeyEnv"):
        return provider.get("apiKeyEnv")
    auth = provider.get("auth")
    if isinstance(auth, dict):
        return auth.get("apiKeyEnv") or auth.get("env")
    return ""


def _call_openai_compatible(base_url, api_key, model_id, payload, timeout=15):
    if requests is None:
        return {"ok": False, "reason_code": "no_requests_lib"}
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = requests.post(url, json={"model": model_id, **payload}, headers=headers, timeout=timeout)
        if resp.status_code == 429:
            return {"ok": False, "reason_code": "request_http_429"}
        if resp.status_code == 404:
            return {"ok": False, "reason_code": "request_http_404"}
        if resp.status_code >= 500:
            return {"ok": False, "reason_code": "request_http_5xx"}
        if resp.status_code != 200:
            return {"ok": False, "reason_code": f"request_http_{resp.status_code}"}
        data = resp.json()
        choice = data.get("choices", [{}])[0]
        content = ""
        if "message" in choice:
            content = choice.get("message", {}).get("content", "")
        else:
            content = choice.get("text", "")
        return {"ok": True, "text": content}
    except requests.exceptions.Timeout:
        return {"ok": False, "reason_code": "request_timeout"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "reason_code": "request_conn_error"}
    except Exception as exc:
        return {"ok": False, "reason_code": f"request_{type(exc).__name__}"}


def _call_anthropic(base_url, api_key, model_id, payload, timeout=15):
    if requests is None:
        return {"ok": False, "reason_code": "no_requests_lib"}
    url = base_url.rstrip("/") + "/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key or "",
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": model_id,
        "max_tokens": payload.get("max_tokens", 256),
        "temperature": payload.get("temperature", 0.0),
        "messages": payload.get("messages", []),
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=timeout)
        if resp.status_code == 429:
            return {"ok": False, "reason_code": "request_http_429"}
        if resp.status_code == 404:
            return {"ok": False, "reason_code": "request_http_404"}
        if resp.status_code >= 500:
            return {"ok": False, "reason_code": "request_http_5xx"}
        if resp.status_code != 200:
            return {"ok": False, "reason_code": f"request_http_{resp.status_code}"}
        data = resp.json()
        content = ""
        if isinstance(data.get("content"), list) and data["content"]:
            content = data["content"][0].get("text", "")
        return {"ok": True, "text": content}
    except requests.exceptions.Timeout:
        return {"ok": False, "reason_code": "request_timeout"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "reason_code": "request_conn_error"}
    except Exception as exc:
        return {"ok": False, "reason_code": f"request_{type(exc).__name__}"}


def _call_ollama(base_url, model_id, payload, timeout=10):
    if requests is None:
        return {"ok": False, "reason_code": "no_requests_lib"}
    url = base_url.rstrip("/") + "/api/generate"
    prompt = payload.get("prompt")
    if not prompt:
        prompt = _extract_text_from_payload(payload)
    body = {
        "model": model_id,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": payload.get("temperature", 0.0), "num_predict": payload.get("max_tokens", 256)},
    }
    try:
        resp = requests.post(url, json=body, timeout=timeout)
        if resp.status_code == 404:
            return {"ok": False, "reason_code": "request_http_404"}
        if resp.status_code != 200:
            return {"ok": False, "reason_code": f"request_http_{resp.status_code}"}
        data = resp.json()
        return {"ok": True, "text": data.get("response", "")}
    except requests.exceptions.Timeout:
        return {"ok": False, "reason_code": "request_timeout"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "reason_code": "request_conn_error"}
    except Exception as exc:
        return {"ok": False, "reason_code": f"request_{type(exc).__name__}"}


def _ollama_reachable(base_url):
    if requests is None:
        return False
    try:
        resp = requests.get(base_url.rstrip("/") + "/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _resolve_order(intent_cfg, policy):
    order = []
    for entry in intent_cfg.get("order", []):
        if entry == "free":
            order.extend(policy.get("routing", {}).get("free_order", []))
        else:
            order.append(normalize_provider_id(entry))
    # de-dup preserving order
    seen = set()
    final = []
    for item in order:
        if item not in seen:
            final.append(item)
            seen.add(item)
    return final


def _budget_remaining(limit, used):
    if limit <= 0:
        return None
    return max(0, limit - used)


def _budget_exhausted(limit, used):
    return limit > 0 and used >= limit


def _circuit_key(name, model_id):
    return f"{name}:{model_id}" if model_id else name


class PolicyRouter:
    def __init__(
        self,
        policy_path=POLICY_FILE,
        budget_path=BUDGET_FILE,
        circuit_path=CIRCUIT_FILE,
        event_log=EVENT_LOG,
        handlers=None,
    ):
        self.policy_path = policy_path
        self.budget_path = budget_path
        self.circuit_path = circuit_path
        self.event_log = event_log
        self.policy = load_policy(policy_path)
        self.budget_state = load_budget_state(budget_path)
        self.circuit_state = load_circuit_state(circuit_path)
        self.handlers = handlers or {}
        self.run_counts = {}
        self._proprio_sampler = ProprioceptiveSampler() if _flag_enabled("OPENCLAW_ROUTER_PROPRIOCEPTION") and ProprioceptiveSampler else None

    def _intent_cfg(self, intent):
        intent = canonical_intent(intent)
        intents = self.policy.get("routing", {}).get("intents", {})
        if isinstance(intent, str) and intent.startswith("teamchat:") and "coding" in intents:
            return intents.get("coding", {})
        if intent in intents:
            return intents.get(intent, {})
        return intents.get("conversation", {})

    def _provider_cfg(self, name):
        providers = self.policy.get("providers", {})
        if name in providers:
            return providers.get(name, {})
        normalized = normalize_provider_id(name)
        if normalized in providers:
            return providers.get(normalized, {})
        mapped = PROVIDER_ID_TO_POLICY_PROVIDER.get(normalized)
        if mapped and mapped in providers:
            return providers.get(mapped, {})
        for provider_name, cfg in providers.items():
            if not isinstance(cfg, dict):
                continue
            pid = cfg.get("provider_id")
            if isinstance(pid, str) and normalize_provider_id(pid) == normalized:
                return providers.get(provider_name, {})
        return {}

    def _provider_model(self, name, intent_cfg, context):
        provider = self._provider_cfg(name)
        models = provider.get("models", [])
        override = (context or {}).get("override_model")
        if override and name == "ollama":
            return override
        if not models:
            return None
        if name == "ollama":
            short_chars = int(intent_cfg.get("shortMessageChars", 240))
            prefer_local_short = bool(intent_cfg.get("preferLocalForShort", False))
            text = (context or {}).get("input_text", "")
            if prefer_local_short and len(text) <= short_chars:
                for m in models:
                    if m.get("tier") == "small":
                        return m.get("id")
            for m in models:
                if m.get("tier") == "large":
                    return m.get("id")
        return models[0].get("id")

    def _provider_max_chars(self, name, model_id):
        provider = self._provider_cfg(name)
        for m in provider.get("models", []):
            if m.get("id") == model_id:
                return int(m.get("maxInputChars", 0))
        models = provider.get("models", [])
        if models:
            return int(models[0].get("maxInputChars", 0))
        return 0

    def _provider_context_window_tokens(self, name):
        provider = self._provider_cfg(name)
        capabilities = provider.get("capabilities", {}) if isinstance(provider, dict) else {}
        manual = _coerce_positive_int(capabilities.get("context_window_tokens"), 0)
        env_key = capabilities.get("context_window_env")
        if env_key:
            env_value = _coerce_positive_int(os.environ.get(env_key), 0)
            if env_value:
                return env_value
        return manual

    def _capability_cfg(self):
        return self.policy.get("routing", {}).get("capability_router", {})

    def _capability_class(self, context_metadata, payload_text=""):
        context_metadata = context_metadata or {}
        text = "\n".join(
            t for t in [str(context_metadata.get("input_text", "")), str(payload_text or "")] if t
        )
        return classify_intent(text)

    def _capability_decision(self, context_metadata, payload_text=""):
        cfg = self._capability_cfg()
        if cfg.get("enabled") is False:
            return None

        context_metadata = context_metadata or {}
        text = "\n".join(
            t for t in [str(context_metadata.get("input_text", "")), str(payload_text or "")] if t
        )

        explicit = cfg.get("explicitTriggers", {})
        apply_to_subagents = bool(cfg.get("explicitApplyToSubagents", False))
        subagent = _is_subagent_context(context_metadata)

        if not subagent or apply_to_subagents:
            for phrase, provider in explicit.items():
                if _contains_phrase(text, phrase):
                    return {
                        "trigger": "explicit_phrase",
                        "matched": phrase,
                        "provider": provider,
                        "reason": f'explicit trigger "{phrase}"',
                    }

        if subagent:
            provider = cfg.get("subagentProvider")
            if provider:
                return {
                    "trigger": "subagent_default",
                    "matched": "subagent=true",
                    "provider": provider,
                    "reason": "subagent primary uses local provider",
                    "capability_class": "mechanical_execution",
                }

        capability_class = self._capability_class(context_metadata, payload_text)
        if capability_class == "mechanical_execution":
            default_cap = DEFAULT_POLICY.get("routing", {}).get("capability_router", {})
            code_provider = cfg.get("codeProvider")
            mechanical_provider = cfg.get("mechanicalProvider")
            small_provider = cfg.get("smallCodeProvider")
            small_by_ctx = str(context_metadata.get("expected_change_size", "")).strip().lower() in {"small", "tiny"}
            loc_hint = _coerce_positive_int(context_metadata.get("expected_loc"), 0)
            small_by_loc = 0 < loc_hint <= 50
            if small_provider and (small_by_ctx or small_by_loc):
                provider = small_provider
            elif code_provider and code_provider != default_cap.get("codeProvider"):
                provider = code_provider
            elif mechanical_provider and mechanical_provider != default_cap.get("mechanicalProvider"):
                provider = mechanical_provider
            else:
                provider = mechanical_provider or code_provider or cfg.get("subagentProvider")
            if provider:
                return {
                    "trigger": "capability_class",
                    "matched": capability_class,
                    "provider": provider,
                    "reason": "mechanical/execution class prefers local vLLM subagent",
                    "capability_class": capability_class,
                }

        if capability_class == "planning_synthesis":
            if not _has_strong_planning_signal(text):
                return None
            default_cap = DEFAULT_POLICY.get("routing", {}).get("capability_router", {})
            reasoning_provider = cfg.get("reasoningProvider")
            planning_provider = cfg.get("planningProvider")
            if reasoning_provider and reasoning_provider != default_cap.get("reasoningProvider"):
                provider = reasoning_provider
            elif planning_provider and planning_provider != default_cap.get("planningProvider"):
                provider = planning_provider
            else:
                provider = reasoning_provider or planning_provider
            if provider:
                return {
                    "trigger": "capability_class",
                    "matched": capability_class,
                    "provider": provider,
                    "reason": "planning/synthesis class prefers cloud reasoning",
                    "capability_class": capability_class,
                }

        return None

    def _ordered_providers(self, intent_cfg, context_metadata, payload_text=""):
        base_order = _resolve_order(intent_cfg, self.policy)
        decision = self._capability_decision(context_metadata, payload_text)
        if not decision:
            return base_order, None
        preferred = normalize_provider_id(decision.get("provider"))
        if preferred:
            order = [preferred] + [name for name in base_order if name != preferred]
        else:
            order = base_order
        return order, decision

    def _provider_available(self, name, intent_cfg):
        provider = self._provider_cfg(name)
        if not provider.get("enabled", True):
            return False, "provider_disabled"
        allow_paid = intent_cfg.get("allowPaid")
        if allow_paid is None:
            allow_paid = self.policy.get("defaults", {}).get("allowPaid", False)
        if provider.get("paid") and not allow_paid:
            return False, "paid_disallowed"

        ptype = provider.get("type")
        if ptype == "openai_auth" or ptype == "anthropic_auth":
            ready_env = provider.get("readyEnv")
            if ready_env and not os.environ.get(ready_env):
                return False, "auth_login_required"

        if ptype == "openai_compatible":
            if provider.get("auth") == "qwen_oauth":
                token, err = get_qwen_token()
                if not token:
                    return False, err or "missing_token"
            else:
                auth_type = _provider_auth_type(provider)
                api_key_env = _provider_api_key_env(provider)
                requires_key = bool(api_key_env) or auth_type == "bearer"
                if requires_key:
                    api_key = read_env_or_secrets(api_key_env)
                    if not api_key:
                        return False, "missing_api_key"

        if ptype == "anthropic":
            api_key = read_env_or_secrets(provider.get("apiKeyEnv", ""))
            if not api_key:
                return False, "missing_api_key"

        if ptype == "ollama":
            base = provider.get("baseUrl", "http://localhost:11434")
            if not _ollama_reachable(base):
                return False, "ollama_unreachable"

        return True, None

    def _circuit_open(self, name, now):
        providers = self.circuit_state.get("providers", {})
        entry = providers.get(name, {})
        return entry.get("openUntil", 0) > now

    def _record_failure(self, name, reason_code):
        cfg = self.policy.get("defaults", {}).get("circuitBreaker", {})
        threshold = int(cfg.get("failureThreshold", 3))
        cooldown = int(cfg.get("cooldownSec", 900))
        window = int(cfg.get("windowSec", 600))
        now = int(time.time())

        providers = self.circuit_state.setdefault("providers", {})
        entry = providers.setdefault(name, {"failures": 0, "firstFailureAt": now, "openUntil": 0})
        if now - entry.get("firstFailureAt", now) > window:
            entry["failures"] = 0
            entry["firstFailureAt"] = now
        entry["failures"] = entry.get("failures", 0) + 1
        if entry["failures"] >= threshold:
            entry["openUntil"] = now + cooldown
        providers[name] = entry
        save_circuit_state(self.circuit_state, self.circuit_path)

    def _record_success(self, name):
        providers = self.circuit_state.setdefault("providers", {})
        if name in providers:
            providers[name]["failures"] = 0
            providers[name]["openUntil"] = 0
            providers[name]["firstFailureAt"] = int(time.time())
        save_circuit_state(self.circuit_state, self.circuit_path)

    def _budget_allows(self, intent, tier, est_tokens):
        budgets = self.policy.get("budgets", {})
        intent_budget = budgets.get("intents", {}).get(intent, {})
        tier_budget = budgets.get("tiers", {}).get(tier, {})

        intent_state = self.budget_state.setdefault("intents", {}).setdefault(intent, {"calls": 0, "tokens": 0})
        tier_state = self.budget_state.setdefault("tiers", {}).setdefault(tier, {"calls": 0, "tokens": 0})

        if _budget_exhausted(int(intent_budget.get("dailyCallBudget", 0)), intent_state["calls"]):
            return False, "intent_call_budget_exhausted"
        if _budget_exhausted(int(tier_budget.get("dailyCallBudget", 0)), tier_state["calls"]):
            return False, "tier_call_budget_exhausted"
        if _budget_exhausted(int(intent_budget.get("dailyTokenBudget", 0)), intent_state["tokens"] + est_tokens):
            return False, "intent_token_budget_exhausted"
        if _budget_exhausted(int(tier_budget.get("dailyTokenBudget", 0)), tier_state["tokens"] + est_tokens):
            return False, "tier_token_budget_exhausted"
        return True, None

    def _tacti_runtime_controls(self, intent, intent_cfg, context_metadata):
        controls = {
            "enabled": False,
            "multiplier": 1.0,
            "suppress_heavy": False,
            "expression": {},
            "prefer_local": False,
            "tighten_budget": False,
        }
        if not callable(tacti_enabled):
            return controls
        if not tacti_enabled("master"):
            return controls

        controls["enabled"] = True
        now_ts = int(time.time())
        now_local = time.localtime(now_ts)
        proprio_snapshot = (context_metadata or {}).get("proprioception", {})
        tacti_features = {}
        if _flag_enabled("OPENCLAW_ROUTER_PROPRIOCEPTION"):
            tacti_features = tacti_features_from_proprioception(proprio_snapshot)

        if callable(compute_expression):
            expression = compute_expression(
                now=datetime.fromtimestamp(now_ts, tz=timezone.utc),
                context={
                    "budget_remaining": 1.0,
                    "local_available": True,
                    "hour": int(now_local.tm_hour),
                    "valence": float((context_metadata or {}).get("valence", 0.0)),
                    "arousal": float((context_metadata or {}).get("arousal", tacti_features.get("arousal", 1.0))),
                },
            )
            controls["expression"] = expression
            suppressed = set(expression.get("suppressed_features", []))
            reasons = expression.get("reasons", {})
            global_reasons = reasons.get("_global", []) if isinstance(reasons, dict) else []
            if "arousal_osc" in suppressed or "negative_valence_guard" in global_reasons:
                controls["suppress_heavy"] = True
            _tacti_event(
                "tacti_cr.expression_profile",
                {"intent": intent, "profile": expression},
            )

        if callable(tacti_routing_bias):
            agent_id = str((context_metadata or {}).get("agent_id", "main"))
            bias = tacti_routing_bias(agent_id, repo_root=BASE_DIR)
            controls["prefer_local"] = bool(bias.get("prefer_local"))
            controls["tighten_budget"] = bool(bias.get("tighten_budget"))
            _tacti_event("tacti_cr.valence_bias", {"intent": intent, "agent_id": agent_id, "bias": bias})

        if tacti_enabled("arousal_osc") and ArousalOscillator is not None:
            osc = ArousalOscillator(repo_root=BASE_DIR)
            explain = osc.explain(datetime.fromtimestamp(now_ts, tz=timezone.utc))
            controls["multiplier"] = float(explain.get("multiplier", 1.0))
            controls["suppress_heavy"] = bool(osc.should_suppress_heavy_escalation())
            _tacti_event(
                "tacti_cr.arousal_multiplier",
                {"intent": intent, "multiplier": controls["multiplier"], "explain": explain},
            )
            if controls["multiplier"] > 0.9 and callable(collapse_emit_recommendation):
                collapse_emit_recommendation(
                    "preemptive_load_shed",
                    detail={"intent": intent, "multiplier": controls["multiplier"], "advisory": True},
                    repo_root=BASE_DIR,
                )

        return controls

    def _budget_consume(self, intent, tier, est_tokens):
        intent_state = self.budget_state.setdefault("intents", {}).setdefault(intent, {"calls": 0, "tokens": 0})
        tier_state = self.budget_state.setdefault("tiers", {}).setdefault(tier, {"calls": 0, "tokens": 0})
        intent_state["calls"] += 1
        intent_state["tokens"] += est_tokens
        tier_state["calls"] += 1
        tier_state["tokens"] += est_tokens
        save_budget_state(self.budget_state, self.budget_path)

    def select_model(self, intent, context_metadata=None):
        intent_cfg = self._intent_cfg(intent)
        order, _decision = self._ordered_providers(intent_cfg, context_metadata or {})
        for name in order:
            ok, reason = self._provider_available(name, intent_cfg)
            if not ok:
                continue
            model_id = self._provider_model(name, intent_cfg, context_metadata or {})
            return {"provider": name, "model": model_id, "reason_code": reason}
        return None

    def intent_status(self, intent):
        intent_cfg = self._intent_cfg(intent)
        order = _resolve_order(intent_cfg, self.policy)
        available = []
        reasons = {}
        now = int(time.time())
        for name in order:
            ok, reason = self._provider_available(name, intent_cfg)
            model_id = self._provider_model(name, intent_cfg, {})
            circuit_key = _circuit_key(name, model_id)
            if ok and not self._circuit_open(circuit_key, now):
                available.append(name)
            else:
                reasons[name] = reason or "circuit_open"
        return {
            "order": order,
            "available": available,
            "reasons": reasons,
        }

    def explain_route(self, intent, context_metadata=None, payload=None):
        context_metadata = context_metadata or {}
        payload_text = _extract_text_from_payload(payload or {})
        intent_cfg = self._intent_cfg(intent)
        base_order = _resolve_order(intent_cfg, self.policy)
        order, decision = self._ordered_providers(intent_cfg, context_metadata, payload_text)

        chosen = None
        unavailable = {}
        for name in order:
            ok, reason = self._provider_available(name, intent_cfg)
            if ok:
                chosen = {
                    "provider": name,
                    "model": self._provider_model(name, intent_cfg, context_metadata),
                }
                break
            unavailable[name] = reason

        local_context_tokens = self._provider_context_window_tokens("local_vllm_assistant")
        return {
            "intent": intent,
            "matched_trigger": (decision or {}).get("trigger") or "default",
            "matched_detail": (decision or {}).get("matched") or "none",
            "reason": (decision or {}).get("reason") or "default intent routing order",
            "capability_class": (decision or {}).get("capability_class")
            or self._capability_class(context_metadata, payload_text),
            "base_order": base_order,
            "evaluated_order": order,
            "chosen": chosen,
            "unavailable": unavailable,
            "fallback_candidates": [name for name in order if not chosen or name != chosen.get("provider")],
            "local_context_window_tokens": local_context_tokens,
        }

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        intent_cfg = self._intent_cfg(intent)
        attempts = 0
        last_reason = None
        context_metadata = context_metadata or {}
        runtime_context = dict(context_metadata)
        request_id = str(runtime_context.get("request_id") or _new_request_id("rt"))
        runtime_context["request_id"] = request_id
        payload_text = _extract_text_from_payload(payload)
        capability_class = self._capability_class(runtime_context, payload_text)
        runtime_context.setdefault("capability_class", capability_class)
        budget_intent = _budget_intent_key(intent)

        def _emit(event_type, detail=None):
            event_detail = dict(detail or {})
            event_detail.setdefault("request_id", request_id)
            event_detail.setdefault("capability_class", capability_class)
            log_event(event_type, event_detail, self.event_log)

        if self._proprio_sampler is not None:
            snap = self._proprio_sampler.snapshot()
            runtime_context.setdefault("proprioception", snap)
        if _flag_enabled("ENABLE_ACTIVE_INFERENCE"):
            runtime_context["active_inference"] = _active_inference_payload(runtime_context)
        tacti_controls = self._tacti_runtime_controls(intent, intent_cfg, runtime_context)
        order, decision = self._ordered_providers(intent_cfg, runtime_context, payload_text)
        route_explain = self.explain_route(intent, context_metadata=runtime_context, payload=payload)
        if decision:
            _emit(
                "router_route_selected",
                {
                    "intent": intent,
                    "trigger": decision.get("trigger"),
                    "matched": decision.get("matched"),
                    "preferred_provider": decision.get("provider"),
                    "reason": decision.get("reason"),
                    "capability_class": decision.get("capability_class") or capability_class,
                    "fallback_candidates": route_explain.get("fallback_candidates", []),
                },
            )
        else:
            _emit(
                "router_route_selected",
                {
                    "intent": intent,
                    "trigger": "default",
                    "preferred_provider": None,
                    "fallback_candidates": route_explain.get("fallback_candidates", []),
                },
            )

        max_per_run = int(self.policy.get("budgets", {}).get("intents", {}).get(budget_intent, {}).get("maxCallsPerRun", 0))
        self.run_counts.setdefault(budget_intent, 0)
        now = int(time.time())

        for name in order:
            provider_start = time.perf_counter()
            if max_per_run and self.run_counts[budget_intent] >= max_per_run:
                last_reason = "max_calls_per_run_exhausted"
                _emit("router_skip", {"intent": intent, "provider": name, "reason_code": last_reason})
                break

            ok, reason = self._provider_available(name, intent_cfg)
            if not ok:
                last_reason = reason
                _emit("router_skip", {"intent": intent, "provider": name, "reason_code": reason})
                continue

            provider = self._provider_cfg(name)
            tier = provider.get("tier", "free")
            model_id = self._provider_model(name, intent_cfg, runtime_context)
            circuit_key = _circuit_key(name, model_id)

            if tacti_controls.get("suppress_heavy"):
                is_heavy = tier in {"paid", "auth"} or str(name).startswith(("openai_", "claude_", "grok_"))
                if is_heavy:
                    last_reason = "tacti_cr_arousal_suppress_heavy"
                    _emit(
                        "router_skip",
                        {"intent": intent, "provider": name, "reason_code": last_reason},
                    )
                    continue
            if tacti_controls.get("prefer_local"):
                if str(name).startswith(("openai_", "claude_", "grok_")):
                    last_reason = "tacti_cr_valence_prefer_local"
                    _emit(
                        "router_skip",
                        {"intent": intent, "provider": name, "reason_code": last_reason},
                    )
                    continue

            if self._circuit_open(circuit_key, now):
                last_reason = "circuit_open"
                _emit("router_skip", {"intent": intent, "provider": name, "reason_code": "circuit_open"})
                continue
            max_chars = self._provider_max_chars(name, model_id)

            # enforce per-request cap and per-provider max chars
            text = _extract_text_from_payload(payload)
            text = _truncate_text(text, max_chars or 0)
            if "prompt" in payload:
                payload = dict(payload)
                payload["prompt"] = text
            elif "messages" in payload:
                payload = dict(payload)
                payload["messages"] = [{"role": "user", "content": text}]

            est_tokens = estimate_tokens(text)
            max_tokens_req = int(
                intent_cfg.get(
                    "maxTokensPerRequest",
                    self.policy.get("defaults", {}).get("maxTokensPerRequest", 0),
                )
            )
            if max_tokens_req and est_tokens > max_tokens_req:
                last_reason = "request_token_cap_exceeded"
                _emit(
                    "router_skip",
                    {"intent": intent, "provider": name, "reason_code": last_reason},
                )
                continue
            effective_tokens = est_tokens
            if tacti_controls.get("enabled"):
                multiplier = max(0.0, min(1.0, float(tacti_controls.get("multiplier", 1.0))))
                effective_tokens = max(1, int(round(est_tokens / max(multiplier, 0.05))))
                if tacti_controls.get("tighten_budget"):
                    effective_tokens = max(1, int(round(effective_tokens * 1.25)))
            allowed, reason = self._budget_allows(budget_intent, tier, effective_tokens)
            if not allowed:
                last_reason = reason
                _emit("router_skip", {"intent": intent, "provider": name, "reason_code": reason})
                continue

            attempts += 1
            self.run_counts[budget_intent] += 1
            self._budget_consume(budget_intent, tier, effective_tokens)

            started_at = time.perf_counter()

            # handler dispatch
            try:
                handler = self.handlers.get(name)
                if handler:
                    result = handler(payload, model_id, runtime_context)
                else:
                    ptype = provider.get("type")
                    if ptype == "openai_compatible":
                        api_key = None
                        if provider.get("auth") == "qwen_oauth":
                            api_key, _ = get_qwen_token()
                        else:
                            api_key_env = _provider_api_key_env(provider)
                            if api_key_env:
                                api_key = read_env_or_secrets(api_key_env)
                        provider_caps = resolve_tool_call_capability(provider, model_id)
                        result = _call_openai_compatible(
                            provider.get("baseUrl", ""),
                            api_key,
                            model_id,
                            payload,
                            provider_caps=provider_caps,
                        )
                    elif ptype == "anthropic":
                        api_key = read_env_or_secrets(provider.get("apiKeyEnv", ""))
                        result = _call_anthropic(provider.get("baseUrl", ""), api_key, model_id, payload)
                    elif ptype == "ollama":
                        base = provider.get("baseUrl", "http://localhost:11434")
                        result = _call_ollama(base, model_id, payload)
                    elif ptype == "openai_auth" or ptype == "anthropic_auth":
                        result = {"ok": False, "reason_code": "auth_login_required"}
                    else:
                        result = {"ok": False, "reason_code": "provider_unhandled"}
            except Exception as exc:
                result = {"ok": False, "reason_code": f"provider_exception_{type(exc).__name__}", "error": str(exc)}

            latency_ms = int((time.perf_counter() - started_at) * 1000)

            if not result.get("ok"):
                reason_code = result.get("reason_code", "provider_error")
                last_reason = reason_code
                cfg = self.policy.get("defaults", {}).get("circuitBreaker", {})
                if reason_code in cfg.get("failOn", []):
                    self._record_failure(circuit_key, reason_code)
                _emit(
                    "router_attempt",
                    {
                        "intent": intent,
                        "provider": name,
                        "model": model_id,
                        "tier": tier,
                        "reason_code": reason_code,
                        "outcome_class": _outcome_class_from_reason(reason_code),
                        "latency_ms": latency_ms,
                        "attempt": attempts,
                        "selected_tool": runtime_context.get("selected_tool"),
                    },
                )
                _emit(
                    "router_escalate",
                    {
                        "intent": intent,
                        "from_provider": name,
                        "reason_code": reason_code,
                        "outcome_class": _outcome_class_from_reason(reason_code),
                        "latency_ms": latency_ms,
                        "attempt": attempts,
                    },
                )
                if self._proprio_sampler is not None:
                    breaker_open = []
                    for prov_name, entry in (self.circuit_state.get("providers", {}) or {}).items():
                        try:
                            if int(entry.get("openUntil", 0)) > int(time.time()):
                                breaker_open.append(str(prov_name))
                        except Exception:
                            continue
                    self._proprio_sampler.set_breaker_open_providers(breaker_open)
                    self._proprio_sampler.record_decision(
                        duration_ms=(time.perf_counter() - provider_start) * 1000.0,
                        tokens_in=est_tokens,
                        tokens_out=0,
                        provider=name,
                        ok=False,
                        err=reason_code,
                    )
                continue

            text_out = result.get("text", "")
            parsed = None
            if validate_fn:
                try:
                    parsed = validate_fn(text_out)
                except Exception:
                    parsed = None
                if not parsed:
                    last_reason = "response_invalid"
                    _emit(
                        "router_attempt",
                        {
                            "intent": intent,
                            "provider": name,
                            "model": model_id,
                            "tier": tier,
                            "reason_code": "response_invalid",
                            "outcome_class": _outcome_class_from_reason("response_invalid"),
                            "latency_ms": latency_ms,
                            "attempt": attempts,
                        },
                    )
                    _emit(
                        "router_escalate",
                        {
                            "intent": intent,
                            "from_provider": name,
                            "reason_code": "response_invalid",
                            "outcome_class": _outcome_class_from_reason("response_invalid"),
                            "latency_ms": latency_ms,
                            "attempt": attempts,
                        },
                    )
                    continue

            self._record_success(circuit_key)
            _emit(
                "router_success",
                {
                    "intent": intent,
                    "provider": name,
                    "model": model_id,
                    "tier": tier,
                    "outcome_class": "success",
                    "latency_ms": latency_ms,
                    "selected_tool": runtime_context.get("selected_tool"),
                    "attempt": attempts,
                },
            )
            tacti_plan = None
            if _legacy_tacti_flags_enabled():
                tacti_plan = tacti_enhance_plan(
                    {"enabled": True, "agent_ids": [name], "provider": name},
                    context_metadata=runtime_context,
                    intent=intent,
                )
                log_event("tacti_routing_plan", tacti_plan, self.event_log)
            meta = None
            if self._proprio_sampler is not None:
                breaker_open = []
                for prov_name, entry in (self.circuit_state.get("providers", {}) or {}).items():
                    try:
                        if int(entry.get("openUntil", 0)) > int(time.time()):
                            breaker_open.append(str(prov_name))
                    except Exception:
                        continue
                self._proprio_sampler.set_breaker_open_providers(breaker_open)
                self._proprio_sampler.record_decision(
                    duration_ms=(time.perf_counter() - provider_start) * 1000.0,
                    tokens_in=est_tokens,
                    tokens_out=estimate_tokens(text_out),
                    provider=name,
                    ok=True,
                )
                snap = self._proprio_sampler.snapshot()
                runtime_context.setdefault("proprioception", snap)
                meta = {"proprioception": snap}
            result_payload = {
                "ok": True,
                "provider": name,
                "model": model_id,
                "text": text_out,
                "parsed": parsed,
                "attempts": attempts,
                "reason_code": "success",
                "request_id": request_id,
                "capability_class": capability_class,
                "tacti": tacti_plan,
            }
            if meta is not None:
                result_payload["meta"] = meta
            return result_payload

        _emit(
            "router_fail",
            {
                "intent": intent,
                "reason_code": last_reason or "no_provider_available",
                "outcome_class": _outcome_class_from_reason(last_reason or "no_provider_available"),
                "attempts": attempts,
            },
        )
        return {
            "ok": False,
            "reason_code": last_reason or "no_provider_available",
            "attempts": attempts,
            "request_id": request_id,
            "capability_class": capability_class,
        }
