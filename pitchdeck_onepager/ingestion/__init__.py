"""Document ingestion: PDF / PPTX / legacy PPT -> :class:`DeckDocument`."""

from .document_router import load_deck

__all__ = ["load_deck"]
