"""
OPEN_QUESTIONS.md section parser.

Parses the append-only ledger into CorrespondenceSection objects.
Only sections with Roman numeral headers are treated as correspondence entries.
Structural sections (✦ Decision Rule, How to Use, etc.) are skipped.
"""
from __future__ import annotations
import re
from datetime import date
from schema import CorrespondenceSection, EXTERNAL_CALLERS

# Roman numeral lookup — covers I through LXXXIX (89) safely
ROMAN_VALUES = {
    'M': 1000, 'CM': 900, 'D': 500, 'CD': 400,
    'C': 100,  'XC': 90,  'L': 50,  'XL': 40,
    'X': 10,   'IX': 9,   'V': 5,   'IV': 4,   'I': 1
}

def roman_to_int(s: str) -> int:
    """Convert Roman numeral string to integer. Returns 0 on failure."""
    s = s.upper().strip()
    result = 0
    i = 0
    sorted_vals = sorted(ROMAN_VALUES.items(), key=lambda x: -x[1])
    while i < len(s):
        matched = False
        for symbol, value in sorted_vals:
            if s[i:i+len(symbol)] == symbol:
                result += value
                i += len(symbol)
                matched = True
                break
        if not matched:
            return 0
    return result


# Known author names for extraction
KNOWN_AUTHORS = [
    "Claude Code", "Claude (ext)", "Claude ext", "Claude",
    "c_lawd", "Dali", "Grok", "Gemini", "ChatGPT", "Heath"
]
# Ordered longest-first to avoid partial matches
KNOWN_AUTHORS_SORTED = sorted(KNOWN_AUTHORS, key=lambda x: -len(x))

# Header pattern: ## ROMAN. rest
SECTION_HEADER_RE = re.compile(
    r'^## ([IVXLCDM]+)\.\s+(.+)$',
    re.IGNORECASE
)

# Date pattern in headers
DATE_RE = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')

# Exec tag patterns in body
EXEC_TAG_RE = re.compile(r'\[EXEC:(MICRO|GOV)\]')

# Status tag patterns
STATUS_TAG_RE = re.compile(
    r'\[(EXPERIMENT PENDING|GOVERNANCE RULE CANDIDATE|PHILOSOPHICAL ONLY|CLOSED)\]'
)

# Collision note pattern in header (indicates the section was misfiled)
COLLISION_RE = re.compile(r'\[ARCHIVED|collision|misfiled|filed as', re.IGNORECASE)


def extract_author_and_title(header_body: str) -> tuple[list[str], str]:
    """
    Extract author(s) and clean title from the part after the Roman numeral.
    Handles patterns:
      - "Grok — Title (Date)"
      - "Title (c_lawd, Date)"
      - "Title (Date)"
      - "Claude Code — Title (Date)"
    """
    authors = []
    title = header_body.strip()

    # Remove date from title
    title = DATE_RE.sub('', title).strip().strip('()').strip().strip(',').strip()

    # Pattern 1: "Author — Title"
    if ' — ' in header_body:
        parts = header_body.split(' — ', 1)
        candidate = parts[0].strip()
        for known in KNOWN_AUTHORS_SORTED:
            if known.lower() in candidate.lower():
                authors.append(known)
                title = parts[1].strip()
                title = DATE_RE.sub('', title).strip().strip('()').strip()
                break

    # Pattern 2: "Title (Author, Date)" or "Title (Author)"
    if not authors:
        paren_match = re.search(r'\(([^)]+)\)', header_body)
        if paren_match:
            paren_content = paren_match.group(1)
            for known in KNOWN_AUTHORS_SORTED:
                if known.lower() in paren_content.lower():
                    authors.append(known)
                    # Title is before the paren
                    title = header_body[:paren_match.start()].strip()
                    title = title.rstrip('—').strip()
                    break

    # Clean title of leftover date/parens
    title = DATE_RE.sub('', title).strip()
    title = re.sub(r'\(\s*,?\s*\)', '', title).strip()
    title = title.strip('.,').strip()

    return authors, title


def is_external_caller(authors: list[str]) -> bool:
    for a in authors:
        if a.lower() in EXTERNAL_CALLERS:
            return True
    return False


def parse_sections(filepath: str) -> list[CorrespondenceSection]:
    """
    Parse OPEN_QUESTIONS.md into CorrespondenceSection objects.
    Only Roman-numeral-headed sections are returned.
    Canonical section number is assigned in order of appearance.
    Collisions are detected when filed number ≠ expected canonical sequence.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find all section boundaries
    section_starts = []  # (line_index, roman_str, header_body)
    for i, line in enumerate(lines):
        m = SECTION_HEADER_RE.match(line.rstrip())
        if m:
            roman_str = m.group(1).upper()
            header_body = m.group(2)
            n = roman_to_int(roman_str)
            if n > 0:  # Valid Roman numeral section
                section_starts.append((i, roman_str, header_body, n))

    sections = []
    canonical = 0  # Assign canonical numbers in order of appearance

    for idx, (line_i, roman_str, header_body, filed_int) in enumerate(section_starts):
        canonical += 1

        # Determine body: from line after header to next section header or EOF
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1][0]
        else:
            end_line = len(lines)

        body_lines = lines[line_i + 1:end_line]
        body = ''.join(body_lines).strip()

        # Detect collision: filed number should match canonical number
        # Account for the fact that early sections (I-L) are thematic, not correspondence
        # — we use canonical order, not filed order, as truth
        collision = (filed_int != canonical)

        # Extract metadata
        authors, title = extract_author_and_title(header_body)

        # Extract date from header body
        date_match = DATE_RE.search(header_body)
        created_at = date_match.group(1) if date_match else ""

        # Extract exec_tags from body
        exec_tag_matches = EXEC_TAG_RE.findall(body)
        exec_tags = list(set(f"EXEC:{t}" for t in exec_tag_matches))

        # Extract status_tags from body
        status_tag_matches = STATUS_TAG_RE.findall(body)
        status_tags = list(set(status_tag_matches))

        # Determine retro:dark fields
        retro_dark = CorrespondenceSection.retro_dark_for_number(canonical)

        # If section is retro:dark for exec_tags but we found some anyway
        # (e.g. v9 addendum within an existing section), remove from dark list
        if exec_tags and "exec_tags" in retro_dark:
            retro_dark = [f for f in retro_dark if f != "exec_tags"]

        section = CorrespondenceSection(
            canonical_section_number=canonical,
            section_number_filed=roman_str,
            collision=collision,
            authors=authors,
            created_at=created_at,
            is_external_caller=is_external_caller(authors),
            title=title,
            body=body,
            exec_tags=exec_tags,
            status_tags=status_tags,
            retro_dark_fields=retro_dark,
            response_to=None,       # retro:dark for most sections
            knowledge_refs=None,    # retro:dark for most sections
        )
        sections.append(section)

    return sections
