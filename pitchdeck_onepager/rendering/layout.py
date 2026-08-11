"""Measurable, drawable layout blocks.

Every block can report its exact height for a given width and theme *before*
anything is drawn. That is what makes the one-page guarantee deterministic:
:mod:`rendering.onepager` sums the measurements, and only commits to a canvas
once the total fits.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from xml.sax.saxutils import escape

from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from .styles import (
    ACCENT,
    FONT,
    FONT_BOLD,
    HAIRLINE,
    INK,
    MUTED,
    RULE,
    TINT,
    Theme,
    conviction_color,
)

_BIG = 10_000.0  # effectively unbounded height for wrap()
COLUMN_GAP = 13.0
CONVICTION_BOX_WIDTH = 104.0


# --- Paragraph helpers -------------------------------------------------------


def esc(text: str | None) -> str:
    """Escape user text for ReportLab's mini-markup."""
    return escape((text or "").strip())


def _para(markup: str, style) -> Paragraph:
    return Paragraph(markup, style)


def _height(par: Paragraph, width: float) -> float:
    return par.wrap(max(width, 1.0), _BIG)[1]


def _draw(par: Paragraph, canvas: Canvas, x: float, y_top: float, width: float) -> float:
    height = _height(par, width)
    par.drawOn(canvas, x, y_top - height)
    return height


def source_marker(page: int | None, theme: Theme) -> str:
    """Compact ``[S8]`` marker, when source display is enabled."""
    if not theme.show_sources or not page:
        return ""
    return f' <font size="{theme.footnote_size:.1f}" color="#69737F">[S{page}]</font>'


def _small_caps(canvas: Canvas, x: float, y: float, text: str, size: float, color=ACCENT, spacing: float = 0.7) -> None:
    """Letter-spaced upper-case label.

    The save/restore pair is load-bearing: character spacing (``Tc``) is part of
    the PDF graphics state and survives the end of a text object. Without the
    q/Q wrapper it leaks into every later paragraph, which then renders wider
    than it was measured and overflows the frame.
    """
    canvas.saveState()
    text_object = canvas.beginText(x, y)
    text_object.setFont(FONT_BOLD, size)
    text_object.setFillColor(color)
    text_object.setCharSpace(spacing)
    text_object.textOut(text.upper())
    canvas.drawText(text_object)
    canvas.restoreState()


def _small_caps_width(text: str, size: float, spacing: float = 0.7) -> float:
    return stringWidth(text.upper(), FONT_BOLD, size) + spacing * len(text)


def fit_text(
    text: str,
    font: str,
    size: float,
    max_width: float,
    min_size: float,
    char_space: float = 0.0,
) -> tuple[str, float]:
    """Shrink then truncate a single line so it cannot exceed ``max_width``.

    Used for canvas-drawn labels and values, which - unlike paragraphs - do not
    wrap and would otherwise run off the page.
    """

    def width_of(candidate: str, at_size: float) -> float:
        return stringWidth(candidate, font, at_size) + char_space * len(candidate)

    while size > min_size and width_of(text, size) > max_width:
        size -= 0.25

    if width_of(text, size) <= max_width:
        return text, size

    ellipsis = "…"
    truncated = text
    while truncated and width_of(truncated + ellipsis, size) > max_width:
        truncated = truncated[:-1]
    return (truncated + ellipsis) if truncated else "", size


# --- Base ---------------------------------------------------------------------


class Block(ABC):
    """A vertically stacked, self-measuring unit of the page."""

    @abstractmethod
    def measure(self, width: float, theme: Theme) -> float: ...

    @abstractmethod
    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None: ...

    @property
    def is_empty(self) -> bool:
        return False


