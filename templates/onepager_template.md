# One-Page Investment Analysis — Document Template

The canonical structure of every one-pager the application produces. It defines
the sections, their order, the fields each section draws from, the content rules
that govern them, and the typography used to render them.

Nothing in this file is company-specific. Square brackets mark placeholders that
are filled per deck; a field with no supporting evidence in the source deck is
omitted rather than invented.

- **Source of truth for content:** `InvestmentOnePager`
  (`pitchdeck_onepager/models/investment_analysis.py`)
- **Source of truth for layout:** `pitchdeck_onepager/rendering/onepager.py`
- **Blank rendered template:** `python cli.py --template` → `output/onepager_template.pdf`

---

## 1. Page setup

| Property | Value |
|---|---|
| Page size | US Letter portrait (8.5 × 11 in), configurable to A4 |
| Page count | **Exactly 1**, always — verified after rendering |
| Margins | 33 pt on all sides; footer reserve 17 pt |
| Column grid | Two columns, 13 pt gutter, equal width |
| Typeface | Helvetica / Helvetica-Bold (single family, no decoration) |
| Colour | Ink, muted grey, one navy accent, one status colour on the badge |

### Type scale

| Element | Size at scale 1.0 | Minimum |
|---|---|---|
| Company name | 19 pt bold | 16 pt |
| Conviction score | 17 pt bold | — |
| Section header | 8.8 pt bold, letter-spaced caps | 8.0 pt |
| Body / bullets | 8.4 pt | 7.5 pt |
| Table cells, chips | 7.6 pt | 6.5 pt |
| Source markers, footer | 7.2 pt | 6.5 pt |
| Metric value | 11.5 pt bold | 7.0 pt |

Font and spacing scale down together to fit one page; sizes never fall below the
minimum column. Compression removes content only after the type ladder is
exhausted (§6).

---

## 2. Layout skeleton

```
┌──────────────────────────────────────────────────┬────────────────┐
│ [COMPANY NAME]                                   │  CONVICTION    │
│ [Company description — 20-30 words]              │    [X.X] / 10  │
│ SECTOR [..] | STAGE [..] | RAISE [..] | ...      │    [BAND]      │
└──────────────────────────────────────────────────┴────────────────┘
════════════════════════════════════════════════════════════════════
┌────────────────────────────────────────────────────────────────────┐
│ CORE INVESTMENT BELIEF                                             │
│ [One sentence: the economic bet and its critical conditions]       │
└────────────────────────────────────────────────────────────────────┘
────────────────────────────────────────────────────────────────────
 [VALUE]      │ [VALUE]      │ [VALUE]      │ [VALUE]     (up to 6)
 [LABEL] [Sn] │ [LABEL] [Sn] │ [LABEL] [Sn] │ [LABEL] [Sn]
────────────────────────────────────────────────────────────────────
EVIDENCE SUPPORTING THESIS      │ WHAT MUST BE TRUE
• [Evidence] — [significance]   │ • [Assumption] — [why it matters]
  ([type], [strength]) [Sn]     │   [status] — CRITICAL DEPENDENCY
• …  (3-5 items)                │ • …  (3-5 items)

WEAKEST LINK
▌[The gap between narrative and demonstrated fact; what is NOT shown]

RISK MAP
RISK              | PROB.  | IMPACT | EARLY WARNING SIGNAL
[Failure mechanism] | [..]  | [..]   | [Observable signal]
…  (3-5 rows)

CONVICTION STRENGTHENS IF       │ CONVICTION WEAKENS IF
• [Observable development]      │ • [Observable development]
…  (2-4 items)                  │ …  (2-4 items)

BEST OPPOSING VIEW              │ THESIS INVALID IF
[Steel-manned bear case]        │ • [Thesis-breaking condition]  (1-2)

NEXT PROOF POINT
▌[Smallest highest-information test: what, measured how, which result matters]

KEY DILIGENCE QUESTIONS
1. [Question targeting an unresolved evidence gap]
…  (3-5 items)
────────────────────────────────────────────────────────────────────
Source: [file] ([n] slides)      Generated [date]  [model]  [disclaimer]
```

