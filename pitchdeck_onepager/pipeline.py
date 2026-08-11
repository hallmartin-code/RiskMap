"""End-to-end orchestration: deck file in, one-page PDF (+ JSON) out."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis.analyzer import AnalysisOutcome, InvestmentAnalyzer
from .analysis.llm import LLMClient, build_client
from .config import AppConfig
from .errors import OnePageOverflowError
from .ingestion import load_deck
from .logging_setup import configure_logging, get_logger
from .models.deck import DeckDocument
from .models.investment_analysis import InvestmentOnePager
from .rendering import DocumentMeta, RenderResult, render_onepager

log = get_logger("pipeline")

ProgressCallback = Callable[[str], None]


@dataclass
class PipelineResult:
    """Everything produced by a run."""

    pdf_path: Path
    analysis: InvestmentOnePager
    render: RenderResult
    outcome: AnalysisOutcome
    deck: DeckDocument
    json_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"Company            {self.analysis.company_name}",
            f"Conviction         {self.analysis.conviction_score:.1f} / 10  ({self.analysis.conviction_label})",
            f"Deck               {self.deck.filename} - {self.deck.page_count} slides",
            f"Metrics rendered   {len(self.analysis.traction_metrics)}",
            f"Layout             {self.render.summary()}",
            f"PDF                {self.pdf_path}",
        ]
        if self.json_path:
            lines.append(f"JSON               {self.json_path}")
        return lines


def default_output_path(input_path: Path, config: AppConfig) -> Path:
    return config.output_dir / f"{Path(input_path).stem}_onepager.pdf"


def generate_onepager(
    input_path: str | Path,
    output_path: str | Path | None = None,
    config: AppConfig | None = None,
    client: LLMClient | None = None,
    progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Run ingestion, analysis and rendering.

    ``client`` may be injected (tests, alternate providers); otherwise it is
    built from ``config``.
    """
    config = config or AppConfig.from_env()
    configure_logging(config.log_level)
    config.ensure_dirs()

    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else default_output_path(input_path, config)

    def step(message: str) -> None:
        log.info(message)
        if progress:
            progress(message)

    log.info("Starting run | %s", config.redacted())

    step(f"Reading {input_path.name}")
    deck = load_deck(input_path, config)
    step(f"Extracted {deck.page_count} slides ({deck.total_chars:,} characters)")

    llm = client or build_client(config)
    analyzer = InvestmentAnalyzer(llm)

    step("Reconstructing the investment thesis")
    outcome = analyzer.analyze(deck)

    meta = DocumentMeta(
        source_filename=deck.filename,
        slide_count=deck.page_count,
        model=outcome.model or config.resolved_model,
    )

    step("Rendering the one-pager")
    try:
        render = _render(outcome.analysis, output_path, meta, config)
    except OnePageOverflowError:
        # Stage 2: compress prose and retry. The renderer's own compression
        # ladder has already been exhausted at this point.
        step("Content did not fit - running the compression pass")
        outcome = analyzer.compress(outcome, deck)
        render = _render(outcome.analysis, output_path, meta, config)

    warnings = list(outcome.validation_warnings)
    warnings.extend(deck.warnings)
    if outcome.provenance.dropped_metrics:
        warnings.append(
            f"{len(outcome.provenance.dropped_metrics)} metric(s) were dropped because they "
            "could not be traced to the deck."
        )
    if outcome.provenance.flagged_claims:
        warnings.append(
            f"{len(outcome.provenance.flagged_claims)} figure(s) in prose could not be traced "
            "to the deck (see the JSON sidecar)."
        )

    json_path: Path | None = None
    if config.keep_analysis_json:
        json_path = output_path.with_suffix(".json")
        json_path.write_text(
            json.dumps(_sidecar(outcome, deck, render, config, warnings), indent=2), encoding="utf-8"
        )
        step(f"Wrote {json_path.name}")

    step(f"Done: {output_path.name} ({render.summary()})")
    return PipelineResult(
        pdf_path=output_path,
        analysis=outcome.analysis,
        render=render,
        outcome=outcome,
        deck=deck,
        json_path=json_path,
        warnings=warnings,
    )


def _render(
    analysis: InvestmentOnePager, output_path: Path, meta: DocumentMeta, config: AppConfig
) -> RenderResult:
    return render_onepager(
        analysis=analysis,
        output_path=output_path,
        meta=meta,
        page_size_name=config.page_size,
        show_sources=config.show_source_references,
    )


def _sidecar(
    outcome: AnalysisOutcome,
    deck: DeckDocument,
    render: RenderResult,
    config: AppConfig,
    warnings: list[str],
) -> dict[str, Any]:
    """Structured analysis plus the audit trail, written next to the PDF."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "filename": deck.filename,
            "file_type": deck.file_type,
            "slide_count": deck.page_count,
            "characters_extracted": deck.total_chars,
            "image_only_pages": deck.image_only_pages,
            "extraction_warnings": deck.warnings,
        },
        "llm": {
            "provider": config.provider,
            "model": outcome.model or config.resolved_model,
            "input_tokens": outcome.input_tokens,
            "output_tokens": outcome.output_tokens,
            "compression_pass_used": outcome.compressed,
        },
        "render": {
            "page_count": render.page_count,
            "font_scale": render.font_scale,
            "spacing_scale": render.space_scale,
            "content_level": render.caps_level,
            "page_size": config.page_size,
        },
        "provenance": {
            "verified_metrics": outcome.provenance.verified_metrics,
            "dropped_metrics": outcome.provenance.dropped_metrics,
            "flagged_prose_figures": outcome.provenance.flagged_claims,
        },
        "validation_warnings": outcome.validation_warnings,
        "warnings": warnings,
        "analysis": outcome.analysis.model_dump(mode="json"),
    }
