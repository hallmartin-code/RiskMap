"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import AppConfig
from .errors import PitchDeckError
from .logging_setup import configure_logging
from .pipeline import generate_onepager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pitchdeck-onepager",
        description="Turn an investor pitch deck (.pdf/.pptx/.ppt) into a one-page investment analysis PDF.",
        epilog=(
            "Deck text is sent to the configured LLM provider for analysis. "
            "Everything else happens locally."
        ),
    )
    parser.add_argument("input", type=Path, nargs="?", help="Path to the pitch deck")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output PDF path")
    parser.add_argument(
        "--template",
        action="store_true",
        help="Render the blank one-pager template (no deck, no API call) and exit",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "openai_compatible"],
        default=None,
        help="LLM provider (default: LLM_PROVIDER, else anthropic)",
    )
    parser.add_argument("--model", default=None, help="Model id (default: LLM_MODEL)")
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        default=None,
        help="Reasoning effort for Anthropic models (default: high)",
    )
    parser.add_argument("--page-size", choices=["LETTER", "A4"], default=None, help="Output page size")

    sources = parser.add_mutually_exclusive_group()
    sources.add_argument(
        "--show-sources", dest="show_sources", action="store_true", default=None,
        help="Show compact [S8] slide markers on sourced claims",
    )
    sources.add_argument(
        "--no-sources", dest="show_sources", action="store_false", help="Hide slide markers"
    )

    parser.add_argument("--no-json", action="store_true", help="Do not write the JSON sidecar")
    parser.add_argument("--ocr", action="store_true", default=None, help="Enable the OCR fallback")
    parser.add_argument("--quiet", action="store_true", help="Only print the final summary")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser


def _render_template(args: argparse.Namespace, config: AppConfig) -> int:
    """Write the blank structural template. No deck and no LLM call involved."""
    from .rendering.template import render_template

    config.ensure_dirs()
    output = args.output or config.output_dir / "onepager_template.pdf"

    try:
        result = render_template(
            output, page_size_name=config.page_size, show_sources=config.show_source_references
        )
    except PitchDeckError as exc:
        print(f"\nError: {exc.message}", file=sys.stderr)
        if exc.hint:
            print(f"  {exc.hint}", file=sys.stderr)
        return 1

    print(f"\nTemplate         {result.output_path}")
    print(f"Layout           {result.summary()}")
    print("Specification    templates/onepager_template.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.input is None and not args.template:
        parser.error("an input deck is required (or use --template)")

    log_level = "DEBUG" if args.verbose else ("WARNING" if args.quiet else "INFO")
    configure_logging(log_level)

    config = AppConfig.from_env(
        provider=args.provider,
        model=args.model,
        effort=args.effort,
        page_size=args.page_size,
        show_source_references=args.show_sources,
        keep_analysis_json=False if args.no_json else None,
        enable_ocr=args.ocr,
        log_level=log_level,
    )

    if args.template:
        return _render_template(args, config)

    try:
        result = generate_onepager(args.input, args.output, config=config)
    except PitchDeckError as exc:
        print(f"\nError: {exc.message}", file=sys.stderr)
        if exc.hint:
            print(f"  {exc.hint}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print("\nInterrupted.", file=sys.stderr)
        return 130

    print()
    for line in result.summary_lines():
        print(line)

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
