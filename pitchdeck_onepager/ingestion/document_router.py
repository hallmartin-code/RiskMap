"""Dispatch a file to the right parser and enforce extraction quality."""

from __future__ import annotations

from pathlib import Path

from ..config import AppConfig
from ..errors import EmptyExtractionError, UnsupportedFileTypeError
from ..logging_setup import get_logger
from ..models.deck import DeckDocument
from .ocr import ocr_available, ocr_pdf_pages
from .pdf_parser import parse_pdf
from .ppt_converter import convert_ppt_to_pptx
from .pptx_parser import parse_pptx

log = get_logger("ingestion.router")

SUPPORTED_SUFFIXES = {".pdf", ".pptx", ".ppt"}

#: A deck with less text than this cannot support a credible analysis.
MIN_TOTAL_CHARS = 200


def load_deck(path: Path, config: AppConfig) -> DeckDocument:
    """Load any supported deck format into a :class:`DeckDocument`."""
    path = Path(path)
    if not path.exists():
        raise UnsupportedFileTypeError(f"File not found: {path}", hint="Check the path and try again.")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedFileTypeError(f"Unsupported file type '{suffix or path.name}'.")

    temp_artifacts: list[Path] = []
    try:
        if suffix == ".pdf":
            deck = parse_pdf(path)
            deck = _maybe_ocr(deck, path, config)
        elif suffix == ".pptx":
            deck = parse_pptx(path)
        else:  # .ppt
            converted = convert_ppt_to_pptx(path, config.temp_dir, config.libreoffice_path)
            temp_artifacts.append(converted)
            deck = parse_pptx(converted, original_name=path.name, file_type="ppt")
    finally:
        for artifact in temp_artifacts:
            try:
                artifact.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - best effort cleanup
                log.debug("Could not remove temp file %s", artifact.name)

    _validate_extraction(deck, config)
    return deck


def _maybe_ocr(deck: DeckDocument, path: Path, config: AppConfig) -> DeckDocument:
    image_only = deck.image_only_pages
    if not image_only:
        return deck

    if not config.enable_ocr:
        deck.warnings.append(
            f"{len(image_only)} page(s) had little or no extractable text "
            f"(pages {', '.join(map(str, image_only[:8]))}). OCR is disabled."
        )
        return deck

    if not ocr_available():
        deck.warnings.append("OCR requested but pytesseract/Pillow are not installed; skipped.")
        return deck

    log.info("Running OCR fallback on %d page(s)", len(image_only))
    deck = ocr_pdf_pages(deck, path, image_only)
    still_empty = deck.image_only_pages
    if still_empty:
        deck.warnings.append(f"OCR produced no text for pages {', '.join(map(str, still_empty[:8]))}.")
    return deck


def _validate_extraction(deck: DeckDocument, config: AppConfig) -> None:
    if deck.page_count == 0:
        raise EmptyExtractionError(f"'{deck.filename}' contains no pages.")

    if deck.total_chars < MIN_TOTAL_CHARS:
        hint = (
            "The deck appears to be image-only. Enable OCR with ENABLE_OCR=true "
            "(requires pytesseract + the Tesseract binary)."
            if not config.enable_ocr
            else "OCR was enabled but still produced too little text to analyse."
        )
        raise EmptyExtractionError(
            f"Only {deck.total_chars} characters were extracted from '{deck.filename}'.",
            hint=hint,
        )

    for warning in deck.warnings:
        log.warning("Extraction warning: %s", warning)
