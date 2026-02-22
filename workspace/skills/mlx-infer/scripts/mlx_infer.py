#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from pathlib import Path


def emit(payload, code=0):
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()
    raise SystemExit(code)


def load_config(path):
    if not path:
        return {}
    cfg_path = Path(path)
    if not cfg_path.exists():
        emit({
            "ok": False,
            "error": {
                "type": "INVALID_ARGS",
                "message": f"config not found: {cfg_path}",
                "details": {"config": str(cfg_path)},
            },
        }, 1)
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        emit({
            "ok": False,
            "error": {
                "type": "INVALID_ARGS",
                "message": f"invalid config JSON: {exc}",
                "details": {"config": str(cfg_path)},
            },
        }, 1)


def map_error(exc):
    text = str(exc).lower()
    if "out of memory" in text or "oom" in text or "cannot allocate memory" in text:
        return "OOM"
    if "not found" in text or "no such file" in text or "cannot find" in text:
        return "MODEL_NOT_FOUND"
    if isinstance(exc, ValueError):
        return "INVALID_ARGS"
    return "RUNTIME"


def approx_tokens(text):
    parts = [p for p in text.split() if p]
    return max(1, len(parts))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model")
    parser.add_argument("--max_tokens", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--model_path")
    parser.add_argument("--config")
    args = parser.parse_args()

    if args.max_tokens is not None and args.max_tokens < 1:
        emit({
            "ok": False,
            "error": {"type": "INVALID_ARGS", "message": "max_tokens must be >= 1", "details": {}},
        }, 1)
    if args.temperature is not None and (args.temperature < 0 or args.temperature > 2):
        emit({
            "ok": False,
            "error": {"type": "INVALID_ARGS", "message": "temperature must be between 0 and 2", "details": {}},
        }, 1)

    cfg_path = args.config or os.environ.get("OPENCLAW_SKILL_CONFIG")
    cfg = load_config(cfg_path)

    model_name = args.model or cfg.get("default_model")
    if not model_name:
        emit({
            "ok": False,
            "error": {
                "type": "INVALID_ARGS",
                "message": "model is required (arg --model or config.default_model)",
                "details": {},
            },
        }, 1)

    model_path = args.model_path or cfg.get("model_path")
    model_ref = model_name
    if model_path:
        model_ref = str(Path(model_path) / model_name)

    max_tokens = args.max_tokens if args.max_tokens is not None else 256
    temperature = args.temperature if args.temperature is not None else 0.1

    try:
        from mlx_lm import generate, load  # type: ignore
    except Exception as exc:
        emit({
            "ok": False,
            "error": {
                "type": "RUNTIME",
                "message": f"mlx_lm import failed: {exc}",
                "details": {},
            },
        }, 1)

    start = time.perf_counter()
    try:
        model, tokenizer = load(model_ref)
        completion = generate(
            model,
            tokenizer,
            prompt=args.prompt,
            max_tokens=max_tokens,
            temp=temperature,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        tokens_used = None
        estimated = False
        try:
            if hasattr(tokenizer, "encode"):
                encoded = tokenizer.encode(completion)
                tokens_used = int(len(encoded))
            else:
                raise ValueError("tokenizer does not expose encode")
        except Exception:
            tokens_used = approx_tokens(completion)
            estimated = True

        emit(
            {
                "ok": True,
                "completion": completion,
                "latency_ms": latency_ms,
                "tokens_used": int(tokens_used),
                "tokens_used_estimated": estimated,
            },
            0,
        )
    except Exception as exc:
        kind = map_error(exc)
        emit(
            {
                "ok": False,
                "error": {
                    "type": kind,
                    "message": str(exc),
                    "details": {"model": model_ref},
                },
            },
            1,
        )


if __name__ == "__main__":
    main()