---

## 3. Section reference

Sections render in this order. "Field" is the key in `InvestmentOnePager`.

### 3.1 Header

| Element | Field | Rule |
|---|---|---|
| Company name | `company_name` | Exactly as written in the deck |
| Description | `company_description` | 20–30 words max; omitted if absent |
| Metadata chips | `sector`, `stage`, `raise_amount`, `valuation`, `geography` | Each chip omitted when the deck does not state it — never filled with a placeholder |
| Conviction badge | `conviction_score`, `conviction_label` | Score to one decimal; band derived from the score, never asserted independently |

Conviction bands: `0.0–3.9` LOW · `4.0–6.9` MODERATE · `7.0–10.0` HIGH. The score
measures **strength of evidence**, not attractiveness of the story.

### 3.2 Core investment belief

| Element | Field | Rule |
|---|---|---|
| Statement | `core_investment_belief` | One sentence, form: *"[Company] has a credible opportunity to [outcome] if it can [critical conditions]."* Economic or strategic bet, not the product |
| Qualifier | `conviction_rationale` | One clause on what caps the score; appended to the statement |

### 3.3 Key metrics

| Element | Field | Rule |
|---|---|---|
| Value | `traction_metrics[].value` | Verbatim from the deck: currency symbols, `%`, K/M/B suffixes and ranges preserved. Ranges are never averaged |
| Label | `traction_metrics[].label` | Short metric name |
| Marker | `traction_metrics[].source_page` | Rendered as `[Sn]` when source display is on |

Up to 6 metrics, chosen for the company's business model. The strip is omitted
entirely when the deck contains no usable metrics — empty cells are never padded
to fill the row. Any value that cannot be traced to deck text is dropped before
rendering (§5).

### 3.4 Evidence supporting thesis · What must be true (two columns)

| Element | Field | Rule |
|---|---|---|
| Evidence | `strongest_evidence[].evidence` | What the deck **demonstrates**. Forecasts, targets and unsourced superlatives are not evidence |
| Significance | `strongest_evidence[].significance` | One clause on why it matters |
| Classification | `strongest_evidence[].evidence_type` | Company Data · Market Data · Customer Evidence · Case / Example · Management Experience · Logical Inference · Founder Claim · Third-Party Evidence |
| Strength | `strongest_evidence[].strength` | Strong · Moderate · Weak |
| Assumption | `key_assumptions[].assumption` | Specific and testable |
| Consequence | `key_assumptions[].why_it_matters` | What breaks if it is false |
| Status | `key_assumptions[].status` | Supported · Partially supported · Unproven |
| Critical dependency | `key_assumptions[].is_critical_dependency` | **Exactly one** item; the assumption whose failure damages several others |

3–5 items each.

### 3.5 Weakest link

| Element | Field | Rule |
|---|---|---|
| Statement | `weak_link` | The largest gap between founder narrative and demonstrated fact. States explicitly what has **not** been shown. 1–2 sentences |

Rendered full width with a left accent bar in the alert colour.

### 3.6 Risk map

| Column | Field | Rule |
|---|---|---|
| Risk | `major_risks[].risk` | The failure **mechanism**, specific to this company — never a category such as "competition increases" |
| Prob. | `major_risks[].probability` | High · Medium-High · Medium · Low-Medium · Low |
| Impact | `major_risks[].impact` | Very High · High · Medium · Low |
| Early warning signal | `major_risks[].early_warning` | Something an investor could actually observe |

3–5 rows. Column widths 40 / 11 / 10 / 39 %.

### 3.7 Conviction triggers (two columns)

