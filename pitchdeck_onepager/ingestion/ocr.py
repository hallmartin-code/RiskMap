"""Optional OCR fallback for image-only PDF pages.

OCR is never the default extraction path. It runs only when a page yields
almost no text *and* ``ENABLE_OCR=true``. The dependency is imported lazily so
the rest of the application works without pytesseract installed.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import OCRUnavailableError
from ..logging_setup import get_logger
from ..models.deck import DeckDocument

log = get_logger("ingestion.ocr")

#: Rendering scale for OCR input. 2x gives usable accuracy on slide text.
_ZOOM = 2.0


def ocr_available() -> bool:
    """True when the optional OCR dependencies are importable."""
    from importlib.util import find_spec

    return all(find_spec(name) is not None for name in ("pytesseract", "PIL"))


def ocr_pdf_pages(deck: DeckDocument, pdf_path: Path, page_numbers: list[int]) -> DeckDocument:
    """Fill in text for image-only pages using OCR. Mutates and returns ``deck``."""
    if not page_numbers:
        return deck
    if not ocr_available():
        raise OCRUnavailableError("OCR was requested but pytesseract/Pillow are not installed.")

    import io

    import pytesseract
    from PIL import Image

    from .pdf_parser import _import_pymupdf

    fitz = _import_pymupdf()

    from ..extraction.metric_extractor import extract_metrics
    from ..extraction.text_cleaner import clean_page_text, guess_title, split_bullets

    document = fitz.open(pdf_path)
    try:
        for number in page_numbers:
            page = document[number - 1]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(_ZOOM, _ZOOM))
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            try:
                text = clean_page_text(pytesseract.image_to_string(image))
            except Exception as exc:  # pragma: no cover - tesseract binary missing
                raise OCRUnavailableError(f"OCR failed on page {number}: {exc}") from exc

            target = deck.pages[number - 1]
            if text:
                target.raw_text = text
                target.title = target.title or guess_title(text)
                target.bullets = split_bullets(text)
                target.metrics = extract_metrics(text, number)
                target.is_image_only = False
                target.ocr_applied = True
                log.info("OCR recovered %d chars on page %d", len(text), number)
    finally:
        document.close()

    return deck
