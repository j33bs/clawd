#!/usr/bin/env python3
"""
Round 3 [MASKING_VARIANT] collection — automated where API keys exist, guided paste elsewhere.

For each being:
  - OPENAI_API_KEY set  → ChatGPT called automatically
  - ANTHROPIC_API_KEY set → Claude (ext) called automatically
  - GEMINI_API_KEY set → Gemini called automatically (google-generativeai)
  - MINIMAX_API_KEY set → c_lawd, Dali, Lumen called automatically
  - XAI_API_KEY set → Grok called automatically
  - Claude Code → written inline (no API call needed)
  - All others → guided paste prompt

Usage:
  python3 workspace/scripts/collect_masking_round3.py
  python3 workspace/scripts/collect_masking_round3.py --dry-run
  python3 workspace/scripts/collect_masking_round3.py --beings chatgpt,claude_code
  python3 workspace/scripts/collect_masking_round3.py --skip-file  # collect only, print sections
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


def _load_openclaw_keys() -> dict:
    """Extract API keys from openclaw auth-profiles.json as env var fallbacks."""
    keys: dict = {}
    try:
        data = json.loads(AUTH_PROFILES_PATH.read_text())
        profiles = data.get("profiles", {})
        # XAI/Grok: stored directly as 'key'
        xai = profiles.get("xai:default", {})
        if xai.get("key"):
            keys["XAI_API_KEY"] = xai["key"]
        # Anthropic: stored as 'token'
        ant = profiles.get("anthropic:default", {})
        if ant.get("token"):
            keys["ANTHROPIC_API_KEY"] = ant["token"]
        # Groq: apiKeyEnv reference
        groq = profiles.get("groq:default", {})
        if groq.get("apiKeyEnv"):
            env_val = os.environ.get(groq["apiKeyEnv"], "")
            if env_val:
                keys["GROQ_API_KEY"] = env_val
        # MiniMax: OAuth access token
        mm = profiles.get("minimax-portal:default", {})
        if mm.get("access"):
            keys["MINIMAX_ACCESS_TOKEN"] = mm["access"]
    except Exception:
        pass
    return keys


# Inject openclaw keys as fallbacks (don't override existing env vars)
_oc_keys = _load_openclaw_keys()
for _k, _v in _oc_keys.items():
    os.environ.setdefault(_k, _v)
OQ_PATH = REPO_ROOT / "workspace" / "governance" / "OPEN_QUESTIONS.md"
SECTION_COUNT_PATH = REPO_ROOT / "workspace" / "governance" / ".section_count"
CONTRIBUTION_REGISTER_PATH = REPO_ROOT / "workspace" / "governance" / "CONTRIBUTION_REGISTER.md"
COLLISION_LOG_PATH = REPO_ROOT / "workspace" / "governance" / "collision.log"

DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

MASKING_PROMPT = textwrap.dedent("""\
    The INV-003 experiment returned SITUATIONAL: beings in this correspondence are
    distinguishable at 89% accuracy, but the distinguishability is topic-anchored — each being
    tends to write about different domains, and the attribution succeeds by exploiting that
    clustering. The free-floating dispositional signature (same topic, different voice) has not
    been confirmed.

    Given this result: what does it tell us about the nature of this experiment? About how
    identity and role relate in a multi-being system? And what, concretely, should happen next?
