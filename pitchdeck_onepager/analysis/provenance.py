"""Hallucination control for quantitative claims.

Before a number reaches the rendered page it must be traceable to a number that
actually appears in the extracted deck text. Metrics are the highest-risk
surface (they are read as fact at a glance), so an unverifiable metric is
dropped outright. Numbers inside prose are flagged rather than deleted, because
removing them mid-sentence would corrupt the analyst's judgment - the flags are
written to the JSON sidecar and the log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..extraction.metric_extractor import NUMBER_RE, normalize_number, numeric_tokens
from ..logging_setup import get_logger
from ..models.deck import DeckDocument
from ..models.investment_analysis import InvestmentOnePager

log = get_logger("analysis.provenance")

#: Prose fields scanned for unverifiable figures.
_PROSE_FIELDS = (
    "core_investment_belief",
    "weak_link",
    "critical_dependency",
    "strongest_counterargument",
    "highest_value_test",
    "company_description",
    "conviction_rationale",
)

#: Tokens that are almost never a fabricated company metric.
_BENIGN = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "0"}

_NON_NUMERIC = re.compile(r"[^0-9a-z.%x]")


@dataclass
class ProvenanceReport:
    """What the provenance check changed and what it could not verify."""

    dropped_metrics: list[str] = field(default_factory=list)
    flagged_claims: list[str] = field(default_factory=list)
    verified_metrics: int = 0

    @property
    def clean(self) -> bool:
        return not self.dropped_metrics and not self.flagged_claims

    def summary(self) -> str:
        return (
            f"{self.verified_metrics} metric(s) verified, "
            f"{len(self.dropped_metrics)} dropped, "
            f"{len(self.flagged_claims)} prose figure(s) flagged"
        )


class DeckNumberIndex:
    """Numbers present in a deck, in a form tolerant of formatting differences."""

    def __init__(self, deck: DeckDocument) -> None:
        text = deck.full_text()
        self._tokens = numeric_tokens(text)
        # Loose haystack: digits and separators only, so "2.4" matches inside
        # "$2.4M" regardless of how either side was punctuated.
        self._loose = _NON_NUMERIC.sub("", text.lower())

    def contains(self, token: str) -> bool:
        normalized = normalize_number(token)
        if normalized in self._tokens or normalized in _BENIGN:
            return True
        # Fall back to substring containment for compound tokens such as
        # "2.4m" written in the deck as "2.4 million" inside a longer phrase.
        stripped = _NON_NUMERIC.sub("", normalized)
        return bool(stripped) and stripped in self._loose

    def unverified(self, text: str) -> list[str]:
        """Numeric tokens in ``text`` that do not appear in the deck."""
        missing: list[str] = []
        for match in NUMBER_RE.finditer(text or ""):
            raw = match.group(0).strip()
            if not self.contains(raw):
                missing.append(raw)
        return missing


def apply_provenance_controls(
    analysis: InvestmentOnePager, deck: DeckDocument
) -> ProvenanceReport:
    """Drop unverifiable metrics and flag unverifiable prose figures in place."""
    index = DeckNumberIndex(deck)
    report = ProvenanceReport()

    kept = []
    for metric in analysis.traction_metrics:
        missing = index.unverified(metric.value)
        if missing:
            report.dropped_metrics.append(f"{metric.label}: {metric.value} ({', '.join(missing)})")
            log.warning(
                "Dropped unverifiable metric '%s' = '%s' (not found in deck)",
                metric.label,
                metric.value,
            )
            continue
        report.verified_metrics += 1
        kept.append(metric)
    analysis.traction_metrics = kept

    for name in _PROSE_FIELDS:
        value = getattr(analysis, name, None)
        if not isinstance(value, str):
            continue
        for token in index.unverified(value):
            report.flagged_claims.append(f"{name}: '{token}'")

    for i, item in enumerate(analysis.strongest_evidence):
        for token in index.unverified(item.evidence):
            report.flagged_claims.append(f"strongest_evidence[{i}]: '{token}'")

    for i, risk in enumerate(analysis.major_risks):
        for token in index.unverified(f"{risk.risk} {risk.early_warning}"):
            report.flagged_claims.append(f"major_risks[{i}]: '{token}'")

    if report.flagged_claims:
        log.warning(
            "%d figure(s) in prose could not be matched to deck text: %s",
            len(report.flagged_claims),
            "; ".join(report.flagged_claims[:6]),
        )

    return report
