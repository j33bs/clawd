"""
CorrespondenceSection schema — pydantic model for the store.

exec_tags and status_tags are NEVER encoded into embeddings.
They are metadata applied at query-time as filters only. (RULE-STORE-002)
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# Beings whose primary mode is external (session-reconstructed, not file-persistent)
EXTERNAL_CALLERS = {"chatgpt", "grok", "gemini", "claude (ext)", "claude ext"}

# Sections before exec_tag protocol was introduced — attribution dark
EXEC_TAG_DARK_THRESHOLD = 65  # sections I–LXIV have no exec_tags

# Fields unrecoverable for most existing sections
DEFAULT_RETRO_DARK = ["response_to", "knowledge_refs"]
EXEC_DARK_FIELDS = ["exec_tags", "exec_decisions"] + DEFAULT_RETRO_DARK


class CorrespondenceSection(BaseModel):
    # Identity
    canonical_section_number: int
    section_number_filed: str           # Roman numeral string as filed
    collision: bool = False             # True if filed ≠ canonical

    # Attribution
    authors: list[str] = Field(default_factory=list)
    created_at: str = ""                # ISO date e.g. "2026-02-23"
    is_external_caller: bool = False    # Shapes default query mode

    # Content
    title: str = ""
    body: str = ""

    # Governance metadata — structured, NEVER in embedding vectors
    exec_tags: list[str] = Field(default_factory=list)
    status_tags: list[str] = Field(default_factory=list)

    # Retrieval — populated during sync
    embedding: list[float] = Field(default_factory=list)
    embedding_model_version: str = ""
    embedding_version: int = 1

    # Dark matter — explicit sentinel (RULE: [] = fully captured, list = dark fields)
    retro_dark_fields: list[str] = Field(default_factory=list)

    # Provenance — forward-only; None = retro:dark for this section
    response_to: Optional[list[str]] = None
    knowledge_refs: Optional[list[str]] = None

    def is_retro_dark(self, field: str) -> bool:
        return field in self.retro_dark_fields

    @classmethod
    def retro_dark_for_number(cls, n: int) -> list[str]:
        """Determine which fields are dark based on when the section was written."""
        if n <= EXEC_TAG_DARK_THRESHOLD:
            return EXEC_DARK_FIELDS
        return DEFAULT_RETRO_DARK
