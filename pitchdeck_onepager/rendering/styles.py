"""Typography, colour and spacing for the one-pager.

A :class:`Theme` is parameterised by a font scale and a spacing scale so the
fitting logic in :mod:`rendering.onepager` can compress the document
deterministically. Minimum font sizes are enforced here: overflow is never
solved by making the page unreadable.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle

# --- Palette -----------------------------------------------------------------

INK = HexColor("#111418")
BODY = HexColor("#2B3340")
MUTED = HexColor("#69737F")
ACCENT = HexColor("#1B3A5C")
RULE = HexColor("#B9C3CE")
HAIRLINE = HexColor("#DEE4EA")
TINT = HexColor("#F1F4F7")

CONVICTION_HIGH = HexColor("#1E5B3B")
CONVICTION_MODERATE = HexColor("#8A6516")
CONVICTION_LOW = HexColor("#8A2B2B")

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

# --- Base sizes (points, at scale 1.0) ---------------------------------------

BASE_COMPANY = 19.0
BASE_SCORE = 17.0
BASE_SECTION = 8.8
BASE_BODY = 8.4
BASE_SMALL = 7.6
BASE_FOOTNOTE = 7.2
BASE_METRIC_VALUE = 11.5

# --- Minimum readable sizes (hard floor) -------------------------------------

MIN_COMPANY = 16.0
MIN_SECTION = 8.0
MIN_BODY = 7.5
MIN_FOOTNOTE = 6.5

#: (font_scale, spacing_scale) ladder, tried in order. Spacing compresses
#: faster than type, because whitespace is cheaper to lose than legibility.
DENSITY_PROFILES: tuple[tuple[float, float], ...] = (
    (1.000, 1.00),
    (1.000, 0.86),
    (0.975, 0.80),
    (0.950, 0.72),
    (0.925, 0.66),
    (0.900, 0.58),
)

PAGE_SIZES = {"LETTER": LETTER, "A4": A4}


@dataclass(frozen=True)
class Theme:
    """Resolved typography and spacing for one render attempt."""

    font_scale: float = 1.0
    space_scale: float = 1.0
    show_sources: bool = True

    # --- sizes ---
    @property
    def company_size(self) -> float:
        return max(MIN_COMPANY, BASE_COMPANY * self.font_scale)

    @property
    def score_size(self) -> float:
        return BASE_SCORE * self.font_scale

    @property
    def section_size(self) -> float:
        return max(MIN_SECTION, BASE_SECTION * self.font_scale)

    @property
    def body_size(self) -> float:
        return max(MIN_BODY, BASE_BODY * self.font_scale)

    @property
    def small_size(self) -> float:
        return max(MIN_FOOTNOTE, BASE_SMALL * self.font_scale)

    @property
    def footnote_size(self) -> float:
        return max(MIN_FOOTNOTE, BASE_FOOTNOTE * self.font_scale)

    @property
    def metric_value_size(self) -> float:
        return BASE_METRIC_VALUE * self.font_scale

    # --- spacing ---
    @property
    def block_gap(self) -> float:
        return 7.5 * self.space_scale

    @property
    def inner_gap(self) -> float:
        return 3.2 * self.space_scale

    @property
    def pad(self) -> float:
        return 4.6 * self.space_scale

    @property
    def section_header_gap(self) -> float:
        return 3.4 * self.space_scale

    @property
    def leading(self) -> float:
        return self.body_size * 1.22

    # --- paragraph styles ---
    def _style(self, name: str, size: float, **kwargs) -> ParagraphStyle:
        return ParagraphStyle(
            name=name,
            fontName=kwargs.pop("fontName", FONT),
            fontSize=size,
            leading=kwargs.pop("leading", size * 1.22),
            textColor=kwargs.pop("textColor", BODY),
            alignment=TA_LEFT,
            spaceBefore=0,
            spaceAfter=0,
            **kwargs,
        )

    @property
    def company(self) -> ParagraphStyle:
        return self._style(
            "company",
            self.company_size,
            fontName=FONT_BOLD,
            textColor=INK,
            leading=self.company_size * 1.06,
        )

    @property
    def description(self) -> ParagraphStyle:
        return self._style("description", self.small_size, textColor=BODY)

    @property
    def body(self) -> ParagraphStyle:
        return self._style("body", self.body_size, leading=self.leading)

    @property
    def body_tight(self) -> ParagraphStyle:
        return self._style("body_tight", self.body_size, leading=self.body_size * 1.14)

    @property
    def bullet(self) -> ParagraphStyle:
        indent = self.body_size * 0.85
        return self._style(
            "bullet",
            self.body_size,
            leading=self.leading,
            leftIndent=indent,
            firstLineIndent=-indent,
        )

    @property
    def cell(self) -> ParagraphStyle:
        return self._style("cell", self.small_size, leading=self.small_size * 1.16)

    @property
    def cell_bold(self) -> ParagraphStyle:
        return self._style(
            "cell_bold", self.small_size, fontName=FONT_BOLD, leading=self.small_size * 1.16, textColor=INK
        )

    @property
    def footnote(self) -> ParagraphStyle:
        return self._style("footnote", self.footnote_size, textColor=MUTED)


def conviction_color(label: str) -> Color:
    return {
        "HIGH": CONVICTION_HIGH,
        "MODERATE": CONVICTION_MODERATE,
        "LOW": CONVICTION_LOW,
    }.get(label.upper(), CONVICTION_MODERATE)


def page_size(name: str) -> tuple[float, float]:
    try:
        return PAGE_SIZES[name.upper()]
    except KeyError as exc:
        raise ValueError(f"Unsupported page size '{name}'. Use LETTER or A4.") from exc
