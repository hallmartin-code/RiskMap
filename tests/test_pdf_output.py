"""Rendering: the one-page guarantee, readability floors and content priority."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from pitchdeck_onepager.errors import OnePageOverflowError
from pitchdeck_onepager.models.investment_analysis import InvestmentOnePager
from pitchdeck_onepager.rendering.onepager import (
    CAP_LEVELS,
    MARGIN,
    DocumentMeta,
    _build_blocks,
    _total_height,
    render_onepager,
)
from pitchdeck_onepager.rendering.styles import MIN_BODY, DENSITY_PROFILES, Theme, page_size

META = DocumentMeta(source_filename="sample_pitch.pdf", slide_count=12, model="test-model")


def _render(analysis: InvestmentOnePager, path: Path, **kwargs):
    return render_onepager(analysis, path, META, **kwargs)


def test_output_is_exactly_one_page(sample_analysis, tmp_path: Path) -> None:
    result = _render(sample_analysis, tmp_path / "out.pdf")

    assert result.page_count == 1
    assert len(PdfReader(str(result.output_path)).pages) == 1


def test_a4_output_is_also_one_page(sample_analysis, tmp_path: Path) -> None:
    result = _render(sample_analysis, tmp_path / "a4.pdf", page_size_name="A4")

    assert result.page_count == 1
    width, height = PdfReader(str(result.output_path)).pages[0].mediabox.upper_right
    assert round(float(width)) == 595 and round(float(height)) == 842


def test_rendered_text_contains_the_decision_content(sample_analysis, tmp_path: Path) -> None:
    result = _render(sample_analysis, tmp_path / "out.pdf")
    text = PdfReader(str(result.output_path)).pages[0].extract_text()

    assert "Meridian Freight OS" in text
    assert "6.4" in text
    assert "MODERATE" in text
    for heading in (
        "CORE INVESTMENT BELIEF",
        "EVIDENCE SUPPORTING THESIS",
        "WHAT MUST BE TRUE",
        "WEAKEST LINK",
        "RISK MAP",
        "NEXT PROOF POINT",
    ):
        assert heading in text, f"missing section: {heading}"


def test_metrics_and_their_values_are_rendered(sample_analysis, tmp_path: Path) -> None:
    result = _render(sample_analysis, tmp_path / "out.pdf")
    text = PdfReader(str(result.output_path)).pages[0].extract_text()

    for value in ("$2.4M", "118%", "71%"):
        assert value in text


def test_source_markers_can_be_disabled(sample_analysis, tmp_path: Path) -> None:
    with_markers = PdfReader(
        str(_render(sample_analysis, tmp_path / "a.pdf", show_sources=True).output_path)
    ).pages[0].extract_text()
    without = PdfReader(
        str(_render(sample_analysis, tmp_path / "b.pdf", show_sources=False).output_path)
    ).pages[0].extract_text()

    assert "[S5]" in with_markers
    assert "[S5]" not in without


def test_content_fits_without_compression_for_a_normal_analysis(sample_analysis, tmp_path: Path) -> None:
    result = _render(sample_analysis, tmp_path / "out.pdf")

    assert result.caps_level == 0, "a typical analysis should not need content trimming"
    assert result.font_scale >= 0.95


def test_verbose_analysis_still_produces_one_page(sample_analysis, tmp_path: Path) -> None:
    """A verbose but plausible analysis is absorbed by the compression ladder."""
    filler = (
        "This sentence exists to consume vertical space and force the renderer to "
        "compress the layout across several density and content levels. "
    ) * 2
    bloated = sample_analysis.model_copy(deep=True)
    bloated.weak_link = filler
    bloated.strongest_counterargument = filler
    bloated.highest_value_test = filler
    bloated.core_investment_belief = filler
    for item in bloated.strongest_evidence:
        item.evidence = filler
    for risk in bloated.major_risks:
        risk.risk = filler
        risk.early_warning = filler
    bloated.key_questions = [filler for _ in range(5)]

    result = _render(bloated, tmp_path / "big.pdf")

    assert result.page_count == 1
    assert result.caps_level > 0 or result.font_scale < 1.0


def test_overflow_raises_rather_than_shrinking_below_minimum(sample_analysis, tmp_path: Path) -> None:
    absurd = sample_analysis.model_copy(deep=True)
    absurd.weak_link = "word " * 4000
    absurd.highest_value_test = "word " * 4000

    with pytest.raises(OnePageOverflowError):
        _render(absurd, tmp_path / "overflow.pdf")


def test_body_font_never_drops_below_the_minimum() -> None:
    for font_scale, space_scale in DENSITY_PROFILES:
        theme = Theme(font_scale=font_scale, space_scale=space_scale)
        assert theme.body_size >= MIN_BODY


def test_compression_levels_only_ever_remove_content(sample_analysis) -> None:
    width = page_size("LETTER")[0] - 2 * MARGIN
    theme = Theme()
    heights = [_total_height(_build_blocks(sample_analysis, caps), width, theme) for caps in CAP_LEVELS]

    assert heights == sorted(heights, reverse=True)


def test_lowest_priority_sections_are_dropped_first(sample_analysis) -> None:
    """Thesis, conviction, traction, dependency, weakest link and risks always survive."""
    blocks = _build_blocks(sample_analysis, CAP_LEVELS[-1])
    titles = {getattr(b, "title", "") for b in blocks}
    nested = {
        getattr(part, "title", "")
        for b in blocks
        for part in (getattr(b, "left", None), getattr(b, "right", None))
        if part is not None
    }
    titles |= nested

    assert "Core investment belief" in titles
    assert "Weakest link" in titles
    assert "Risk map" in titles
    assert "Key diligence questions" not in titles


def _spans(pdf_path: Path):
    """Every text span on page 1, with its bounding box."""
    import pymupdf

    document = pymupdf.open(pdf_path)
    try:
        page = document[0]
        return [
            (span["text"], span["bbox"])
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
            if span["text"].strip()
        ], page.rect
    finally:
        document.close()


def test_no_text_escapes_the_page_margins(sample_analysis, tmp_path: Path) -> None:
    """Guards against clipped text - e.g. graphics state leaking between blocks."""
    result = _render(sample_analysis, tmp_path / "out.pdf")
    spans, rect = _spans(result.output_path)

    tolerance = 1.5
    # The footer sits deliberately inside the bottom margin.
    bottom_limit = rect.height - MARGIN * 0.35

    overflowing = [
        text
        for text, (x0, y0, x1, y1) in spans
        if x1 > rect.width - MARGIN + tolerance
        or x0 < MARGIN - tolerance
        or y0 < MARGIN * 0.4
        or y1 > bottom_limit
    ]

    assert not overflowing, f"text drawn outside the frame: {overflowing[:5]}"


def test_two_column_text_stays_in_its_column(sample_analysis, tmp_path: Path) -> None:
    """A left-column bullet must not bleed into the right column's x range."""
    from pitchdeck_onepager.rendering.layout import COLUMN_GAP

    result = _render(sample_analysis, tmp_path / "out.pdf")
    spans, rect = _spans(result.output_path)

    usable = rect.width - 2 * MARGIN - COLUMN_GAP
    divider = MARGIN + usable / 2
    # Section headings identify the two-column bands; their bullets follow.
    evidence_bullets = [
        (text, box)
        for text, box in spans
        if text.startswith("$2.4M ARR across") or text.startswith("Net revenue retention")
    ]

    assert evidence_bullets, "expected the evidence column to render"
    for text, (_x0, _y0, x1, _y1) in evidence_bullets:
        assert x1 <= divider + 1, f"left-column text crossed the divider: {text}"


