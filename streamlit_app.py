"""TEN Capital Network - Deck to One-Pager.

Web UI, running locally and as the deployed app.

Local::

    streamlit run streamlit_app.py

Deployed (Railway injects ``$PORT``)::

    streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0

The uploaded deck is written to a temporary file, processed, and removed again.
Deck text is sent to the configured LLM provider; nothing else leaves the host.

Set ``APP_PASSWORD`` to require a shared password before the app can be used -
strongly recommended for any public deployment, since the app spends API credits
and handles confidential decks.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import tempfile
from pathlib import Path

import streamlit as st

from pitchdeck_onepager.config import AppConfig, is_hosted_environment
from pitchdeck_onepager.errors import PitchDeckError
from pitchdeck_onepager.pipeline import generate_onepager
from pitchdeck_onepager.web.theme import (
    band_color,
    inject_theme,
    render_brand,
    render_disclosure,
    render_dropzone_head,
    render_footer,
    render_hero,
    render_verdict,
)

MAX_UPLOAD_MB = 25
ACCEPTED_TYPES = ["pdf", "pptx", "ppt"]

st.set_page_config(
    page_title="TEN Capital Network - Deck to One-Pager",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

inject_theme()


def check_access() -> bool:
    """Gate the app behind ``APP_PASSWORD`` when one is configured."""
    expected = os.environ.get("APP_PASSWORD", "").strip()
    if not expected:
        if is_hosted_environment():
            st.warning(
                "This deployment is **not password protected**. Anyone with the URL can "
                "upload decks and spend your API credits. Set an `APP_PASSWORD` variable "
                "and redeploy."
            )
        return True

    if st.session_state.get("access_granted"):
        return True

    with st.form("access"):
        entered = st.text_input("Password", type="password")
        if st.form_submit_button("Continue"):
            if hmac.compare_digest(entered, expected):
                st.session_state["access_granted"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


defaults = AppConfig.from_env()

# --- Settings live in the sidebar so the main card stays a single task -------

with st.sidebar:
    st.header("Settings")
    providers = ["anthropic", "openai", "openai_compatible"]
    provider = st.selectbox(
        "Provider",
        providers,
        index=providers.index(defaults.provider) if defaults.provider in providers else 0,
    )
    model = st.text_input("Model", value=defaults.resolved_model, placeholder="provider default")
    effort = st.selectbox("Effort (Anthropic)", ["low", "medium", "high", "xhigh", "max"], index=2)
    page_size = st.selectbox(
        "Page size", ["LETTER", "A4"], index=0 if defaults.page_size == "LETTER" else 1
    )
    show_sources = st.checkbox("Show [S8] slide markers", value=defaults.show_source_references)
    enable_ocr = st.checkbox("OCR image-only slides", value=defaults.enable_ocr)

    config = AppConfig.from_env(
        provider=provider,
        model=model or None,
        effort=effort,
        page_size=page_size,
        show_source_references=show_sources,
        enable_ocr=enable_ocr,
    )

    key_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    if config.api_key():
        st.success(f"{key_var} detected")
    elif is_hosted_environment():
        st.error(f"{key_var} is not set. Add it under your service's Variables and redeploy.")
    else:
        st.error(f"{key_var} is not set. Add it to your environment or .env file.")

    if not config.resolved_model:
        st.error("No model configured. Set LLM_MODEL for this provider.")

# --- Main card ---------------------------------------------------------------

render_brand()

with st.container(key="tc_card"):
    render_hero(
        eyebrow="Deck Analyzer",
        lede=(
            "Upload a pitch deck and get a polished single-page investor PDF, "
            "analyzed and structured by Claude."
        ),
    )

    if not check_access():
        render_disclosure("Access is restricted. Contact the workspace owner for the password.")
        st.stop()

    # The sidebar starts collapsed, so a missing key has to surface here too.
    if not config.api_key():
        st.error(
            f"**{key_var} is not set.** Add it "
            + ("under your service's Variables and redeploy." if is_hosted_environment()
               else "to your environment or .env file.")
        )

    with st.container(key="tc_drop"):
        render_dropzone_head("Click to choose a deck")
        uploaded = st.file_uploader(
            f"Deck file - {' · '.join('.' + t for t in ACCEPTED_TYPES)} · up to {MAX_UPLOAD_MB} MB",
            type=ACCEPTED_TYPES,
            label_visibility="collapsed",
        )

    with st.container(key="tc_generate"):
        generate = st.button(
            "Generate one-pager PDF",
            type="primary",
            disabled=uploaded is None,
            use_container_width=True,
        )

    if uploaded is not None and generate:
        status = st.empty()
        progress = st.progress(0.0)
        steps = {
            "Reading": 0.15,
            "Extracted": 0.3,
            "Reconstructing": 0.5,
            "Rendering": 0.85,
            "Done": 1.0,
        }

        def on_progress(message: str) -> None:
            status.info(message)
            for prefix, value in steps.items():
                if message.startswith(prefix):
                    progress.progress(value)

        workdir = Path(tempfile.mkdtemp(prefix="pitchdeck_"))
        source = workdir / uploaded.name
        source.write_bytes(uploaded.getbuffer())

        try:
            result = generate_onepager(
                source, workdir / f"{source.stem}_onepager.pdf", config=config, progress=on_progress
            )
        except PitchDeckError as exc:
            progress.empty()
            status.empty()
            st.error(f"**{exc.message}**\n\n{exc.hint}")
        except Exception:  # noqa: BLE001 - never leak internals to a public URL
            progress.empty()
            status.empty()
            logging.getLogger("pitchdeck_onepager.ui").exception(
                "Unhandled failure during generation"
            )
            st.error(
                "**Generation failed unexpectedly.** The details were written to the server "
                "logs. Retry, and if it persists check the deploy logs."
            )
        else:
            progress.empty()
            status.empty()
            analysis = result.analysis

            render_verdict(
                company=analysis.company_name,
                score=analysis.conviction_score,
                band=analysis.conviction_label,
                belief=analysis.core_investment_belief,
                color=band_color(analysis.conviction_label),
            )

            left, right = st.columns(2)
            left.download_button(
                "Download PDF",
                result.pdf_path.read_bytes(),
                file_name=result.pdf_path.name,
                mime="application/pdf",
                use_container_width=True,
            )
            if result.json_path:
                right.download_button(
                    "Download analysis (JSON)",
                    result.json_path.read_text(encoding="utf-8"),
                    file_name=result.json_path.name,
                    mime="application/json",
                    use_container_width=True,
                )

            try:
                import pymupdf

                with pymupdf.open(result.pdf_path) as document:
                    pixmap = document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2))
                    st.image(pixmap.tobytes("png"), use_container_width=True)
            except Exception:  # pragma: no cover - preview is best effort
                st.caption("Preview unavailable; download the PDF above.")

            if result.warnings:
                with st.expander(f"{len(result.warnings)} analysis warning(s)"):
                    for warning in result.warnings:
                        st.write(f"- {warning}")

            with st.expander("Structured analysis"):
                st.json(json.loads(analysis.model_dump_json()))
        finally:
            # Remove the uploaded copy; generated artefacts were read above.
            source.unlink(missing_ok=True)

    render_disclosure(
        "The uploaded file is processed on this server and deleted immediately after the "
        "one-pager is generated. Deck text is sent to the configured model provider "
        f"(<code>{config.resolved_model or 'not configured'}</code>) for analysis; nothing "
        "is stored or forwarded anywhere else."
    )

render_footer()
