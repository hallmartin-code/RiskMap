# Pitch Deck → One-Page Investment Analysis

Turns an investor pitch deck (`.pdf`, `.pptx`, `.ppt`) into a single-page,
information-dense investment analysis PDF suitable for an investment committee.

It does **not** summarise the deck. It reconstructs the underlying investment
thesis, separates what the deck *demonstrates* from what the founder *asserts*,
identifies the dependency whose failure would break the most of the case, and
states the observable conditions that would raise, lower or invalidate
conviction.

```
deck.pdf ──▶ ingestion ──▶ structured deck JSON ──▶ LLM analysis ──▶ validation
                                                                        │
                                              one-page PDF ◀── rendering ┘
```

---

## Sample output

The included fixture (`tests/fixtures/sample_pitch.pdf`, a fictional seed-stage
logistics SaaS company) produces a one-pager with these sections:

| Section | Content |
|---|---|
| Header | Company, description, sector / stage / raise / valuation, conviction badge |
| Core investment belief | One sentence: the economic bet, not the product |
| Key metrics | Up to 6 decision-relevant metrics, each traceable to a slide |
| Evidence supporting thesis | 3–5 items, each classified and strength-rated |
| What must be true | 3–5 assumptions, one flagged as the critical dependency |
| Weakest link | The largest gap between narrative and demonstrated fact |
| Risk map | Risk / probability / impact / early-warning signal |
| Conviction strengthens ⟷ weakens if | Observable developments in both directions |
| Best opposing view · Thesis invalid if | The steel-manned bear case and its breaking conditions |
| Next proof point | The smallest, highest-information test |
| Key diligence questions | 3–5 questions targeting the actual evidence gaps |

---

## Installation

Requires **Python 3.11+**.

```bash
git clone <your-repo> && cd RiskMap
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

`streamlit`, `openai` and `anthropic` are all listed; you only need the provider
you intend to use.

### API keys

```bash
cp .env.example .env      # then edit .env
```

```ini
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Environment variables take precedence over `.env`. No key is ever written to a
log or to the JSON sidecar. **Do not commit `.env`.**

Supported providers:

| `LLM_PROVIDER` | Model default | Notes |
|---|---|---|
| `anthropic` | `claude-opus-5` | Structured outputs, adaptive thinking, `LLM_EFFORT` |
| `openai` | none — set `LLM_MODEL` | Strict JSON-schema mode |
| `openai_compatible` | none — set `LLM_MODEL` | Also set `OPENAI_BASE_URL` (vLLM, LiteLLM, …) |

The app never guesses an OpenAI model id; if `LLM_MODEL` is unset for those
providers it fails with an explicit message.

---

## CLI

```bash
python cli.py input/acme_pitch.pdf
```

```bash
python cli.py input/acme_pitch.pdf \
    --output output/acme_onepager.pdf \
    --provider anthropic \
    --model claude-opus-5 \
    --effort high \
    --page-size A4 \
    --show-sources
```

| Flag | Effect |
|---|---|
| `-o, --output` | Output PDF path (default `output/<name>_onepager.pdf`) |
| `--template` | Render the blank structural template; no deck, no API call |
| `--provider` | `anthropic`, `openai`, `openai_compatible` |
| `--model` | Model id |
| `--effort` | `low`…`max` (Anthropic reasoning effort) |
| `--page-size` | `LETTER` (default) or `A4` |
| `--show-sources` / `--no-sources` | Compact `[S8]` slide markers |
| `--no-json` | Skip the JSON sidecar |
| `--ocr` | Enable the OCR fallback for image-only slides |
| `--quiet` / `--verbose` | Logging level |

Exit code `0` on success, `1` on a handled error (with a one-line hint), `130`
on interrupt.

## Web UI

```bash
streamlit run streamlit_app.py            # http://localhost:8501
```

Upload a deck, generate, preview the page inline, and download the PDF or the
structured JSON. Provider, model, effort, page size and OCR live in the sidebar
(collapsed by default so the main card stays a single task).

The interface carries the TEN Capital Network identity — dark navy surface,
tri-colour coral/amber/teal accent echoing the three figures in the mark, Sora
display type over Inter. Styling lives in
[`pitchdeck_onepager/web/theme.py`](pitchdeck_onepager/web/theme.py): design
tokens in `BRAND`, one stylesheet, and small render helpers for the brand
lockup, hero, dropzone, result verdict and footer. Widget styling is scoped to
`st.container(key=...)` wrappers (`.st-key-tc_card`, `tc_drop`, `tc_generate`),
so retuning the palette means editing tokens in one file.

Selectors that reach into Streamlit internals are marked in `theme.py` and
degrade to the default widget appearance rather than breaking. Note that
Streamlit's module watcher does not reliably reload `theme.py` — **restart the
server after editing it**.

