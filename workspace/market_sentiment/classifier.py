from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_IDLE_ONLY_PATTERNS = ("phi4", "phi-4")
DEFAULT_IDLE_MAX_LOAD_PER_CPU = 0.7


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _normalize_model_name(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    return text.split(":", 1)[0]


def _is_same_model(left: str, right: str) -> bool:
    left_name = _normalize_model_name(left)
    right_name = _normalize_model_name(right)
    return bool(left_name and right_name and left_name == right_name)


def _normalize_idle_pattern(pattern: str) -> str:
    return str(pattern or "").strip().lower()


def _model_requires_idle(name: str, idle_only_patterns: list[str]) -> bool:
    base_name = _normalize_model_name(name).lower()
    if not base_name:
        return False
    for pattern in idle_only_patterns:
        needle = _normalize_idle_pattern(pattern)
        if needle and base_name.startswith(needle):
            return True
    return False


def _idle_override() -> bool | None:
    override = str(os.environ.get("OPENCLAW_MARKET_SENTIMENT_IDLE_OVERRIDE") or "").strip().lower()
    if override in {"1", "true", "idle"}:
        return True
    if override in {"0", "false", "busy"}:
        return False
    return None


def _detect_idle_state(idle_max_load_per_cpu: float | None) -> tuple[bool, str | None]:
    override = _idle_override()
    if override is not None:
        return override, "override"
    if idle_max_load_per_cpu is None:
        return True, None
    try:
        load1 = float(os.getloadavg()[0])
        cpu_count = max(1, int(os.cpu_count() or 1))
        load_per_cpu = load1 / cpu_count
    except (AttributeError, OSError, TypeError, ValueError):
        return False, "load_probe_unavailable"
    detail = f"load1_per_cpu={load_per_cpu:.3f},max={float(idle_max_load_per_cpu):.3f}"
    return load_per_cpu <= float(idle_max_load_per_cpu), detail


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("json_object_not_found")
    return json.loads(text[start : end + 1])


def normalize_classification(raw: dict[str, Any]) -> dict[str, Any]:
    sentiment = clamp(float(raw.get("sentiment", 0.0)), -1.0, 1.0)
    confidence = clamp(float(raw.get("confidence", 0.0)), 0.0, 1.0)
    risk_on = clamp(float(raw.get("risk_on", max(0.0, sentiment))), 0.0, 1.0)
    risk_off = clamp(float(raw.get("risk_off", max(0.0, -sentiment))), 0.0, 1.0)
    regime = str(raw.get("regime", "neutral")).strip().lower() or "neutral"
    if regime not in {"risk_on", "risk_off", "neutral", "mixed"}:
        regime = "neutral"
    drivers = []
    for item in raw.get("drivers") or []:
        text = str(item).strip()
        if text:
            drivers.append(text[:120])
    return {
        "sentiment": round(sentiment, 6),
        "confidence": round(confidence, 6),
        "risk_on": round(risk_on, 6),
        "risk_off": round(risk_off, 6),
        "regime": regime,
        "drivers": drivers[:5],
    }


@dataclass
class ClassifierRuntime:
    provider: str
    requested: str
    resolved: str
    fallback_used: bool
    status: str
    error: str | None = None


def _resolve_candidate_model(
    *,
    requested_model: str,
    fallback_models: list[str],
    idle_only_patterns: list[str],
    idle_max_load_per_cpu: float | None,
    available: list[str],
) -> tuple[str | None, str | None]:
    by_base_name: dict[str, str] = {}
    for model in available:
        if model not in by_base_name:
            by_base_name[model] = model
        base_name = _normalize_model_name(model)
        if base_name and base_name not in by_base_name:
            by_base_name[base_name] = model
    idle_gate_reason = None
    idle_state: tuple[bool, str | None] | None = None
    for candidate in [requested_model, *fallback_models]:
        if _model_requires_idle(candidate, idle_only_patterns):
            if idle_state is None:
                idle_state = _detect_idle_state(idle_max_load_per_cpu)
            is_idle, idle_detail = idle_state
            if not is_idle:
                if _is_same_model(candidate, requested_model):
                    idle_gate_reason = f"requested_model_requires_idle:{idle_detail or 'system_busy'}"
                continue
        resolved = by_base_name.get(candidate) or by_base_name.get(_normalize_model_name(candidate))
        if resolved:
            return resolved, idle_gate_reason
    return None, idle_gate_reason


class OllamaMarketClassifier:
    def __init__(
        self,
        *,
        base_url: str,
        requested_model: str,
        fallback_models: list[str],
        timeout_seconds: int,
        temperature: float,
        num_predict: int,
        keep_alive: str,
        idle_only_patterns: list[str] | None = None,
        idle_max_load_per_cpu: float | None = DEFAULT_IDLE_MAX_LOAD_PER_CPU,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.requested_model = requested_model
        self.fallback_models = list(fallback_models)
        self.timeout_seconds = int(timeout_seconds)
        self.temperature = float(temperature)
        self.num_predict = int(num_predict)
        self.keep_alive = str(keep_alive or "0s")
        self.idle_only_patterns = [
            _normalize_idle_pattern(item) for item in (idle_only_patterns or DEFAULT_IDLE_ONLY_PATTERNS)
            if _normalize_idle_pattern(item)
        ]
        self.idle_max_load_per_cpu = None if idle_max_load_per_cpu is None else float(idle_max_load_per_cpu)
        self._resolved_model: str | None = None
        self._runtime_error: str | None = None
        self._idle_gate_reason: str | None = None

    def _list_models(self) -> list[str]:
        resp = requests.get(f"{self.base_url}/api/tags", timeout=min(self.timeout_seconds, 10))
        resp.raise_for_status()
        data = resp.json()
        models = []
        for item in data.get("models") or []:
            name = str(item.get("name") or "").strip()
            if name:
                models.append(name)
        return models

    def _resolve_available_model(self, available: list[str]) -> str | None:
        resolved, idle_gate_reason = _resolve_candidate_model(
            requested_model=self.requested_model,
            fallback_models=self.fallback_models,
            idle_only_patterns=self.idle_only_patterns,
            idle_max_load_per_cpu=self.idle_max_load_per_cpu,
            available=available,
        )
        self._idle_gate_reason = idle_gate_reason
        return resolved

    def runtime(self) -> ClassifierRuntime:
        if self._resolved_model:
            return ClassifierRuntime(
                provider="ollama",
                requested=self.requested_model,
                resolved=self._resolved_model,
                fallback_used=not _is_same_model(self._resolved_model, self.requested_model),
                status="ok",
            )
        if self._runtime_error:
            return ClassifierRuntime(
                provider="ollama",
                requested=self.requested_model,
                resolved="",
                fallback_used=False,
                status="error",
                error=self._runtime_error,
            )
        try:
            available = self._list_models()
        except Exception as exc:
            self._runtime_error = f"model_list_failed:{exc}"
            return self.runtime()
        self._resolved_model = self._resolve_available_model(available)
        if self._resolved_model is None:
            self._runtime_error = self._idle_gate_reason or "no_requested_or_fallback_model_available"
            return self.runtime()
        return self.runtime()

    def classify(
        self,
        *,
        source_name: str,
        summary: str,
        metrics: dict[str, Any],
        heuristic: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        runtime = self.runtime()
        if runtime.status != "ok":
            return None, {
                "provider": runtime.provider,
                "requested": runtime.requested,
                "resolved": runtime.resolved,
                "fallback_used": runtime.fallback_used,
                "status": runtime.status,
                "error": runtime.error,
                "latency_ms": 0,
            }

        prompt = (
            "You score structured market inputs for a trading support system.\n"
            "Return JSON only with keys: sentiment, confidence, risk_on, risk_off, regime, drivers.\n"
            "Rules:\n"
            "- sentiment: number from -1 to 1.\n"
            "- confidence: number from 0 to 1.\n"
            "- risk_on and risk_off: numbers from 0 to 1.\n"
            "- regime: one of risk_on, risk_off, neutral, mixed.\n"
            "- drivers: array of up to 5 short strings.\n"
            "- No markdown. No prose.\n\n"
            f"source={source_name}\n"
            f"summary={summary}\n"
            f"metrics={json.dumps(metrics, ensure_ascii=False, sort_keys=True)}\n"
            f"heuristic={json.dumps(heuristic, ensure_ascii=False, sort_keys=True)}\n"
        )
        payload = {
            "model": runtime.resolved,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        text = str(data.get("response") or "").strip()
        classification = normalize_classification(_extract_json_object(text))
        meta = {
            "provider": runtime.provider,
            "requested": runtime.requested,
            "resolved": runtime.resolved,
            "fallback_used": runtime.fallback_used,
            "status": "ok",
            "error": None,
            "latency_ms": int((data.get("total_duration") or 0) / 1_000_000),
        }
        return classification, meta


class OpenAICompatibleMarketClassifier:
    def __init__(
        self,
        *,
        base_url: str,
        requested_model: str,
        fallback_models: list[str],
        timeout_seconds: int,
        temperature: float,
        num_predict: int,
        api_key: str | None = None,
        api_key_env: str | None = None,
        idle_only_patterns: list[str] | None = None,
        idle_max_load_per_cpu: float | None = DEFAULT_IDLE_MAX_LOAD_PER_CPU,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.requested_model = requested_model
        self.fallback_models = list(fallback_models)
        self.timeout_seconds = int(timeout_seconds)
        self.temperature = float(temperature)
        self.num_predict = int(num_predict)
        self.api_key = str(api_key or "").strip()
        self.api_key_env = str(api_key_env or "").strip()
        self.idle_only_patterns = [
            _normalize_idle_pattern(item) for item in (idle_only_patterns or DEFAULT_IDLE_ONLY_PATTERNS)
            if _normalize_idle_pattern(item)
        ]
        self.idle_max_load_per_cpu = None if idle_max_load_per_cpu is None else float(idle_max_load_per_cpu)
        self._resolved_model: str | None = None
        self._runtime_error: str | None = None
        self._idle_gate_reason: str | None = None

    def _headers(self) -> dict[str, str]:
        api_key = self.api_key or os.environ.get(self.api_key_env or "", "").strip() or os.environ.get(
            "OPENCLAW_LOCAL_ASSISTANT_API_KEY",
            "local",
        )
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _list_models(self) -> list[str]:
        resp = requests.get(
            f"{self.base_url}/models",
            headers=self._headers(),
            timeout=min(self.timeout_seconds, 10),
        )
        resp.raise_for_status()
        data = resp.json()
        models = []
        for item in data.get("data") or []:
            name = str(item.get("id") or "").strip()
            if name:
                models.append(name)
        return models

    def _resolve_available_model(self, available: list[str]) -> str | None:
        resolved, idle_gate_reason = _resolve_candidate_model(
            requested_model=self.requested_model,
            fallback_models=self.fallback_models,
            idle_only_patterns=self.idle_only_patterns,
            idle_max_load_per_cpu=self.idle_max_load_per_cpu,
            available=available,
        )
        self._idle_gate_reason = idle_gate_reason
        return resolved

    def runtime(self) -> ClassifierRuntime:
        if self._resolved_model:
            return ClassifierRuntime(
                provider="openai_compatible",
                requested=self.requested_model,
                resolved=self._resolved_model,
                fallback_used=not _is_same_model(self._resolved_model, self.requested_model),
                status="ok",
            )
        if self._runtime_error:
            return ClassifierRuntime(
                provider="openai_compatible",
                requested=self.requested_model,
                resolved="",
                fallback_used=False,
                status="error",
                error=self._runtime_error,
            )
        try:
            available = self._list_models()
        except Exception as exc:
            self._runtime_error = f"model_list_failed:{exc}"
            return self.runtime()
        self._resolved_model = self._resolve_available_model(available)
        if self._resolved_model is None:
            self._runtime_error = self._idle_gate_reason or "no_requested_or_fallback_model_available"
            return self.runtime()
        return self.runtime()

    def classify(
        self,
        *,
        source_name: str,
        summary: str,
        metrics: dict[str, Any],
        heuristic: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        runtime = self.runtime()
        if runtime.status != "ok":
            return None, {
                "provider": runtime.provider,
                "requested": runtime.requested,
                "resolved": runtime.resolved,
                "fallback_used": runtime.fallback_used,
                "status": runtime.status,
                "error": runtime.error,
                "latency_ms": 0,
            }

        prompt = (
            "You score structured market inputs for a trading support system.\n"
            "Return JSON only with keys: sentiment, confidence, risk_on, risk_off, regime, drivers.\n"
            "Rules:\n"
            "- sentiment: number from -1 to 1.\n"
            "- confidence: number from 0 to 1.\n"
            "- risk_on and risk_off: numbers from 0 to 1.\n"
            "- regime: one of risk_on, risk_off, neutral, mixed.\n"
            "- drivers: array of up to 5 short strings.\n"
            "- No markdown. No prose.\n\n"
            f"source={source_name}\n"
            f"summary={summary}\n"
            f"metrics={json.dumps(metrics, ensure_ascii=False, sort_keys=True)}\n"
            f"heuristic={json.dumps(heuristic, ensure_ascii=False, sort_keys=True)}\n"
        )
        payload = {
            "model": runtime.resolved,
            "messages": [
                {
                    "role": "system",
                    "content": "Return compact JSON only for a market sentiment classifier.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.num_predict,
            "response_format": {"type": "json_object"},
        }
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        message = ((data.get("choices") or [{}])[0] or {}).get("message") or {}
        text = str(message.get("content") or "").strip()
        if not text and isinstance(message.get("reasoning_content"), str):
            text = message.get("reasoning_content")
        classification = normalize_classification(_extract_json_object(text))
        meta = {
            "provider": runtime.provider,
            "requested": runtime.requested,
            "resolved": runtime.resolved,
            "fallback_used": runtime.fallback_used,
            "status": "ok",
            "error": None,
            "latency_ms": int((time.time() - start) * 1000.0),
        }
        return classification, meta


def build_classifier(config: dict[str, Any]) -> OllamaMarketClassifier | OpenAICompatibleMarketClassifier:
    provider = str(config.get("provider") or "ollama").strip().lower() or "ollama"
    common = {
        "base_url": str(config.get("base_url") or "http://127.0.0.1:11434"),
        "requested_model": str(config.get("requested") or "phi4"),
        "fallback_models": [str(item) for item in config.get("fallbacks") or []],
        "timeout_seconds": int(config.get("timeout_seconds") or 120),
        "temperature": float(config.get("temperature") or 0.0),
        "num_predict": int(config.get("num_predict") or 220),
        "idle_only_patterns": [str(item) for item in config.get("idle_only_patterns") or []] or None,
        "idle_max_load_per_cpu": config.get("idle_max_load_per_cpu"),
    }
    if provider == "openai_compatible":
        return OpenAICompatibleMarketClassifier(
            api_key=str(config.get("api_key") or "").strip() or None,
            api_key_env=str(config.get("api_key_env") or "").strip() or None,
            **common,
        )
    if provider != "ollama":
        raise ValueError(f"unsupported_market_sentiment_provider:{provider}")
    return OllamaMarketClassifier(
        keep_alive=str(config.get("keep_alive") or "0s"),
        **common,
    )
