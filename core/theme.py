"""Bank of Baroda inspired palette (orange and deep blue) and small HTML helpers."""
import html

import streamlit as st

ORANGE = "#F26B21"
ORANGE_DK = "#D4540F"
NAVY = "#0B2E5C"
NAVY_DK = "#071E3D"
CREAM = "#FFF4EC"
MIST = "#EEF2F8"
INK = "#14213D"
MUTED = "#5B6B82"
LINE = "#E3E8F0"

POS = "#2E9E6B"
NEG = "#D64545"
NEU = "#9AA5B1"
SENT_COLORS = {"Positive": POS, "Neutral": NEU, "Negative": NEG}


def score_color(score: float, neutral_band: float = 5) -> str:
    if score >= neutral_band:
        return POS
    if score <= -neutral_band:
        return NEG
    return NEU


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'IBM Plex Sans', system-ui, sans-serif; color: {INK}; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1500px; }}
header[data-testid="stHeader"] {{ background: transparent; }}

.hero {{ background: {NAVY}; border-bottom: 5px solid {ORANGE}; border-radius: 6px; padding: 22px 28px;
        display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 18px; }}
.hero h1 {{ color: #fff; font-size: 1.65rem; font-weight: 700; margin: 0; letter-spacing: .1px; }}
.hero p {{ color: #C9D6EA; margin: 4px 0 0; font-size: .95rem; }}
.hero .co {{ text-align: right; color: #fff; }}
.hero .co b {{ font-size: 1.15rem; color: {ORANGE}; display: block; }}
.hero .co span {{ color: #C9D6EA; font-size: .85rem; }}

.kpi {{ background: #fff; border: 1px solid {LINE}; border-left: 5px solid {NAVY}; border-radius: 6px;
       padding: 12px 16px; height: 100%; }}
.kpi .l {{ color: {MUTED}; font-size: .82rem; }}
.kpi .v {{ font-size: 1.75rem; font-weight: 700; color: {NAVY}; line-height: 1.2; }}
.kpi .s {{ color: {MUTED}; font-size: .8rem; }}
.kpi.o {{ border-left-color: {ORANGE}; }}
.kpi.g {{ border-left-color: {POS}; }}
.kpi.r {{ border-left-color: {NEG}; }}

.panel {{ background: {CREAM}; border: 1px solid #F8D9C4; border-radius: 6px; padding: 14px 18px; }}
.card {{ background: #fff; border: 1px solid {LINE}; border-radius: 6px; padding: 14px 18px; }}
.card h4, .panel h4 {{ margin: 0 0 6px; color: {NAVY}; font-size: 1rem; }}
.card ul, .panel ul {{ margin: 4px 0 0 18px; padding: 0; }}
.card li, .panel li {{ margin-bottom: 3px; font-size: .92rem; }}

.badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; color: #fff; font-size: .8rem; font-weight: 600; }}
.pill {{ display: inline-block; padding: 1px 8px; border-radius: 10px; background: {MIST}; color: {NAVY};
        font-size: .78rem; margin: 2px 4px 2px 0; }}
.hl {{ border-bottom: 1px solid {LINE}; padding: 8px 0; font-size: .92rem; }}
.hl small {{ color: {MUTED}; }}
.sectionhead {{ color: {NAVY}; font-weight: 700; font-size: 1.1rem; border-left: 5px solid {ORANGE};
               padding-left: 10px; margin: 18px 0 10px; }}

/* Streamlit widgets */
div[data-testid="stSidebar"] {{ background: {MIST}; border-right: 1px solid {LINE}; }}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
    background: {ORANGE}; border: 1px solid {ORANGE}; color: #fff; font-weight: 600; }}
.stButton > button[kind="primary"]:hover {{ background: {ORANGE_DK}; border-color: {ORANGE_DK}; color: #fff; }}
.stButton > button[kind="secondary"] {{ border: 1px solid {NAVY}; color: {NAVY}; }}
.stButton > button[kind="secondary"]:hover {{ border-color: {ORANGE}; color: {ORANGE}; }}
button[data-baseweb="tab"] {{ font-weight: 600; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: {ORANGE}; }}
div[data-baseweb="tab-highlight"] {{ background-color: {ORANGE}; }}
span[data-baseweb="tag"] {{ background-color: {NAVY}; color: #fff; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def kpi(label: str, value, sub: str = "", tone: str = "") -> str:
    return (f'<div class="kpi {tone}"><div class="l">{esc(label)}</div>'
            f'<div class="v">{esc(value)}</div><div class="s">{esc(sub)}</div></div>')


def badge(text: str, color: str) -> str:
    return f'<span class="badge" style="background:{color}">{esc(text)}</span>'


def section(title: str) -> None:
    st.markdown(f'<div class="sectionhead">{esc(title)}</div>', unsafe_allow_html=True)


def bullets(items) -> str:
    if not items:
        return "<ul><li>None flagged</li></ul>"
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"
