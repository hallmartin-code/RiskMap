"""Normalised internal representation of an ingested pitch deck.

Every extracted statement keeps its page/slide number so downstream claims stay
traceable back to the source document.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["pdf", "pptx", "ppt"]


class ExtractedMetric(BaseModel):
    """A numeric-looking token found in the deck, with its context."""

    raw_text: str = Field(description="Exactly as it appears in the deck, e.g. '$2.4M ARR'")
    value: str = Field(description="The numeric token itself, e.g. '$2.4M'")
    kind: Literal["currency", "percent", "multiple", "count", "date", "other"] = "other"
    context: str = Field(default="", description="Surrounding text fragment")
    page_number: int


class DeckTable(BaseModel):
    page_number: int
    rows: list[list[str]] = Field(default_factory=list)

    def to_text(self) -> str:
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in self.rows if any(row))


class DeckPage(BaseModel):
    """One page (PDF) or slide (PowerPoint)."""

    page_number: int
    title: str | None = None
    raw_text: str = ""
    bullets: list[str] = Field(default_factory=list)
    tables: list[DeckTable] = Field(default_factory=list)
    metrics: list[ExtractedMetric] = Field(default_factory=list)
    speaker_notes: str = ""
    is_image_only: bool = False
    ocr_applied: bool = False

    @property
    def char_count(self) -> int:
        return len(self.raw_text.strip())

    def to_prompt_text(self, include_notes: bool = True) -> str:
        """Render this page for the LLM prompt."""
        parts: list[str] = [f"--- SLIDE {self.page_number} ---"]
        body = self.raw_text.strip()
        # PDF titles are inferred from the first body line; don't repeat them.
        if self.title and not body.startswith(self.title):
            parts.append(f"TITLE: {self.title}")
        if body:
            parts.append(body)
        for table in self.tables:
            text = table.to_text()
            if text:
                parts.append(f"TABLE:\n{text}")
        if include_notes and self.speaker_notes.strip():
            parts.append(f"SPEAKER NOTES: {self.speaker_notes.strip()}")
        if self.is_image_only:
            parts.append("[NOTE: this slide had little or no extractable text]")
        return "\n".join(parts)


class DeckDocument(BaseModel):
    """A parsed deck, ready for analysis."""

    filename: str
    file_type: SourceType
    pages: list[DeckPage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def total_chars(self) -> int:
        return sum(p.char_count for p in self.pages)

    @property
    def image_only_pages(self) -> list[int]:
        return [p.page_number for p in self.pages if p.is_image_only]

    def all_metrics(self) -> list[ExtractedMetric]:
        return [m for p in self.pages for m in p.metrics]

    def to_prompt_text(self, include_notes: bool = True) -> str:
        header = (
            f"DECK FILE: {self.filename}\n"
            f"FORMAT: {self.file_type}\n"
            f"SLIDES: {self.page_count}\n"
        )
        body = "\n\n".join(p.to_prompt_text(include_notes) for p in self.pages)
        return f"{header}\n{body}"

    def full_text(self) -> str:
        """All extracted text, used for provenance checks."""
        chunks: list[str] = []
        for page in self.pages:
            if page.title:
                chunks.append(page.title)
            chunks.append(page.raw_text)
            chunks.append(page.speaker_notes)
            for table in page.tables:
                chunks.append(table.to_text())
        return "\n".join(chunks)
