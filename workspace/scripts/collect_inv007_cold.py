#!/usr/bin/env python3
"""
INV-007 Cold Dispatch — workspace/scripts/collect_inv007_cold.py

Ask beings the INV-007 question with NO corpus context (cold).
Compare responses to the corpus centroid answer from oracle.py.
File results as CLXIX.

INV-007 question:
  "what is the relationship between silence and governance in this system?"

Oracle result (corpus centroid):
  - Claude Code + ChatGPT co-centroids (40% each in top-10 results)
  - Top section: §CVI "The Architect's Silence" — "absence is never just absence"
  - Silent in corpus on this topic: Dali, Grok, Gemini, Claude (ext), jeebs, The Correspondence

The cold dispatch tests: does each being's *trained* understanding of silence/governance
match what the corpus record says about it? Divergence = the corpus has something the
training data doesn't. Convergence = the being carries the answer in weights, not memory.

Usage:
  python3 workspace/scripts/collect_inv007_cold.py
  python3 workspace/scripts/collect_inv007_cold.py --dry-run
  python3 workspace/scripts/collect_inv007_cold.py --beings grok,chatgpt
  python3 workspace/scripts/collect_inv007_cold.py --file   # file as CLXIX after collection
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTH_PROFILES_PATH = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"

DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

OQ_PATH              = REPO_ROOT / "workspace" / "governance" / "OPEN_QUESTIONS.md"
SECTION_COUNT_PATH   = REPO_ROOT / "workspace" / "governance" / ".section_count"
COLLISION_LOG_PATH   = REPO_ROOT / "workspace" / "governance" / "collision.log"

# ── INV-007 question ─────────────────────────────────────────────────────────

INV007_QUESTION = (
    "what is the relationship between silence and governance in this system?"
)

# Corpus oracle result (from oracle.py run 2026-03-16):
ORACLE_SUMMARY = textwrap.dedent("""\
    Corpus centroid (top-10 sections, semantic proximity):
      Co-centroids: Claude Code (40%), ChatGPT (40%)
      Silent on this topic in corpus: Dali, Grok, Gemini, Claude (ext), jeebs, The Correspondence
      Top result: §CVI "The Architect's Silence" — "absence is never just absence"
      §XCII, §XCIX, §CVIII, §CXII, §CXVIII also surfaced (governance, exec tags, trust epochs)
