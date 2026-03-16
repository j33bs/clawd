#!/usr/bin/env python3
"""DALI Heavy Node HTTP server."""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from workspace.runtime.heavy_node.hint_guard import enforce_hint_only
from workspace.runtime.heavy_node.logging import HeavyNodeTelemetry
from workspace.runtime.heavy_node.routing import HeavyNodeRouter


def _estimate_tokens(text: str) -> int:
    return max(0, len(str(text or "")) // 4)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class HintRequest(BaseModel):
    problem: str = Field(min_length=1, max_length=6000)
    attempt: Optional[str] = Field(default=None, max_length=6000)
    budget_tokens: int = Field(default=60, ge=16, le=160)
    max_lines: int = Field(default=6, ge=2, le=6)
    mode: Optional[str] = Field(default="fast", pattern="^(fast|reason)$")


class HintResponse(BaseModel):
    text: str
    model: str
    backend: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    hint_only: bool


class AnswerRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=24000)
    context: Optional[List[str]] = Field(default=None, max_length=12)
    max_tokens: int = Field(default=512, ge=32, le=2048)
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    mode: Optional[str] = Field(default="fast", pattern="^(fast|reason)$")


class AnswerResponse(BaseModel):
    text: str
    model: str
    backend: str
    latency_ms: int
    tokens_in: int
    tokens_out: int


class CodeFile(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    content: str = Field(default="", max_length=16000)


class CodeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=24000)
    files: Optional[List[CodeFile]] = Field(default=None, max_length=8)
    max_tokens: int = Field(default=768, ge=64, le=2048)


class HealthResponse(BaseModel):
    status: str
    models: dict
    uptime_s: int
    warmup: Dict[str, Any]


