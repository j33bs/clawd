#!/usr/bin/env python3
"""Model routing/adapters for DALI heavy node."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml


@dataclass
class RoleModel:
    role: str
    model_id: str
    backend: str
    quantization: str
    max_context: int
    notes: str


class OllamaAdapter:
    def __init__(self, base_url: str, request_timeout_s: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_timeout_s = request_timeout_s

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        timeout_s: Optional[int] = None,
        keep_alive: str = "15m",
    ) -> Dict[str, Any]:
        started = time.time()
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": keep_alive,
            "options": {
                "num_predict": int(max_tokens),
                "temperature": float(temperature),
            },
        }
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=timeout_s or self.request_timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message") or {}
        text = str(message.get("content") or data.get("response") or "").strip()
        latency_ms = int((time.time() - started) * 1000)
        return {
            "text": text,
            "tokens_in": int(data.get("prompt_eval_count") or 0),
            "tokens_out": int(data.get("eval_count") or 0),
            "latency_ms": latency_ms,
            "model": model,
            "backend": "ollama",
        }

    def warmup(self, model: str) -> Dict[str, Any]:
        return self.generate(model=model, prompt="Reply with OK.", max_tokens=8, temperature=0.0, timeout_s=90)

    def list_models(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/api/tags", timeout=min(self.request_timeout_s, 12))
        resp.raise_for_status()
        data = resp.json()
        models = set()
        for row in data.get("models") or []:
            name = str(row.get("name") or "").strip()
            if name:
                models.add(name)
        return {"models": models}

    def health_model(self, model: str, available_models: Optional[set[str]] = None) -> Dict[str, Any]:
        try:
            available = available_models if available_models is not None else self.list_models().get("models", set())
            found = model in available
            return {
                "status": "ok" if found else "error",
                "model": model,
                "available": bool(found),
                "error": None if found else "model_not_present",
            }
        except Exception as exc:
            return {"status": "error", "model": model, "error": str(exc)}


class HeavyNodeRouter:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = Path(manifest_path)
        self.manifest = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
        server = self.manifest.get("server", {})
        self.host = str(server.get("host", "0.0.0.0"))
        self.port = int(server.get("port", 18891))

        self.roles: Dict[str, RoleModel] = {}
        for role in ("hint", "answer", "code"):
            cfg = (self.manifest.get("roles") or {}).get(role) or {}
            if not cfg:
                continue
            self.roles[role] = RoleModel(
                role=role,
                model_id=str(cfg.get("model_id", "")).strip(),
                backend=str(cfg.get("backend", "ollama")).strip().lower(),
                quantization=str(cfg.get("quantization", "")).strip(),
                max_context=int(cfg.get("max_context", 4096)),
                notes=str(cfg.get("notes", "")).strip(),
            )

        ollama_url = str(
            self.manifest.get("ollama", {}).get("base_url")
            or __import__("os").environ.get("DALI_OLLAMA_URL")
            or "http://127.0.0.1:11434"
        )
        self.ollama = OllamaAdapter(base_url=ollama_url, request_timeout_s=int(__import__("os").environ.get("DALI_REQUEST_TIMEOUT_S", "180")))

    def role_config(self, role: str) -> RoleModel:
        if role not in self.roles:
            raise RuntimeError(f"role not configured: {role}")
        return self.roles[role]

    def warmup(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for role, cfg in self.roles.items():
            try:
                if cfg.backend == "ollama":
                    res = self.ollama.warmup(cfg.model_id)
                else:
                    raise RuntimeError(f"unsupported backend: {cfg.backend}")
                out[role] = {"status": "ok", "latency_ms": res.get("latency_ms"), "model": cfg.model_id, "backend": cfg.backend}
            except Exception as exc:
                out[role] = {"status": "error", "error": str(exc), "model": cfg.model_id, "backend": cfg.backend}
        return out

    def health(self) -> Dict[str, Any]:
        models = {}
        available_models: set[str] = set()
        tags_error: Optional[str] = None
        try:
            available_models = self.ollama.list_models().get("models", set())
        except Exception as exc:
            tags_error = str(exc)
        for role, cfg in self.roles.items():
            if cfg.backend == "ollama":
                if tags_error:
                    models[role] = {"status": "error", "model": cfg.model_id, "error": f"ollama_tags_failed: {tags_error}"}
                else:
                    models[role] = self.ollama.health_model(cfg.model_id, available_models=available_models)
            else:
                models[role] = {"status": "error", "error": f"unsupported backend: {cfg.backend}", "model": cfg.model_id}
        status = "ok" if all((m.get("status") == "ok") for m in models.values()) else "degraded"
        return {"status": status, "models": models}

    def run_role(
        self,
        *,
        role: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        mode: str,
    ) -> Dict[str, Any]:
        cfg = self.role_config(role)
        max_tokens = max(8, min(2048, int(max_tokens)))
        if cfg.backend == "ollama":
            return self.ollama.generate(
                model=cfg.model_id,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                keep_alive="20m" if role in {"answer", "code"} else "10m",
            )
        raise RuntimeError(f"unsupported backend: {cfg.backend}")
