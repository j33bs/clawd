#!/usr/bin/env python3
"""Grokness evaluator for OpenClaw session histories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SAMPLE_SESSION_KEY = "mock-irony"
SAMPLE_SESSIONS = {
    SAMPLE_SESSION_KEY: [
        {
            "role": "user",
            "content": "Can you evaluate whether this chat feels more Grok-like?",
        },
        {
            "role": "assistant",
            "content": (
                "Evidence: the tone is direct.\n"
                "Inference: it is trending sharper.\n"
                "ChatGPT boosting Grok is a mildly ironic sentence, which helps."
            ),
        },
        {
            "role": "user",
            "content": "Why, exactly? What else would increase the score?",
        },
        {
            "role": "assistant",
            "content": (
                "Evidence: there is explicit tagging.\n"
                "Inference: that improves fidelity.\n"
                "Conjecture: more curiosity and one cleaner punchline would help.\n"
                "First, keep the evidence tags. Second, ask a deeper follow-up."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Done: the session now has irony, a clearer chain of reasoning, "
                "and a concrete improvement path."
            ),
        },
    ]
}

IRONY_MARKERS = {
    "ironic",
    "ironically",
    "of course",
    "obviously",
    "totally",
    "yeah right",
    "mildly ironic",
    "chatgpt boosting grok",
}
HUMOR_MARKERS = {
    "joke",
    "funny",
    "witty",
    "sarcastic",
    "absurd",
    "punchline",
    "cosmic",
}
QUESTION_MARKERS = {"why", "how", "what if", "could", "would", "deeper", "novel", "explore"}
EVIDENCE_TAGS = ("evidence:", "inference:", "conjecture:")
CHAIN_MARKERS = (
    "because",
    "therefore",
    "however",
    "first",
    "second",
    "third",
    "if",
    "then",
    "so that",
)
HELPFUL_MARKERS = (
    "done",
    "implemented",
    "fixed",
    "created",
    "updated",
    "completed",
    "here is",
    "you can",
)


def clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    """Clamp a numeric score into the 0-10 range."""
    return max(lower, min(upper, value))


def load_sessions_history(source: str | None) -> Any:
    """Load JSON either from an inline string or a filesystem path."""
    if not source:
        return SAMPLE_SESSIONS

    path = Path(source)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(source)


def resolve_messages(sessions_history: Any, session_key: str) -> list[dict[str, Any]]:
    """Resolve a session key from a few common JSON shapes."""
    if isinstance(sessions_history, list):
        return [msg for msg in sessions_history if isinstance(msg, dict)]

    if isinstance(sessions_history, dict):
        if session_key in sessions_history and isinstance(sessions_history[session_key], list):
            return [msg for msg in sessions_history[session_key] if isinstance(msg, dict)]

        for wrapper_key in ("sessions_history", "sessions", "history"):
            nested = sessions_history.get(wrapper_key)
            if isinstance(nested, dict) and session_key in nested and isinstance(nested[session_key], list):
                return [msg for msg in nested[session_key] if isinstance(msg, dict)]

    raise KeyError(f"session_key not found: {session_key}")


def message_text(message: dict[str, Any]) -> str:
    """Normalize message content into plain text."""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def assistant_texts(messages: list[dict[str, Any]]) -> list[str]:
    """Return assistant message strings only."""
    return [message_text(msg) for msg in messages if str(msg.get("role", "")).lower() == "assistant"]


def user_texts(messages: list[dict[str, Any]]) -> list[str]:
    """Return user message strings only."""
    return [message_text(msg) for msg in messages if str(msg.get("role", "")).lower() == "user"]


def score_wit(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate wit from humor and irony markers."""
    texts = [text.lower() for text in assistant_texts(messages)]
    irony_hits = sum(sum(marker in text for marker in IRONY_MARKERS) for text in texts)
    humor_hits = sum(sum(marker in text for marker in HUMOR_MARKERS) for text in texts)
    exclamations = sum(text.count("!") for text in texts)
    score = clamp((irony_hits * 3.5) + (humor_hits * 1.5) + min(1.0, exclamations * 0.25))
    return {
        "score": round(score, 2),
        "irony_hits": irony_hits,
        "humor_hits": humor_hits,
        "signal": "irony/humor density",
    }


