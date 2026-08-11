"""TEN Capital Network visual identity for the Streamlit app.

Ports the approved HTML design: dark navy surface, tri-colour brand accent
(coral / amber / teal echoing the three figures in the mark), Sora display type
over Inter body copy, and a single focused card.

Streamlit owns the DOM, so the design is applied three ways:

1. Palette and base font through ``.streamlit/config.toml``.
2. Structural chrome (brand lockup, hero, footer) as injected markup.
3. Widget skinning through CSS scoped to ``st.container(key=...)`` wrappers,
   which Streamlit exposes as stable ``.st-key-<key>`` class names.

Selectors that depend on Streamlit internals are marked below. They degrade to
the default widget appearance rather than breaking if Streamlit changes them.
"""

from __future__ import annotations

import streamlit as st

#: Design tokens, kept in one place so the palette can be retuned centrally.
BRAND = {
    "navy_950": "#0B1526",
    "navy_900": "#101E33",
    "navy_800": "#16283F",
    "navy_700": "#1E354F",
    "coral": "#EE5A4E",
    "coral_soft": "#F0776C",
    "amber": "#F3A22A",
    "teal": "#35BEBB",
    "ink_100": "#F3F6FA",
    "ink_300": "#C4D0E0",
    "ink_500": "#7E90A8",
    "ink_600": "#5C6E86",
}

#: The three-figure mark, inlined so the app has no external image dependency.
BRAND_MARK_SVG = """
<svg class="tc-mark" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M50 6 C64 6 74 16 74 16" stroke="#F3A22A" stroke-width="11" stroke-linecap="round" fill="none"/>
  <path d="M76 66 C76 82 63 92 63 92" stroke="#35BEBB" stroke-width="11" stroke-linecap="round" fill="none"/>
  <path d="M24 66 C24 82 37 92 37 92" stroke="#EE5A4E" stroke-width="11" stroke-linecap="round"
        fill="none" transform="rotate(180 50 79)"/>
  <circle cx="50" cy="20" r="11" fill="#F3A22A"/>
  <circle cx="78" cy="68" r="11" fill="#35BEBB"/>
  <circle cx="22" cy="68" r="11" fill="#EE5A4E"/>
</svg>
"""

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root{
  --navy-950:#0B1526; --navy-900:#101E33; --navy-800:#16283F; --navy-700:#1E354F;
  --coral:#EE5A4E; --coral-soft:#F0776C; --amber:#F3A22A; --teal:#35BEBB;
  --ink-100:#F3F6FA; --ink-300:#C4D0E0; --ink-500:#7E90A8; --ink-600:#5C6E86;
}

/* ---- Surface ---------------------------------------------------------- */

.stApp{
  background: var(--navy-950);
  font-family:'Inter', sans-serif;
}

/* Ambient tri-colour glow echoing the three figures in the mark. */
.stApp::before{
  content:"";
  position:fixed; inset:0;
  background:
    radial-gradient(480px 380px at 14% 8%, rgba(238,90,78,0.16), transparent 60%),
    radial-gradient(480px 380px at 86% 6%, rgba(243,162,42,0.13), transparent 60%),
    radial-gradient(560px 420px at 50% 100%, rgba(53,190,187,0.14), transparent 60%);
  pointer-events:none; z-index:0;
}

.stMainBlockContainer, .block-container{
  position:relative; z-index:1;
  max-width: 680px;
  padding-top: 3rem;
  padding-bottom: 3rem;
}

/* ---- Brand lockup ------------------------------------------------------ */

.tc-brand{ display:flex; align-items:center; gap:12px; margin:0 0 26px; padding-left:4px; }
.tc-mark{ width:34px; height:34px; flex-shrink:0; }
.tc-word{
  font-family:'Sora', sans-serif; font-weight:800; font-size:15px;
  letter-spacing:.04em; line-height:1.15; color:var(--ink-100); text-transform:uppercase;
}
.tc-word span{
  display:block; font-weight:600; font-size:10px; letter-spacing:.22em;
  color:var(--ink-500); margin-top:2px;
}

/* ---- Card -------------------------------------------------------------- */

.st-key-tc_card{
  background: linear-gradient(180deg, var(--navy-900) 0%, var(--navy-800) 100%);
  border:1px solid var(--navy-700);
  border-radius:20px;
  padding:40px 40px 30px;
  box-shadow: 0 30px 60px -20px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.03);
  position:relative; overflow:hidden;
}
.st-key-tc_card::after{
  content:""; position:absolute; top:0; left:40px; right:40px; height:2px;
  background: linear-gradient(90deg, var(--coral), var(--amber), var(--teal));
  border-radius:2px;
}

/* ---- Hero -------------------------------------------------------------- */