def test_long_metric_values_are_truncated_not_overflowed(sample_analysis, tmp_path: Path) -> None:
    """A verbose metric must never run past its column or off the page."""
    wordy = sample_analysis.model_copy(deep=True)
    wordy.traction_metrics[0].value = "CAC $19,400 blended; payback in 14 months at current margin"
    wordy.traction_metrics[0].label = "Customer acquisition cost and payback period"

    result = _render(wordy, tmp_path / "wordy.pdf")
    spans, rect = _spans(result.output_path)

    overflowing = [t for t, (_x0, _y0, x1, _y1) in spans if x1 > rect.width - MARGIN + 1.5]
    assert not overflowing, f"metric text overflowed: {overflowing[:3]}"


def test_no_glyph_is_rendered_below_the_readability_floor(sample_analysis, tmp_path: Path) -> None:
    """Overflow is never solved by shrinking text below the documented minimum."""
    from pitchdeck_onepager.rendering.styles import MIN_FOOTNOTE

    stressed = sample_analysis.model_copy(deep=True)
    for metric in stressed.traction_metrics:
        metric.label = "Customer acquisition cost and blended payback period"
        metric.value = "$19,400 blended; payback in 14 months"

    for page_size_name in ("LETTER", "A4"):
        result = _render(stressed, tmp_path / f"{page_size_name}.pdf", page_size_name=page_size_name)
        sizes = [size for _text, _box, size in _spans_with_size(result.output_path)]

        assert sizes, "expected rendered text"
        assert min(sizes) >= MIN_FOOTNOTE - 0.11, (
            f"{page_size_name}: smallest glyph {min(sizes):.2f}pt is below the "
            f"{MIN_FOOTNOTE}pt floor"
        )


