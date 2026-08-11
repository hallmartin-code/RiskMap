"""Typed exceptions.

Every failure mode the user can act on gets its own class so the CLI and the
Streamlit UI can render an actionable message instead of a stack trace.
"""

from __future__ import annotations


class PitchDeckError(Exception):
    """Base class for all application errors."""

    hint: str = ""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        if hint:
            self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.message} {self.hint}".strip()


# --- Ingestion ---------------------------------------------------------------


class UnsupportedFileTypeError(PitchDeckError):
    hint = "Supported inputs are .pdf, .pptx and .ppt."


class EncryptedDocumentError(PitchDeckError):
    hint = "Remove the password from the file and try again."


class CorruptDocumentError(PitchDeckError):
    hint = "The file could not be parsed. Re-export it and try again."


class LibreOfficeUnavailableError(PitchDeckError):
    hint = (
        "Legacy .ppt conversion needs LibreOffice. Install it, set "
        "LIBREOFFICE_PATH, or save the deck as .pptx / .pdf first."
    )


class EmptyExtractionError(PitchDeckError):
    hint = (
        "No readable text was found. The deck is probably image-only - enable "
        "OCR with ENABLE_OCR=true (requires pytesseract + Tesseract)."
    )


class OCRUnavailableError(PitchDeckError):
    hint = "Install pytesseract and the Tesseract binary, or set ENABLE_OCR=false."


# --- LLM ---------------------------------------------------------------------


class LLMConfigurationError(PitchDeckError):
    hint = "Check LLM_PROVIDER / LLM_MODEL and the matching API key."


class LLMRequestError(PitchDeckError):
    hint = "The model call failed. Retry, or switch provider with --provider."


class LLMResponseError(PitchDeckError):
    hint = "The model returned output that did not match the required schema."


class AnalysisValidationError(PitchDeckError):
    hint = "The analysis failed validation and was not rendered."


# --- Rendering ---------------------------------------------------------------


class OnePageOverflowError(PitchDeckError):
    hint = (
        "Content could not be compressed onto a single page without dropping "
        "below the minimum readable font size."
    )


class RenderError(PitchDeckError):
    hint = "PDF rendering failed."
