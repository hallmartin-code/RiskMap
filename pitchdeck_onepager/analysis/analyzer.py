"""Two-stage analysis: generate structured JSON, then optionally compress it."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..logging_setup import get_logger
from ..models.deck import DeckDocument
from ..models.investment_analysis import InvestmentOnePager
from .investor_prompt import (
    COMPRESSION_SYSTEM_PROMPT,
    build_analysis_user_prompt,
    build_compression_user_prompt,
    load_system_prompt,
)
from .llm import LLMClient
from .provenance import ProvenanceReport, apply_provenance_controls
from .schema_tools import build_schema
from .validation import parse_analysis, validate_and_repair

log = get_logger("analysis.analyzer")


@dataclass
class AnalysisOutcome:
    """The analysis plus everything the caller needs to report on it."""

    analysis: InvestmentOnePager
    provenance: ProvenanceReport
    validation_warnings: list[str] = field(default_factory=list)
    compressed: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str = ""


class InvestmentAnalyzer:
    """Runs the LLM stages and enforces the output contract."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._schema = build_schema(InvestmentOnePager)

    def analyze(self, deck: DeckDocument) -> AnalysisOutcome:
        """Stage 1: deck -> validated, provenance-checked analysis."""
        log.info("Analysing '%s' (%d slides) with %s", deck.filename, deck.page_count, self._client.model)

        result = self._client.generate_json(
            system=load_system_prompt(),
            user=build_analysis_user_prompt(deck),
            schema=self._schema,
            schema_name="investment_onepager",
        )
        log.info("Analysis returned (%s)", result.usage_summary())

        analysis = parse_analysis(result.data)
        warnings = validate_and_repair(analysis)
        provenance = apply_provenance_controls(analysis, deck)
        log.info("Provenance: %s", provenance.summary())

        return AnalysisOutcome(
            analysis=analysis,
            provenance=provenance,
            validation_warnings=warnings,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            model=result.model,
        )

    def compress(
        self,
        outcome: AnalysisOutcome,
        deck: DeckDocument,
        target_reduction: int = 25,
    ) -> AnalysisOutcome:
        """Stage 2: shorten prose without changing facts or judgments.

        Runs only when the renderer cannot fit the content. The compressed
        output is re-validated and re-checked for provenance, so the
        compression stage cannot introduce a new claim that survives to the PDF.
        """
        log.info("Running compression pass (target -%d%% prose)", target_reduction)

        result = self._client.generate_json(
            system=COMPRESSION_SYSTEM_PROMPT,
            user=build_compression_user_prompt(
                outcome.analysis.model_dump_json(indent=None), target_reduction
            ),
            schema=self._schema,
            schema_name="investment_onepager",
        )

        analysis = parse_analysis(result.data)
        warnings = validate_and_repair(analysis)
        provenance = apply_provenance_controls(analysis, deck)

        if _lost_content(outcome.analysis, analysis):
            log.warning("Compression dropped list content; keeping the original analysis.")
            return outcome

        log.info("Compression complete (%s)", result.usage_summary())
        return AnalysisOutcome(
            analysis=analysis,
            provenance=provenance,
            validation_warnings=outcome.validation_warnings + warnings,
            compressed=True,
            input_tokens=_add(outcome.input_tokens, result.input_tokens),
            output_tokens=_add(outcome.output_tokens, result.output_tokens),
            model=outcome.model or result.model,
        )


def _lost_content(before: InvestmentOnePager, after: InvestmentOnePager) -> bool:
    """True if compression removed list entries it was told to preserve."""
    tracked = (
        "traction_metrics",
        "strongest_evidence",
        "key_assumptions",
        "major_risks",
        "key_questions",
        "thesis_invalid_if",
    )
    return any(len(getattr(after, name)) < len(getattr(before, name)) for name in tracked)


def _add(a: int | None, b: int | None) -> int | None:
    if a is None:
        return b
    if b is None:
        return a
    return a + b
