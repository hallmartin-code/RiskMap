"""Prompt assembly for the analysis and compression stages.

The system prompt lives in ``prompts/investor_system_prompt.txt`` so it can be
edited without touching application code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..models.deck import DeckDocument

PROMPT_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPT_DIR / "investor_system_prompt.txt"

#: Cap on deck text sent to the model. Large enough for any realistic deck.
MAX_DECK_CHARS = 220_000


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_analysis_user_prompt(deck: DeckDocument) -> str:
    """User turn for stage 1: the normalised deck plus the extracted numbers."""
    deck_text = deck.to_prompt_text()
    truncation_note = ""
    if len(deck_text) > MAX_DECK_CHARS:
        deck_text = deck_text[:MAX_DECK_CHARS]
        truncation_note = (
            "\n\n[NOTE: the deck text was truncated at the extraction limit. "
            "Base your analysis only on what is shown above.]"
        )

    numbers = _format_extracted_numbers(deck)
    warnings = ""
    if deck.warnings:
        warnings = "\n\nEXTRACTION WARNINGS (affect what you can rely on):\n" + "\n".join(
            f"- {w}" for w in deck.warnings[:10]
        )

    return (
        "Analyse the pitch deck below and return the structured investment "
        "analysis defined by the JSON schema.\n\n"
        f"{deck_text}{truncation_note}\n\n"
        f"{numbers}{warnings}\n\n"
        "Every figure you report must appear in the deck text above, written "
        "exactly as it appears there."
    )


def _format_extracted_numbers(deck: DeckDocument, limit: int = 90) -> str:
    """A compact index of numeric tokens found in the deck, with slide numbers."""
    metrics = deck.all_metrics()
    if not metrics:
        return "NUMERIC VALUES FOUND IN DECK: none detected."

    seen: set[tuple[str, int]] = set()
    lines: list[str] = []
    for metric in metrics:
        key = (metric.value, metric.page_number)
        if key in seen:
            continue
        seen.add(key)
        context = metric.context[:90]
        lines.append(f"- [S{metric.page_number}] {metric.value} :: {context}")
        if len(lines) >= limit:
            break

    return (
        "NUMERIC VALUES FOUND IN DECK (the complete set of figures you may cite):\n"
        + "\n".join(lines)
    )


COMPRESSION_SYSTEM_PROMPT = """You compress an existing structured investment analysis so it fits on one printed page.

You are editing, not analysing. Obey these rules exactly:

- Preserve every factual claim, number, unit, range and qualifier verbatim.
- Preserve all investment judgments, risk severities, conviction score and label.
- Preserve the number of items in every list. Do not drop, merge or add entries.
- Never introduce a claim, figure, company, competitor or metric that is not already present.
- Remove repetition, hedging, filler and restated context. Tighten prose only.
- Prose fields become one sentence where possible; `significance` and `why_it_matters` become a single clause.
- Return the same JSON schema with the same field values, only shorter text.
"""


def build_compression_user_prompt(analysis_json: str, target_reduction: int) -> str:
    return (
        f"Shorten the prose in this analysis by roughly {target_reduction}% without "
        "losing any fact, number, qualifier or judgment. Keep every list at its "
        "current length.\n\n"
        f"{analysis_json}"
    )