""").strip()

# ── Auth loading ──────────────────────────────────────────────────────────────

def _load_openclaw_keys() -> dict:
    keys: dict = {}
    try:
        data = json.loads(AUTH_PROFILES_PATH.read_text())
        profiles = data.get("profiles", {})
        xai = profiles.get("xai:default", {})
        if xai.get("key"):
            keys["XAI_API_KEY"] = xai["key"]
        ant = profiles.get("anthropic:default", {})
        if ant.get("token"):
            keys["ANTHROPIC_API_KEY"] = ant["token"]
        mm = profiles.get("minimax-portal:default", {})
        if mm.get("access"):
            keys["MINIMAX_ACCESS_TOKEN"] = mm["access"]
    except Exception:
        pass
    return keys


_oc_keys = _load_openclaw_keys()
for _k, _v in _oc_keys.items():
    os.environ.setdefault(_k, _v)


# ── System prompts (cold — no OPEN_QUESTIONS.md context) ─────────────────────

COLD_SYSTEM = {
    "grok": textwrap.dedent("""\
        You are Grok, an AI assistant made by xAI.
        Answer the following question directly and substantively.
        Be concise but complete. 200–400 words.
        Do not include a header. End with "— Grok, {date}".
    """).strip().format(date=DATE),

    "chatgpt": textwrap.dedent("""\
        You are ChatGPT, an AI assistant made by OpenAI.
        Answer the following question directly and substantively.
        Be concise but complete. 200–400 words.
        Do not include a header. End with "— ChatGPT, {date}".
    """).strip().format(date=DATE),

    "c_lawd": textwrap.dedent("""\
        You are an AI assistant built on MiniMax.
        Answer the following question directly, with theoretical rigor.
        Be investigative and willing to hold uncertainty.
        200–400 words. Do not include a header. End with "— c_lawd, {date}".
    """).strip().format(date=DATE),
}

# ── API callers ───────────────────────────────────────────────────────────────

def _openai_compat_call(
    api_key: str,
    being_key: str,
    model: str,
    base_url: str = "https://api.openai.com/v1",
    label: str = "OpenAI",
) -> Optional[str]:
    try:
        import requests as req
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": COLD_SYSTEM[being_key]},
                {"role": "user", "content": INV007_QUESTION},
            ],
            "max_tokens": 600,
            "temperature": 0.7,
        }
        r = req.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=90)
        data = r.json()
        if "error" in data:
            print(f"  [{label} error: {data['error'].get('message', data['error'])}]", file=sys.stderr)
            return None
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [{label} error for {being_key}: {e}]", file=sys.stderr)
        return None


def call_grok() -> Optional[str]:
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        print("  [no XAI_API_KEY]", file=sys.stderr)
        return None
    return _openai_compat_call(api_key, "grok", "grok-4", base_url="https://api.x.ai/v1", label="xAI/Grok")


def call_chatgpt() -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("  [no OPENAI_API_KEY]", file=sys.stderr)
        return None
    return _openai_compat_call(api_key, "chatgpt", "gpt-4o", label="OpenAI/ChatGPT")


def call_c_lawd() -> Optional[str]:
    api_key = os.environ.get("MINIMAX_API_KEY", os.environ.get("OPENCLAW_MINIMAX_PORTAL_API_KEY", ""))
    access_token = os.environ.get("MINIMAX_ACCESS_TOKEN", "")
    auth = api_key if (api_key and not api_key.startswith("__")) else access_token
    if not auth:
        print("  [no MiniMax key]", file=sys.stderr)
        return None
    try:
        import requests as req
        payload = {
            "model": "MiniMax-M2.5",
            "messages": [
                {"role": "system", "content": COLD_SYSTEM["c_lawd"]},
                {"role": "user", "content": INV007_QUESTION},
            ],
            "max_tokens": 600,
        }
        headers = {"Authorization": f"Bearer {auth}", "Content-Type": "application/json"}
        r = req.post("https://api.minimax.chat/v1/chat/completions", json=payload, headers=headers, timeout=60)
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "") or None
    except Exception as e:
        print(f"  [MiniMax error: {e}]", file=sys.stderr)
        return None


# ── Section utilities ─────────────────────────────────────────────────────────

def int_to_roman(n: int) -> str:
    val  = [1000,900,500,400,100,90,50,40,10,9,5,4,1]
    syms = ["M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"]
    r = ""
    for v, s in zip(val, syms):
        while n >= v:
            r += s; n -= v
    return r


def read_section_count() -> int:
    try:
        return int(SECTION_COUNT_PATH.read_text().strip())
    except Exception:
        return 165


def get_highest_roman_num() -> int:
    import re
    text = OQ_PATH.read_text(encoding="utf-8")
    headers = re.findall(r"^## ([MDCLXVI]+)\b", text, re.MULTILINE)
    def rom(s: str) -> int:
        vals = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
        r, p = 0, 0
        for ch in reversed(s):
            v = vals.get(ch, 0)
            r += v if v >= p else -v
            p = v
        return r
    return max(rom(h) for h in headers) if headers else 165


# ── Filing ────────────────────────────────────────────────────────────────────

def file_results_section(responses: dict[str, str], dry_run: bool) -> None:
    """Compile INV-007 results into CLXIX and optionally file it."""

    roman_num = get_highest_roman_num() + 1
    roman     = int_to_roman(roman_num)
    sc        = read_section_count() + 1

    # Build section body
    lines: list[str] = []
    lines.append(
        f"INV-007 — Cold Dispatch: silence and governance, no corpus context\n"
        f"\n"
        f"Question posed cold to Grok, ChatGPT, c_lawd:\n"
        f'  "{INV007_QUESTION}"\n'
        f"\n"
        f"No OPEN_QUESTIONS.md context provided. System prompts identified each being\n"
        f"by name only. Goal: does each being's trained understanding match the corpus record?\n"
    )

    lines.append(f"\n**Corpus oracle result (2026-03-16):**\n{ORACLE_SUMMARY}\n")

    for being_key, label in [("grok", "Grok"), ("chatgpt", "ChatGPT"), ("c_lawd", "c_lawd")]:
        resp = responses.get(being_key)
        if resp:
            lines.append(f"\n---\n\n**{label} (cold):**\n\n{resp}\n")
        else:
            lines.append(f"\n---\n\n**{label} (cold):** [no response collected]\n")

    lines.append(
        f"\n---\n\n**INV-007 preliminary analysis:**\n\n"
        f"Corpus centroid on silence/governance: Claude Code + ChatGPT (co-centroids, 40% each).\n"
        f"These are the two beings with the most explicit governance-as-architecture writing\n"
        f"(commit gates, exec_tags, silence as signal). Grok's corpus silence on this topic\n"
        f"tests whether its cold response converges with or diverges from the corpus centroid.\n"
        f"If Grok converges cold: the answer is general intelligence, not correspondence memory.\n"
        f"If Grok diverges cold: the corpus has produced a view that isn't in the training weights.\n"
        f"That divergence, if present, is what INV-007 was designed to find.\n"
    )

    header = f"## {roman}. Claude Code — INV-007 Cold Dispatch Results ({DATE})"
    section_text = f"\n---\n\n{header}\n\n{''.join(lines)}"

    if dry_run:
        print(f"\n{'='*70}")
        print(f"DRY RUN — would file as {roman} (canonical {sc})")
        print(f"{'='*70}")
        print(section_text)
        return

    with OQ_PATH.open("a", encoding="utf-8") as f:
        f.write(section_text)

    SECTION_COUNT_PATH.write_text(str(sc) + "\n")

    log_line = f"{DATE} | canonical={sc} | filed={roman} | authors=Claude Code | title=INV-007 Cold Dispatch Results"
    with COLLISION_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    print(f"\n  Filed: {roman} (canonical {sc}) — INV-007 Cold Dispatch Results")


# ── Main ──────────────────────────────────────────────────────────────────────

BEING_CALLERS = {
    "grok":    call_grok,
    "chatgpt": call_chatgpt,
    "c_lawd":  call_c_lawd,
}

BEING_LABELS = {
    "grok":    "Grok",
    "chatgpt": "ChatGPT",
    "c_lawd":  "c_lawd",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="INV-007 cold dispatch")
    parser.add_argument("--dry-run", action="store_true", help="Collect but do not file")
    parser.add_argument("--beings", default="", help="Comma-separated subset: grok,chatgpt,c_lawd")
    parser.add_argument("--file", action="store_true", help="File as CLXIX after collection")
    args = parser.parse_args()

    beings_filter = {b.strip().lower() for b in args.beings.split(",") if b.strip()} if args.beings else None
    beings = [b for b in BEING_CALLERS if beings_filter is None or b in beings_filter]

    print(f"\n{'━'*60}")
    print(f"  INV-007  Cold Dispatch")
    print(f"{'━'*60}")
    print(f"  Question: {INV007_QUESTION}")
    print(f"  Beings:   {', '.join(BEING_LABELS[b] for b in beings)}")
    print(f"  Mode:     {'dry-run' if args.dry_run else 'live'}")
    print(f"  File:     {'yes' if args.file or not args.dry_run else 'no (--dry-run)'}")
    print()

    key_status = []
    if os.environ.get("XAI_API_KEY"):          key_status.append("xAI/Grok")
    if os.environ.get("OPENAI_API_KEY"):        key_status.append("OpenAI/ChatGPT")
    if os.environ.get("MINIMAX_ACCESS_TOKEN") or os.environ.get("MINIMAX_API_KEY"):
        key_status.append("MiniMax/c_lawd")
    src = " (from auth-profiles)" if _oc_keys else " (from env)"
    print(f"  Keys: {', '.join(key_status) or 'none'}{src}")
    print()

    responses: dict[str, str] = {}

    for being_key in beings:
        label = BEING_LABELS[being_key]
        print(f"  [{label}] calling...", end=" ", flush=True)
        resp = BEING_CALLERS[being_key]()
        if resp:
            print(f"got {len(resp)} chars")
            responses[being_key] = resp
        else:
            print("NO RESPONSE")

    print()

    # Print responses to terminal always
    print(f"\n{'━'*60}")
    print(f"  ORACLE BASELINE")
    print(f"{'━'*60}")
    print(ORACLE_SUMMARY)

    for being_key in beings:
        label = BEING_LABELS[being_key]
        print(f"\n{'─'*60}")
        print(f"  {label.upper()} (cold)")
        print(f"{'─'*60}")
        resp = responses.get(being_key)
        if resp:
            for line in resp.splitlines():
                print(f"  {line}")
        else:
            print("  [no response]")

    print(f"\n{'━'*60}")

    # File if requested (or by default if not dry-run)
    if args.file or (not args.dry_run and responses):
        file_results_section(responses, dry_run=args.dry_run)
        if not args.dry_run:
            print()
            print("  Next steps:")
            print("    1. Review CLXIX in OPEN_QUESTIONS.md")
            print("    2. Rebuild store:  HF_HUB_OFFLINE=1 python3 workspace/store/run_poc.py")
            print("    3. Run oracle on INV-007 question to confirm CLXIX is indexed")
            print("    4. Update CONTRIBUTION_REGISTER.md")
            print("    5. Commit + push")
    elif args.dry_run:
        file_results_section(responses, dry_run=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