class SectionMixin:
    """Shared section-header rendering."""

    title: str

    def header_height(self, theme: Theme) -> float:
        return theme.section_size + theme.section_header_gap + 1.6

    def draw_header(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> float:
        baseline = y_top - theme.section_size * 0.86
        _small_caps(canvas, x, baseline, self.title, theme.section_size)
        rule_y = y_top - theme.section_size - theme.section_header_gap * 0.55
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(x, rule_y, x + width, rule_y)
        return self.header_height(theme)


# --- Header -------------------------------------------------------------------


class HeaderBlock(Block):
    """Company name, description, deal metadata and the conviction badge."""

    def __init__(
        self,
        company: str,
        description: str | None,
        chips: list[tuple[str, str]],
        score: float,
        label: str,
        placeholder: bool = False,
    ) -> None:
        self.company = company
        self.description = description
        self.chips = chips
        self.score = score
        self.label = label
        #: Blank-template mode: show the badge's shape, not a fabricated verdict.
        self.placeholder = placeholder

    def _left_width(self, width: float) -> float:
        return width - CONVICTION_BOX_WIDTH - COLUMN_GAP

    def _parts(self, width: float, theme: Theme) -> list[Paragraph]:
        left = self._left_width(width)
        parts = [_para(f"<b>{esc(self.company)}</b>", theme.company)]
        if self.description:
            parts.append(_para(esc(self.description), theme.description))
        if self.chips:
            chip_markup = '<font color="#B9C3CE"> | </font>'.join(
                f'<font color="#69737F">{esc(k).upper()}</font> '
                f'<font color="#2B3340"><b>{esc(v)}</b></font>'
                for k, v in self.chips
            )
            parts.append(_para(chip_markup, theme.footnote))
        for part in parts:
            part.wrap(left, _BIG)
        return parts

    def _box_height(self, theme: Theme) -> float:
        return theme.score_size + theme.footnote_size + theme.small_size + 15 * theme.space_scale

    def measure(self, width: float, theme: Theme) -> float:
        left = self._left_width(width)
        gaps = theme.inner_gap * (len(self._parts(width, theme)) - 1)
        stack = sum(_height(p, left) for p in self._parts(width, theme)) + gaps
        return max(stack, self._box_height(theme))

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        left_width = self._left_width(width)
        cursor = y_top
        for index, part in enumerate(self._parts(width, theme)):
            if index:
                cursor -= theme.inner_gap
            cursor -= _draw(part, canvas, x, cursor, left_width)

        self._draw_badge(canvas, x + width - CONVICTION_BOX_WIDTH, y_top, theme)

    def _draw_badge(self, canvas: Canvas, x: float, y_top: float, theme: Theme) -> None:
        height = self._box_height(theme)
        width = CONVICTION_BOX_WIDTH
        color = MUTED if self.placeholder else conviction_color(self.label)
        score_text = "X.X" if self.placeholder else f"{self.score:.1f}"
        band_text = "[BAND]" if self.placeholder else self.label

        canvas.saveState()
        canvas.setFillColor(TINT)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.rect(x, y_top - height, width, height, stroke=1, fill=1)
        canvas.setFillColor(color)
        canvas.rect(x, y_top - 2.6, width, 2.6, stroke=0, fill=1)
        canvas.restoreState()

        pad = 5.0 * theme.space_scale
        label_y = y_top - 3.4 - theme.footnote_size
        _small_caps(
            canvas,
            x + (width - _small_caps_width("CONVICTION", theme.footnote_size, 0.9)) / 2,
            label_y,
            "CONVICTION",
            theme.footnote_size,
            color=MUTED,
            spacing=0.9,
        )

        canvas.saveState()
        canvas.setFont(FONT_BOLD, theme.score_size)
        canvas.setFillColor(color)
        score_width = stringWidth(score_text, FONT_BOLD, theme.score_size)
        suffix = " / 10"
        suffix_width = stringWidth(suffix, FONT, theme.small_size)
        start = x + (width - score_width - suffix_width) / 2
        score_y = label_y - theme.score_size - pad * 0.45
        canvas.drawString(start, score_y, score_text)
        canvas.setFont(FONT, theme.small_size)
        canvas.setFillColor(MUTED)
        canvas.drawString(start + score_width, score_y, suffix)
        canvas.restoreState()

        band_y = score_y - theme.small_size - pad * 0.5
        _small_caps(
            canvas,
            x + (width - _small_caps_width(band_text, theme.small_size, 1.1)) / 2,
            band_y,
            band_text,
            theme.small_size,
            color=color,
            spacing=1.1,
        )


# --- Simple blocks ------------------------------------------------------------


class RuleBlock(Block):
    """A horizontal rule used to separate the header from the analysis."""

    def __init__(self, weight: float = 1.1, color=INK) -> None:
        self.weight = weight
        self.color = color

    def measure(self, width: float, theme: Theme) -> float:
        return self.weight

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        canvas.saveState()
        canvas.setStrokeColor(self.color)
        canvas.setLineWidth(self.weight)
        canvas.line(x, y_top - self.weight / 2, x + width, y_top - self.weight / 2)
        canvas.restoreState()


class BeliefBlock(Block):
    """The core investment belief, in a tinted band."""

    def __init__(self, title: str, text: str) -> None:
        self.title = title
        self.text = text

    def _para(self, width: float, theme: Theme) -> Paragraph:
        style = theme.body
        style = style.clone("belief", fontSize=theme.body_size + 0.7, leading=(theme.body_size + 0.7) * 1.24, textColor=INK)
        return _para(esc(self.text), style)

    def _inner_width(self, width: float, theme: Theme) -> float:
        return width - 2 * theme.pad * 1.6

    def measure(self, width: float, theme: Theme) -> float:
        inner = self._inner_width(width, theme)
        text_height = _height(self._para(width, theme), inner)
        return text_height + theme.section_size + theme.inner_gap + 2 * theme.pad * 1.35

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        height = self.measure(width, theme)
        canvas.saveState()
        canvas.setFillColor(TINT)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.rect(x, y_top - height, width, height, stroke=1, fill=1)
        canvas.setFillColor(ACCENT)
        canvas.rect(x, y_top - height, 2.4, height, stroke=0, fill=1)
        canvas.restoreState()

        pad_x = theme.pad * 1.6
        pad_y = theme.pad * 1.35
        _small_caps(canvas, x + pad_x, y_top - pad_y - theme.section_size * 0.86, self.title, theme.section_size)
        text_top = y_top - pad_y - theme.section_size - theme.inner_gap
        _draw(self._para(width, theme), canvas, x + pad_x, text_top, self._inner_width(width, theme))


class MetricStrip(Block):
    """Compact metric row. Renders nothing when the deck had no usable metrics."""

    def __init__(self, metrics: list[tuple[str, str, int | None]]) -> None:
        self.metrics = metrics

    @property
    def is_empty(self) -> bool:
        return not self.metrics

    def measure(self, width: float, theme: Theme) -> float:
        if self.is_empty:
            return 0.0
        return theme.metric_value_size + theme.footnote_size + theme.pad * 2.6 + 3.0

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        if self.is_empty:
            return
        height = self.measure(width, theme)
        bottom = y_top - height

        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(x, y_top, x + width, y_top)
        canvas.line(x, bottom, x + width, bottom)
        canvas.restoreState()

        count = len(self.metrics)
        column = width / count
        pad = theme.pad

        for index, (label, value, page) in enumerate(self.metrics):
            cx = x + index * column
            if index:
                canvas.saveState()
                canvas.setStrokeColor(HAIRLINE)
                canvas.setLineWidth(0.5)
                canvas.line(cx, bottom + pad * 0.4, cx, y_top - pad * 0.4)
                canvas.restoreState()

            available = column - pad * 1.9
            value_text, size = fit_text(
                value, FONT_BOLD, theme.metric_value_size, available, min_size=7.0
            )

            canvas.saveState()
            canvas.setFont(FONT_BOLD, size)
            canvas.setFillColor(INK)
            canvas.drawString(cx + pad * 0.8, y_top - pad - size * 0.86, value_text)
            canvas.restoreState()

            suffix = f" [S{page}]" if (theme.show_sources and page) else ""
            # No shrinking below the footnote floor: a long label is truncated
            # rather than rendered at an unreadable size.
            label_text, label_size = fit_text(
                f"{label}{suffix}".upper(),
                FONT_BOLD,
                theme.footnote_size,
                available,
                min_size=theme.footnote_size,
                char_space=0.5,
            )
            _small_caps(
                canvas,
                cx + pad * 0.8,
                bottom + pad * 0.9,
                label_text,
                label_size,
                color=MUTED,
                spacing=0.5,
            )


class ProseBlock(Block, SectionMixin):
    """A titled paragraph, optionally emphasised with a left accent bar."""

    def __init__(self, title: str, text: str, accent_bar: bool = False, bar_color=None) -> None:
        self.title = title
        self.text = text
        self.accent_bar = accent_bar
        self.bar_color = bar_color or ACCENT

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()

    def _indent(self, theme: Theme) -> float:
        return theme.pad * 1.5 if self.accent_bar else 0.0

    def measure(self, width: float, theme: Theme) -> float:
        if self.is_empty:
            return 0.0
        indent = self._indent(theme)
        return self.header_height(theme) + _height(_para(esc(self.text), theme.body), width - indent)

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        if self.is_empty:
            return
        used = self.draw_header(canvas, x, y_top, width, theme)
        indent = self._indent(theme)
        text_top = y_top - used
        height = _draw(_para(esc(self.text), theme.body), canvas, x + indent, text_top, width - indent)
        if self.accent_bar:
            canvas.saveState()
            canvas.setFillColor(self.bar_color)
            canvas.rect(x, text_top - height, 2.2, height, stroke=0, fill=1)
            canvas.restoreState()


class BulletBlock(Block, SectionMixin):
    """A titled bullet list. Items are ``(lead, text, source_page)``."""

    def __init__(self, title: str, items: list[tuple[str, str, int | None]]) -> None:
        self.title = title
        self.items = items

    @property
    def is_empty(self) -> bool:
        return not self.items

    def _paras(self, theme: Theme) -> list[Paragraph]:
        out: list[Paragraph] = []
        for lead, text, page in self.items:
            markup = "• "
            if lead:
                markup += f'<font color="#111418"><b>{esc(lead)}</b></font>'
                if text:
                    markup += " &mdash; "
            markup += esc(text) + source_marker(page, theme)
            out.append(_para(markup, theme.bullet))
        return out

    def measure(self, width: float, theme: Theme) -> float:
        if self.is_empty:
            return 0.0
        paras = self._paras(theme)
        body = sum(_height(p, width) for p in paras) + theme.inner_gap * (len(paras) - 1)
        return self.header_height(theme) + body

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        if self.is_empty:
            return
        cursor = y_top - self.draw_header(canvas, x, y_top, width, theme)
        for index, para in enumerate(self._paras(theme)):
            if index:
                cursor -= theme.inner_gap
            cursor -= _draw(para, canvas, x, cursor, width)


class NumberedBlock(Block, SectionMixin):
    """A titled, numbered list - used for the diligence questions."""

    def __init__(self, title: str, items: list[str]) -> None:
        self.title = title
        self.items = items

    @property
    def is_empty(self) -> bool:
        return not self.items

    def _paras(self, theme: Theme) -> list[Paragraph]:
        return [
            _para(f'<font color="#1B3A5C"><b>{i}.</b></font> {esc(text)}', theme.bullet)
            for i, text in enumerate(self.items, start=1)
        ]

    def measure(self, width: float, theme: Theme) -> float:
        if self.is_empty:
            return 0.0
        paras = self._paras(theme)
        body = sum(_height(p, width) for p in paras) + theme.inner_gap * (len(paras) - 1)
        return self.header_height(theme) + body

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        if self.is_empty:
            return
        cursor = y_top - self.draw_header(canvas, x, y_top, width, theme)
        for index, para in enumerate(self._paras(theme)):
            if index:
                cursor -= theme.inner_gap
            cursor -= _draw(para, canvas, x, cursor, width)


class RiskTable(Block, SectionMixin):
    """Risk | Probability | Impact | Early warning."""

    COLUMNS = ("Risk", "Prob.", "Impact", "Early warning signal")
    WIDTHS = (0.40, 0.11, 0.10, 0.39)

    def __init__(self, title: str, rows: list[tuple[str, str, str, str]]) -> None:
        self.title = title
        self.rows = rows

    @property
    def is_empty(self) -> bool:
        return not self.rows

    def _col_widths(self, width: float) -> list[float]:
        pad = 4.0
        usable = width - pad * (len(self.WIDTHS) - 1)
        return [usable * w for w in self.WIDTHS]

    def _row_paras(self, row: tuple[str, str, str, str], theme: Theme) -> list[Paragraph]:
        risk, probability, impact, warning = row
        return [
            _para(esc(risk), theme.cell_bold),
            _para(esc(probability), theme.cell),
            _para(esc(impact), theme.cell),
            _para(esc(warning), theme.cell),
        ]

    def _row_height(self, row: tuple[str, str, str, str], width: float, theme: Theme) -> float:
        widths = self._col_widths(width)
        paras = self._row_paras(row, theme)
        return max(_height(p, w) for p, w in zip(paras, widths)) + theme.pad * 0.9

    def measure(self, width: float, theme: Theme) -> float:
        if self.is_empty:
            return 0.0
        header = theme.footnote_size + theme.pad * 0.8
        body = sum(self._row_height(row, width, theme) for row in self.rows)
        return self.header_height(theme) + header + body

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        if self.is_empty:
            return
        cursor = y_top - self.draw_header(canvas, x, y_top, width, theme)
        widths = self._col_widths(width)
        pad = 4.0

        # Column headings
        column_x = x
        for label, column_width in zip(self.COLUMNS, widths):
            _small_caps(
                canvas,
                column_x,
                cursor - theme.footnote_size * 0.9,
                label,
                theme.footnote_size,
                color=MUTED,
                spacing=0.5,
            )
            column_x += column_width + pad
        cursor -= theme.footnote_size + theme.pad * 0.8

        canvas.saveState()
        canvas.setStrokeColor(HAIRLINE)
        canvas.setLineWidth(0.5)
        canvas.line(x, cursor + theme.pad * 0.35, x + width, cursor + theme.pad * 0.35)
        canvas.restoreState()

        for index, row in enumerate(self.rows):
            height = self._row_height(row, width, theme)
            column_x = x
            for para, column_width in zip(self._row_paras(row, theme), widths):
                _draw(para, canvas, column_x, cursor - theme.pad * 0.35, column_width)
                column_x += column_width + pad
            cursor -= height
            if index < len(self.rows) - 1:
                canvas.saveState()
                canvas.setStrokeColor(HAIRLINE)
                canvas.setLineWidth(0.4)
                canvas.line(x, cursor + theme.pad * 0.3, x + width, cursor + theme.pad * 0.3)
                canvas.restoreState()


class TwoColumn(Block):
    """Two blocks side by side, aligned to the taller one."""

    def __init__(self, left: Block, right: Block, ratio: float = 0.5) -> None:
        self.left = left
        self.right = right
        self.ratio = ratio

    @property
    def is_empty(self) -> bool:
        return self.left.is_empty and self.right.is_empty

    def _widths(self, width: float) -> tuple[float, float]:
        usable = width - COLUMN_GAP
        left = usable * self.ratio
        return left, usable - left

    def measure(self, width: float, theme: Theme) -> float:
        if self.is_empty:
            return 0.0
        left_width, right_width = self._widths(width)
        if self.left.is_empty:
            return self.right.measure(width, theme)
        if self.right.is_empty:
            return self.left.measure(width, theme)
        return max(self.left.measure(left_width, theme), self.right.measure(right_width, theme))

    def draw(self, canvas: Canvas, x: float, y_top: float, width: float, theme: Theme) -> None:
        if self.is_empty:
            return
        left_width, right_width = self._widths(width)
        if self.left.is_empty:
            self.right.draw(canvas, x, y_top, width, theme)
            return
        if self.right.is_empty:
            self.left.draw(canvas, x, y_top, width, theme)
            return
        self.left.draw(canvas, x, y_top, left_width, theme)
        self.right.draw(canvas, x + left_width + COLUMN_GAP, y_top, right_width, theme)