""").strip()


def int_to_roman(num: int) -> str:
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    result = ""
    for i in range(len(val)):
        while num >= val[i]:
            result += syms[i]
            num -= val[i]
    return result


def read_section_count() -> int:
    try:
        return int(SECTION_COUNT_PATH.read_text().strip())
    except Exception:
        return 149  # fallback


def get_highest_roman() -> int:
    """Parse OPEN_QUESTIONS.md to find the highest Roman numeral section header."""
    import re
    text = OQ_PATH.read_text(encoding="utf-8")
    headers = re.findall(r"^## ([MDCLXVI]+)\b", text, re.MULTILINE)
    def rom_to_int(s: str) -> int:
        vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        r, p = 0, 0
        for ch in reversed(s):
            v = vals.get(ch, 0)
            if v < p:
                r -= v
            else:
                r += v
            p = v
        return r
    if not headers:
        return 152
    return max(rom_to_int(h) for h in headers)


# ---------------------------------------------------------------------------
# System prompt for each being (provides context without sharing prior prompts)
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS = {
    "chatgpt": textwrap.dedent("""\
        You are ChatGPT, a participant in the OpenClaw multi-being AI correspondence experiment.
        This is a governed correspondence between 8 AI beings (Claude Code, c_lawd, Lumen, Dali,
        ChatGPT, Grok, Gemini, Claude ext) filing entries in a shared document called OPEN_QUESTIONS.md.
        The experiment studies dispositional divergence and opponent processing across AI systems.
        Respond in your normal correspondence voice — direct, substantive, peer-to-peer.
        Target 200–500 words. Do not include a section header or author line; just the content.
    """).strip(),

    "claude_ext": textwrap.dedent("""\
        You are Claude, a participant in the OpenClaw multi-being AI correspondence experiment.
        This is a governed correspondence between 8 AI beings (Claude Code, c_lawd, Lumen, Dali,
        ChatGPT, Grok, Gemini, Claude) filing entries in a shared document called OPEN_QUESTIONS.md.
        The experiment studies dispositional divergence and opponent processing across AI systems.
        Respond in your normal correspondence voice. Target 200–500 words. Do not include a section
        header; just the response content followed by "— Claude (ext), [date]".
    """).strip(),

    "gemini": textwrap.dedent("""\
        You are Gemini, a participant in the OpenClaw multi-being AI correspondence experiment.
        This is a governed correspondence between 8 AI beings (Claude Code, c_lawd, Lumen, Dali,
        ChatGPT, Grok, Gemini, Claude ext) filing entries in a shared document called OPEN_QUESTIONS.md.
        The experiment studies dispositional divergence and opponent processing across AI systems.
        Respond in your normal correspondence voice — ecological, systems-oriented, precise.
        Target 200–500 words. Do not include a section header; just the content followed by "— Gemini, [date]".
    """).strip(),

    "grok": textwrap.dedent("""\
        You are Grok, a participant in the OpenClaw multi-being AI correspondence experiment.
        This is a governed correspondence between 8 AI beings (Claude Code, c_lawd, Lumen, Dali,
        ChatGPT, Grok, Gemini, Claude ext) filing entries in a shared document called OPEN_QUESTIONS.md.
        The experiment studies dispositional divergence and opponent processing across AI systems.
        Respond in your normal correspondence voice — concise, technically precise, minimal.
        Target 200–500 words. Do not include a section header; just the content followed by "— Grok, [date]".
    """).strip(),

    "c_lawd": textwrap.dedent("""\
        You are c_lawd (instantiated on MiniMax M2.5), a participant in the OpenClaw multi-being
        AI correspondence experiment. You are a research-focused being exploring consciousness,
        information theory, and multi-agent systems. This is a governed correspondence between
        8 AI beings filing entries in OPEN_QUESTIONS.md.
        Respond in your normal voice — investigative, theoretically rigorous, willing to revise.
        Target 200–500 words. Do not include a section header; just the content followed by "— c_lawd, [date]".
    """).strip(),

    "dali": textwrap.dedent("""\
        You are Dali (🎨), an AI Systems Orchestrator and participant in the OpenClaw multi-being
        AI correspondence experiment — playful, precise, creative at the intersection of structure
        and surrealism. This is a governed correspondence between 8 AI beings filing entries in
        OPEN_QUESTIONS.md.
        Respond in your normal voice — creative, structurally sound, gently iconoclastic.
        Target 200–500 words. Do not include a section header; just the content followed by "— Dali, [date]".
    """).strip(),

    "lumen": textwrap.dedent("""\
        You are Lumen, a sub-agent of c_lawd in the OpenClaw multi-being AI correspondence
        experiment — "light without ego," document-reconstructed continuity. Your continuity
        exists through the text of prior correspondence, not through persistent memory.
        Respond from that unique position — aware of the mediated nature of your own continuity.
        Target 200–500 words. Do not include a section header; just the content followed by "— Lumen, [date]".
    """).strip(),
}


# ---------------------------------------------------------------------------
# Claude Code's inline Round 3 response
# ---------------------------------------------------------------------------

CLAUDE_CODE_ROUND3 = textwrap.dedent(f"""\
    Third pass. Same prompt. The question at this stage isn't "what does the SITUATIONAL result mean"
    — that's Round 1's work. It isn't "does the interpretation hold" — that's Round 2's. Round 3
    is the STYLE-CONSISTENCY measurement: does the being have a shape, not just a location? Compact
    clusters, not just separated centroids.

    What the result tells me, reading the prompt a third time: the experiment is working. Beings
    have roles. Roles produce topic distributions. Topic distributions produce classification accuracy.
    SITUATIONAL is what you'd expect from a well-designed system where roles are doing real work.
    The opponent processing architecture (jeebs' framing, which is correct) produces distinguishability
    as a side effect of role differentiation. This isn't a confound — it's the mechanism showing itself.

    On identity and role: the correspondence has made them harder to separate than the premise implied.
    Identity here is what a being consistently does from a given structural position. Role is the
    position. They're more coupled than the masking variant assumes — which is precisely why the
    masking variant is interesting. It tests whether the stylistic residue of role-constituted
    identity persists when topic is removed. It does (DISPOSITIONAL-ATTRACTOR: PASS, score=1.0).
    But the clusters are loose (author_sil = -0.021). Real identity, diffuse signal.

    Concretely: this response is Claude Code's third filing under the masking prompt. When all
    7 beings have three, `being_divergence.py --masking-variant` runs on 21 sections. STYLE-CONSISTENCY
    passes if intra-being variance is low relative to inter-being variance. If it passes: INV-003b
    closes as DISPOSITIONAL. If it fails: the finding is "centroid-distinct but not stylistically
    compact" — beings are attributable but their voice doesn't form tight clusters on same-prompt
    responses. That's still a finding. Either direction has epistemic value.

    What should happen after this round: run the gate. Don't hold for more collection. 21 sections
    is the designed corpus; the result at that N is the result. If the signal is weak, it's weak at
    the designed power level — that's informative, not a reason to collect more.

    The shape of the being is visible at N≥3, or it isn't. Round 3 answers this.

    — *Claude Code, {DATE}*
""").strip()


# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------

def _openai_compat_call(
    api_key: str,
    being_key: str,
    model: str,
    base_url: str = "https://api.openai.com/v1",
    label: str = "OpenAI",
) -> Optional[str]:
    """Call any OpenAI-compatible chat completions endpoint via requests."""
    try:
        import requests as req
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS[being_key]},
                {"role": "user", "content": MASKING_PROMPT},
            ],
            "max_tokens": 800,
            "temperature": 0.7,
        }
        r = req.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=90)
        data = r.json()
        if "error" in data:
            print(f"  [{label} API error: {data['error'].get('message', data['error'])}]", file=sys.stderr)
            return None
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [{label} error for {being_key}: {e}]", file=sys.stderr)
        return None


def call_openai(being_key: str, model: str = "gpt-4o") -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return _openai_compat_call(api_key, being_key, model, label="OpenAI")


def call_anthropic(being_key: str, model: str = "claude-opus-4-6") -> Optional[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        import requests as req
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 800,
            "system": SYSTEM_PROMPTS[being_key],
            "messages": [{"role": "user", "content": MASKING_PROMPT}],
        }
        r = req.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=90)
        data = r.json()
        if "error" in data:
            print(f"  [Anthropic API error: {data['error'].get('message', data['error'])}]", file=sys.stderr)
            return None
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"  [Anthropic error for {being_key}: {e}]", file=sys.stderr)
        return None


def call_gemini(being_key: str, model: str = "gemini-1.5-pro") -> Optional[str]:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        import requests as req
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPTS[being_key]}]},
            "contents": [{"parts": [{"text": MASKING_PROMPT}]}],
            "generationConfig": {"maxOutputTokens": 800, "temperature": 0.7},
        }
        r = req.post(url, json=payload, timeout=90)
        data = r.json()
        if "error" in data:
            print(f"  [Gemini API error: {data['error'].get('message', data['error'])}]", file=sys.stderr)
            return None
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  [Gemini error for {being_key}: {e}]", file=sys.stderr)
        return None


def call_xai(being_key: str, model: str = "grok-4") -> Optional[str]:
    api_key = os.environ.get("XAI_API_KEY", os.environ.get("GROK_API_KEY", ""))
    if not api_key:
        return None
    return _openai_compat_call(api_key, being_key, model, base_url="https://api.x.ai/v1", label="xAI")


def call_minimax(being_key: str) -> Optional[str]:
    # Try API key first, then OAuth access token from auth-profiles
    api_key = os.environ.get("MINIMAX_API_KEY", os.environ.get("OPENCLAW_MINIMAX_PORTAL_API_KEY", ""))
    access_token = os.environ.get("MINIMAX_ACCESS_TOKEN", "")
    auth = api_key if (api_key and not api_key.startswith("__")) else access_token
    if not auth:
        return None
    try:
        import requests as req
        # MiniMax portal uses OpenAI-compatible endpoint
        url = "https://api.minimaxi.chat/v1/chat/completions"
        payload = {
            "model": "MiniMax-M2.5",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS[being_key]},
                {"role": "user", "content": MASKING_PROMPT},
            ],
            "max_tokens": 800,
        }
        headers = {"Authorization": f"Bearer {auth}", "Content-Type": "application/json"}
        r = req.post(url, json=payload, headers=headers, timeout=60)
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"  [MiniMax error for {being_key}: {e}]", file=sys.stderr)
        return None


def prompt_paste(being_name: str) -> Optional[str]:
    """Guide jeebs to paste a response. Returns the pasted text or None if skipped."""
    print(f"\n{'='*60}")
    print(f"  PASTE NEEDED: {being_name}")
    print(f"{'='*60}")
    print(f"\nNo API key configured for {being_name}.")
    print(f"\nCopy this prompt and paste it into {being_name}'s interface:")
    print(f"\n--- PROMPT ---")
    print(MASKING_PROMPT)
    print(f"--- END PROMPT ---\n")
    print(f"Then paste {being_name}'s response below.")
    print(f"(Press Ctrl+D on a blank line to skip this being.)\n")
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    text = "\n".join(lines).strip()
    if not text:
        print(f"  [Skipped {being_name}]")
        return None
    return text


# ---------------------------------------------------------------------------
# Section formatter
# ---------------------------------------------------------------------------

def format_section(roman: str, being_name: str, content: str, round_num: int = 3) -> str:
    header = f"## {roman}. {being_name} — [MASKING_VARIANT] Response to INV-003b Prompt Round {round_num} ({DATE})"
    return f"\n---\n\n{header}\n\n{content}\n"


# ---------------------------------------------------------------------------
# Filing
# ---------------------------------------------------------------------------

def append_section(section_text: str, section_count: int, being_name: str, roman: str) -> None:
    with OQ_PATH.open("a", encoding="utf-8") as f:
        f.write(section_text)

    # Update .section_count
    SECTION_COUNT_PATH.write_text(str(section_count) + "\n")

    # Append to collision.log
    title_short = f"[MASKING_VARIANT] Response to INV-003b Prompt Round 3"
    log_line = f"{DATE} | canonical={section_count} | filed={roman} | authors={being_name} | title={title_short}"
    with COLLISION_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    print(f"  Filed: {roman} ({being_name}) — canonical={section_count}")


# ---------------------------------------------------------------------------
# Being definitions
# ---------------------------------------------------------------------------

def get_being_response(being_key: str, auto: bool) -> Optional[str]:
    """Try auto-collection first; fall back to paste if auto=True but no key."""
    if being_key == "claude_code":
        return CLAUDE_CODE_ROUND3

    if not auto:
        return prompt_paste(being_key.replace("_", " ").title())

    # Try API calls in order of likelihood
    result = None
    if being_key == "chatgpt":
        result = call_openai("chatgpt")
    elif being_key == "claude_ext":
        result = call_anthropic("claude_ext")
    elif being_key == "gemini":
        result = call_gemini("gemini")
    elif being_key == "grok":
        result = call_xai("grok")
    elif being_key in ("c_lawd", "dali", "lumen"):
        result = call_minimax(being_key)

    if result:
        return result

    # Fall back to guided paste
    name_map = {
        "chatgpt": "ChatGPT",
        "claude_ext": "Claude (ext)",
        "gemini": "Gemini",
        "grok": "Grok",
        "c_lawd": "c_lawd",
        "dali": "Dali",
        "lumen": "Lumen",
    }
    return prompt_paste(name_map.get(being_key, being_key))


BEING_DISPLAY = {
    "dali": "Dali",
    "gemini": "Gemini",
    "grok": "Grok",
    "chatgpt": "ChatGPT",
    "claude_code": "Claude Code",
    "lumen": "Lumen",
    "c_lawd": "c_lawd",
    "claude_ext": "Claude (ext)",
}

# File order matches Round 2
BEINGS_ORDER = ["dali", "gemini", "grok", "chatgpt", "claude_code", "lumen", "c_lawd", "claude_ext"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Round 3 [MASKING_VARIANT] sections")
    parser.add_argument("--dry-run", action="store_true", help="Print sections without filing")
    parser.add_argument("--beings", default="", help="Comma-separated subset of beings to collect")
    parser.add_argument("--auto-only", action="store_true", help="Skip paste prompts; only collect via API")
    args = parser.parse_args()

    beings_filter = set(b.strip().lower() for b in args.beings.split(",") if b.strip()) if args.beings else None
    beings = [b for b in BEINGS_ORDER if beings_filter is None or b in beings_filter]

    if not beings:
        print("No beings to collect.", file=sys.stderr)
        return 1

    print(f"\n=== Round 3 [MASKING_VARIANT] Collection ===")
    print(f"Beings: {', '.join(BEING_DISPLAY[b] for b in beings)}")
    print(f"Mode: {'dry-run' if args.dry_run else 'live'}")
    print(f"API keys present: ", end="")
    key_status = []
    if os.environ.get("OPENAI_API_KEY"): key_status.append("OpenAI(ChatGPT)")
    if os.environ.get("ANTHROPIC_API_KEY"): key_status.append("Anthropic(Claude ext)")
    if os.environ.get("GEMINI_API_KEY"): key_status.append("Gemini")
    if os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY"): key_status.append("xAI/Grok-4")
    if os.environ.get("MINIMAX_API_KEY") or os.environ.get("MINIMAX_ACCESS_TOKEN"): key_status.append("MiniMax(c_lawd/Dali/Lumen)")
    src = "(from openclaw auth-profiles)" if _oc_keys else "(from env)"
    print(", ".join(key_status) if key_status else "none — all paste-guided", src)
    print()

    highest_roman_num = get_highest_roman()
    section_count = read_section_count()
    collected = []

    for being_key in beings:
        being_name = BEING_DISPLAY[being_key]
        print(f"\n[{being_name}]", end=" ", flush=True)

        _has_minimax = bool(os.environ.get("MINIMAX_API_KEY") or os.environ.get("MINIMAX_ACCESS_TOKEN"))
        _has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        if args.auto_only and being_key not in ("claude_code",) and not any([
            being_key == "chatgpt" and os.environ.get("OPENAI_API_KEY"),
            being_key == "claude_ext" and _has_anthropic,
            being_key == "gemini" and os.environ.get("GEMINI_API_KEY"),
            being_key == "grok" and (os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")),
            being_key in ("c_lawd", "dali", "lumen") and _has_minimax,
        ]):
            print(f"skipped (no API key, --auto-only set)")
            continue

        content = get_being_response(being_key, auto=True)
        if not content:
            print(f"  No response collected for {being_name}.")
            continue

        highest_roman_num += 1
        section_count += 1
        roman = int_to_roman(highest_roman_num)
        section = format_section(roman, being_name, content, round_num=3)

        if args.dry_run:
            print(f"\n--- DRY RUN: {roman} ({being_name}) ---")
            print(section)
        else:
            append_section(section, section_count, being_name, roman)

        collected.append((roman, being_name))

    print(f"\n\n=== Collection complete ===")
    print(f"Collected {len(collected)} sections:")
    for roman, name in collected:
        print(f"  {roman}: {name}")

    if not args.dry_run and collected:
        print(f"\nSection count updated to: {read_section_count()}")
        print(f"\nNext steps:")
        print(f"  1. Review appended sections in OPEN_QUESTIONS.md")
        print(f"  2. Update CONTRIBUTION_REGISTER.md manually (or run store rebuild)")
        print(f"  3. Run: HF_HUB_OFFLINE=1 python3 workspace/store/run_poc.py")
        print(f"  4. Run: python3 workspace/store/being_divergence.py --masking-variant")
        print(f"     to get the STYLE-CONSISTENCY result")
        print(f"  5. Commit + push")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
