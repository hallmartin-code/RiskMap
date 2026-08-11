"""Brand theme checks.

The UI is styled by injected CSS, so the tests assert the contract that styling
depends on: the palette, the container keys the stylesheet is scoped to, and the
copy that must stay truthful about what the app does.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pitchdeck_onepager.web import theme

ROOT = Path(__file__).resolve().parent.parent
APP_SOURCE = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")


def test_palette_matches_the_approved_design() -> None:
    assert theme.BRAND["navy_950"] == "#0B1526"
    assert theme.BRAND["coral"] == "#EE5A4E"
    assert theme.BRAND["amber"] == "#F3A22A"
    assert theme.BRAND["teal"] == "#35BEBB"


@pytest.mark.parametrize(
    ("band", "expected"),
    [("HIGH", theme.BRAND["teal"]), ("MODERATE", theme.BRAND["amber"]), ("LOW", theme.BRAND["coral"])],
)
def test_conviction_bands_map_to_brand_colours(band: str, expected: str) -> None:
    assert theme.band_color(band) == expected
    assert theme.band_color(band.lower()) == expected


def test_unknown_band_falls_back_to_neutral() -> None:
    assert theme.band_color("[BAND]") == theme.BRAND["ink_300"]


@pytest.mark.parametrize("key", ["tc_card", "tc_drop", "tc_generate"])
def test_stylesheet_and_app_agree_on_container_keys(key: str) -> None:
    """CSS is scoped to .st-key-<key>; the app must create those containers."""
    assert f".st-key-{key}" in theme._CSS, f"stylesheet does not target {key}"
    assert f'key="{key}"' in APP_SOURCE, f"app never creates a container keyed {key}"


def test_every_brand_colour_is_used_by_the_stylesheet() -> None:
    for name, value in theme.BRAND.items():
        assert value.lower() in theme._CSS.lower(), f"{name} ({value}) is unused"


def test_upload_limit_copy_matches_the_server_limit() -> None:
    """UI copy states the cap; Streamlit enforces it. They must not drift."""
    declared = int(re.search(r"MAX_UPLOAD_MB\s*=\s*(\d+)", APP_SOURCE).group(1))
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    enforced = int(re.search(r"maxUploadSize\s*=\s*(\d+)", config).group(1))

    assert declared == enforced, "MAX_UPLOAD_MB and maxUploadSize disagree"


def test_accepted_types_match_what_ingestion_supports() -> None:
    """The UI must not advertise a format the router would reject."""
    from pitchdeck_onepager.ingestion.document_router import SUPPORTED_SUFFIXES

    advertised = re.search(r"ACCEPTED_TYPES\s*=\s*\[(.*?)\]", APP_SOURCE, re.S).group(1)
    types = {t.strip().strip("\"'") for t in advertised.split(",") if t.strip()}

    assert {f".{t}" for t in types} <= SUPPORTED_SUFFIXES, (
        f"UI advertises unsupported types: {types}"
    )


def test_disclosure_does_not_promise_delivery_the_app_does_not_perform() -> None:
    """Guards against re-introducing an email/forwarding claim with no code behind it."""
    for banned in ("emailed", "email a copy", "forwarded to", "@gmail.com"):
        assert banned not in APP_SOURCE.lower(), f"UI copy claims '{banned}' but nothing implements it"
