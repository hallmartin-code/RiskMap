"""The structured investment analysis the LLM must return.

Field descriptions are part of the prompt contract: they are emitted into the
JSON schema handed to the model, so they carry the analytical instructions for
each field. Keep them precise.

Note on schema design: no numeric/length constraints are declared here, because
the Anthropic and OpenAI structured-output schemas ignore or reject them. List
caps and score bounds are enforced in :mod:`analysis.validation` instead.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceType = Literal[
    "Company Data",
    "Market Data",
    "Customer Evidence",
    "Case / Example",
    "Management Experience",
    "Logical Inference",
    "Founder Claim",
    "Third-Party Evidence",
]

EvidenceStrength = Literal["Strong", "Moderate", "Weak"]
Probability = Literal["High", "Medium-High", "Medium", "Low-Medium", "Low"]
Impact = Literal["Very High", "High", "Medium", "Low"]
AssumptionStatus = Literal["Supported", "Partially supported", "Unproven"]


class SourceReference(BaseModel):
    """Traceability record for a material claim."""

    label: str = Field(description="Compact marker shown in the PDF, e.g. 'S8' for slide 8.")
    page_number: int = Field(description="Slide/page number the claim came from.")
    claim: str = Field(description="The claim or metric taken from that slide.")
    quote: str = Field(default="", description="Verbatim supporting fragment from the deck, if any.")


class TractionMetric(BaseModel):
    """A decision-relevant metric that is actually present in the deck."""

    label: str = Field(description="Short metric name, e.g. 'ARR', 'Gross Margin', 'Customers'.")
    value: str = Field(
        description=(
            "The value exactly as stated in the deck, preserving units and ranges "
            "($, %, M, B, K). Never re-derive, round or average a stated range."
        )
    )
    source_page: int | None = Field(
        default=None, description="Slide the value came from. Null only if genuinely unknown."
    )
    note: str = Field(
        default="",
        description="Optional 2-5 word qualifier, e.g. 'as of Q2 2026' or 'founder projection'.",
    )


class EvidenceItem(BaseModel):
    """Something the deck actually demonstrates, not something it asserts."""

    evidence: str = Field(description="What the deck demonstrates. One sentence, concrete.")
    significance: str = Field(description="Why it matters to the investment case. One short clause.")
    evidence_type: EvidenceType = Field(description="Classification of the evidence.")
    strength: EvidenceStrength = Field(description="How much weight this evidence can bear.")
    source_page: int | None = Field(default=None, description="Slide number, if identifiable.")


class Assumption(BaseModel):
    """A condition that must become true for the thesis to work."""

    assumption: str = Field(description="What must be true. Specific and testable.")
    why_it_matters: str = Field(description="What breaks if it is false. One short clause.")
    status: AssumptionStatus = Field(description="Current evidentiary status based on the deck only.")
    is_critical_dependency: bool = Field(
        default=False,
        description=(
            "True for exactly one assumption: the one whose failure would damage "
            "multiple other assumptions or forecasts."
        ),
    )


class Risk(BaseModel):
    """A specific, observable risk - never a generic category."""

    risk: str = Field(
        description=(
            "Concrete failure mechanism specific to this company. Not 'competition "
            "increases' but the actual mechanism by which value is lost."
        )
    )
    probability: Probability
    impact: Impact
    early_warning: str = Field(
        description="An observable signal that would indicate this risk is materialising."
    )


class InvestmentOnePager(BaseModel):
    """Complete structured analysis rendered onto the one-pager."""

    company_name: str = Field(description="Company name exactly as it appears in the deck.")
    company_description: str | None = Field(
        default=None, description="What the company does. 20-30 words maximum."
    )

    sector: str | None = Field(default=None, description="Sector / sub-sector, or null if not stated.")
    stage: str | None = Field(default=None, description="Stage, e.g. 'Seed', or null if not stated.")
    raise_amount: str | None = Field(default=None, description="Amount being raised, or null.")
    valuation: str | None = Field(default=None, description="Valuation or cap, or null.")
    geography: str | None = Field(default=None, description="Primary geography, or null.")

    core_investment_belief: str = Field(
        description=(
            "One sentence: '[Company] has a credible opportunity to [outcome] if it "
            "can [critical conditions].' Describe the economic or strategic bet, not "
            "the product."
        )
    )

    conviction_score: float = Field(
        description=(
            "0.0-10.0, scoring the strength of evidence supporting the thesis, not "
            "the attractiveness of the story. 0-3.9 Low, 4.0-6.9 Moderate, 7.0-10 High."
        )
    )
    conviction_label: Literal["LOW", "MODERATE", "HIGH"] = Field(
        description="Band matching conviction_score."
    )
    conviction_rationale: str = Field(
        default="", description="One clause explaining what caps the score."
    )

    traction_metrics: list[TractionMetric] = Field(
        default_factory=list,
        description=(
            "Up to 6 of the most decision-relevant metrics that appear in the deck. "
            "Choose metrics that fit this company's business model. Return an empty "
            "list rather than inventing metrics."
        ),
    )

    strongest_evidence: list[EvidenceItem] = Field(
        default_factory=list, description="3-5 items. Evidence, not founder positioning or forecasts."
    )

    key_assumptions: list[Assumption] = Field(
        default_factory=list,
        description="3-5 critical assumptions. Exactly one must be the critical dependency.",
    )

    major_risks: list[Risk] = Field(default_factory=list, description="3-5 specific, material risks.")

    weak_link: str = Field(
        description=(
            "The largest gap between founder narrative and what the deck demonstrates. "
            "State explicitly what has NOT been shown. 1-2 sentences."
        )
    )
    critical_dependency: str = Field(
        description="Restate the single assumption whose failure damages the most downstream claims."
    )
    strongest_counterargument: str = Field(
        description=(
            "The strongest credible skeptical reading of this opportunity. Steel-man "
            "it - no straw men. 1-2 sentences."
        )
    )

    conviction_strengthens_if: list[str] = Field(
        default_factory=list,
        description=(
            "2-4 observable developments that would materially increase conviction. "
            "Use numeric thresholds only where the deck justifies them."
        ),
    )
    conviction_weakens_if: list[str] = Field(
        default_factory=list, description="2-4 observable developments that would reduce conviction."
    )
    thesis_invalid_if: list[str] = Field(
        default_factory=list,
        description="1-2 genuine thesis-breaking conditions. Stronger than ordinary risks.",
    )

    highest_value_test: str = Field(
        description=(
            "The smallest, highest-information experiment or milestone that would "
            "resolve the largest remaining uncertainty. State what to test, what to "
            "measure, and which result matters."
        )
    )

    key_questions: list[str] = Field(
        default_factory=list,
        description=(
            "3-5 diligence questions targeting unresolved evidence gaps, adapted to "
            "this deck's specifics. No generic questions."
        ),
    )

    missing_information: list[str] = Field(
        default_factory=list,
        description="Up to 4 materially important things the deck does not provide.",
    )

    source_references: list[SourceReference] = Field(
        default_factory=list, description="Provenance for every material factual claim used above."
    )

    # --- Convenience -------------------------------------------------------

    @property
    def critical_assumption(self) -> Assumption | None:
        for assumption in self.key_assumptions:
            if assumption.is_critical_dependency:
                return assumption
        return self.key_assumptions[0] if self.key_assumptions else None

    def meta_chips(self) -> list[tuple[str, str]]:
        """Non-empty deal metadata, in display order."""
        pairs = [
            ("Sector", self.sector),
            ("Stage", self.stage),
            ("Raise", self.raise_amount),
            ("Valuation", self.valuation),
            ("Geography", self.geography),
        ]
        skip = {"n/a", "none", "not provided in deck"}
        return [(k, v.strip()) for k, v in pairs if v and v.strip() and v.strip().lower() not in skip]