## Deploying as a web app

The repository is deployment-ready for Railway (or any container host):
`Dockerfile`, `railway.json` (start command, `/_stcore/health` health check,
restart policy), `Procfile` for the Nixpacks path, and `.streamlit/config.toml`.

```
Railway service ── env vars ──▶ ANTHROPIC_API_KEY   (from the Claude Console)
                               APP_PASSWORD        (gate the public URL)
```

Full walkthrough — key creation, variables, domain, security, cost control and
troubleshooting: **[docs/DEPLOY_RAILWAY.md](docs/DEPLOY_RAILWAY.md)**.

Two things worth knowing before you deploy:

- **Set `APP_PASSWORD`.** Without it, anyone with the URL can upload decks and
  spend your API credits. The app shows a warning banner when it detects a
  hosted environment with no password configured.
- **Do not set `PORT`.** The platform injects it; the start command binds
  `${PORT:-8501}` on `::` (dual-stack). Railway's internal network is IPv6-only,
  so a `0.0.0.0` bind builds and starts fine but fails every health check.
- **`railway.json` owns the start command.** Railway's precedence runs dashboard
  → `railway.json` → `Procfile` → Dockerfile `CMD`, so removing `startCommand`
  falls through to the `Procfile`, not the Dockerfile. All four are kept in sync
  and [tests/test_deployment.py](tests/test_deployment.py) asserts it.

---

## Document template

The structure every one-pager follows is specified in
[`templates/onepager_template.md`](templates/onepager_template.md): section
order, the field each element draws from, content rules, item limits, the type
scale and the compression priority order.

A blank rendered version — same renderer, same layout code, placeholders instead
of content — is produced without a deck or an API call:

```bash
python cli.py --template                    # → output/onepager_template.pdf
python cli.py --template --page-size A4 -o templates/blank_a4.pdf
```

Because the blank template is built from the production `InvestmentOnePager`
model and rendered by the production renderer, it cannot drift from real output;
a test asserts both produce the same sections in the same order.

## Output

Two files are written next to each other:

- `output/<name>_onepager.pdf` — **exactly one page**, always.
- `output/<name>_onepager.json` — the structured analysis plus the audit trail:
  extraction stats, token usage, render settings, provenance results
  (verified / dropped / flagged figures) and validation repairs.

---

## Architecture

```
pitchdeck_onepager/
├── config.py              Environment-driven configuration
├── errors.py              Typed, actionable exceptions
├── pipeline.py            Orchestration (ingest → analyse → render)
├── cli.py                 Argument parsing
├── models/
│   ├── deck.py            DeckDocument / DeckPage - normalised deck
│   └── investment_analysis.py   InvestmentOnePager - the analysis contract
├── ingestion/
│   ├── document_router.py Dispatch + extraction-quality gate
│   ├── pdf_parser.py      PyMuPDF text + table extraction
│   ├── pptx_parser.py     python-pptx, reading-order shape traversal
│   ├── ppt_converter.py   Legacy .ppt via headless LibreOffice
│   └── ocr.py             Optional image-only fallback
├── extraction/
│   ├── text_cleaner.py    Header/footer, wrap and duplicate repair
│   └── metric_extractor.py Number detection + meaning-preserving normalisation
├── analysis/
│   ├── prompts/investor_system_prompt.txt   Editable analyst prompt
│   ├── investor_prompt.py Prompt assembly (analysis + compression stages)
│   ├── llm.py             Provider abstraction, structured output
│   ├── schema_tools.py    Pydantic → provider-safe JSON schema
│   ├── analyzer.py        Stage 1 (analyse) and stage 2 (compress)
│   ├── validation.py      Caps, bounds, required content, repairs
│   └── provenance.py      Hallucination control for numbers
├── rendering/
│   ├── styles.py          Palette, type scale, density ladder
│   ├── layout.py          Measurable/drawable blocks
│   ├── onepager.py        Page-fit search + one-page guarantee
│   └── template.py        Blank structural template (placeholders only)
└── web/
    └── theme.py           TEN Capital identity for the Streamlit UI

templates/onepager_template.md   Document structure specification
```

### Key design decisions

**The LLM never writes the PDF.** It returns JSON against a schema derived from
the Pydantic model. Rendering is entirely deterministic.

**Numbers are checked against the deck before they are printed.** Every figure
the model reports is normalised (`$2.4 million` → `2.4m`, `71.0%` → `71%`) and
matched against numbers actually extracted from the deck. A metric that cannot
be matched is **dropped** from the page; a figure inside prose is **flagged** in
the JSON sidecar and the log rather than deleted mid-sentence. Ranges are never
collapsed to a midpoint.