def _spans_with_size(pdf_path: Path):
    import pymupdf

    document = pymupdf.open(pdf_path)
    try:
        page = document[0]
        return [
            (span["text"], span["bbox"], span["size"])
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
            if span["text"].strip()
        ]
    finally:
        document.close()


def test_blank_template_renders_one_page_with_no_company_content(tmp_path: Path) -> None:
    """The structural template must carry placeholders only."""
    from pitchdeck_onepager.rendering.template import render_template

    result = render_template(tmp_path / "template.pdf")
    text = PdfReader(str(result.output_path)).pages[0].extract_text()

    assert result.page_count == 1
    assert "[COMPANY NAME]" in text
    for heading in (
        "CORE INVESTMENT BELIEF",
        "EVIDENCE SUPPORTING THESIS",
        "WHAT MUST BE TRUE",
        "WEAKEST LINK",
        "RISK MAP",
        "CONVICTION STRENGTHENS IF",
        "CONVICTION WEAKENS IF",
        "BEST OPPOSING VIEW",
        "THESIS INVALID IF",
        "NEXT PROOF POINT",
        "KEY DILIGENCE QUESTIONS",
    ):
        assert heading in text, f"template is missing section: {heading}"

    # No verdict-shaped content: the badge shows the field, not a score.
    assert "X.X" in text and "[BAND]" in text
    for leaked in ("Meridian", "$2.4M", "MODERATE", "Company Data"):
        assert leaked not in text, f"template leaked non-placeholder content: {leaked}"


def test_blank_template_has_the_same_sections_as_a_real_analysis(sample_analysis) -> None:
    """The template cannot drift from production output: same blocks, same order."""
    from pitchdeck_onepager.rendering.template import build_template_analysis

    def titles(analysis) -> list[str]:
        blocks = _build_blocks(analysis, CAP_LEVELS[0])
        out: list[str] = []
        for block in blocks:
            for part in (block, getattr(block, "left", None), getattr(block, "right", None)):
                if part is not None and getattr(part, "title", None):
                    out.append(part.title)
        return out

    assert titles(build_template_analysis()) == titles(sample_analysis)


def test_empty_metric_strip_is_skipped(sample_analysis, tmp_path: Path) -> None:
    no_metrics = sample_analysis.model_copy(deep=True)
    no_metrics.traction_metrics = []

    result = _render(no_metrics, tmp_path / "nometrics.pdf")
    assert result.page_count == 1
