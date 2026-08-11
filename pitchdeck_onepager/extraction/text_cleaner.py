"""Conservative cleanup of extracted deck text.

Pitch decks extract badly: hard-wrapped lines, fragmented bullets, repeated
headers/footers. The rules here fix layout noise only. Numeric values, units,
ranges and currency symbols are never rewritten - changing '$1.2M-$1.5M' into
'$1.35M' would change the meaning of the claim.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence

_BULLET_CHARS = "•·▪◦‣–—*"
_BULLET_RE = re.compile(rf"^\s*[{re.escape(_BULLET_CHARS)}]\s*")
_PAGE_NUM_RE = re.compile(r"^\s*(?:page\s*)?\d{1,3}\s*(?:/\s*\d{1,3})?\s*$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"[ \t ]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

# A line that ends mid-sentence and is followed by a lowercase continuation is a
# hard wrap, not a real line break.
_CONTINUES_RE = re.compile(r"[a-z,;:\-]$")
_STARTS_LOWER_RE = re.compile(r"^[a-z(]")


def strip_repeated_lines(pages: Sequence[str], min_pages: int = 3) -> list[str]:
    """Remove header/footer lines that repeat across most pages.

    A line must appear on at least ``min_pages`` pages *and* on more than half of
    them to be considered boilerplate. Short decks are left untouched.
    """
    if len(pages) < min_pages:
        return list(pages)

    counter: Counter[str] = Counter()
    for text in pages:
        seen = {ln.strip() for ln in text.splitlines() if 0 < len(ln.strip()) <= 80}
        counter.update(seen)

    threshold = max(min_pages, len(pages) // 2 + 1)
    boilerplate = {line for line, count in counter.items() if count >= threshold}
    if not boilerplate:
        return list(pages)

    cleaned: list[str] = []
    for text in pages:
        kept = [ln for ln in text.splitlines() if ln.strip() not in boilerplate]
        cleaned.append("\n".join(kept))
    return cleaned


def _dedupe_adjacent(lines: Iterable[str]) -> list[str]:
    """Drop consecutive duplicate lines (a common PDF double-render artifact)."""
    out: list[str] = []
    for line in lines:
        if out and line.strip() and line.strip() == out[-1].strip():
            continue
        out.append(line)
    return out


def _unwrap(lines: Sequence[str]) -> list[str]:
    """Rejoin lines broken by hard wrapping."""
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if (
            out
            and stripped
            and not _BULLET_RE.match(line)
            and _CONTINUES_RE.search(out[-1])
            and _STARTS_LOWER_RE.match(stripped)
        ):
            out[-1] = f"{out[-1]} {stripped}"
        else:
            out.append(stripped)
    return out


def clean_page_text(raw: str) -> str:
    """Normalise whitespace and layout artifacts on a single page."""
    if not raw:
        return ""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", "\n").replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = _WHITESPACE_RE.sub(" ", text)

    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln and not _PAGE_NUM_RE.match(ln)]
    lines = _dedupe_adjacent(lines)
    lines = _unwrap(lines)

    cleaned = "\n".join(ln for ln in lines if ln)
    return _MULTI_NEWLINE_RE.sub("\n\n", cleaned).strip()


def split_bullets(text: str) -> list[str]:
    """Extract bullet-like lines, with leading markers removed."""
    bullets: list[str] = []
    for line in text.splitlines():
        if _BULLET_RE.match(line):
            item = _BULLET_RE.sub("", line).strip()
            if item:
                bullets.append(item)
    return bullets


def guess_title(text: str, max_len: int = 90) -> str | None:
    """Use the first short, non-bullet line as the slide title."""
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or _BULLET_RE.match(line):
            continue
        if len(candidate) <= max_len:
            return candidate
        return None
    return None
