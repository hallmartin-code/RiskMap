"""Numeric extraction and normalisation.

Two jobs:

1. Pull metric-looking tokens out of deck text with their surrounding context,
   so the analysis prompt can see them in one place.
2. Provide the normalisation used by the hallucination control in
   :mod:`analysis.provenance` - a number the model reports must be traceable to
   a number that actually appears in the deck.

Normalisation is deliberately lossless in meaning: units and magnitude suffixes
are preserved, only formatting differences (commas, spacing, spelled-out
magnitudes, currency symbols) are collapsed.
"""

from __future__ import annotations

import re

from ..models.deck import ExtractedMetric

#: Matches "$2.4M", "118%", "37", "3.5x", "$1.2M-$1.5M" (each side separately).
NUMBER_RE = re.compile(
    r"""
    (?P<currency>[$€£¥])?\s?
    (?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    \s?
    (?P<suffix>%|[Xx]\b|
        (?:[MBKmbk])(?![A-Za-z])|
        \s?(?:million|billion|thousand|bn|mm)\b
    )?
    """,
    re.VERBOSE,
)

_MAGNITUDE_WORDS = {
    "million": "m",
    "mm": "m",
    "billion": "b",
    "bn": "b",
    "thousand": "k",
}

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def normalize_number(token: str) -> str:
    """Collapse formatting differences while preserving meaning.

    ``"$2,400,000"`` -> ``"2400000"``; ``"$2.4 million"`` -> ``"2.4m"``;
    ``"118 %"`` -> ``"118%"``. Trailing zeros are trimmed so ``"71.0%"`` and
    ``"71%"`` compare equal.
    """
    match = NUMBER_RE.search(token.strip())
    if not match:
        return token.strip().lower()

    number = match.group("number").replace(",", "")
    if "." in number:
        number = number.rstrip("0").rstrip(".")

    suffix = (match.group("suffix") or "").strip().lower()
    suffix = _MAGNITUDE_WORDS.get(suffix, suffix)
    if suffix == "x":
        suffix = "x"
    return f"{number}{suffix}"


def _classify(currency: str | None, suffix: str | None, number: str) -> str:
    suffix = (suffix or "").strip().lower()
    if currency:
        return "currency"
    if suffix == "%":
        return "percent"
    if suffix == "x":
        return "multiple"
    if _YEAR_RE.match(number.replace(",", "")):
        return "date"
    if suffix in {"m", "b", "k", "million", "billion", "thousand", "bn", "mm"}:
        return "count"
    return "count" if number.replace(",", "").isdigit() else "other"


def numeric_tokens(text: str) -> set[str]:
    """All normalised numeric tokens present in a block of text."""
    tokens: set[str] = set()
    for match in NUMBER_RE.finditer(text):
        tokens.add(normalize_number(match.group(0)))
    return tokens


def _context(text: str, start: int, end: int, window: int = 60) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return " ".join(text[left:right].split())


def extract_metrics(text: str, page_number: int, max_per_page: int = 40) -> list[ExtractedMetric]:
    """Extract metric-looking tokens with context from one page of text."""
    metrics: list[ExtractedMetric] = []
    seen: set[tuple[str, str]] = set()

    for match in NUMBER_RE.finditer(text):
        raw = match.group(0).strip()
        number = match.group("number")
        kind = _classify(match.group("currency"), match.group("suffix"), number)

        # Bare small integers with no unit are usually layout noise.
        if kind == "count" and not match.group("suffix") and not match.group("currency"):
            digits = number.replace(",", "")
            if digits.isdigit() and len(digits) <= 2:
                continue

        context = _context(text, match.start(), match.end())
        key = (normalize_number(raw), context[:40])
        if key in seen:
            continue
        seen.add(key)

        metrics.append(
            ExtractedMetric(
                raw_text=raw,
                value=raw,
                kind=kind,  # type: ignore[arg-type]
                context=context,
                page_number=page_number,
            )
        )
        if len(metrics) >= max_per_page:
            break
    return metrics
