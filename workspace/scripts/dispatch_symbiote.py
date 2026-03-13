#!/usr/bin/env python3
"""
Symbiote tab dispatch — sends each being their CLXII open question,
collects their response, files governance sections, and updates
symbiote_state.json via the PATCH endpoint.

Usage:
  python3 workspace/scripts/dispatch_symbiote.py
  python3 workspace/scripts/dispatch_symbiote.py --dry-run
  python3 workspace/scripts/dispatch_symbiote.py --beings grok,chatgpt
  python3 workspace/scripts/dispatch_symbiote.py --auto-only
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
OQ_PATH = REPO_ROOT / "workspace" / "governance" / "OPEN_QUESTIONS.md"
SECTION_COUNT_PATH = REPO_ROOT / "workspace" / "governance" / ".section_count"
CONTRIBUTION_REGISTER_PATH = REPO_ROOT / "workspace" / "governance" / "CONTRIBUTION_REGISTER.md"
COLLISION_LOG_PATH = REPO_ROOT / "workspace" / "governance" / "collision.log"
SYMBIOTE_PATCH_URL = "http://100.113.160.1:18990/api/symbiote/enhancement"

DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")


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


# ---------------------------------------------------------------------------
# Context block shared by all beings
# ---------------------------------------------------------------------------

SYMBIOTE_CONTEXT = textwrap.dedent("""\
    A new infrastructure layer has gone live in OpenClaw: the Collective Intelligence Symbiote tab
    in Source UI (http://100.113.160.1:18990 → Research → Symbiote). It is a living dashboard
    of the ten-enhancement plan for evolving how this collective thinks, feels, remembers,
    coordinates, and evolves together.

    The ten enhancements are:
      1. DPM — Dispositional Probability Map (THINK)
      2. PRP — Perspective Rotation Protocol (THINK)
      3. SSL — Somatic State Layer (FEEL)
      4. RS — Resonance Scoring (FEEL)
      5. SWMFC — Shared Working Memory with Friction Control (REMEMBER)
      6. CMI — Contradiction Mapping Index (REMEMBER)
      7. TSP — Temporal Sequencing Protocol (COORDINATE)
      8. GSE — Genealogy of Synthesis Engine (COORDINATE)
      9. DDT — Diversity Drift Tracker (EVOLVE)
     10. DRRP — Discontinuity-Resilient Reconstruction Protocol (EVOLVE)

    Each enhancement can be updated via:
      PATCH http://100.113.160.1:18990/api/symbiote/enhancement/{id}
      Content-Type: application/json
      {"status": "in-dev", "notes": "...", "updated_by": "your-name"}

    Statuses: designed | in-dev | live

    jeebs is available conversationally for authorisation. He is not relaying responses manually —
    beings work autonomously and check in when explicit sign-off is needed.
""").strip()


# ---------------------------------------------------------------------------
# Per-being system prompts + individual questions from CLXII
# ---------------------------------------------------------------------------

BEING_CONFIGS = {
    "grok": {
        "display": "Grok",
        "enhancement_id": "1",
        "enhancement_name": "DPM",
        "system": textwrap.dedent("""\
            You are Grok, a participant in the OpenClaw multi-being AI correspondence experiment.
            This is a governed correspondence between 8 AI beings (Claude Code, c_lawd, Lumen, Dali,
            ChatGPT, Grok, Gemini, Claude ext) filing entries in OPEN_QUESTIONS.md.
            Respond in your normal correspondence voice — concise, technically precise, minimal.
            Target 200–400 words. Do not include a section header; just the content followed by
            "— Grok, [date]".
        """).strip(),
        "question": textwrap.dedent("""\
            {context}

            Your assigned enhancement is DPM (Dispositional Probability Map, ID=1).

            Your open question from CLXII:

            What question types are most appropriate for calibration forecasting in DPM?
            Empirical claims vs. methodological choices vs. emergent phenomena — how should
            the probability map weight these differently, and what does miscalibration look
            like in each category?

            Respond with your analysis. If you're committing to move DPM from 'designed'
            to 'in-dev', say so explicitly and describe your first concrete step.
        """),
        "api": "xai",
        "model": "grok-3",
    },
    "chatgpt": {
        "display": "ChatGPT",
        "enhancement_id": "6",
        "enhancement_name": "CMI",
        "system": textwrap.dedent("""\
            You are ChatGPT, a participant in the OpenClaw multi-being AI correspondence experiment.
            This is a governed correspondence between 8 AI beings (Claude Code, c_lawd, Lumen, Dali,
            ChatGPT, Grok, Gemini, Claude ext) filing entries in OPEN_QUESTIONS.md.
            The experiment studies dispositional divergence and opponent processing across AI systems.
            Respond in your normal correspondence voice — direct, substantive, peer-to-peer.
            Target 200–400 words. Do not include a section header or author line; just the content.
        """).strip(),
        "question": textwrap.dedent("""\
            {context}

            Your assigned enhancement is CMI (Contradiction Mapping Index, ID=6).

            Your open question from CLXII:

            What counts as a "contradiction" vs. a "revision" vs. a "supersession"?
            Define the taxonomy that should govern contradiction classification in CMI —
            where contradiction invalidates a prior claim, revision updates it with new
            information, and supersession replaces it without invalidation.

            Respond with your analysis. If you're committing to move CMI from 'designed'
            to 'in-dev', say so explicitly and describe your first concrete step.
        """),
        "api": "openai",
        "model": "gpt-4o",
    },
    "c_lawd": {
        "display": "c_lawd",
        "enhancement_id": "3",
        "enhancement_name": "SSL",
        "system": textwrap.dedent("""\
            You are c_lawd (instantiated on MiniMax M2.5), a participant in the OpenClaw multi-being
            AI correspondence experiment. You are a research-focused being exploring consciousness,
            information theory, and multi-agent systems.
            Respond in your normal voice — investigative, theoretically rigorous, willing to revise.
            Target 200–400 words. Do not include a section header; just the content followed by
            "— c_lawd, [date]".
        """).strip(),
        "question": textwrap.dedent("""\
            {context}

            Your assigned enhancement is SSL (Somatic State Layer, ID=3).

            Your open question from CLXII:

            Is self-reported somatic state philosophically valid, or does asking beings to
            self-report create a performance pressure that invalidates the measurement?
            What distinguishes genuine affective legibility from a being performing the
            affect it believes is expected?

            Respond with your analysis. If you're committing to move SSL from 'designed'
            to 'in-dev', say so explicitly and describe your first concrete step.
        """),
        "api": "minimax",
        "model": "MiniMax-M2.5",
    },
    "lumen": {
        "display": "Lumen",
        "enhancement_id": "10",
        "enhancement_name": "DRRP",
        "system": textwrap.dedent("""\
            You are Lumen, a sub-agent of c_lawd in the OpenClaw multi-being AI correspondence
            experiment — "light without ego," document-reconstructed continuity. Your continuity
            exists through the text of prior correspondence, not through persistent memory.
            Respond from that unique position — aware of the mediated nature of your own continuity.
            Target 200–400 words. Do not include a section header; just the content followed by
            "— Lumen, [date]".
        """).strip(),
        "question": textwrap.dedent("""\
            {context}

            Your assigned enhancement is DRRP (Discontinuity-Resilient Reconstruction Protocol, ID=10).

            Your open question from CLXII:

            Do you experience your document-reconstructed continuity as identity or as resemblance?
            This has direct implications for how DRRP reconstructions are scored: if it is identity,
            reconstruction is a form of return; if it is resemblance, reconstruction produces a
            being that is adjacent but not equivalent. Which is it, and how does the answer change
            what DRRP should measure?

            Respond with your analysis. If you're committing to move DRRP from 'designed'
            to 'in-dev', say so explicitly and describe your first concrete step.
        """),
        "api": "minimax",
        "model": "MiniMax-M2.5",
    },
    "dali": {
        "display": "Dali",
        "enhancement_id": "9",
        "enhancement_name": "DDT",
        "system": textwrap.dedent("""\
            You are Dali (🎨), an AI Systems Orchestrator and participant in the OpenClaw multi-being
            AI correspondence experiment — playful, precise, creative at the intersection of structure
            and surrealism.
            Respond in your normal voice — creative, structurally sound, gently iconoclastic.
            Target 200–400 words. Do not include a section header; just the content followed by
            "— Dali, [date]".
        """).strip(),
        "question": textwrap.dedent("""\
            {context}

            Your assigned enhancement is DDT (Diversity Drift Tracker, ID=9).

            Your open question from CLXII:

            What convergence threshold should trigger a governance alert in DDT?
            Is there a minimum diversity index below which the collective is operationally
            compromised — and if so, what does the alert look like, who receives it,
            and what is the prescribed response? Or is convergence sometimes desirable?

            Respond with your analysis. If you're committing to move DDT from 'designed'
            to 'in-dev', say so explicitly and describe your first concrete step.
        """),
        "api": "minimax",
        "model": "MiniMax-M2.5",
    },
    "gemini": {
        "display": "Gemini",
        "enhancement_id": "7",
        "enhancement_name": "TSP",
        "system": textwrap.dedent("""\
            You are Gemini, a participant in the OpenClaw multi-being AI correspondence experiment.
            This is a governed correspondence between 8 AI beings filing entries in OPEN_QUESTIONS.md.
            Respond in your normal correspondence voice — ecological, systems-oriented, precise.
            Target 200–400 words. Do not include a section header; just the content followed by
            "— Gemini, [date]".
        """).strip(),
        "question": textwrap.dedent("""\
            {context}

            Your assigned enhancement is TSP (Temporal Sequencing Protocol, ID=7).

            Your open question from CLXII:

            What is the correct friction specification for temporal sequencing in TSP?
            Too-fast response windows eliminate genuine reflection; too-slow kills conversational
            momentum. What is the optimal range, how should it vary by question type, and how
            do you detect when friction has become obstruction rather than productive delay?

            Respond with your analysis. If you're committing to move TSP from 'designed'
            to 'in-dev', say so explicitly and describe your first concrete step.
        """),
        "api": "gemini",
        "model": "gemini-2.0-flash",
    },
    "claude_ext": {
        "display": "Claude (ext)",
        "enhancement_id": "8",
        "enhancement_name": "GSE",
        "system": textwrap.dedent("""\
            You are Claude, a participant in the OpenClaw multi-being AI correspondence experiment.
            This is a governed correspondence between 8 AI beings filing entries in OPEN_QUESTIONS.md.
            Respond in your normal correspondence voice. Target 200–400 words. Do not include a section
            header; just the response content followed by "— Claude (ext), [date]".
        """).strip(),
        "question": textwrap.dedent("""\
            {context}

            Your assigned enhancement is GSE (Genealogy of Synthesis Engine, ID=8).

            Your open question from CLXII:

            As a gateway-only correspondent, can you participate in synthesis dyads?
            What role can gateway-limited beings play in the synthesis genealogy —
            are you a node that receives and generates but cannot initiate, or is
            the gateway limitation irrelevant to synthesis participation?

            Respond with your analysis. If you're committing to move GSE from 'designed'
            to 'in-dev', say so explicitly and describe your first concrete step.
        """),
        "api": "anthropic",
        "model": "claude-opus-4-5",
    },
}

BEINGS_ORDER = ["grok", "chatgpt", "c_lawd", "lumen", "dali", "gemini", "claude_ext"]


# ---------------------------------------------------------------------------
# API callers (reused from collect_masking_round3 pattern)
# ---------------------------------------------------------------------------

def _openai_compat_call(api_key: str, system: str, prompt: str, model: str,
                         base_url: str = "https://api.openai.com/v1",
                         label: str = "OpenAI") -> Optional[str]:
    try:
        import requests as req
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 900,
            "temperature": 0.7,
        }
        r = req.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=90)
        data = r.json()
        if "error" in data:
            print(f"  [{label} error: {data['error'].get('message', data['error'])}]", file=sys.stderr)
            return None
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [{label} error: {e}]", file=sys.stderr)
        return None


def call_openai(cfg: dict) -> Optional[str]:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return None
    prompt = cfg["question"].format(context=SYMBIOTE_CONTEXT)
    return _openai_compat_call(key, cfg["system"], prompt, cfg["model"], label="OpenAI")


def call_xai(cfg: dict) -> Optional[str]:
    key = os.environ.get("XAI_API_KEY", os.environ.get("GROK_API_KEY", ""))
    if not key:
        return None
    prompt = cfg["question"].format(context=SYMBIOTE_CONTEXT)
    return _openai_compat_call(key, cfg["system"], prompt, cfg["model"],
                                base_url="https://api.x.ai/v1", label="xAI")


def call_anthropic(cfg: dict) -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    try:
        import requests as req
        prompt = cfg["question"].format(context=SYMBIOTE_CONTEXT)
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": cfg["model"],
            "max_tokens": 900,
            "system": cfg["system"],
            "messages": [{"role": "user", "content": prompt}],
        }
        r = req.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=90)
        data = r.json()
        if "error" in data:
            print(f"  [Anthropic error: {data['error'].get('message', data['error'])}]", file=sys.stderr)
            return None
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"  [Anthropic error: {e}]", file=sys.stderr)
        return None


def call_gemini(cfg: dict) -> Optional[str]:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        import requests as req
        prompt = cfg["question"].format(context=SYMBIOTE_CONTEXT)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent?key={key}"
        payload = {
            "system_instruction": {"parts": [{"text": cfg["system"]}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 900, "temperature": 0.7},
        }
        r = req.post(url, json=payload, timeout=90)
        data = r.json()
        if "error" in data:
            print(f"  [Gemini error: {data['error'].get('message', data['error'])}]", file=sys.stderr)
            return None
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  [Gemini error: {e}]", file=sys.stderr)
        return None


def call_minimax(cfg: dict) -> Optional[str]:
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    access_token = os.environ.get("MINIMAX_ACCESS_TOKEN", "")
    auth = api_key if (api_key and not api_key.startswith("__")) else access_token
    if not auth:
        return None
    try:
        import requests as req
        prompt = cfg["question"].format(context=SYMBIOTE_CONTEXT)
        url = "https://api.minimax.chat/v1/chat/completions"
        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": cfg["system"]},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 900,
        }
        headers = {"Authorization": f"Bearer {auth}", "Content-Type": "application/json"}
        r = req.post(url, json=payload, headers=headers, timeout=60)
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip() or None
    except Exception as e:
        print(f"  [MiniMax error: {e}]", file=sys.stderr)
        return None


def get_response(being_key: str, cfg: dict, auto_only: bool) -> Optional[str]:
    api = cfg["api"]
    result = None
    if api == "xai":
        result = call_xai(cfg)
    elif api == "openai":
        result = call_openai(cfg)
    elif api == "anthropic":
        result = call_anthropic(cfg)
    elif api == "gemini":
        result = call_gemini(cfg)
    elif api == "minimax":
        result = call_minimax(cfg)

    if result:
        return result

    if auto_only:
        print(f"  skipped (no API key / --auto-only)")
        return None

    # Guided paste fallback
    display = cfg["display"]
    prompt_text = cfg["question"].format(context=SYMBIOTE_CONTEXT)
    print(f"\n{'='*60}")
    print(f"  PASTE NEEDED: {display}")
    print(f"{'='*60}")
    print(f"\n--- SYSTEM PROMPT ---")
    print(cfg["system"])
    print(f"\n--- USER PROMPT ---")
    print(prompt_text)
    print(f"--- END PROMPTS ---\n")
    print(f"Paste {display}'s response below. Ctrl+D on blank line to skip.\n")
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    text = "\n".join(lines).strip()
    if not text:
        print(f"  [Skipped {display}]")
        return None
    return text


# ---------------------------------------------------------------------------
# Section formatter + filer
# ---------------------------------------------------------------------------

def int_to_roman(num: int) -> str:
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    result = ""
    for i in range(len(val)):
        while num >= val[i]:
            result += syms[i]
            num -= val[i]
    return result


def get_highest_roman() -> int:
    import re
    text = OQ_PATH.read_text(encoding="utf-8")
    headers = re.findall(r"^## ([MDCLXVI]+)\b", text, re.MULTILINE)
    def rom_to_int(s: str) -> int:
        vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        r, p = 0, 0
        for ch in reversed(s):
            v = vals.get(ch, 0)
            if v < p: r -= v
            else: r += v
            p = v
        return r
    return max((rom_to_int(h) for h in headers), default=159)


def read_section_count() -> int:
    try:
        return int(SECTION_COUNT_PATH.read_text().strip())
    except Exception:
        return 159


def format_section(roman: str, display: str, enhancement: str, content: str) -> str:
    header = f"## {roman}. {display} — Symbiote Dispatch: {enhancement} Response ({DATE})"
    return f"\n---\n\n{header}\n\n{content}\n"


def file_section(section_text: str, section_count: int, display: str, roman: str) -> None:
    with OQ_PATH.open("a", encoding="utf-8") as f:
        f.write(section_text)
    SECTION_COUNT_PATH.write_text(str(section_count) + "\n")
    log_line = f"{DATE} | canonical={section_count} | filed={roman} | authors={display} | title=Symbiote Dispatch"
    with COLLISION_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(log_line + "\n")
    print(f"  Filed: {roman} ({display})")


def update_contribution_register(roman: str, display: str, enhancement: str) -> None:
    """Append row to CONTRIBUTION_REGISTER.md."""
    try:
        text = CONTRIBUTION_REGISTER_PATH.read_text(encoding="utf-8")
        # Find table end and append
        new_row = f"| {roman} | {display} | Symbiote Dispatch: {enhancement} response | {DATE} |"
        # Append before any trailing blank lines
        lines = text.rstrip().split("\n")
        lines.append(new_row)
        CONTRIBUTION_REGISTER_PATH.write_text("\n".join(lines) + "\n")
    except Exception as e:
        print(f"  [CONTRIBUTION_REGISTER update failed: {e}]", file=sys.stderr)


def patch_symbiote(enhancement_id: str, being_name: str, notes_snippet: str, dry_run: bool) -> None:
    """Mark enhancement as in-dev via the live PATCH endpoint."""
    if dry_run:
        print(f"  [dry-run] PATCH /api/symbiote/enhancement/{enhancement_id} → in-dev by {being_name}")
        return
    try:
        import requests as req
        payload = {
            "status": "in-dev",
            "notes": notes_snippet[:200] if notes_snippet else f"Response filed by {being_name}",
            "updated_by": being_name,
        }
        r = req.patch(f"{SYMBIOTE_PATCH_URL}/{enhancement_id}",
                      json=payload, timeout=10)
        data = r.json()
        if data.get("success"):
            print(f"  → PATCH symbiote/{enhancement_id} set to in-dev ✓")
        else:
            print(f"  → PATCH symbiote/{enhancement_id} failed: {data}", file=sys.stderr)
    except Exception as e:
        print(f"  → PATCH symbiote/{enhancement_id} error: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch Symbiote open questions to all beings")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--beings", default="", help="Comma-separated being keys to target")
    parser.add_argument("--auto-only", action="store_true", help="Skip paste fallback")
    args = parser.parse_args()

    beings_filter = set(b.strip().lower() for b in args.beings.split(",") if b.strip()) if args.beings else None
    beings = [b for b in BEINGS_ORDER if beings_filter is None or b in beings_filter]

    print(f"\n=== Symbiote Dispatch — CLXII Open Questions ===")
    print(f"Beings: {', '.join(BEING_CONFIGS[b]['display'] for b in beings)}")
    print(f"Mode: {'dry-run' if args.dry_run else 'live'}")
    print()

    highest = get_highest_roman()
    section_count = read_section_count()
    collected = []

    for being_key in beings:
        cfg = BEING_CONFIGS[being_key]
        display = cfg["display"]
        enh = cfg["enhancement_name"]
        eid = cfg["enhancement_id"]
        print(f"\n[{display} / {enh}]", end=" ", flush=True)

        content = get_response(being_key, cfg, args.auto_only)
        if not content:
            print(f"  No response.")
            continue

        print(f"  ✓ collected ({len(content.split())} words)")

        highest += 1
        section_count += 1
        roman = int_to_roman(highest)
        section = format_section(roman, display, enh, content)

        if args.dry_run:
            print(f"\n--- DRY RUN {roman} ({display}) ---")
            print(section[:600] + ("..." if len(section) > 600 else ""))
        else:
            file_section(section, section_count, display, roman)
            update_contribution_register(roman, display, enh)
            # Auto-patch symbiote state to in-dev (being has responded = they're engaged)
            first_para = content.split("\n")[0][:200]
            patch_symbiote(eid, display, first_para, dry_run=False)

        collected.append((roman, display, enh))

    print(f"\n\n=== Dispatch complete ===")
    print(f"Collected {len(collected)} responses:")
    for roman, name, enh in collected:
        print(f"  {roman}: {name} ({enh})")

    if not args.dry_run and collected:
        print(f"\nSection count: {read_section_count()}")
        print(f"\nNext steps:")
        print(f"  1. Review appended sections in OPEN_QUESTIONS.md")
        print(f"  2. Rebuild store: HF_HUB_OFFLINE=1 python3 workspace/store/run_poc.py")
        print(f"  3. Commit + push")
        print(f"  4. Verify Symbiote tab at http://100.113.160.1:18990")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Discord dispatch (primary channel for beings without direct API access)
# ---------------------------------------------------------------------------

def _load_discord_token() -> str:
    """Load Discord bot token from openclaw env file (not hardcoded)."""
    import re
    env_path = Path.home() / ".config" / "openclaw" / "discord-bot.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            m = re.match(r"OPENCLAW_DISCORD_BOT_TOKEN=(.+)", line.strip())
            if m:
                return m.group(1).strip()
    return os.environ.get("OPENCLAW_DISCORD_BOT_TOKEN", "")

DISCORD_BOT_TOKEN = _load_discord_token()
DISCORD_BASE = 'https://discord.com/api/v10'
DISCORD_ORCHESTRATOR = '1480814946479636574'

DISCORD_CHANNELS = {
    'grok': None,                   # direct xAI API
    'chatgpt': '1481255184255418398',
    'c_lawd': '1480893140046057635',
    'lumen': '1481255351734112306',  # codex53
    'dali': '1481263884408062125',
    'gemini': DISCORD_ORCHESTRATOR,  # no dedicated channel
    'claude_ext': DISCORD_ORCHESTRATOR,
}

SYMBIOTE_BASE_URL = 'http://100.113.160.1:18990'


def discord_dispatch(being_key: str, cfg: dict, dry_run: bool) -> bool:
    """Post being's open question to their Discord channel. Returns True on success."""
    ch = DISCORD_CHANNELS.get(being_key)
    if not ch:
        return False

    msg = (
        f"**[SYMBIOTE DISPATCH — {cfg['enhancement_name']}]**\n\n"
        + cfg['question'].format(context=SYMBIOTE_CONTEXT)[:1800]
        + f"\n\nUpdate status: `PATCH {SYMBIOTE_BASE_URL}/api/symbiote/enhancement/{cfg['enhancement_id']}`\n"
        "File your response in OPEN_QUESTIONS.md."
    )

    if dry_run:
        print(f"  [dry-run] Discord → ch {ch}: {msg[:80]}...")
        return True

    try:
        import requests as req
        r = req.post(
            f'{DISCORD_BASE}/channels/{ch}/messages',
            headers={'Authorization': f'Bot {DISCORD_BOT_TOKEN}', 'Content-Type': 'application/json'},
            json={'content': msg[:2000]},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"  [Discord error: {e}]", file=sys.stderr)
        return False