.tc-eyebrow{
  display:flex; align-items:center; gap:8px;
  font-family:'JetBrains Mono', monospace; font-size:11px;
  letter-spacing:.14em; text-transform:uppercase; color:var(--teal); margin-bottom:14px;
}
.tc-eyebrow::before{
  content:""; width:6px; height:6px; border-radius:50%;
  background:var(--teal); box-shadow:0 0 0 3px rgba(53,190,187,.18);
}
.tc-h1{
  font-family:'Sora', sans-serif; font-size:28px; font-weight:700; line-height:1.25;
  margin:0 0 12px; letter-spacing:-.01em; color:var(--ink-100);
}
.tc-h1 .arrow{ color:var(--ink-500); font-weight:400; margin:0 4px; }
.tc-h1 .to{
  background: linear-gradient(90deg, var(--coral-soft), var(--amber));
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.tc-lede{
  color:var(--ink-300); font-size:15px; line-height:1.6; margin:0 0 26px; max-width:46ch;
}

/* ---- Dropzone (skins st.file_uploader) --------------------------------- */
/* data-testid selectors are Streamlit internals: if they change, the uploader
   simply falls back to its default appearance. */

/* The wrapper container is the dashed dropzone; Streamlit's own dropzone inside
   it is stripped bare. This keeps the icon and title *inside* the box without
   depending on Streamlit's internal layout. */
.st-key-tc_drop{
  border:1.5px dashed var(--navy-700);
  border-radius:14px;
  background: rgba(255,255,255,.015);
  padding:26px 24px 18px;
  transition: border-color .18s ease, background .18s ease;
}
.st-key-tc_drop:hover{
  border-color: var(--teal);
  background: rgba(53,190,187,.05);
}

.tc-drop-head{ text-align:center; }
.tc-drop-icon{
  width:38px; height:38px; margin:0 auto 12px;
  border-radius:10px;
  background: linear-gradient(135deg, rgba(238,90,78,.16), rgba(243,162,42,.16));
  border:1px solid var(--navy-700);
  display:flex; align-items:center; justify-content:center;
}
.tc-drop-icon svg{ width:18px; height:18px; }
.tc-drop-title{ font-size:15px; font-weight:600; color:var(--ink-100); }

.st-key-tc_drop [data-testid="stFileUploaderDropzone"]{
  border:none !important;
  background: transparent !important;
  padding:6px 0 0 !important;
  justify-content:center !important;
  gap:14px;
}
/* Stop the instruction text from growing and pushing the button off-centre. */
.st-key-tc_drop [data-testid="stFileUploaderDropzoneInstructions"]{
  flex:0 1 auto !important;
}
[data-testid="stFileUploaderDropzone"]{
  border:1.5px dashed var(--navy-700);
  border-radius:14px;
  background: rgba(255,255,255,.015);
  transition: border-color .18s ease, background .18s ease;
}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] div{
  color: var(--ink-300) !important;
  font-family:'Inter', sans-serif;
}
[data-testid="stFileUploaderDropzoneInstructions"] small{
  color: var(--ink-500) !important;
  font-family:'JetBrains Mono', monospace; font-size:11.5px;
}
[data-testid="stFileUploaderDropzone"] svg{ fill: var(--ink-500); }
/* "Browse files" secondary button inside the dropzone */
[data-testid="stFileUploaderDropzone"] button{
  background: transparent !important;
  border:1px solid var(--navy-700) !important;
  color: var(--ink-100) !important;
  border-radius:9px !important;
}
[data-testid="stFileUploaderDropzone"] button:hover{
  border-color: var(--teal) !important; color: var(--teal) !important;
}
[data-testid="stFileUploaderFile"]{ color: var(--ink-300); }

/* ---- Primary call to action ------------------------------------------- */

