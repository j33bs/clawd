#!/usr/bin/env python3
"""Research Wanderer with deterministic novelty + duplicate suppression."""

from __future__ import annotations

import json
import math
import os
import random
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent
RESEARCH_DIR = WORKSPACE_DIR / "research"
GOVERNANCE_DIR = WORKSPACE_DIR / "governance"

QUEUE_FILE = RESEARCH_DIR / "queue.json"
FINDINGS_FILE = RESEARCH_DIR / "findings.json"
LOG_FILE = RESEARCH_DIR / "wander_log.md"
TOPICS_FILE = RESEARCH_DIR / "TOPICS.md"
OPEN_QUESTIONS_FILE = GOVERNANCE_DIR / "OPEN_QUESTIONS.md"

DEFAULT_TOPICS = [
    "predictive processing vs next token prediction",
    "AI consciousness measurement integrated information",
    "multi-agent collective cognition emergence",
    "LLM world models internal representations",
    "embodied cognition symbol grounding AI",
    "AI memory consolidation sleep replay",
    "distributed AI identity continuity",
    "alien intelligence detection framework",
]

BUILTIN_PROMPTS = [
    "What measurable prediction would falsify this claim?",
    "What hidden variable could explain the same observation?",
    "Where does this break under adversarial conditions?",
    "What is the smallest runnable experiment?",
    "What would a null result look like and how would we log it?",
]

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "what", "would", "does", "mean",
    "have", "into", "about", "your", "their", "then", "when", "where", "which", "while", "were",
    "been", "more", "most", "some", "such", "than", "very", "will", "just", "into", "across",
    "should", "could", "between", "being", "them", "they", "there", "here", "over", "under",
}


@dataclass
class NoveltyDecision:
    accepted: bool
    overlap_max: float
    similarity_max: float
    reason: str


def _env_truthy(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def researcher_mode_enabled() -> bool:
    """Feature flag for novelty/duplicate suppression behavior."""
    return _env_truthy("OPENCLAW_WANDERER_RESEARCHER", "0")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc() -> str:
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_topics_file(path: Path = TOPICS_FILE) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Research Seed Topics\n\n"
        "- active inference\n"
        "- global workspace theory\n"
        "- neuromodulation and gain control\n"
        "- allostasis and predictive regulation\n"
        "- collective intelligence and stigmergy\n"
        "- mechanistic interpretability\n"
        "- memory consolidation and replay\n"
        "- social epistemology and calibration\n",
        encoding="utf-8",
    )


def load_topics(path: Path = TOPICS_FILE) -> list[str]:
    ensure_topics_file(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    topics: list[str] = []
    for line in lines:
        m = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if m:
            topics.append(m.group(1).strip())
    return topics


def load_queue(path: Path = QUEUE_FILE) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"topics": list(DEFAULT_TOPICS), "completed": [], "last_wander": None}


def save_queue(q: dict[str, Any], path: Path = QUEUE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(q, indent=2) + "\n", encoding="utf-8")


def load_findings(path: Path = FINDINGS_FILE) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"findings": [], "questions_generated": []}


def save_findings(findings: dict[str, Any], path: Path = FINDINGS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")


def tokenize_keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in tokens if len(t) >= 3 and t not in STOPWORDS}


def overlap_ratio(a: str, b: str) -> float:
    ka = tokenize_keywords(a)
    kb = tokenize_keywords(b)
    if not ka and not kb:
        return 0.0
    return len(ka & kb) / max(1, len(ka | kb))


