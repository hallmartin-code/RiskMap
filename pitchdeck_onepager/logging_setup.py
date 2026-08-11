"""Logging configuration.

Deck contents are confidential: page text is never logged at INFO. Debug-level
logging emits short previews only, and API keys are never touched.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    root = logging.getLogger("pitchdeck_onepager")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S"))
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"pitchdeck_onepager.{name}")
