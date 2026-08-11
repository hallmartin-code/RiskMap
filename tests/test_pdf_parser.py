"""PDF ingestion: ordering, content preservation, metric extraction, errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from pitchdeck_onepager.errors import EmptyExtractionError, UnsupportedFileTypeError
from pitchdeck_onepager.extraction.metric_extractor import normalize_number, numeric_tokens
from pitchdeck_onepager.extraction.text_cleaner import clean_page_text, strip_repeated_lines
from pitchdeck_onepager.ingestion import load_deck
from pitchdeck_onepager.ingestion.pdf_parser import parse_pdf


def test_parses_all_pages_in_order(sample_pdf: Path) -> None:
    deck = parse_pdf(sample_pdf)

    assert deck.page_count == 12
    assert [p.page_number for p in deck.pages] == list(range(1, 13))
    assert deck.file_type == "pdf"
    assert deck.filename == "sample_pitch.pdf"


def test_slide_order_is_preserved(sample_pdf: Path) -> None:
    deck = parse_pdf(sample_pdf)

    assert "Meridian Freight OS" in deck.pages[0].raw_text
    assert "Traction" in deck.pages[4].raw_text
    assert "Raising $6M Seed" in deck.pages[10].raw_text


def test_numbers_survive_extraction_unchanged(sample_pdf: Path) -> None:
    text = parse_pdf(sample_pdf).full_text()

    for figure in ("$2.4M", "118%", "37", "71%", "114%", "$64,800", "$6M", "$12M"):
        assert figure in text, f"{figure} was lost during extraction"


def test_metrics_carry_page_provenance(sample_pdf: Path) -> None:
    deck = parse_pdf(sample_pdf)
    traction = [m for m in deck.all_metrics() if m.page_number == 5]

    values = {m.value for m in traction}
    assert "$2.4M" in values
    assert "118%" in values
    assert all(m.context for m in traction)


def test_repeated_footer_is_removed(sample_pdf: Path) -> None:
    deck = parse_pdf(sample_pdf)
    footer_pages = [p for p in deck.pages if "Confidential" in p.raw_text]

    # The footer appears on every slide of the fixture and should be stripped.
    assert footer_pages == []


def test_unsupported_extension_is_rejected(tmp_path: Path, config) -> None:
    bogus = tmp_path / "deck.txt"
    bogus.write_text("not a deck", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError):
        load_deck(bogus, config)


def test_missing_file_is_rejected(tmp_path: Path, config) -> None:
    with pytest.raises(UnsupportedFileTypeError):
        load_deck(tmp_path / "nope.pdf", config)


def test_empty_deck_is_rejected(tmp_path: Path, config) -> None:
    from reportlab.pdfgen.canvas import Canvas

    empty = tmp_path / "empty.pdf"
    canvas = Canvas(str(empty))
    canvas.showPage()
    canvas.save()

    with pytest.raises(EmptyExtractionError):
        load_deck(empty, config)


# --- cleanup / normalisation units -------------------------------------------


def test_hard_wrapped_lines_are_rejoined() -> None:
    cleaned = clean_page_text("We serve mid-market brokers who\nlose hours each week")
    assert "brokers who lose hours" in cleaned


def test_bullets_are_not_merged_into_previous_line() -> None:
    cleaned = clean_page_text("Traction highlights,\n• $2.4M ARR\n• 37 customers")
    assert cleaned.count("•") == 2


def test_page_numbers_are_dropped() -> None:
    assert clean_page_text("Real content here\n7") == "Real content here"


def test_strip_repeated_lines_leaves_short_decks_alone() -> None:
    pages = ["Header\nA", "Header\nB"]
    assert strip_repeated_lines(pages) == pages


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$2.4M", "2.4m"),
        ("$2,400,000", "2400000"),
        ("2.4 million", "2.4m"),
        ("118 %", "118%"),
        ("71.0%", "71%"),
        ("3.5x", "3.5x"),
        ("$64,800", "64800"),
    ],
)
def test_number_normalisation_preserves_meaning(raw: str, expected: str) -> None:
    assert normalize_number(raw) == expected


def test_ranges_are_kept_as_two_values_not_averaged() -> None:
    tokens = numeric_tokens("$1.2M-$1.5M")
    assert tokens == {"1.2m", "1.5m"}
    assert "1.35m" not in tokens