def cosine_similarity(a: str, b: str) -> float:
    ta = tokenize_keywords(a)
    tb = tokenize_keywords(b)
    if not ta or not tb:
        return 0.0
    va: dict[str, float] = {}
    vb: dict[str, float] = {}
    for tok in ta:
        va[tok] = va.get(tok, 0.0) + 1.0
    for tok in tb:
        vb[tok] = vb.get(tok, 0.0) + 1.0
    dot = sum(va.get(tok, 0.0) * vb.get(tok, 0.0) for tok in (set(va) | set(vb)))
    norm_a = math.sqrt(sum(x * x for x in va.values()))
    norm_b = math.sqrt(sum(x * x for x in vb.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def parse_wander_log_questions(path: Path = LOG_FILE, last_n: int = 20) -> list[str]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("|"):
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 2:
                continue
            if parts[0].lower() in {"date_utc", "date"}:
                continue
            if all(set(p) <= {"-", ":"} for p in parts):
                continue
            rows.append(parts[1])
        elif line.strip().lower().startswith("generated question:"):
            _, _, question = line.partition(":")
            question = question.strip()
            if question:
                rows.append(question)
    return rows[-last_n:]


def _extract_date(line: str) -> datetime | None:
    m = re.search(r"(20\d\d-\d\d-\d\d)", line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_open_questions(path: Path = OPEN_QUESTIONS_FILE, *, days: int = 7, last_k: int = 20) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    cutoff = now_utc() - timedelta(days=days)
    has_dates = False
    for line in lines:
        if "?" not in line:
            continue
        date_obj = _extract_date(line)
        if date_obj is not None:
            has_dates = True
            if date_obj < cutoff:
                continue
        q = line.strip().lstrip("-*0123456789. ")
        if "?" in q:
            out.append(q)
    if not has_dates:
        return out[-last_k:]
    return out[-last_k:]


def load_recent_questions(log_path: Path = LOG_FILE, oq_path: Path = OPEN_QUESTIONS_FILE) -> list[str]:
    return parse_wander_log_questions(log_path, last_n=20) + parse_open_questions(oq_path, days=7, last_k=20)


def evaluate_novelty(candidate: str, recent_questions: list[str]) -> NoveltyDecision:
    overlap_max = 0.0
    similarity_max = 0.0
    for prior in recent_questions:
        overlap_max = max(overlap_max, overlap_ratio(candidate, prior))
    for prior in recent_questions[-10:]:
        similarity_max = max(similarity_max, cosine_similarity(candidate, prior))
    if overlap_max > 0.5:
        return NoveltyDecision(False, overlap_max, similarity_max, "rejected_overlap")
    if similarity_max > 0.7:
        return NoveltyDecision(False, overlap_max, similarity_max, "rejected_similarity")
    return NoveltyDecision(True, overlap_max, similarity_max, "accepted")


def pick_open_loop(oq_path: Path = OPEN_QUESTIONS_FILE) -> str:
    qs = parse_open_questions(oq_path, days=7, last_k=20)
    return qs[-1] if qs else "open loop unavailable"


def generate_candidate_question(topic: str, *, seed_topic: str, open_loop: str, random_prompt: str) -> str:
    return (
        f"How might {topic} intersect with {seed_topic}, given open loop: {open_loop}? "
        f"{random_prompt}"
    )


def select_question(
    topic: str,
    recent_questions: list[str],
    *,
    rng: random.Random,
    topics_path: Path = TOPICS_FILE,
    oq_path: Path = OPEN_QUESTIONS_FILE,
    max_attempts: int = 5,
) -> tuple[str, dict[str, Any]]:
    seed_topics = load_topics(topics_path)
    open_loop = pick_open_loop(oq_path)

    best_q = ""
    best_score = -1.0
    best_meta: NoveltyDecision | None = None
    best_seed = ""

    for attempt in range(max_attempts):
        seed_topic = seed_topics[attempt % len(seed_topics)] if seed_topics else "active inference"
        prompt = BUILTIN_PROMPTS[rng.randrange(len(BUILTIN_PROMPTS))]
        candidate = generate_candidate_question(topic, seed_topic=seed_topic, open_loop=open_loop, random_prompt=prompt)
        decision = evaluate_novelty(candidate, recent_questions)
        score = (1.0 - decision.overlap_max) + (1.0 - decision.similarity_max)
        if score > best_score:
            best_score = score
            best_q = candidate
            best_meta = decision
            best_seed = seed_topic
        if decision.accepted:
            return candidate, {
                "attempts": attempt + 1,
                "overlap_max": round(decision.overlap_max, 3),
                "similarity_max": round(decision.similarity_max, 3),
                "seed_topic": seed_topic,
                "open_loop": open_loop,
                "novelty_reason": decision.reason,
            }

    assert best_meta is not None
    return best_q, {
        "attempts": max_attempts,
        "overlap_max": round(best_meta.overlap_max, 3),
        "similarity_max": round(best_meta.similarity_max, 3),
        "seed_topic": best_seed,
        "open_loop": open_loop,
        "novelty_reason": f"fallback_best_of_{max_attempts}",
    }


def ensure_log_table(path: Path = LOG_FILE) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Wander Log\n\n"
        "| date_utc | question | overlap_max | similarity_max | seed_topic | attempts |\n"
        "|---|---|---:|---:|---|---:|\n",
        encoding="utf-8",
    )


def append_wander_log(
    question: str,
    *,
    overlap_max: float,
    similarity_max: float,
    seed_topic: str,
    attempts: int,
    path: Path = LOG_FILE,
) -> None:
    ensure_log_table(path)
    safe_question = question.replace("|", "\\|").strip()
    safe_seed = (seed_topic or "").replace("|", "\\|").strip()
    row = (
        f"| {iso_utc()} | {safe_question} | {overlap_max:.3f} | {similarity_max:.3f} | "
        f"{safe_seed} | {int(attempts)} |\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(row)


def append_legacy_wander_log(content: str, path: Path = LOG_FILE) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {now_utc().strftime('%Y-%m-%d %H:%M')}\n\n{content}\n\n---\n\n")


def add_topic(topic: str) -> None:
    q = load_queue()
    if topic not in q["topics"] and topic not in q["completed"]:
        q["topics"].append(topic)
        save_queue(q)
        print(f"✅ Added: {topic}")
    else:
        print(f"📝 Already in queue: {topic}")


def show_queue() -> None:
    q = load_queue()
    print("\n📚 Research Queue:")
    for i, t in enumerate(q["topics"], 1):
        print(f"  {i}. {t}")


def show_status() -> None:
    f = load_findings()
    q = load_queue()
    print("\n🧠 Research Wanderer Status")
    print(f"   Topics in queue: {len(q['topics'])}")
    print(f"   Topics completed: {len(q['completed'])}")
    print(f"   Findings recorded: {len(f['findings'])}")
    print(f"   Questions generated: {len(f['questions_generated'])}")
    if q.get("last_wander"):
        print(f"   Last wander: {q['last_wander']}")


def do_wander(*, seed: int = 17) -> int:
    q = load_queue()
    if not q["topics"]:
        print("No topics to research. Add some!")
        return 1

    topic = q["topics"].pop(0)
    q["completed"].append(topic)
    q["last_wander"] = iso_utc()

    findings = load_findings()
    findings["findings"].append({"topic": topic, "finding": f"Explored: {topic}", "timestamp": iso_utc()})

    if researcher_mode_enabled():
        recent = load_recent_questions()
        rng = random.Random(seed)
        question, meta = select_question(topic, recent, rng=rng)

        findings["questions_generated"].append(
            {
                "question": question,
                "from_topic": topic,
                "timestamp": iso_utc(),
                "overlap_max": meta["overlap_max"],
                "similarity_max": meta["similarity_max"],
                "seed_topic": meta["seed_topic"],
                "attempts": meta["attempts"],
                "novelty_reason": meta["novelty_reason"],
            }
        )

        save_queue(q)
        save_findings(findings)
        append_wander_log(
            question,
            overlap_max=float(meta["overlap_max"]),
            similarity_max=float(meta["similarity_max"]),
            seed_topic=str(meta["seed_topic"]),
            attempts=int(meta["attempts"]),
        )

        print(f"✅ Wandered: {topic}")
        print(f"   New question: {question}")
        print(
            f"   Novelty: overlap={meta['overlap_max']:.3f}, similarity={meta['similarity_max']:.3f}, "
            f"reason={meta['novelty_reason']}, attempts={meta['attempts']}"
        )
    else:
        # Legacy/default behavior: deterministic single question, no novelty filter.
        question = f"What would {topic} mean for TACTI(C)-R?"
        findings["questions_generated"].append(
            {
                "question": question,
                "from_topic": topic,
                "timestamp": iso_utc(),
            }
        )
        save_queue(q)
        save_findings(findings)
        append_legacy_wander_log(f"Wandered: {topic}\n\nGenerated question: {question}")
        print(f"✅ Wandered: {topic}")
        print(f"   New question: {question}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        show_status()
        return 0

    cmd = args[0]
    if cmd == "add":
        if len(args) < 2:
            print("Usage: research_wanderer.py add 'topic'")
            return 1
        add_topic(args[1])
        return 0
    if cmd == "queue":
        show_queue()
        return 0
    if cmd == "status":
        show_status()
        return 0
    if cmd == "wander":
        return do_wander()
    if cmd == "init":
        ensure_topics_file()
        q = load_queue()
        if not q["topics"]:
            q["topics"] = list(DEFAULT_TOPICS)
            save_queue(q)
        ensure_log_table()
        print("✅ Initialized research wanderer")
        return 0

    print(f"Unknown command: {cmd}")
    print("Commands: add, queue, status, wander, init")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