| Element | Field | Rule |
|---|---|---|
| Strengthens if | `conviction_strengthens_if[]` | 2–4 observable developments |
| Weakens if | `conviction_weakens_if[]` | 2–4 observable developments |

Numeric thresholds only where the deck or the company's stated economics justify
a specific number; otherwise qualitative.

### 3.8 Best opposing view · Thesis invalid if (two columns)

| Element | Field | Rule |
|---|---|---|
| Opposing view | `strongest_counterargument` | The strongest credible skeptical reading. Steel-manned, never a straw man. 1–2 sentences |
| Thesis breakers | `thesis_invalid_if[]` | 1–2 conditions, materially stronger than ordinary risks |

### 3.9 Next proof point

| Element | Field | Rule |
|---|---|---|
| Test | `highest_value_test` | The smallest, highest-information experiment or milestone that resolves the largest uncertainty. States what to test, what to measure, and which result matters |

Rendered full width with a left accent bar.

### 3.10 Key diligence questions

| Element | Field | Rule |
|---|---|---|
| Questions | `key_questions[]` | 3–5, numbered. Each targets a specific unresolved evidence gap in this deck. Generic questions are not permitted |

### 3.11 Footer

`Source: [filename] ([n] slides)` — left · `Generated [date]  [model]  LLM-generated
analysis - verify before any investment decision` — right.

---

## 4. Fields carried in the JSON sidecar only

Not rendered on the page, but always present in `<name>_onepager.json`:

| Field | Purpose |
|---|---|
| `critical_dependency` | Restates the critical assumption as standalone text |
| `missing_information[]` | Up to 4 materially important things the deck does not provide |
| `source_references[]` | `label` (`Sn`), `page_number`, `claim`, verbatim `quote` for every material claim |

The sidecar additionally records the run's audit trail: extraction statistics and
warnings, provider/model and token usage, render settings (font scale, spacing
scale, content level, page count), provenance results (verified / dropped /
flagged figures) and validation repairs.

---

## 5. Content rules

These apply to every document produced from this template.

1. **Evidence is separated from assumption.** A founder claim is never presented
   as an independently established fact.
2. **Only deck content supplies company facts.** No metric, market statistic,
   competitor, customer, benchmark or financial figure is introduced from
   outside the deck.
3. **Projections are assumptions** unless operating evidence supports them.
4. **Absent information is stated, not filled.** Optional metadata is omitted;
   material gaps are listed in `missing_information`.
5. **Figures are reproduced verbatim** — currency symbols, percentages,
   magnitude suffixes and ranges preserved. `[low]–[high]` is never collapsed to
   a midpoint; units are never converted.
6. **Every printed figure is provenance-checked.** A metric that cannot be
   matched to deck text is dropped from the page; a figure inside prose is
   flagged in the sidecar rather than deleted mid-sentence.
7. **Risks are mechanisms with observable early-warning signals**, not
   categories.
8. **Product-market fit is distinguished from scalable economics**; defensibility
   claims (patents, proprietary data, network effects, partnerships, first-mover
   advantage) are assessed only on evidence contained in the deck.
9. **The conviction score reflects evidence strength**, expressed to one decimal
   place, with no implied precision beyond that.

---

## 6. Priority order under compression

When content exceeds one page, the renderer first reduces font and spacing
scales, then trims items in this order — lowest investment priority first:

1. Diligence questions — count reduced, then the section dropped
2. Best opposing view — dropped last
3. Conviction triggers — reduced from 4 items to 2
4. Evidence, assumptions and risks — reduced from 5 items to 3
5. Metrics — reduced from 6 to 4

Never removed at any compression level: the core investment belief, the
conviction badge, the metric strip (when metrics exist), the critical dependency,
the weakest link, the risk map and the next proof point.

If the content still does not fit, a compression pass shortens prose while
preserving every fact, number, qualifier and judgment, and list lengths are held
constant. If that also fails, the run raises an error rather than emitting a
clipped or unreadably small page.