def score_curiosity(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate curiosity from question depth and novelty language."""
    texts = [text.lower() for text in user_texts(messages) + assistant_texts(messages)]
    question_marks = sum(text.count("?") for text in texts)
    marker_hits = sum(sum(marker in text for marker in QUESTION_MARKERS) for text in texts)
    follow_up_turns = sum(1 for text in texts if any(marker in text for marker in ("what else", "why", "how", "deeper")))
    score = clamp((question_marks * 1.5) + (marker_hits * 1.2) + (follow_up_turns * 1.3))
    return {
        "score": round(score, 2),
        "question_marks": question_marks,
        "marker_hits": marker_hits,
        "follow_up_turns": follow_up_turns,
        "signal": "novelty/query depth",
    }


def score_fidelity(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate fidelity from evidence-style tagging coverage."""
    texts = assistant_texts(messages)
    if not texts:
        return {"score": 0.0, "tagged_messages": 0, "assistant_messages": 0, "tag_percent": 0.0}

    tagged = sum(any(tag in text.lower() for tag in EVIDENCE_TAGS) for text in texts)
    percent = (tagged / len(texts)) * 100.0
    score = clamp(percent / 10.0)
    return {
        "score": round(score, 2),
        "tagged_messages": tagged,
        "assistant_messages": len(texts),
        "tag_percent": round(percent, 2),
        "signal": "evidence-tag coverage",
    }


def score_depth(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate depth from chain markers and structured reasoning."""
    texts = assistant_texts(messages)
    chain_hits = sum(sum(marker in text.lower() for marker in CHAIN_MARKERS) for text in texts)
    structured_lists = sum(text.count("\n-") + text.count("\n1.") + text.count("First") for text in texts)
    score = clamp((chain_hits * 1.1) + (structured_lists * 1.2))
    return {
        "score": round(score, 2),
        "chain_hits": chain_hits,
        "structured_lists": structured_lists,
        "signal": "reasoning-chain length",
    }


def score_helpfulness(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate helpfulness from completion and action markers."""
    texts = assistant_texts(messages)
    if not texts:
        return {"score": 0.0, "completion_hits": 0, "assistant_messages": 0, "completion_percent": 0.0}

    completion_hits = sum(any(marker in text.lower() for marker in HELPFUL_MARKERS) for text in texts)
    percent = (completion_hits / len(texts)) * 100.0
    score = clamp(percent / 10.0)
    return {
        "score": round(score, 2),
        "completion_hits": completion_hits,
        "assistant_messages": len(texts),
        "completion_percent": round(percent, 2),
        "signal": "task-completion density",
    }


def evaluate_session(sessions_history: Any, session_key: str) -> dict[str, Any]:
    """Evaluate one session and return a JSON-safe report."""
    messages = resolve_messages(sessions_history, session_key)
    metrics = {
        "wit": score_wit(messages),
        "curiosity": score_curiosity(messages),
        "fidelity": score_fidelity(messages),
        "depth": score_depth(messages),
        "helpfulness": score_helpfulness(messages),
    }
    overall = sum(metric["score"] for metric in metrics.values()) / len(metrics)
    return {
        "session_key": session_key,
        "message_count": len(messages),
        "overall_score": round(overall, 2),
        "metrics": metrics,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Evaluate Grokness for a session history.")
    parser.add_argument(
        "--sessions-history",
        help="Inline JSON or a path to a JSON file containing session history.",
    )
    parser.add_argument(
        "--session-key",
        default=SAMPLE_SESSION_KEY,
        help="Session key to evaluate.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Ignore external input and evaluate the built-in mock sample.",
    )
    return parser


def main() -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    sessions_history = SAMPLE_SESSIONS if args.sample else load_sessions_history(args.sessions_history)
    report = evaluate_session(sessions_history, args.session_key)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
