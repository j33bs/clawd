#!/usr/bin/env python3
"""
Policy Router
- Centralized routing, budgeting, and circuit-breaking for all LLM calls.
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

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
POLICY_SCHEMA_FILE = BASE_DIR / "workspace" / "policy" / "llm_policy.schema.json"
BUDGET_FILE = BASE_DIR / "itc" / "llm_budget.json"
CIRCUIT_FILE = BASE_DIR / "itc" / "llm_circuit.json"
EVENT_LOG = BASE_DIR / "itc" / "llm_router_events.jsonl"
QWEN_AUTH_FILE = BASE_DIR / "agents" / "main" / "agent" / "auth-profiles.json"
ACTIVE_INFERENCE_STATE_PATH = BASE_DIR / "workspace" / "hivemind" / "data" / "active_inference_state.json"

HIVEMIND_ROOT = BASE_DIR / "workspace" / "hivemind"
if HIVEMIND_ROOT.exists() and str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

try:
    from hivemind.active_inference import PreferenceModel
    from hivemind.flags import is_enabled as hivemind_flag_enabled
    from hivemind.integrations.main_flow_hook import (
        dynamics_flags_enabled as tacti_dynamics_enabled,
        tacti_enhance_plan,
        tacti_record_outcome,
    )
except Exception:  # pragma: no cover - optional dependency hook
    PreferenceModel = None
    hivemind_flag_enabled = None
    tacti_dynamics_enabled = None
    tacti_enhance_plan = None
    tacti_record_outcome = None


class PolicyValidationError(Exception):
    pass

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
    },
}


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


def _policy_strict_mode():
    return os.environ.get("OPENCLAW_POLICY_STRICT", "1") != "0"


def _active_inference_enabled():
    if hivemind_flag_enabled is not None:
        return bool(hivemind_flag_enabled("ENABLE_ACTIVE_INFERENCE"))
    return os.environ.get("ENABLE_ACTIVE_INFERENCE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_policy_schema_path(policy_path):
    local = Path(policy_path).with_name("llm_policy.schema.json")
    if local.exists():
        return local
    return POLICY_SCHEMA_FILE


def _load_policy_schema(policy_path):
    schema_path = _resolve_policy_schema_path(policy_path)
    if not schema_path.exists():
        raise PolicyValidationError(f"policy schema missing: {schema_path}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PolicyValidationError(f"policy schema invalid JSON: {schema_path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise PolicyValidationError(f"policy schema must be object: {schema_path}")
    return schema


def _type_matches(expected, value):
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_with_schema(value, schema, where="$"):
    expected_type = schema.get("type")
    if expected_type is not None:
        if isinstance(expected_type, list):
            ok = any(_type_matches(t, value) for t in expected_type)
        else:
            ok = _type_matches(expected_type, value)
        if not ok:
            raise PolicyValidationError(f"{where}: expected type {expected_type}")

    if "enum" in schema and value not in schema["enum"]:
        raise PolicyValidationError(f"{where}: value not in enum")

    if "minimum" in schema:
        if not _type_matches("number", value):
            raise PolicyValidationError(f"{where}: minimum requires numeric value")
        if value < schema["minimum"]:
            raise PolicyValidationError(f"{where}: value below minimum {schema['minimum']}")

    if expected_type == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise PolicyValidationError(f"{where}.{key}: required key missing")
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                _validate_with_schema(item, props[key], f"{where}.{key}")
            else:
                if additional is False:
                    raise PolicyValidationError(f"{where}.{key}: unknown key")
                if isinstance(additional, dict):
                    _validate_with_schema(item, additional, f"{where}.{key}")

    if expected_type == "array":
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            raise PolicyValidationError(f"{where}: expected at least {min_items} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                _validate_with_schema(item, item_schema, f"{where}[{idx}]")


def _raw_policy_schema(schema):
    if not isinstance(schema, dict):
        return schema
    out = dict(schema)
    expected_type = out.get("type")
    if expected_type == "object":
        out.pop("required", None)
        props = out.get("properties")
        if isinstance(props, dict):
            out["properties"] = {k: _raw_policy_schema(v) for k, v in props.items()}
        additional = out.get("additionalProperties")
        if isinstance(additional, dict):
            out["additionalProperties"] = _raw_policy_schema(additional)
    elif expected_type == "array":
        items = out.get("items")
        if isinstance(items, dict):
            out["items"] = _raw_policy_schema(items)
    return out


def load_policy(path=POLICY_FILE):
    policy = DEFAULT_POLICY
    if path.exists():
        raw = None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log_event("policy_load_fail", {"path": str(path), "error": str(exc)})
            if _policy_strict_mode():
                raise PolicyValidationError(f"policy JSON invalid: {path}: {exc}") from exc
            sys.stderr.write(f"WARNING: OPENCLAW_POLICY_STRICT=0; invalid policy JSON ignored: {path}\n")
            return policy
        try:
            schema = _load_policy_schema(path)
            _validate_with_schema(raw, _raw_policy_schema(schema), "$raw")
            policy = _deep_merge(DEFAULT_POLICY, raw)
            _validate_with_schema(policy, schema, "$policy")
        except PolicyValidationError as exc:
            log_event("policy_validation_fail", {"path": str(path), "error": str(exc)})
            if _policy_strict_mode():
                raise
            sys.stderr.write(f"WARNING: OPENCLAW_POLICY_STRICT=0; policy validation skipped: {exc}\n")
            if isinstance(raw, dict):
                policy = _deep_merge(DEFAULT_POLICY, raw)
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
        entry["detail"] = detail
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


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


def build_chat_payload(prompt, temperature=0.0, max_tokens=256):
    return {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


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
            order.append(entry)
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
        self.active_inference_model = None
        if _active_inference_enabled() and PreferenceModel is not None:
            self.active_inference_model = PreferenceModel.load_path(Path(ACTIVE_INFERENCE_STATE_PATH))

    def _intent_cfg(self, intent):
        return self.policy.get("routing", {}).get("intents", {}).get(intent, {})

    def _provider_cfg(self, name):
        return self.policy.get("providers", {}).get(name, {})

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
                api_key = read_env_or_secrets(provider.get("apiKeyEnv", ""))
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
        order = _resolve_order(intent_cfg, self.policy)
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

    def _predict_preferences(self, context_metadata):
        if not self.active_inference_model:
            return None
        params, confidence = self.active_inference_model.predict(context_metadata or {})
        return {"preference_params": params, "confidence": confidence}

    def _update_preferences(self, context_metadata, observed_outcome):
        if not self.active_inference_model:
            return None
        feedback = {}
        if isinstance(context_metadata, dict):
            raw_feedback = context_metadata.get("feedback", {})
            if isinstance(raw_feedback, dict):
                feedback = raw_feedback
        result = self.active_inference_model.update(feedback, observed_outcome or {})
        self.active_inference_model.save_path(Path(ACTIVE_INFERENCE_STATE_PATH))
        return result

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        intent_cfg = self._intent_cfg(intent)
        order = _resolve_order(intent_cfg, self.policy)
        attempts = 0
        last_reason = None
        context_metadata = dict(context_metadata or {})
        route_source_agent = str(context_metadata.get("agent_id", "router")).strip() or "router"
        route_context = {
            "intent": intent,
            "source_agent": route_source_agent,
            "session_id": str(context_metadata.get("session_id", "")).strip(),
            "input_text": _extract_text_from_payload(payload),
        }
        tacti_annotations = None

        ai_prediction = self._predict_preferences(context_metadata)
        if ai_prediction is not None:
            context_metadata["active_inference"] = ai_prediction
            log_event(
                "active_inference_predict",
                {
                    "intent": intent,
                    "confidence": ai_prediction.get("confidence"),
                },
                self.event_log,
            )

        if tacti_enhance_plan is not None and tacti_dynamics_enabled is not None and tacti_dynamics_enabled():
            original_order = list(order)
            try:
                order, tacti_annotations = tacti_enhance_plan(route_context, order, policy=self.policy)
                if isinstance(tacti_annotations, dict) and tacti_annotations.get("enabled"):
                    log_event(
                        "tacti_routing_plan",
                        {
                            "intent": intent,
                            "source_agent": route_source_agent,
                            "before_order": original_order,
                            "after_order": order,
                            "applied": bool(tacti_annotations.get("applied")),
                            "agent_ids": tacti_annotations.get("agent_ids", []),
                        },
                        self.event_log,
                    )
            except Exception as exc:
                order = original_order
                tacti_annotations = {"enabled": False, "reason": "tacti_hook_error"}
                log_event(
                    "tacti_routing_plan_error",
                    {
                        "intent": intent,
                        "error": type(exc).__name__,
                    },
                    self.event_log,
                )

        max_per_run = int(self.policy.get("budgets", {}).get("intents", {}).get(intent, {}).get("maxCallsPerRun", 0))
        self.run_counts.setdefault(intent, 0)
        now = int(time.time())

        def _record_tacti(success, provider, reward, latency, tokens):
            if tacti_record_outcome is None or tacti_dynamics_enabled is None or not tacti_dynamics_enabled():
                return
            try:
                outcome = tacti_record_outcome(
                    context=route_context,
                    path=[route_source_agent, str(provider)],
                    success=bool(success),
                    latency=float(latency),
                    tokens=float(tokens),
                    reward=float(reward),
                    policy=self.policy,
                )
                if isinstance(outcome, dict) and outcome.get("enabled"):
                    log_event(
                        "tacti_routing_outcome",
                        {
                            "intent": intent,
                            "provider": str(provider),
                            "success": bool(success),
                            "reward": float(reward),
                        },
                        self.event_log,
                    )
            except Exception as exc:
                log_event(
                    "tacti_routing_outcome_error",
                    {
                        "intent": intent,
                        "provider": str(provider),
                        "error": type(exc).__name__,
                    },
                    self.event_log,
                )

        for name in order:
            if max_per_run and self.run_counts[intent] >= max_per_run:
                last_reason = "max_calls_per_run_exhausted"
                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": last_reason}, self.event_log)
                break

            ok, reason = self._provider_available(name, intent_cfg)
            if not ok:
                last_reason = reason
                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": reason}, self.event_log)
                continue

            provider = self._provider_cfg(name)
            tier = provider.get("tier", "free")
            model_id = self._provider_model(name, intent_cfg, context_metadata)
            circuit_key = _circuit_key(name, model_id)

            if self._circuit_open(circuit_key, now):
                last_reason = "circuit_open"
                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": "circuit_open"}, self.event_log)
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
                log_event(
                    "router_skip",
                    {"intent": intent, "provider": name, "reason_code": last_reason},
                    self.event_log,
                )
                continue
            allowed, reason = self._budget_allows(intent, tier, est_tokens)
            if not allowed:
                last_reason = reason
                log_event("router_skip", {"intent": intent, "provider": name, "reason_code": reason}, self.event_log)
                continue

            attempts += 1
            self.run_counts[intent] += 1
            self._budget_consume(intent, tier, est_tokens)

            # handler dispatch
            handler = self.handlers.get(name)
            if handler:
                result = handler(payload, model_id, context_metadata)
            else:
                ptype = provider.get("type")
                if ptype == "openai_compatible":
                    api_key = None
                    if provider.get("auth") == "qwen_oauth":
                        api_key, _ = get_qwen_token()
                    else:
                        api_key = read_env_or_secrets(provider.get("apiKeyEnv", ""))
                    result = _call_openai_compatible(provider.get("baseUrl", ""), api_key, model_id, payload)
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

            if not result.get("ok"):
                reason_code = result.get("reason_code", "provider_error")
                last_reason = reason_code
                cfg = self.policy.get("defaults", {}).get("circuitBreaker", {})
                if reason_code in cfg.get("failOn", []):
                    self._record_failure(circuit_key, reason_code)
                _record_tacti(False, name, -0.25, 0.0, est_tokens)
                self._update_preferences(
                    context_metadata,
                    {
                        "verbosity_score": 0.2,
                        "format_score": 0.2,
                        "tool_score": 0.4,
                        "correction_score": 0.2,
                    },
                )
                log_event(
                    "router_attempt",
                    {
                        "intent": intent,
                        "provider": name,
                        "model": model_id,
                        "tier": tier,
                        "reason_code": reason_code,
                        "attempt": attempts,
                    },
                    self.event_log,
                )
                log_event(
                    "router_escalate",
                    {
                        "intent": intent,
                        "from_provider": name,
                        "reason_code": reason_code,
                        "attempt": attempts,
                    },
                    self.event_log,
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
                    log_event(
                        "router_attempt",
                        {
                            "intent": intent,
                            "provider": name,
                            "model": model_id,
                            "tier": tier,
                            "reason_code": "response_invalid",
                            "attempt": attempts,
                        },
                        self.event_log,
                    )
                    log_event(
                        "router_escalate",
                        {
                            "intent": intent,
                            "from_provider": name,
                            "reason_code": "response_invalid",
                            "attempt": attempts,
                        },
                        self.event_log,
                    )
                    _record_tacti(False, name, -0.15, 0.0, est_tokens)
                    continue

            self._record_success(circuit_key)
            out_tokens = estimate_tokens(text_out)
            in_tokens = max(1, estimate_tokens(_extract_text_from_payload(payload)))
            verbosity_ratio = max(0.0, min(1.0, out_tokens / max(1, in_tokens * 2)))
            format_score = 0.8 if ("\n" in text_out or "- " in text_out) else 0.45
            tool_score = 0.8 if bool(context_metadata.get("requires_tools")) else 0.55
            correction_score = 0.9 if result.get("ok") else 0.3
            route_reward = max(0.05, min(1.0, 0.5 + (0.5 * verbosity_ratio)))
            _record_tacti(True, name, route_reward, 0.0, in_tokens + out_tokens)
            ai_update = self._update_preferences(
                context_metadata,
                {
                    "verbosity_score": verbosity_ratio,
                    "format_score": format_score,
                    "tool_score": tool_score,
                    "correction_score": correction_score,
                },
            )
            if ai_update is not None:
                log_event(
                    "active_inference_update",
                    {
                        "intent": intent,
                        "prediction_error": ai_update.get("prediction_error"),
                        "interactions": ai_update.get("interactions"),
                    },
                    self.event_log,
                )
            log_event(
                "router_success",
                {
                    "intent": intent,
                    "provider": name,
                    "model": model_id,
                    "tier": tier,
                    "attempt": attempts,
                },
                self.event_log,
            )
            return {
                "ok": True,
                "provider": name,
                "model": model_id,
                "text": text_out,
                "parsed": parsed,
                "attempts": attempts,
                "reason_code": "success",
                "tacti": tacti_annotations,
            }

        log_event(
            "router_fail",
            {
                "intent": intent,
                "reason_code": last_reason or "no_provider_available",
                "attempts": attempts,
            },
            self.event_log,
        )
        return {
            "ok": False,
            "reason_code": last_reason or "no_provider_available",
            "attempts": attempts,
            "tacti": tacti_annotations,
        }


if __name__ == "__main__":
    try:
        load_policy(POLICY_FILE)
    except PolicyValidationError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        raise SystemExit(2)
