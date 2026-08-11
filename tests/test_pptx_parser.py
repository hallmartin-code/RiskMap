"""PPTX ingestion, including titles, speaker notes and legacy .ppt handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from pitchdeck_onepager.errors import LibreOfficeUnavailableError
from pitchdeck_onepager.ingestion.ppt_converter import convert_ppt_to_pptx, find_libreoffice
from pitchdeck_onepager.ingestion.pptx_parser import parse_pptx


def test_parses_all_slides_in_order(sample_pptx: Path) -> None:
    deck = parse_pptx(sample_pptx)

    assert deck.page_count == 12
    assert [p.page_number for p in deck.pages] == list(range(1, 13))
    assert deck.file_type == "pptx"


def test_slide_content_matches_source_order(sample_pptx: Path) -> None:
    deck = parse_pptx(sample_pptx)

    assert "Meridian Freight OS" in deck.pages[0].raw_text
    assert "$2.4M ARR" in deck.pages[4].raw_text
    assert "Raising $6M Seed" in deck.pages[10].raw_text


def test_speaker_notes_are_captured(sample_pptx: Path) -> None:
    deck = parse_pptx(sample_pptx)
    assert "Speaker notes for 'Traction'." in deck.pages[4].speaker_notes


def test_numbers_survive_extraction(sample_pptx: Path) -> None:
    text = parse_pptx(sample_pptx).full_text()
    for figure in ("$2.4M", "118%", "71%", "$64,800", "$6M"):
        assert figure in text


def test_metrics_are_extracted_with_page_numbers(sample_pptx: Path) -> None:
    deck = parse_pptx(sample_pptx)
    pages_with_metrics = {m.page_number for m in deck.all_metrics()}
    assert 5 in pages_with_metrics


def test_legacy_ppt_fails_clearly_without_libreoffice(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "pitchdeck_onepager.ingestion.ppt_converter.find_libreoffice", lambda *_args, **_kw: None
    )
    legacy = tmp_path / "old.ppt"
    legacy.write_bytes(b"\xd0\xcf\x11\xe0")

    with pytest.raises(LibreOfficeUnavailableError) as excinfo:
        convert_ppt_to_pptx(legacy, tmp_path)

    assert "LibreOffice" in str(excinfo.value)


def test_find_libreoffice_accepts_explicit_path(tmp_path: Path) -> None:
    fake = tmp_path / "soffice"
    fake.write_text("", encoding="utf-8")
    assert find_libreoffice(str(fake)) == str(fake)
