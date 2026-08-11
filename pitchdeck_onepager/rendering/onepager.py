"""One-page PDF renderer with deterministic page-fit logic.

The renderer never lets content flow onto a second page. It measures the whole
document before drawing anything and searches a two-dimensional ladder for the
first combination that fits:

1. **Density** - font and spacing scales, tried first so that content is
   preserved in preference to cosmetics.
2. **Content caps** - progressively fewer items per section, in reverse order of
   investment priority, only once the density ladder is exhausted.

Font sizes never fall below the minimums declared in :mod:`rendering.styles`.
If nothing fits, the renderer raises rather than shipping an unreadable or
truncated page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from ..errors import OnePageOverflowError, RenderError
from ..logging_setup import get_logger
from ..models.investment_analysis import InvestmentOnePager
from .layout import (
    Block,
    BeliefBlock,
    BulletBlock,
    HeaderBlock,
    MetricStrip,
    NumberedBlock,
    ProseBlock,
    RiskTable,
    RuleBlock,
    TwoColumn,
)
from .styles import (
    CONVICTION_LOW,
    DENSITY_PROFILES,
    FONT,
    HAIRLINE,
    MIN_FOOTNOTE,
    MUTED,
    Theme,
    page_size,
)

log = get_logger("rendering.onepager")

MARGIN = 33.0
FOOTER_RESERVE = 17.0


@dataclass(frozen=True)
class ContentCaps:
    """How many items each section may render at this compression level."""

    metrics: int
    evidence: int
    assumptions: int
    risks: int
    triggers: int
    questions: int
    show_questions: bool = True
    show_counterargument: bool = True


#: Compression ladder. Later levels drop the lowest-priority content first:
#: diligence questions, then the opposing view. Thesis, conviction, traction,
#: critical dependency, weakest link and risks are never dropped.
CAP_LEVELS: tuple[ContentCaps, ...] = (
    ContentCaps(metrics=6, evidence=5, assumptions=5, risks=5, triggers=4, questions=5),
    ContentCaps(metrics=6, evidence=4, assumptions=4, risks=4, triggers=3, questions=4),
    ContentCaps(metrics=5, evidence=4, assumptions=4, risks=4, triggers=3, questions=3),
    ContentCaps(metrics=4, evidence=3, assumptions=3, risks=3, triggers=2, questions=3),
    ContentCaps(metrics=4, evidence=3, assumptions=3, risks=3, triggers=2, questions=0, show_questions=False),
    ContentCaps(
        metrics=4,
        evidence=3,
        assumptions=3,
        risks=3,
        triggers=2,
        questions=0,
        show_questions=False,
        show_counterargument=False,
    ),
)


@dataclass
class DocumentMeta:
    """Provenance shown in the page footer."""

    source_filename: str
    #: ``str`` only for the blank template, which shows "[n] slides".
    slide_count: int | str
    model: str = ""
    generated_on: str = ""

    def __post_init__(self) -> None:
        if not self.generated_on:
            self.generated_on = date.today().isoformat()


@dataclass
class RenderResult:
    output_path: Path
    font_scale: float
    space_scale: float
    caps_level: int
    page_count: int

    def summary(self) -> str:
        return (
            f"1 page @ font x{self.font_scale:.3f}, spacing x{self.space_scale:.2f}, "
            f"content level {self.caps_level}"
        )


# --- Block assembly -----------------------------------------------------------


def _build_blocks(
    analysis: InvestmentOnePager, caps: ContentCaps, placeholder_badge: bool = False
) -> list[Block]:
    blocks: list[Block] = [
        HeaderBlock(
            company=analysis.company_name,
            description=analysis.company_description,
            chips=analysis.meta_chips(),
            score=analysis.conviction_score,
            label=analysis.conviction_label,
            placeholder=placeholder_badge,
        ),
        RuleBlock(weight=1.1),
        _belief_block(analysis),
        MetricStrip(
            [(m.label, m.value, m.source_page) for m in analysis.traction_metrics[: caps.metrics]]
        ),
        TwoColumn(
            BulletBlock(
                "Evidence supporting thesis",
                [
                    (
                        item.evidence,
                        f"{item.significance} ({item.evidence_type}, {item.strength.lower()})",
                        item.source_page,
                    )
                    for item in analysis.strongest_evidence[: caps.evidence]
                ],
            ),
            BulletBlock(
                "What must be true",
                [
                    (
                        item.assumption,
                        (
                            f"{item.why_it_matters} [{item.status.lower()}]"
                            + (" — CRITICAL DEPENDENCY" if item.is_critical_dependency else "")
                        ),
                        None,
                    )
                    for item in analysis.key_assumptions[: caps.assumptions]
                ],
            ),
        ),
        ProseBlock("Weakest link", analysis.weak_link, accent_bar=True, bar_color=CONVICTION_LOW),
        RiskTable(
            "Risk map",
            [(r.risk, r.probability, r.impact, r.early_warning) for r in analysis.major_risks[: caps.risks]],
        ),
        TwoColumn(
            BulletBlock(
                "Conviction strengthens if",
                [("", text, None) for text in analysis.conviction_strengthens_if[: caps.triggers]],
            ),
            BulletBlock(
                "Conviction weakens if",
                [("", text, None) for text in analysis.conviction_weakens_if[: caps.triggers]],
            ),
        ),
        TwoColumn(
            ProseBlock(
                "Best opposing view",
                analysis.strongest_counterargument if caps.show_counterargument else "",
            ),
            BulletBlock(
                "Thesis invalid if",
                [("", text, None) for text in analysis.thesis_invalid_if[:2]],
            ),
        ),
        ProseBlock("Next proof point", analysis.highest_value_test, accent_bar=True),
    ]

    if caps.show_questions and caps.questions:
        blocks.append(NumberedBlock("Key diligence questions", analysis.key_questions[: caps.questions]))

    return [b for b in blocks if not b.is_empty]


def _belief_block(analysis: InvestmentOnePager) -> BeliefBlock:
    text = analysis.core_investment_belief.strip()
    if analysis.conviction_rationale.strip():
        text = f"{text} {analysis.conviction_rationale.strip()}"
    return BeliefBlock("Core investment belief", text)


# --- Fitting ------------------------------------------------------------------


def _total_height(blocks: list[Block], width: float, theme: Theme) -> float:
    heights = [b.measure(width, theme) for b in blocks]
    return sum(heights) + theme.block_gap * max(0, len(blocks) - 1)


def _fit(
    analysis: InvestmentOnePager,
    width: float,
    available: float,
    show_sources: bool,
    placeholder_badge: bool = False,
) -> tuple[list[Block], Theme, int]:
    """Find the least-compressed layout that fits on one page."""
    best_overflow = float("inf")
    for level, caps in enumerate(CAP_LEVELS):
        blocks = _build_blocks(analysis, caps, placeholder_badge)
        for font_scale, space_scale in DENSITY_PROFILES:
            theme = Theme(font_scale=font_scale, space_scale=space_scale, show_sources=show_sources)
            total = _total_height(blocks, width, theme)
            if total <= available:
                if level or font_scale < 1.0:
                    log.info(
                        "Page fit at content level %d, font x%.3f, spacing x%.2f (%.0f/%.0fpt)",
                        level,
                        font_scale,
                        space_scale,
                        total,
                        available,
                    )
                return blocks, theme, level
            best_overflow = min(best_overflow, total - available)

    raise OnePageOverflowError(
        f"Content overflows a single page by {best_overflow:.0f}pt at maximum compression."
    )


# --- Rendering ----------------------------------------------------------------


def _draw_footer(canvas: Canvas, x: float, y: float, width: float, meta: DocumentMeta, theme: Theme) -> None:
    canvas.saveState()
    canvas.setStrokeColor(HAIRLINE)
    canvas.setLineWidth(0.5)
    canvas.line(x, y + theme.footnote_size * 1.35, x + width, y + theme.footnote_size * 1.35)

    canvas.setFont(FONT, max(MIN_FOOTNOTE, theme.footnote_size - 0.4))
    canvas.setFillColor(MUTED)
    left = f"Source: {meta.source_filename} ({meta.slide_count} slides)"
    right_parts = [f"Generated {meta.generated_on}"]
    if meta.model:
        right_parts.append(meta.model)
    right_parts.append("LLM-generated analysis - verify before any investment decision")
    right = "  ".join(right_parts)

    canvas.drawString(x, y, left[:120])
    canvas.drawRightString(x + width, y, right)
    canvas.restoreState()


def render_onepager(
    analysis: InvestmentOnePager,
    output_path: Path,
    meta: DocumentMeta,
    page_size_name: str = "LETTER",
    show_sources: bool = True,
    placeholder_badge: bool = False,
) -> RenderResult:
    """Render the analysis to a single-page PDF at ``output_path``.

    ``placeholder_badge`` renders the conviction badge as ``X.X / 10 [BAND]`` in
    neutral grey, for the blank structural template.
    """
    width_pt, height_pt = page_size(page_size_name)
    content_width = width_pt - 2 * MARGIN
    available = height_pt - 2 * MARGIN - FOOTER_RESERVE

    blocks, theme, level = _fit(analysis, content_width, available, show_sources, placeholder_badge)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        canvas = Canvas(
            str(output_path),
            pagesize=(width_pt, height_pt),
            pageCompression=1,
            invariant=1,
        )
        canvas.setTitle(f"{analysis.company_name} - Investment One-Pager")
        canvas.setSubject("Confidential investment analysis")
        canvas.setAuthor("pitchdeck_onepager")

        cursor = height_pt - MARGIN
        for index, block in enumerate(blocks):
            if index:
                cursor -= theme.block_gap
            height = block.measure(content_width, theme)
            block.draw(canvas, MARGIN, cursor, content_width, theme)
            cursor -= height

        _draw_footer(canvas, MARGIN, MARGIN * 0.55, content_width, meta, theme)
        canvas.showPage()
        canvas.save()
    except Exception as exc:  # noqa: BLE001 - surface any drawing failure cleanly
        raise RenderError(f"Failed to render the PDF: {exc}") from exc

    page_count = _verify_page_count(output_path)
    if page_count != 1:
        raise OnePageOverflowError(f"The rendered PDF has {page_count} pages; exactly 1 is required.")

    return RenderResult(
        output_path=output_path,
        font_scale=theme.font_scale,
        space_scale=theme.space_scale,
        caps_level=level,
        page_count=page_count,
    )


def _verify_page_count(path: Path) -> int:
    """Independently confirm the output really is one page."""
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except ImportError:  # pragma: no cover - pypdf is a declared dependency
        log.warning("pypdf is not installed; skipping page-count verification.")
        return 1
    except Exception as exc:  # pragma: no cover
        raise RenderError(f"Could not verify the rendered PDF: {exc}") from exc
