"""Post-generation validation of the structured analysis.

The JSON schema handed to the model cannot express list caps or numeric bounds
(both providers reject those keywords), so they are enforced here. Validation
repairs what is safely repairable - trimming an over-long list, clamping a
score, normalising a placeholder to null - and raises when a load-bearing field
is missing, because rendering an empty thesis would be worse than failing.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..errors import AnalysisValidationError
from ..logging_setup import get_logger
from ..models.investment_analysis import InvestmentOnePager

log = get_logger("analysis.validation")

#: Maximum items rendered for each list, in priority order of the one-pager.
LIST_CAPS: dict[str, int] = {
    "traction_metrics": 6,
    "strongest_evidence": 5,
    "key_assumptions": 5,
    "major_risks": 5,
    "conviction_strengthens_if": 4,
    "conviction_weakens_if": 4,
    "thesis_invalid_if": 2,
    "key_questions": 5,
    "missing_information": 4,
    "source_references": 40,
}

REQUIRED_TEXT_FIELDS = (
    "company_name",
    "core_investment_belief",
    "weak_link",
    "critical_dependency",
    "highest_value_test",
)

#: Values that mean "the deck did not say" and should render as absent.
_PLACEHOLDERS = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "not provided",
    "not provided in deck",
    "not stated",
    "not disclosed",
    "not specified",
    "-",
    "—",
}

_OPTIONAL_TEXT_FIELDS = ("sector", "stage", "raise_amount", "valuation", "geography", "company_description")


def parse_analysis(payload: dict[str, Any]) -> InvestmentOnePager:
    """Validate raw model output against the Pydantic model."""
    try:
        return InvestmentOnePager.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(p) for p in first.get("loc", ()))
        raise AnalysisValidationError(
            f"The model output did not match the required schema at '{location}': "
            f"{first.get('msg', 'unknown error')}"
        ) from exc


def validate_and_repair(analysis: InvestmentOnePager) -> list[str]:
    """Enforce invariants in place. Returns the list of repairs made."""
    warnings: list[str] = []

    _check_required(analysis)
    warnings += _normalise_optionals(analysis)
    warnings += _clamp_score(analysis)
    warnings += _trim_lists(analysis)
    warnings += _fix_critical_dependency(analysis)
    warnings += _check_minimums(analysis)

    for warning in warnings:
        log.warning("Validation repair: %s", warning)
    return warnings


def _check_required(analysis: InvestmentOnePager) -> None:
    missing = [f for f in REQUIRED_TEXT_FIELDS if not str(getattr(analysis, f, "") or "").strip()]
    if missing:
        raise AnalysisValidationError(
            f"The analysis is missing required content: {', '.join(missing)}.",
            hint="Re-run the analysis; if it persists the deck may be too sparse.",
        )


def _normalise_optionals(analysis: InvestmentOnePager) -> list[str]:
    warnings: list[str] = []
    for name in _OPTIONAL_TEXT_FIELDS:
        value = getattr(analysis, name, None)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.lower() in _PLACEHOLDERS:
                setattr(analysis, name, None)
                warnings.append(f"{name}: placeholder text replaced with 'not provided'")
            elif cleaned != value:
                setattr(analysis, name, cleaned)
    return warnings


def _clamp_score(analysis: InvestmentOnePager) -> list[str]:
    warnings: list[str] = []
    score = float(analysis.conviction_score)
    if score < 0 or score > 10:
        clamped = min(10.0, max(0.0, score))
        warnings.append(f"conviction_score {score} clamped to {clamped}")
        score = clamped
    analysis.conviction_score = round(score, 1)

    expected = band_for_score(analysis.conviction_score)
    if analysis.conviction_label != expected:
        warnings.append(
            f"conviction_label '{analysis.conviction_label}' corrected to '{expected}' "
            f"for score {analysis.conviction_score}"
        )
        analysis.conviction_label = expected
    return warnings


def band_for_score(score: float) -> str:
    """Conviction band for a score. 0-3.9 LOW, 4.0-6.9 MODERATE, 7.0+ HIGH."""
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MODERATE"
    return "LOW"


def _trim_lists(analysis: InvestmentOnePager) -> list[str]:
    warnings: list[str] = []
    for name, cap in LIST_CAPS.items():
        items = getattr(analysis, name, None)
        if isinstance(items, list) and len(items) > cap:
            warnings.append(f"{name}: {len(items)} items trimmed to {cap}")
            setattr(analysis, name, items[:cap])
    return warnings


def _fix_critical_dependency(analysis: InvestmentOnePager) -> list[str]:
    warnings: list[str] = []
    flagged = [a for a in analysis.key_assumptions if a.is_critical_dependency]

    if len(flagged) > 1:
        for extra in flagged[1:]:
            extra.is_critical_dependency = False
        warnings.append(f"{len(flagged)} assumptions were marked critical; kept the first")
    elif not flagged and analysis.key_assumptions:
        analysis.key_assumptions[0].is_critical_dependency = True
        warnings.append("no critical dependency was flagged; marked the first assumption")
    return warnings


def _check_minimums(analysis: InvestmentOnePager) -> list[str]:
    """Warn (don't fail) when the model under-delivered on a section."""
    warnings: list[str] = []
    expectations = {
        "strongest_evidence": 3,
        "key_assumptions": 3,
        "major_risks": 3,
        "key_questions": 3,
        "conviction_strengthens_if": 2,
        "conviction_weakens_if": 2,
        "thesis_invalid_if": 1,
    }
    for name, minimum in expectations.items():
        count = len(getattr(analysis, name, []))
        if count < minimum:
            warnings.append(f"{name}: only {count} item(s), expected at least {minimum}")
    return warnings