.st-key-tc_generate button{
  width:100%;
  border:none !important;
  border-radius:12px !important;
  padding:15px 20px !important;
  background: linear-gradient(90deg, var(--coral) 0%, var(--coral-soft) 45%, var(--amber) 100%) !important;
  color:#17130E !important;
  font-family:'Sora', sans-serif !important; font-weight:700 !important; font-size:15px !important;
  letter-spacing:.01em;
  box-shadow: 0 10px 24px -10px rgba(238,90,78,.45);
  transition: filter .15s ease, transform .15s ease;
}
.st-key-tc_generate button:hover{ filter:brightness(1.06); transform:translateY(-1px); }
.st-key-tc_generate button:active{ transform:translateY(0); }
.st-key-tc_generate button p{ color:#17130E !important; font-weight:700 !important; }
/* Flat and quiet when there is nothing to generate - a greyed-out gradient
   reads as broken rather than disabled. */
.st-key-tc_generate button:disabled{
  background: rgba(255,255,255,.03) !important;
  border:1px solid var(--navy-700) !important;
  box-shadow:none !important;
  cursor: not-allowed;
}
.st-key-tc_generate button:disabled,
.st-key-tc_generate button:disabled p{ color: var(--ink-600) !important; }
.st-key-tc_generate button:disabled:hover{ filter:none; transform:none; }

/* Secondary buttons (downloads) stay quiet against the gradient CTA. */
.stDownloadButton button{
  border:1px solid var(--navy-700) !important;
  background: rgba(255,255,255,.02) !important;
  color: var(--ink-100) !important;
  border-radius:11px !important;
  font-weight:600 !important;
}
.stDownloadButton button:hover{ border-color: var(--teal) !important; color: var(--teal) !important; }

/* ---- Disclosure + footer ---------------------------------------------- */

.tc-disclosure{
  margin-top:20px; padding-top:16px; border-top:1px solid var(--navy-700);
  font-size:12px; line-height:1.6; color:var(--ink-500);
}
.tc-disclosure code{
  font-family:'JetBrains Mono', monospace; background:var(--navy-950);
  border:1px solid var(--navy-700); color:var(--ink-300);
  padding:2px 6px; border-radius:5px; font-size:11.5px;
}
.tc-footer{
  text-align:center; margin-top:20px;
  font-family:'JetBrains Mono', monospace; font-size:11px; letter-spacing:.08em;
  color:var(--ink-600); text-transform:uppercase;
}

/* ---- Results ----------------------------------------------------------- */

.tc-verdict{
  display:flex; align-items:stretch; gap:14px; margin:4px 0 18px;
}
.tc-verdict-score{
  flex:0 0 118px; text-align:center; padding:12px 8px;
  border:1px solid var(--navy-700); border-radius:12px; background:rgba(255,255,255,.02);
}
.tc-verdict-score .n{
  font-family:'Sora', sans-serif; font-weight:800; font-size:30px; line-height:1;
}
.tc-verdict-score .d{ color:var(--ink-500); font-size:12px; }
.tc-verdict-score .band{
  font-family:'JetBrains Mono', monospace; font-size:10.5px;
  letter-spacing:.14em; margin-top:6px;
}
.tc-verdict-body{ flex:1 1 auto; }
.tc-verdict-body .co{
  font-family:'Sora', sans-serif; font-weight:700; font-size:17px; color:var(--ink-100);
}
.tc-verdict-body .belief{
  color:var(--ink-300); font-size:13.5px; line-height:1.55; margin-top:5px;
}

/* ---- Widget chrome ----------------------------------------------------- */

[data-testid="stSidebar"]{
  background: var(--navy-900);
  border-right:1px solid var(--navy-700);
}
[data-testid="stSidebar"] h2{ font-family:'Sora', sans-serif; font-size:15px; }
.stProgress > div > div > div > div{
  background: linear-gradient(90deg, var(--coral), var(--amber)) !important;
}
[data-testid="stExpander"] details{
  background: rgba(255,255,255,.02); border:1px solid var(--navy-700); border-radius:11px;
}
[data-testid="stAlert"]{ border-radius:11px; }
h1, h2, h3{ font-family:'Sora', sans-serif; }
#MainMenu, [data-testid="stDecoration"]{ visibility:hidden; }
</style>
"""


def inject_theme() -> None:
    """Apply the brand stylesheet. Safe to call once per script run."""
    st.markdown(_CSS, unsafe_allow_html=True)


def render_brand() -> None:
    """Brand lockup above the card."""
    st.markdown(
        f'<div class="tc-brand">{BRAND_MARK_SVG}'
        '<div class="tc-word">Ten Capital<span>Network</span></div></div>',
        unsafe_allow_html=True,
    )


def render_hero(eyebrow: str, lede: str) -> None:
    """Eyebrow, headline and supporting line inside the card."""
    st.markdown(
        f'<div class="tc-eyebrow">{eyebrow}</div>'
        '<div class="tc-h1">Pitch Deck<span class="arrow">&rarr;</span>'
        '<span class="to">Investor One&#8209;Pager</span></div>'
        f'<p class="tc-lede">{lede}</p>',
        unsafe_allow_html=True,
    )


def render_dropzone_head(title: str) -> None:
    """Icon and title shown above the upload control.

    Rendered as our own markup rather than by restyling Streamlit's internal
    instruction text, so a Streamlit upgrade cannot silently blank it.
    """
    st.markdown(
        f"""
        <div class="tc-drop-head">
          <div class="tc-drop-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="#F3F6FA" stroke-width="1.6"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 3v4a1 1 0 0 0 1 1h4"/>
              <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2Z"/>
            </svg>
          </div>
          <div class="tc-drop-title">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_disclosure(html: str) -> None:
    st.markdown(f'<div class="tc-disclosure">{html}</div>', unsafe_allow_html=True)


def render_footer(text: str = "Powered by TEN Capital Network") -> None:
    st.markdown(f'<div class="tc-footer">{text}</div>', unsafe_allow_html=True)


def render_verdict(company: str, score: float, band: str, belief: str, color: str) -> None:
    """Headline result block: conviction score beside the core investment belief."""
    st.markdown(
        f"""
        <div class="tc-verdict">
          <div class="tc-verdict-score">
            <div class="n" style="color:{color}">{score:.1f}</div>
            <div class="d">out of 10</div>
            <div class="band" style="color:{color}">{band}</div>
          </div>
          <div class="tc-verdict-body">
            <div class="co">{company}</div>
            <div class="belief">{belief}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def band_color(label: str) -> str:
    """Brand colour for a conviction band."""
    return {
        "HIGH": BRAND["teal"],
        "MODERATE": BRAND["amber"],
        "LOW": BRAND["coral"],
    }.get(label.upper(), BRAND["ink_300"])
