"""Pydantic data models for the deck and the investment analysis."""

from .deck import DeckDocument, DeckPage, DeckTable, ExtractedMetric
from .investment_analysis import (
    Assumption,
    EvidenceItem,
    InvestmentOnePager,
    Risk,
    SourceReference,
    TractionMetric,
)

__all__ = [
    "DeckDocument",
    "DeckPage",
    "DeckTable",
    "ExtractedMetric",
    "Assumption",
    "EvidenceItem",
    "InvestmentOnePager",
    "Risk",
    "SourceReference",
    "TractionMetric",
]
