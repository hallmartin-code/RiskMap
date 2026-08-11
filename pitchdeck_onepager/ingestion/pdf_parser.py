"""PDF ingestion via PyMuPDF."""

from __future__ import annotations

from pathlib import Path

from ..errors import CorruptDocumentError, EncryptedDocumentError
from ..extraction.metric_extractor import extract_metrics
from ..extraction.text_cleaner import clean_page_text, guess_title, split_bullets, strip_repeated_lines
from ..logging_setup import get_logger
from ..models.deck import DeckDocument, DeckPage, DeckTable

log = get_logger("ingestion.pdf")

#: Below this many characters a page is treated as image-only (OCR candidate).
IMAGE_ONLY_CHAR_THRESHOLD = 40


def _extract_tables(page) -> list[list[list[str]]]:
    """Best-effort table extraction; PyMuPDF's finder is version-dependent."""
    try:
        finder = page.find_tables()
    except Exception:  # pragma: no cover - depends on PyMuPDF build
        return []

    tables: list[list[list[str]]] = []
    for table in getattr(finder, "tables", []):
        try:
            rows = table.extract()
        except Exception:  # pragma: no cover
            continue
        cleaned = [[(cell or "").strip() for cell in row] for row in rows if row]
        cleaned = [row for row in cleaned if any(row)]
        if len(cleaned) >= 2:
            tables.append(cleaned)
    return tables


def _import_pymupdf():
    """Import PyMuPDF under either module name (``fitz`` is deprecated)."""
    try:
        import pymupdf

        return pymupdf
    except ImportError:  # pragma: no cover - older PyMuPDF releases
        import fitz

        return fitz


def parse_pdf(path: Path) -> DeckDocument:
    """Parse a PDF deck, preserving page order and provenance."""
    fitz = _import_pymupdf()

    try:
        doc = fitz.open(path)
    except Exception as exc:  # pragma: no cover - malformed input
        raise CorruptDocumentError(f"Could not open PDF '{path.name}': {exc}") from exc

    warnings: list[str] = []
    try:
        if doc.needs_pass:
            raise EncryptedDocumentError(f"'{path.name}' is password protected.")

        raw_pages: list[str] = []
        raw_tables: list[list[list[list[str]]]] = []
        for page in doc:
            try:
                raw_pages.append(page.get_text("text") or "")
            except Exception as exc:  # pragma: no cover
                warnings.append(f"Page {page.number + 1}: text extraction failed ({exc}).")
                raw_pages.append("")
            raw_tables.append(_extract_tables(page))
    finally:
        doc.close()

    deduped = strip_repeated_lines(raw_pages)

    pages: list[DeckPage] = []
    for index, raw in enumerate(deduped, start=1):
        text = clean_page_text(raw)
        tables = [DeckTable(page_number=index, rows=rows) for rows in raw_tables[index - 1]]
        table_text = "\n".join(t.to_text() for t in tables)
        searchable = f"{text}\n{table_text}"

        pages.append(
            DeckPage(
                page_number=index,
                title=guess_title(text),
                raw_text=text,
                bullets=split_bullets(text),
                tables=tables,
                metrics=extract_metrics(searchable, index),
                is_image_only=len(text) < IMAGE_ONLY_CHAR_THRESHOLD,
            )
        )

    log.info("Parsed PDF '%s': %d pages, %d chars", path.name, len(pages), sum(p.char_count for p in pages))
    return DeckDocument(filename=path.name, file_type="pdf", pages=pages, warnings=warnings)
