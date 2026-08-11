"""Shared test fixtures.

No test requires a real pitch deck or a real API key: the deck fixtures are
generated synthetically and the LLM is replaced by a recorded stub.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pitchdeck_onepager.analysis.llm import LLMClient, LLMResult  # noqa: E402
from pitchdeck_onepager.config import AppConfig  # noqa: E402
from pitchdeck_onepager.models.investment_analysis import InvestmentOnePager  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _ensure_fixtures() -> None:
    if (FIXTURE_DIR / "sample_pitch.pdf").exists() and (FIXTURE_DIR / "sample_pitch.pptx").exists():
        return
    sys.path.insert(0, str(FIXTURE_DIR))
    import make_fixtures  # type: ignore[import-not-found]

    make_fixtures.main()


_ensure_fixtures()


@pytest.fixture
def sample_pdf() -> Path:
    return FIXTURE_DIR / "sample_pitch.pdf"


@pytest.fixture
def sample_pptx() -> Path:
    return FIXTURE_DIR / "sample_pitch.pptx"


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig.from_env(
        output_dir=tmp_path / "output",
        temp_dir=tmp_path / "temp",
        log_level="WARNING",
    )


def analysis_payload(**overrides: Any) -> dict[str, Any]:
    """A complete, schema-valid analysis whose figures all exist in the fixture deck."""
    payload: dict[str, Any] = {
        "company_name": "Meridian Freight OS",
        "company_description": "Exception management software for mid-market freight brokers, deployed alongside the incumbent TMS.",
        "sector": "Logistics software",
        "stage": "Seed",
        "raise_amount": "$6M",
        "valuation": "$12M pre-money cap",
        "geography": "United States",
        "core_investment_belief": (
            "Meridian has a credible opportunity to become the exception-resolution layer for "
            "mid-market brokerages if it can convert monthly contracts into annual ones and "
            "sell without founder involvement."
        ),
        "conviction_score": 6.4,
        "conviction_label": "MODERATE",
        "conviction_rationale": "Retention is real but the sales motion is unproven beyond the CEO.",
        "traction_metrics": [
            {"label": "ARR", "value": "$2.4M", "source_page": 5, "note": "as of Q2 2026"},
            {"label": "Growth", "value": "118%", "source_page": 5, "note": "year over year"},
            {"label": "Customers", "value": "37", "source_page": 5, "note": ""},
            {"label": "Gross margin", "value": "71%", "source_page": 5, "note": ""},
            {"label": "NRR", "value": "114%", "source_page": 5, "note": ""},
            {"label": "ACV", "value": "$64,800", "source_page": 5, "note": ""},
        ],
        "strongest_evidence": [
            {
                "evidence": "Net revenue retention of 114% across 37 paying brokerages.",
                "significance": "Existing accounts expand without new logo spend.",
                "evidence_type": "Company Data",
                "strength": "Strong",
                "source_page": 5,
            },
            {
                "evidence": "Ridgeline Logistics cut exception handling time 42% in 90 days.",
                "significance": "The product changes an operating metric buyers already track.",
                "evidence_type": "Customer Evidence",
                "strength": "Moderate",
                "source_page": 6,
            },
            {
                "evidence": "Live integrations with McLeod, Turvo and Aljex.",
                "significance": "Removes the rip-and-replace objection in the sales cycle.",
                "evidence_type": "Company Data",
                "strength": "Moderate",
                "source_page": 4,
            },
        ],
        "key_assumptions": [
            {
                "assumption": "Brokerages will convert from monthly to annual contracts as they scale.",
                "why_it_matters": "Retention and payback both assume contract durability.",
                "status": "Unproven",
                "is_critical_dependency": True,
            },
            {
                "assumption": "Deals can close without the CEO running every enterprise sale.",
                "why_it_matters": "Growth to $10M ARR requires a repeatable sales motion.",
                "status": "Unproven",
                "is_critical_dependency": False,
            },
            {
                "assumption": "Incumbent TMS vendors will not bundle exception resolution.",
                "why_it_matters": "Bundling would collapse standalone willingness to pay.",
                "status": "Partially supported",
                "is_critical_dependency": False,
            },
        ],
        "major_risks": [
            {
                "risk": "McLeod or Turvo bundles exception classification into the core TMS, removing the standalone budget line.",
                "probability": "Medium",
                "impact": "Very High",
                "early_warning": "An incumbent ships exception workflows in a release note or at a user conference.",
            },
            {
                "risk": "Monthly contracts churn at renewal once the initial time saving is banked.",
                "probability": "Medium-High",
                "impact": "High",
                "early_warning": "Logo churn rises above the reported 6% trailing-twelve-month rate.",
            },
            {
                "risk": "Sales stall when the CEO stops carrying every enterprise deal.",
                "probability": "High",
                "impact": "High",
                "early_warning": "First non-founder-closed deals take materially longer than the 74-day average.",
            },
        ],
        "weak_link": (
            "The deck presents retention as proven, but 34 of 37 customers are on monthly "
            "contracts. Durability of revenue has not been demonstrated across a renewal cycle."
        ),
        "critical_dependency": "Brokerages will convert from monthly to annual contracts as they scale.",
        "strongest_counterargument": (
            "Exception management is a workflow feature, not a platform. The incumbents own the "
            "system of record and can bundle it at zero marginal price once it matters."
        ),
        "conviction_strengthens_if": [
            "A majority of the 37 customers renew onto annual contracts.",
            "Two enterprise deals close without CEO involvement.",
        ],
        "conviction_weakens_if": [
            "Logo churn rises above 6% while ACV stays flat.",
            "An incumbent TMS ships equivalent exception workflows.",
        ],
        "thesis_invalid_if": [
            "Net revenue retention falls below 100% as monthly contracts come up for renewal.",
        ],
        "highest_value_test": (
            "Offer annual contracts at a modest discount to the next 10 monthly customers and "
            "measure the conversion rate. Above half converting supports revenue durability."
        ),
        "key_questions": [
            "What is gross revenue retention, separately from the 114% net figure?",
            "How many of the 37 customers have completed a full renewal cycle?",
            "What did the 3 annual contracts require in discount or commitment?",
        ],
        "missing_information": [
            "Gross revenue retention",
            "Pipeline coverage for the $5M ARR milestone",
        ],
        "source_references": [
            {"label": "S5", "page_number": 5, "claim": "$2.4M ARR", "quote": "$2.4M ARR as of Q2 2026"},
            {"label": "S5", "page_number": 5, "claim": "37 paying brokerages", "quote": "37 paying brokerages"},
            {"label": "S11", "page_number": 11, "claim": "Raising $6M Seed", "quote": "Raising $6M Seed"},
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def sample_analysis() -> InvestmentOnePager:
    return InvestmentOnePager.model_validate(analysis_payload())


class StubLLMClient(LLMClient):
    """Returns a canned payload, recording the prompts it was given."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        super().__init__("stub-model")
        self.payload = payload or analysis_payload()
        self.calls: list[tuple[str, str]] = []

    def generate_json(
        self, system: str, user: str, schema: dict[str, Any], schema_name: str = "response"
    ) -> LLMResult:
        self.calls.append((system, user))
        return LLMResult(data=dict(self.payload), model=self.model, input_tokens=1000, output_tokens=500)


@pytest.fixture
def stub_client() -> StubLLMClient:
    return StubLLMClient()