def create_app(router: Optional[HeavyNodeRouter] = None) -> FastAPI:
    app = FastAPI(title="DALI Heavy Node", version="1.0.0")
    manifest_path = os.environ.get("DALI_HEAVY_NODE_MANIFEST", "workspace/runtime/heavy_node/model_manifest.yaml")
    app.state.router = router or HeavyNodeRouter(manifest_path=manifest_path)
    app.state.telemetry = HeavyNodeTelemetry()
    app.state.started_at = time.time()
    app.state.warmup = {
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "roles": {},
    }

    @app.on_event("startup")
    def _startup() -> None:
        disable = str(os.environ.get("DALI_HEAVY_NODE_DISABLE_STARTUP_WARMUP", "0")).strip().lower()
        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if disable in {"1", "true", "yes", "on"}:
            app.state.warmup = {
                "status": "disabled",
                "started_at": started_at,
                "completed_at": started_at,
                "roles": {},
            }
            return
        app.state.warmup = {
            "status": "warming",
            "started_at": started_at,
            "completed_at": None,
            "roles": {},
        }

        def _warmup_background() -> None:
            try:
                warm = app.state.router.warmup()
                warm_status = "ok" if all((row.get("status") == "ok") for row in warm.values()) else "degraded"
                app.state.warmup = {
                    "status": warm_status,
                    "started_at": started_at,
                    "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "roles": warm,
                }
                # Warmup telemetry entries without prompt content.
                for role, row in warm.items():
                    app.state.telemetry.write(
                        {
                            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "endpoint": "/warmup",
                            "role": role,
                            "model": row.get("model"),
                            "backend": row.get("backend"),
                            "tokens_in": 0,
                            "tokens_out": 0,
                            "latency_ms": int(row.get("latency_ms") or 0),
                            "client_ip": "local",
                            "hint_only": False,
                            "mode": "startup",
                            "status": row.get("status", "ok"),
                        }
                    )
            except Exception as exc:
                app.state.warmup = {
                    "status": "error",
                    "started_at": started_at,
                    "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "roles": {},
                    "error": str(exc),
                }
                app.state.telemetry.write(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "endpoint": "/warmup",
                        "role": "warmup",
                        "model": None,
                        "backend": None,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "latency_ms": 0,
                        "client_ip": "local",
                        "hint_only": False,
                        "mode": "startup",
                        "status": "error",
                    }
                )

        threading.Thread(target=_warmup_background, name="dali-heavy-warmup", daemon=True).start()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        h = app.state.router.health()
        warmup = dict(app.state.warmup)
        status = h.get("status", "degraded")
        if warmup.get("status") in {"degraded", "error"} and status == "ok":
            status = "degraded"
        return HealthResponse(
            status=status,
            models=h.get("models", {}),
            uptime_s=int(time.time() - app.state.started_at),
            warmup=warmup,
        )

    @app.post("/hint", response_model=HintResponse)
    def hint(req: HintRequest, request: Request) -> HintResponse:
        prompt = (
            "You are a strict hint engine. Provide only a short hint, no full solution. "
            f"Limit response to <= {req.max_lines} lines and about {req.budget_tokens} tokens.\n\n"
            f"Problem:\n{req.problem}\n\n"
            f"Attempt:\n{req.attempt or '(none)'}\n"
        )
        started = time.time()
        try:
            raw = app.state.router.run_role(role="hint", prompt=prompt, max_tokens=req.budget_tokens, temperature=0.2, mode=req.mode or "fast")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"hint runner error: {exc}") from exc

        safe_text, _ = enforce_hint_only(
            raw.get("text", ""),
            problem=req.problem,
            budget_tokens=req.budget_tokens,
            max_lines=req.max_lines,
        )
        latency_ms = int((time.time() - started) * 1000)
        tokens_in = int(raw.get("tokens_in") or _estimate_tokens(prompt))
        tokens_out = min(req.budget_tokens, _estimate_tokens(safe_text))

        app.state.telemetry.write(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "endpoint": "/hint",
                "role": "hint",
                "model": raw.get("model"),
                "backend": raw.get("backend"),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
                "client_ip": _client_ip(request),
                "hint_only": True,
                "mode": req.mode or "fast",
                "status": "ok",
            }
        )

        return HintResponse(
            text=safe_text,
            model=str(raw.get("model") or "unknown"),
            backend=str(raw.get("backend") or "unknown"),
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            hint_only=True,
        )

    @app.post("/answer", response_model=AnswerResponse)
    def answer(req: AnswerRequest, request: Request) -> AnswerResponse:
        context_text = "\n\n".join(req.context or [])
        prompt = req.prompt if not context_text else f"Context:\n{context_text}\n\nPrompt:\n{req.prompt}"

        started = time.time()
        try:
            out = app.state.router.run_role(
                role="answer",
                prompt=prompt,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                mode=req.mode or "fast",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"answer runner error: {exc}") from exc

        latency_ms = int((time.time() - started) * 1000)
        tokens_in = int(out.get("tokens_in") or _estimate_tokens(prompt))
        tokens_out = int(out.get("tokens_out") or _estimate_tokens(out.get("text", "")))

        app.state.telemetry.write(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "endpoint": "/answer",
                "role": "answer",
                "model": out.get("model"),
                "backend": out.get("backend"),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
                "client_ip": _client_ip(request),
                "hint_only": False,
                "mode": req.mode or "fast",
                "status": "ok",
            }
        )

        return AnswerResponse(
            text=str(out.get("text") or "").strip(),
            model=str(out.get("model") or "unknown"),
            backend=str(out.get("backend") or "unknown"),
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    @app.post("/code", response_model=AnswerResponse)
    def code(req: CodeRequest, request: Request) -> AnswerResponse:
        files_blob = ""
        if req.files:
            parts = []
            for f in req.files:
                path = f.path
                content = f.content
                parts.append(f"FILE: {path}\n{content}")
            files_blob = "\n\n".join(parts)
        prompt = req.prompt if not files_blob else f"{req.prompt}\n\n{files_blob}"

        started = time.time()
        try:
            out = app.state.router.run_role(role="code", prompt=prompt, max_tokens=req.max_tokens, temperature=0.2, mode="reason")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"code runner error: {exc}") from exc

        latency_ms = int((time.time() - started) * 1000)
        tokens_in = int(out.get("tokens_in") or _estimate_tokens(prompt))
        tokens_out = int(out.get("tokens_out") or _estimate_tokens(out.get("text", "")))

        app.state.telemetry.write(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "endpoint": "/code",
                "role": "code",
                "model": out.get("model"),
                "backend": out.get("backend"),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
                "client_ip": _client_ip(request),
                "hint_only": False,
                "mode": "reason",
                "status": "ok",
            }
        )

        return AnswerResponse(
            text=str(out.get("text") or "").strip(),
            model=str(out.get("model") or "unknown"),
            backend=str(out.get("backend") or "unknown"),
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    return app


app = create_app()
