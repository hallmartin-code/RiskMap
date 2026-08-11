"""Schema generation, output validation and hallucination control."""

from __future__ import annotations

from pathlib import Path

import pytest

from pitchdeck_onepager.analysis.provenance import apply_provenance_controls
from pitchdeck_onepager.analysis.schema_tools import build_schema, sanitize_schema
from pitchdeck_onepager.analysis.validation import (
    band_for_score,
    parse_analysis,
    validate_and_repair,
)
from pitchdeck_onepager.errors import AnalysisValidationError, LLMResponseError
from pitchdeck_onepager.ingestion.pdf_parser import parse_pdf
from pitchdeck_onepager.models.investment_analysis import InvestmentOnePager

from conftest import StubLLMClient, analysis_payload


# --- Schema ------------------------------------------------------------------


def _walk_objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for value in node.values():
            yield from _walk_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_objects(item)


def test_schema_marks_every_object_closed_and_fully_required() -> None:
    schema = build_schema(InvestmentOnePager)

    objects = list(_walk_objects(schema))
    assert objects
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj.get("properties", {}))


def test_schema_strips_unsupported_keywords() -> None:
    dirty = {
        "type": "object",
        "properties": {"n": {"type": "number", "minimum": 0, "maximum": 10, "default": 5}},
    }
    clean = sanitize_schema(dirty)

    assert "minimum" not in clean["properties"]["n"]
    assert "maximum" not in clean["properties"]["n"]
    assert "default" not in clean["properties"]["n"]


def test_optional_fields_become_nullable_types() -> None:
    schema = build_schema(InvestmentOnePager)
    assert schema["properties"]["sector"]["type"] == ["string", "null"]


# --- Parsing / validation ----------------------------------------------------


def test_valid_payload_parses() -> None:
    analysis = parse_analysis(analysis_payload())
    assert analysis.company_name == "Meridian Freight OS"
    assert analysis.conviction_score == pytest.approx(6.4)


def test_malformed_payload_raises_actionable_error() -> None:
    with pytest.raises(AnalysisValidationError):
        parse_analysis({"company_name": "X"})


def test_missing_thesis_is_rejected() -> None:
    analysis = parse_analysis(analysis_payload(core_investment_belief="   "))
    with pytest.raises(AnalysisValidationError):
        validate_and_repair(analysis)


def test_score_is_clamped_and_label_corrected() -> None:
    analysis = parse_analysis(analysis_payload(conviction_score=14.0, conviction_label="LOW"))
    warnings = validate_and_repair(analysis)

    assert analysis.conviction_score == 10.0
    assert analysis.conviction_label == "HIGH"
    assert any("clamped" in w for w in warnings)


@pytest.mark.parametrize(
    ("score", "band"), [(0.0, "LOW"), (3.9, "LOW"), (4.0, "MODERATE"), (6.9, "MODERATE"), (7.0, "HIGH")]
)
def test_conviction_bands(score: float, band: str) -> None:
    assert band_for_score(score) == band


def test_over_long_lists_are_trimmed() -> None:
    payload = analysis_payload()
    payload["key_questions"] = [f"Question {i}?" for i in range(20)]
    analysis = parse_analysis(payload)

    validate_and_repair(analysis)
    assert len(analysis.key_questions) == 5


def test_exactly_one_critical_dependency_survives() -> None:
    payload = analysis_payload()
    for assumption in payload["key_assumptions"]:
        assumption["is_critical_dependency"] = True
    analysis = parse_analysis(payload)

    validate_and_repair(analysis)
    assert sum(a.is_critical_dependency for a in analysis.key_assumptions) == 1


def test_missing_critical_dependency_is_assigned() -> None:
    payload = analysis_payload()
    for assumption in payload["key_assumptions"]:
        assumption["is_critical_dependency"] = False
    analysis = parse_analysis(payload)

    validate_and_repair(analysis)
    assert analysis.key_assumptions[0].is_critical_dependency


def test_placeholder_metadata_becomes_absent() -> None:
    analysis = parse_analysis(analysis_payload(valuation="Not provided in deck", stage="N/A"))
    validate_and_repair(analysis)

    assert analysis.valuation is None
    assert analysis.stage is None
    assert ("Valuation", "Not provided in deck") not in analysis.meta_chips()


def test_invalid_json_from_model_is_reported() -> None:
    with pytest.raises(LLMResponseError):
        StubLLMClient._parse_json("this is not json")


# --- Provenance --------------------------------------------------------------


def test_fabricated_metric_is_dropped(sample_pdf: Path) -> None:
    deck = parse_pdf(sample_pdf)
    payload = analysis_payload()
    payload["traction_metrics"].append(
        {"label": "Pipeline", "value": "$9.7M", "source_page": 5, "note": ""}
    )
    analysis = parse_analysis(payload)

    report = apply_provenance_controls(analysis, deck)

    assert "$9.7M" not in [m.value for m in analysis.traction_metrics]
    assert any("9.7" in dropped for dropped in report.dropped_metrics)


def test_real_metrics_are_kept(sample_pdf: Path) -> None:
    deck = parse_pdf(sample_pdf)
    analysis = parse_analysis(analysis_payload())

    report = apply_provenance_controls(analysis, deck)

    values = {m.value for m in analysis.traction_metrics}
    assert {"$2.4M", "118%", "71%", "$64,800"} <= values
    assert report.dropped_metrics == []
    assert report.verified_metrics == 6


def test_unverifiable_prose_figure_is_flagged_not_deleted(sample_pdf: Path) -> None:
    deck = parse_pdf(sample_pdf)
    analysis = parse_analysis(
        analysis_payload(weak_link="Only 3 of 37 customers are annual, and CAC is $88,000.")
    )

    report = apply_provenance_controls(analysis, deck)

    assert any("88,000" in flag or "88000" in flag for flag in report.flagged_claims)
    assert "$88,000" in analysis.weak_link  # judgment text is preserved verbatim
