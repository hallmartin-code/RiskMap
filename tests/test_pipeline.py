"""End-to-end pipeline behaviour, with the LLM stubbed out."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from pitchdeck_onepager.errors import LLMConfigurationError
from pitchdeck_onepager.analysis.llm import build_client
from pitchdeck_onepager.config import AppConfig
from pitchdeck_onepager.pipeline import generate_onepager

from conftest import StubLLMClient, analysis_payload


def test_pdf_deck_produces_one_page_pdf_and_json(sample_pdf: Path, config, stub_client, tmp_path) -> None:
    out = tmp_path / "meridian.pdf"

    result = generate_onepager(sample_pdf, out, config=config, client=stub_client)

    assert result.pdf_path.exists()
    assert len(PdfReader(str(result.pdf_path)).pages) == 1
    assert result.json_path is not None and result.json_path.exists()


def test_pptx_deck_works_through_the_same_path(sample_pptx: Path, config, stub_client, tmp_path) -> None:
    result = generate_onepager(sample_pptx, tmp_path / "from_pptx.pdf", config=config, client=stub_client)
    assert len(PdfReader(str(result.pdf_path)).pages) == 1


def test_json_sidecar_carries_the_audit_trail(sample_pdf: Path, config, stub_client, tmp_path) -> None:
    result = generate_onepager(sample_pdf, tmp_path / "out.pdf", config=config, client=stub_client)
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))

    assert payload["analysis"]["company_name"] == "Meridian Freight OS"
    assert payload["source"]["slide_count"] == 12
    assert payload["render"]["page_count"] == 1
    assert "provenance" in payload
    assert payload["analysis"]["source_references"]


def test_prompt_includes_deck_text_and_extracted_numbers(sample_pdf: Path, config, stub_client, tmp_path) -> None:
    generate_onepager(sample_pdf, tmp_path / "out.pdf", config=config, client=stub_client)
    system, user = stub_client.calls[0]

    assert "skeptical early-stage investment diligence" in system
    assert "SLIDE 5" in user
    assert "$2.4M" in user
    assert "NUMERIC VALUES FOUND IN DECK" in user


def test_fabricated_metrics_never_reach_the_pdf(sample_pdf: Path, config, tmp_path) -> None:
    payload = analysis_payload()
    payload["traction_metrics"] = [
        {"label": "ARR", "value": "$2.4M", "source_page": 5, "note": ""},
        {"label": "Pipeline", "value": "$47.3M", "source_page": 5, "note": ""},
    ]
    client = StubLLMClient(payload)

    result = generate_onepager(sample_pdf, tmp_path / "out.pdf", config=config, client=client)
    text = PdfReader(str(result.pdf_path)).pages[0].extract_text()

    assert "$2.4M" in text
    assert "$47.3M" not in text
    assert any("dropped" in w for w in result.warnings)


def test_compression_pass_recovers_from_overflow(sample_pdf: Path, config, tmp_path) -> None:
    """When the layout ladder is exhausted, stage 2 shortens the prose and the run succeeds."""
    filler = "This clause is padded so the first render cannot possibly fit on one page. " * 6
    bloated = analysis_payload(
        weak_link=filler,
        strongest_counterargument=filler,
        highest_value_test=filler,
        core_investment_belief=filler,
    )
    for item in bloated["strongest_evidence"]:
        item["evidence"] = filler
    for risk in bloated["major_risks"]:
        risk["risk"] = filler
        risk["early_warning"] = filler

    class TwoStageClient(StubLLMClient):
        def generate_json(self, system, user, schema, schema_name="response"):
            self.payload = bloated if not self.calls else analysis_payload()
            return super().generate_json(system, user, schema, schema_name)

    client = TwoStageClient(bloated)
    result = generate_onepager(sample_pdf, tmp_path / "out.pdf", config=config, client=client)

    assert len(client.calls) == 2, "the compression stage should have run"
    assert result.outcome.compressed
    assert len(PdfReader(str(result.pdf_path)).pages) == 1


def test_json_can_be_disabled(sample_pdf: Path, tmp_path, stub_client) -> None:
    config = AppConfig.from_env(
        output_dir=tmp_path, temp_dir=tmp_path / "t", keep_analysis_json=False, log_level="WARNING"
    )
    result = generate_onepager(sample_pdf, tmp_path / "out.pdf", config=config, client=stub_client)

    assert result.json_path is None
    assert not (tmp_path / "out.json").exists()


def test_default_output_path_is_derived_from_the_input(sample_pdf: Path, config, stub_client) -> None:
    result = generate_onepager(sample_pdf, None, config=config, client=stub_client)
    assert result.pdf_path.name == "sample_pitch_onepager.pdf"
    assert result.pdf_path.parent == config.output_dir


def test_missing_api_key_is_reported_clearly(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AppConfig.from_env(provider="anthropic")

    with pytest.raises(LLMConfigurationError) as excinfo:
        build_client(config)
    assert "ANTHROPIC_API_KEY" in str(excinfo.value)


def test_openai_provider_requires_an_explicit_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    config = AppConfig.from_env(provider="openai", model="")

    with pytest.raises(LLMConfigurationError) as excinfo:
        build_client(config)
    assert "does not guess model ids" in str(excinfo.value)


def test_cli_reports_errors_without_a_traceback(tmp_path, capsys) -> None:
    from pitchdeck_onepager.cli import main

    bogus = tmp_path / "deck.txt"
    bogus.write_text("nope", encoding="utf-8")

    assert main([str(bogus)]) == 1
    assert "Error:" in capsys.readouterr().err