**One page is a hard guarantee, not a hope.** The renderer measures the whole
document before drawing. It searches a density ladder (font and spacing scales)
first, so content is preserved in preference to cosmetics, and only then starts
trimming items — lowest investment priority first. Font sizes never fall below
the floors in `styles.py`. If the content still does not fit, an LLM compression
pass shortens the prose while preserving every fact, number and judgment; if
that also fails, the run errors rather than shipping a clipped page.

**Provider-neutral.** `analysis/llm.py` is the only module that knows about
Anthropic or OpenAI.

---

## Source traceability

Every material claim carries a slide reference internally. With
`SHOW_SOURCE_REFERENCES=true` (default) compact `[S8]` markers appear beside
sourced claims and metrics. The full `source_references` list — claim, slide
number and a verbatim quote — is always in the JSON sidecar.

---

## Privacy

Pitch decks are confidential. The application:

- parses everything **locally**;
- sends only extracted **deck text** to the configured LLM provider, in order to
  perform the analysis — this is the one point at which content leaves the
  machine, and it is unavoidable for an LLM-based analysis;
- never logs deck content at `INFO`, and never logs API keys;
- deletes temporary LibreOffice conversion artefacts after use;
- writes nothing outside `output/` and `temp/`.

If your decks may not leave your infrastructure, point the app at a
self-hosted, OpenAI-compatible endpoint:

```ini
LLM_PROVIDER=openai_compatible
OPENAI_BASE_URL=http://localhost:8000/v1
LLM_MODEL=<your local model>
```

---

## OCR

OCR is an opt-in fallback, not the default path. It runs only on pages that
yield almost no text.

```bash
pip install pytesseract pillow      # plus the Tesseract binary on PATH
ENABLE_OCR=true python cli.py input/scanned_deck.pdf
# or: python cli.py input/scanned_deck.pdf --ocr
```

Without OCR, an image-only deck fails with an explicit message rather than
producing an empty analysis.

## Legacy `.ppt`

Binary PowerPoint files are converted to `.pptx` with headless LibreOffice:

```bash
libreoffice --headless --convert-to pptx input.ppt
```

Install LibreOffice, or set `LIBREOFFICE_PATH` to the binary. Without it the run
fails with a clear message — it never silently returns a partial analysis.

---

## Testing

```bash
python -m pytest
```

72 tests, no API key and no proprietary deck required: fixtures are generated
synthetically (`tests/fixtures/make_fixtures.py`) and the LLM is stubbed.
Coverage includes PDF/PPTX extraction and ordering, number-normalisation
invariants, schema sanitisation, validation repairs, provenance dropping of
fabricated metrics, the one-page guarantee (including page-count verification
with `pypdf` and a text-bounds check with PyMuPDF), compression fallback, and
CLI error handling.

Regenerate fixtures with:

```bash
python tests/fixtures/make_fixtures.py
```

---

## Limitations

- **Charts and images are not interpreted.** Only text, tables and labels are
  extracted. A metric that exists solely inside a chart image will not appear
  unless OCR recovers it.
- **The conviction score is a judgment, not a measurement.** It reflects the
  strength of evidence in one deck and should not be compared across companies
  as if it were calibrated.
- **Analysis quality depends on the deck.** A deck with no operating data
  produces an analysis dominated by assumptions — correctly so.
- **Derived figures are flagged, not verified.** If the model computes
  "34 of 37 customers", the `34` will be flagged as untraceable even though the
  inference is sound. Check the `flagged_prose_figures` list in the JSON.
- **Very long analyses may lose the lowest-priority sections** (diligence
  questions, then the opposing view) to keep the page count at one.
- **Legacy `.ppt` requires LibreOffice**; OCR requires Tesseract.
- **`.docx` is not accepted.** The ingestion layer handles `.pdf`, `.pptx` and
  `.ppt` only; the uploader advertises exactly those, enforced by a test.
- **Nothing is emailed or forwarded.** Generated one-pagers are returned to the
  browser and deleted from the server. There is no delivery pipeline, and a test
  fails the build if UI copy starts claiming otherwise.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ANTHROPIC_API_KEY is not set` | Set it in the environment or `.env` |
| `No model configured for provider 'openai'` | Set `LLM_MODEL` or pass `--model` |
| `Only N characters were extracted` | Image-only deck — run with `--ocr` |
| `Cannot convert '...': LibreOffice was not found` | Install LibreOffice or set `LIBREOFFICE_PATH` |
| `'...' is password protected` | Remove the PDF password and retry |
| `The response hit the output token limit` | Raise `LLM_MAX_TOKENS` |
| `Content overflows a single page` | Rerun; the compression pass usually resolves it. Persisting means an unusually verbose analysis |
| Metrics missing from the PDF | They could not be traced to deck text — see `provenance.dropped_metrics` in the JSON |
