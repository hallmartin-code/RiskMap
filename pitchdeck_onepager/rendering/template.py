"""The blank one-pager template.

Builds an :class:`InvestmentOnePager` whose every field is a placeholder, then
renders it through the production renderer. Because it uses the same model and
the same layout code as a real run, the template cannot drift away from what the
application actually produces.

The written specification lives in ``templates/onepager_template.md``.
"""

from __future__ import annotations

from pathlib import Path

from ..models.investment_analysis import (
    Assumption,
    EvidenceItem,
    InvestmentOnePager,
    Risk,
    SourceReference,
    TractionMetric,
)
from .onepager import DocumentMeta, RenderResult, render_onepager

#: Placeholder text is sized to the guidance for each field, so the blank
#: template occupies roughly the same space as a filled one.
_EVIDENCE = (
    "[Evidence item {n} - what the deck demonstrates, stated concretely in one sentence]",
    "[Why it matters to the investment case - one clause]",
)
_ASSUMPTION = (
    "[Assumption {n} - a specific, testable condition that must become true]",
    "[What breaks if it is false - one clause]",
)
_RISK = (
    "[Risk {n} - the concrete failure mechanism, not the risk category]",
    "[An observable signal that this risk is materialising]",
)


def build_template_analysis() -> InvestmentOnePager:
    """A fully populated placeholder analysis with no company-specific content."""
    return InvestmentOnePager(
        company_name="[COMPANY NAME]",
        company_description=(
            "[Company description - what the company does, 20 to 30 words maximum, "
            "drawn from the deck.]"
        ),
        sector="[Sector]",
        stage="[Stage]",
        raise_amount="[Raise]",
        valuation="[Valuation]",
        geography="[Geography]",
        core_investment_belief=(
            "[Core investment belief - one sentence: '[Company] has a credible opportunity "
            "to [outcome] if it can [critical conditions].' The economic or strategic bet, "
            "not the product.]"
        ),
        conviction_score=0.0,
        conviction_label="LOW",
        conviction_rationale="[One clause on what caps the score.]",
        traction_metrics=[
            TractionMetric(
                label=f"[Metric {index}]",
                value=f"[Value {index}]",
                source_page=index,
                note="",
            )
            for index in range(1, 5)
        ],
        # model_construct bypasses the Literal validation on the classification
        # fields so the template names the field instead of asserting a value.
        strongest_evidence=[
            EvidenceItem.model_construct(
                evidence=_EVIDENCE[0].format(n=index),
                significance=_EVIDENCE[1],
                evidence_type="[Evidence type]",
                strength="[Strength]",
                source_page=index,
            )
            for index in range(1, 5)
        ],
        key_assumptions=[
            Assumption.model_construct(
                assumption=_ASSUMPTION[0].format(n=index),
                why_it_matters=_ASSUMPTION[1],
                # The renderer already wraps status in brackets.
                status="Status",
                is_critical_dependency=(index == 1),
            )
            for index in range(1, 5)
        ],
        major_risks=[
            # model_construct bypasses the Literal validation on probability and
            # impact so the template can show the field rather than a verdict.
            Risk.model_construct(
                risk=_RISK[0].format(n=index),
                probability="[Prob.]",
                impact="[Impact]",
                early_warning=_RISK[1],
            )
            for index in range(1, 5)
        ],
        weak_link=(
            "[Weakest link - the largest gap between the founder narrative and what the deck "
            "demonstrates. State explicitly what has NOT been shown. One to two sentences.]"
        ),
        critical_dependency="[Restates the assumption flagged as the critical dependency.]",
        strongest_counterargument=(
            "[Best opposing view - the strongest credible skeptical reading of this "
            "opportunity, steel-manned rather than a straw man. One to two sentences.]"
        ),
        conviction_strengthens_if=[
            f"[Observable development {index} that would materially increase conviction]"
            for index in range(1, 4)
        ],
        conviction_weakens_if=[
            f"[Observable development {index} that would materially reduce conviction]"
            for index in range(1, 4)
        ],
        thesis_invalid_if=[
            f"[Thesis-breaking condition {index} - stronger than an ordinary risk]"
            for index in range(1, 3)
        ],
        highest_value_test=(
            "[Next proof point - the smallest, highest-information test that would resolve the "
            "largest remaining uncertainty. State what to test, what to measure, and which "
            "result matters.]"
        ),
        key_questions=[
            f"[Diligence question {index} - targets a specific unresolved evidence gap]"
            for index in range(1, 5)
        ],
        missing_information=[
            f"[Material item {index} the deck does not provide]" for index in range(1, 3)
        ],
        source_references=[
            SourceReference(
                label="[Sn]",
                page_number=index,
                claim="[Claim taken from that slide]",
                quote="[Verbatim supporting fragment]",
            )
            for index in range(1, 3)
        ],
    )


def render_template(
    output_path: Path,
    page_size_name: str = "LETTER",
    show_sources: bool = True,
) -> RenderResult:
    """Render the blank structural template to ``output_path``."""
    return render_onepager(
        analysis=build_template_analysis(),
        output_path=Path(output_path),
        meta=DocumentMeta(
            source_filename="[source deck filename]",
            slide_count="[n]",
            model="[model]",
            generated_on="[date]",
        ),
        page_size_name=page_size_name,
        show_sources=show_sources,
        placeholder_badge=True,
    )
