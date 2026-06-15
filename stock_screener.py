"""
SwingIt V12.5 — My Portfolio Command Center + Thesis Monitor
Finds 1–4 week swing-trade watchlist candidates by ranking stocks on:
- Current RSI opportunity
- Historical RSI <30 rebound behavior
- Expected bounce size
- Speed to rebound
- Sample confidence

Not financial advice. Use as a watchlist engine, not an entry/exit system.
"""

from io import StringIO
import datetime
import html
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import ta
import yfinance as yf


# ──────────────────────────────────────────────────────────────────────────────
# App setup + softer theme
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SwingIt V12",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    :root {
        --bg:#f4f6f8;
        --surface:#ffffff;
        --surface-2:#eef2f6;
        --border:#d8dee6;
        --text:#1f2937;
        --muted:#64748b;
        --accent:#2563eb;
        --green:#16803c;
        --red:#b42318;
        --amber:#b7791f;
    }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background:var(--bg)!important;
        color:var(--text)!important;
    }
    [data-testid="stSidebar"] {
        background:var(--surface)!important;
        border-right:1px solid var(--border);
    }

    /* Compact sidebar controls */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin-bottom:.25rem; }
    [data-testid="stSidebar"] hr { margin:.65rem 0; }
    [data-testid="stSidebar"] label { font-size:.78rem!important; }
    [data-testid="stSidebar"] .stSelectbox,
    [data-testid="stSidebar"] .stTextArea,
    [data-testid="stSidebar"] .stSlider,
    [data-testid="stSidebar"] .stToggle { margin-bottom:.35rem; }
    h1,h2,h3,h4,p,span,label,div { color:var(--text); }
    .small-muted { color:var(--muted); font-size:0.9rem; }
    [data-testid="stMetric"] {
        background:var(--surface);
        border:1px solid var(--border);
        border-radius:14px;
        padding:14px 16px;
        box-shadow:0 1px 2px rgba(15,23,42,.04);
    }
    [data-testid="stMetricLabel"] {
        color:var(--muted)!important;
        font-size:.75rem;
        text-transform:uppercase;
        letter-spacing:.03em;
    }
    [data-testid="stMetricValue"] { color:var(--text)!important; font-weight:800; }
    .quick-filter-card {
        display:block;
        text-decoration:none!important;
        background:var(--surface);
        border:1px solid var(--border);
        border-radius:14px;
        padding:14px 16px;
        box-shadow:0 1px 2px rgba(15,23,42,.04);
        min-height:86px;
        transition:all .15s ease;
    }
    .quick-filter-card:hover {
        transform:translateY(-1px);
        border-color:#b7c4d6;
        box-shadow:0 6px 18px rgba(15,23,42,.08);
    }
    .quick-filter-label {
        color:var(--muted);
        font-size:.75rem;
        text-transform:uppercase;
        letter-spacing:.03em;
        font-weight:800;
        margin-bottom:.35rem;
    }
    .quick-filter-value {
        color:var(--text);
        font-size:2rem;
        line-height:1;
        font-weight:900;
    }
    [data-testid="stDataFrame"] {
        border:1px solid var(--border)!important;
        border-radius:14px;
        overflow:hidden;
        background:var(--surface)!important;
    }
    .stButton>button {
        background:var(--accent)!important;
        color:white!important;
        border:none!important;
        border-radius:10px!important;
        font-weight:700!important;
        padding:.55rem 1rem!important;
    }
    .hot-card {
        background:var(--surface);
        border:1px solid var(--border);
        border-radius:16px;
        padding:12px 13px 10px 13px;
        box-shadow:0 5px 14px rgba(15,23,42,.05);
        min-height:214px;
        margin-bottom:10px;
        overflow:visible;
        position:relative;
    }
    .hot-title { font-size:.92rem; font-weight:900; margin-bottom:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .company-name { color:var(--muted); font-weight:700; font-size:.78rem; margin-left:4px; }
    .analyst-verdict-box { background:linear-gradient(135deg,#f8fafc 0%,#eef4ff 100%); border:1px solid var(--border); border-radius:12px; padding:7px 8px; margin:5px 0 7px 0; }
    .verdict-line { display:flex; align-items:center; gap:6px; font-size:.74rem; font-weight:950; letter-spacing:.01em; text-transform:uppercase; color:var(--text); line-height:1.15; }
    .verdict-confidence { margin-left:auto; font-size:.58rem; font-weight:900; color:var(--muted); background:#fff; border:1px solid var(--border); border-radius:999px; padding:2px 6px; text-transform:none; white-space:nowrap; }
    .verdict-summary { margin-top:4px; font-size:.66rem; color:#475569; line-height:1.25; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
    .score-row { display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; margin:6px 0 8px 0; }
    .score-tile { background:var(--surface-2); border:1px solid var(--border); border-radius:10px; padding:6px 5px; }
    .score-num { font-size:1.12rem; font-weight:950; color:var(--accent); line-height:1.05; }
    .score-label { font-size:.58rem; color:var(--muted); text-transform:uppercase; letter-spacing:.02em; margin-top:2px; }
    .hot-meta { color:var(--muted); font-size:.69rem; margin-top:6px; line-height:1.42; }
    .terminal-hero {
        background:linear-gradient(135deg,#ffffff 0%,#eef4ff 100%);
        border:1px solid var(--border);
        border-radius:22px;
        padding:20px 22px 18px 22px;
        box-shadow:0 12px 28px rgba(15,23,42,.07);
        margin-bottom:16px;
    }
    .terminal-title {font-size:1.75rem;font-weight:950;letter-spacing:-.04em;margin-bottom:2px;white-space:nowrap;}
    .terminal-subtitle {color:var(--muted);font-size:.92rem;margin-bottom:12px;}
    .toolbar-label {font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:900;margin-bottom:3px;text-align:center;}
    .toolbar-help {font-size:.72rem;color:var(--muted);text-align:center;margin-top:-4px;}
    .stPopover>button {
        background:#ffffff!important;
        color:var(--text)!important;
        border:1px solid var(--border)!important;
        border-radius:12px!important;
        font-weight:800!important;
        box-shadow:0 1px 2px rgba(15,23,42,.04);
    }
    .run-note {font-size:.72rem;color:var(--muted);text-align:center;margin-top:3px;}
    .card-item {
        display:block;
        width:100%;
        margin:4px 0;
        white-space:nowrap;
        overflow:visible;
        text-overflow:clip;
        line-height:1.28;
    }
    .card-value {
        display:inline-block;
        max-width:calc(100% - 82px);
        overflow:hidden;
        text-overflow:ellipsis;
        vertical-align:bottom;
    }
    .item-title { color:var(--text); font-weight:800; }
    .dot { display:inline-block; width:9px; height:9px; border-radius:999px; margin-right:5px; vertical-align:middle; }
    .dot-green { background:#16a34a; }
    .dot-red { background:#dc2626; }
    .dot-yellow { background:#facc15; }
    .dot-blue { background:#2563eb; }
    .dot-gray { background:#9ca3af; }
    .hover-tip {
        position:relative;
        cursor:help;
    }
    .hover-tip::after {
        content:none;
    }
    .hover-tip .tip-box {
        visibility:hidden;
        opacity:0;
        transition:opacity .15s ease;
        position:absolute;
        z-index:99999;
        left:0;
        top:125%;
        width:min(360px, 82vw);
        max-width:360px;
        background:#111827;
        color:#f9fafb!important;
        border-radius:12px;
        padding:12px 14px;
        box-shadow:0 14px 35px rgba(15,23,42,.25);
        font-size:.78rem;
        line-height:1.42;
        font-weight:500;
        text-align:left;
        border:1px solid rgba(255,255,255,.12);
        white-space:normal;
        overflow-wrap:anywhere;
        word-break:normal;
    }
    .hover-tip .tip-box strong, .hover-tip .tip-box span { color:#f9fafb!important; white-space:normal; overflow-wrap:anywhere; }
    .hover-tip:hover .tip-box { visibility:visible; opacity:1; }
    .hot-card:nth-child(5n) .hover-tip .tip-box,
    .hot-card:nth-child(5n-1) .hover-tip .tip-box { right:0; left:auto; }
    .tag {
        display:inline-block;
        border-radius:999px;
        padding:3px 9px;
        font-size:.73rem;
        font-weight:800;
        margin:3px 4px 0 0;
    }
    .tag-green { background:#dcfce7; color:var(--green); }
    .tag-red { background:#fee2e2; color:var(--red); }
    .tag-amber { background:#fef3c7; color:var(--amber); }
    .tag-blue { background:#dbeafe; color:var(--accent); }
    hr { border-color:var(--border)!important; }

    .portfolio-card {
        background:var(--surface);
        border:1px solid var(--border);
        border-radius:18px;
        padding:16px 18px;
        box-shadow:0 8px 22px rgba(15,23,42,.06);
        margin-bottom:16px;
    }
    .portfolio-title {font-size:1.25rem;font-weight:950;margin-bottom:3px;}
    .portfolio-subtitle {color:var(--muted);font-size:.86rem;margin-bottom:10px;}
    .decision-pill {display:inline-block;border-radius:999px;padding:5px 10px;font-weight:900;font-size:.78rem;margin-bottom:8px;}
    .decision-green {background:#dcfce7;color:#166534;}
    .decision-yellow {background:#fef3c7;color:#92400e;}
    .decision-red {background:#fee2e2;color:#991b1b;}
    .decision-blue {background:#dbeafe;color:#1d4ed8;}
    .read-box {background:#f8fafc;border:1px solid var(--border);border-radius:14px;padding:12px 14px;margin:10px 0;}
    .read-title {font-weight:950;font-size:.88rem;margin-bottom:5px;}
    .read-text {font-size:.84rem;color:#475569;line-height:1.45;}

</style>
""",
    unsafe_allow_html=True,
)



# ──────────────────────────────────────────────────────────────────────────────
# Session state — preserves scan results when widgets rerun the app
# ──────────────────────────────────────────────────────────────────────────────
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "scan_meta" not in st.session_state:
    st.session_state.scan_meta = None
if "leaderboard_filter" not in st.session_state:
    st.session_state.leaderboard_filter = "All"
if "cancel_scan_requested" not in st.session_state:
    st.session_state.cancel_scan_requested = False

if "morning_report_active" not in st.session_state:
    st.session_state.morning_report_active = False
if "last_morning_report" not in st.session_state:
    st.session_state.last_morning_report = None

# ──────────────────────────────────────────────────────────────────────────────
# V9 top control bar — replaces the sidebar
# ──────────────────────────────────────────────────────────────────────────────
custom_input = ""
csv_uploaded = None

APP_DATA_DIR = os.path.join("swingit_data")
os.makedirs(APP_DATA_DIR, exist_ok=True)

APP_DEFAULT_SETTINGS = {
    "default_universe": "⭐ Favorites",
    "default_view_by": "🎯 8% Target Hunter",
    "default_candidate_gate": "Balanced",
}

APP_VIEW_BY_OPTIONS = [
    "🎯 8% Target Hunter",
    "⚡ Ready Now",
    "🧠 Highest Confidence",
    "🚀 Maximum Upside",
    "😱 Overreaction",
    "🧊 Stabilizing Panics",
]

APP_CANDIDATE_GATE_OPTIONS = ["Balanced", "Strict", "Loose"]
APP_SETTINGS_FILE = os.path.join(APP_DATA_DIR, "profile_settings.json")
FAVORITES_CSV_FILE = "favorites.csv"

def load_app_settings() -> dict:
    settings = APP_DEFAULT_SETTINGS.copy()
    try:
        if os.path.exists(APP_SETTINGS_FILE):
            with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                settings.update({k: v for k, v in saved.items() if k in settings})
    except Exception:
        pass
    return settings

def save_app_settings(settings: dict) -> None:
    clean = APP_DEFAULT_SETTINGS.copy()
    clean.update({k: v for k, v in settings.items() if k in clean})
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)

if "force_profile_defaults" not in st.session_state:
    st.session_state.force_profile_defaults = True

UNIVERSE_OPTIONS = [
    "⭐ SwingIt Elite (Recommended)",
    "⭐ Favorites",
    "📂 CSV upload",
    "🧠 Institutional Favorites",
    "🚀 AI & Semiconductors",
    "S&P 500",
    "NASDAQ 100",
    "Dow Jones 30",
    "Russell 1000",
    "Russell 3000",
    "FXAIX / VOO Holdings",
    "VTI Holdings",
    "QQQM Holdings",
    "SCHG Holdings",
    "VGT Holdings",
    "SMH Holdings",
    "SOXX Holdings",
    "Custom list",
]

UNIVERSE_HINTS = {
    "⭐ SwingIt Elite (Recommended)": "S&P 500 + broad U.S. market + Nasdaq-100",
    "⭐ Favorites": "Your saved ticker universe",
    "📂 CSV upload": "Upload your own ticker list",
    "🧠 Institutional Favorites": "Large-cap names held across elite funds",
    "🚀 AI & Semiconductors": "Growth, AI, software, and semiconductor-heavy names",
    "S&P 500": "Large-cap U.S. stocks",
    "NASDAQ 100": "Nasdaq-100 growth leaders",
    "Dow Jones 30": "Blue-chip Dow names",
    "Russell 1000": "Top 1,000 U.S. listed stocks by market cap",
    "Russell 3000": "Top 3,000 U.S. listed stocks by market cap",
    "FXAIX / VOO Holdings": "S&P 500 style holdings",
    "VTI Holdings": "Broad total-market universe, capped for scanning speed",
    "QQQM Holdings": "Nasdaq-100 ETF holdings",
    "SCHG Holdings": "SCHG-style large-cap growth universe",
    "VGT Holdings": "VGT-style technology universe, full-sized instead of top-holdings only",
    "SMH Holdings": "Semiconductor ETF holdings",
    "SOXX Holdings": "Semiconductor ETF holdings",
    "Custom list": "Paste tickers manually",
}

current_profile_settings = load_app_settings()
if st.session_state.get("force_profile_defaults", False):
    st.session_state.top_universe = current_profile_settings.get("default_universe", APP_DEFAULT_SETTINGS["default_universe"])
    st.session_state.ranking_mode_selector = current_profile_settings.get("default_view_by", APP_DEFAULT_SETTINGS["default_view_by"])
    st.session_state.candidate_gate_mode = current_profile_settings.get("default_candidate_gate", APP_DEFAULT_SETTINGS["default_candidate_gate"])
    st.session_state.force_profile_defaults = False
else:
    st.session_state.setdefault("top_universe", current_profile_settings.get("default_universe", APP_DEFAULT_SETTINGS["default_universe"]))
    st.session_state.setdefault("ranking_mode_selector", current_profile_settings.get("default_view_by", APP_DEFAULT_SETTINGS["default_view_by"]))
    st.session_state.setdefault("candidate_gate_mode", current_profile_settings.get("default_candidate_gate", APP_DEFAULT_SETTINGS["default_candidate_gate"]))

with st.container(border=True):
    top_title_col, top_workspace_col, top_universe_col, top_profile_settings_col, top_model_col, top_run_col = st.columns(
        [1.05, 1.05, 1.85, 1.25, 1.45, 1.05],
        vertical_alignment="center",
    )

    with top_title_col:
        st.markdown(
            """
            <div class="terminal-title">🔥 SwingIt V13</div>
            <div class="terminal-subtitle">Entry Hunter + Scanner + Portfolio.</div>
            """,
            unsafe_allow_html=True,
        )

    with top_workspace_col:
        st.markdown("<div class='toolbar-label'>Workspace</div>", unsafe_allow_html=True)
        workspace = st.selectbox(
            "Workspace",
            ["⚡ Entry Hunter", "🔥 Scanner", "👑 My Portfolio"],
            index=0,
            label_visibility="collapsed",
            key="workspace_selector",
            help="Entry Hunter finds this week\'s actionable swing entries. Scanner researches the market. Portfolio manages active swing positions and exits.",
        )
        st.markdown("<div class='toolbar-help'>Enter, research, or manage</div>", unsafe_allow_html=True)

    with top_universe_col:
        st.markdown("<div class='toolbar-label'>Universe</div>", unsafe_allow_html=True)
        universe = st.selectbox(
            "Universe",
            UNIVERSE_OPTIONS,
            index=UNIVERSE_OPTIONS.index(st.session_state.top_universe) if st.session_state.get("top_universe") in UNIVERSE_OPTIONS else 0,
            label_visibility="collapsed",
            help="Choose the group to scan. The app scans the full selected universe by default.",
            key="top_universe",
        )
        st.markdown(f"<div class='toolbar-help'>{html.escape(UNIVERSE_HINTS.get(universe, ''))}</div>", unsafe_allow_html=True)

    with top_profile_settings_col:
        st.markdown("<div class='toolbar-label'>Profile Settings</div>", unsafe_allow_html=True)
        with st.popover("👤 Defaults", use_container_width=True):
            st.caption("Saved app defaults. These load automatically when SwingIt starts.")
            ps_universe = st.selectbox(
                "Default universe",
                UNIVERSE_OPTIONS,
                index=UNIVERSE_OPTIONS.index(current_profile_settings.get("default_universe", APP_DEFAULT_SETTINGS["default_universe"])) if current_profile_settings.get("default_universe") in UNIVERSE_OPTIONS else 0,
                help="Which universe should appear first?",
                key="profile_default_universe",
            )
            ps_view_by = st.selectbox(
                "Default View By",
                APP_VIEW_BY_OPTIONS,
                index=APP_VIEW_BY_OPTIONS.index(current_profile_settings.get("default_view_by", APP_DEFAULT_SETTINGS["default_view_by"])) if current_profile_settings.get("default_view_by") in APP_VIEW_BY_OPTIONS else 0,
                help="Which ranking lens should SwingIt start with?",
                key="profile_default_view_by",
            )
            ps_gate = st.selectbox(
                "Default Candidate Quality Gate",
                APP_CANDIDATE_GATE_OPTIONS,
                index=APP_CANDIDATE_GATE_OPTIONS.index(current_profile_settings.get("default_candidate_gate", APP_DEFAULT_SETTINGS["default_candidate_gate"])) if current_profile_settings.get("default_candidate_gate") in APP_CANDIDATE_GATE_OPTIONS else 0,
                help="How strict should the Top Qualified Opportunities cards be by default?",
                key="profile_default_gate",
            )
            if st.button("💾 Save defaults", use_container_width=True, key="save_profile_defaults"):
                save_app_settings({
                    "default_universe": ps_universe,
                    "default_view_by": ps_view_by,
                    "default_candidate_gate": ps_gate,
                })
                st.session_state.force_profile_defaults = True
                st.success("Saved. Reloading with the new defaults…")
                st.rerun()
        default_summary = f"{current_profile_settings.get('default_view_by', '🎯 8% Target Hunter').split(' ', 1)[0]} · {current_profile_settings.get('default_candidate_gate', 'Balanced')}"
        st.markdown(f"<div class='toolbar-help'>Defaults: {html.escape(default_summary)}</div>", unsafe_allow_html=True)

    with top_model_col:
        st.markdown("<div class='toolbar-label'>Model Settings</div>", unsafe_allow_html=True)
        with st.popover("⚙️ Configure", use_container_width=True):
            profit_target = st.select_slider(
                "Profit goal",
                options=[5, 8, 10, 12, 15, 20],
                value=8,
                help="A historical RSI panic event counts as useful if it reached this max closing-price bounce within the selected window."
            )
            bounce_window = st.select_slider(
                "Swing window",
                options=[10, 15, 20, 30, 45, 60],
                value=30,
                help="Trading days after the oversold low to measure the best closing-price bounce."
            )
            spring_timeframe = st.selectbox(
                "TTM timeframe",
                ["1D", "1H"],
                index=0,
                help="1D is better for 1–4 week swing context. 1H is better for near-term timing/watchlist urgency."
            )
            include_news = st.toggle(
                "News/catalyst score",
                value=True,
                help="Adds lightweight Yahoo Finance headline scoring. Turn off if a large scan feels slow."
            )
            deep_scan_top_n = st.select_slider(
                "Deep scan candidates",
                options=[50, 100, 150, 200, 300, 500],
                value=150,
                help="Fast Scan checks the full universe with daily data first, then runs expensive 4H/news analysis only on the best candidates. Raise this for broader coverage; lower it for speed."
            )
            max_workers = st.select_slider(
                "Scan speed",
                options=[1, 4, 8, 12, 16],
                value=8,
                help="Higher = faster, but very high settings may trigger data-provider hiccups on huge universes."
            )
        st.markdown(
            f"<div class='toolbar-help'>Goal {profit_target}% · {bounce_window}d · TTM {spring_timeframe}</div>",
            unsafe_allow_html=True,
        )

    with top_run_col:
        st.markdown("<div class='toolbar-label'>&nbsp;</div>", unsafe_allow_html=True)
        run_label = "⚡ Run Entry Hunt" if st.session_state.get("workspace_selector") == "⚡ Entry Hunter" else "🚀 Run Swing Scan"
        run = st.button(run_label, use_container_width=True, disabled=(st.session_state.get("workspace_selector") == "👑 My Portfolio"))
        st.markdown("<div class='run-note'>Use ToS for entries/exits.</div>", unsafe_allow_html=True)

if universe == "Custom list":
    custom_input = st.text_area(
        "Custom tickers",
        placeholder="ORCL, ADBE, AMZN, MSFT",
        height=75,
        help="Comma, semicolon, or newline separated.",
        key="top_custom_tickers",
    )
elif universe == "📂 CSV upload":
    csv_uploaded = st.file_uploader(
        "📂 Upload ticker CSV",
        type=["csv"],
        help="Upload a CSV with a Ticker/Symbol column, or a one-column ticker list.",
        key="top_csv_upload",
    )

# Single-user mode: Favorites and Morning Report storage are app-level.
ACTIVE_PROFILE = "Amber"
PROFILE_DIR = APP_DATA_DIR
os.makedirs(PROFILE_DIR, exist_ok=True)

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# Favorites + uploaded universe helpers
# ──────────────────────────────────────────────────────────────────────────────
FAVORITES_FILE = FAVORITES_CSV_FILE


def _normalize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper().replace(".", "-")


def _favorites_state_key() -> str:
    return "favorites_single_user"


def favorites_to_csv_text(tickers: list[str]) -> str:
    clean = dedupe([_normalize_ticker(t) for t in tickers if str(t).strip()])
    return "Ticker\n" + "\n".join(clean) + ("\n" if clean else "")


def load_favorites() -> list[str]:
    """Load Favorites from a simple repo CSV file named favorites.csv.

    For permanent Favorites on Streamlit Cloud, keep `favorites.csv` committed in
    your GitHub repo. In-app add/remove works during the session and can write to
    the app filesystem when available, but GitHub remains the permanent source.
    """
    key = _favorites_state_key()
    if key in st.session_state:
        return dedupe([_normalize_ticker(t) for t in st.session_state.get(key, []) if str(t).strip()])

    favs = []
    try:
        if os.path.exists(FAVORITES_FILE):
            df_fav = pd.read_csv(FAVORITES_FILE)
            if not df_fav.empty:
                if "Ticker" in df_fav.columns:
                    favs = df_fav["Ticker"].tolist()
                elif "Symbol" in df_fav.columns:
                    favs = df_fav["Symbol"].tolist()
                else:
                    favs = df_fav.iloc[:, 0].tolist()
    except Exception:
        favs = []

    favs = dedupe([_normalize_ticker(t) for t in favs if str(t).strip()])
    st.session_state[key] = favs
    return favs


def save_favorites(tickers: list[str]) -> None:
    clean = dedupe([_normalize_ticker(t) for t in tickers if str(t).strip()])
    st.session_state[_favorites_state_key()] = clean
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            f.write(favorites_to_csv_text(clean))
    except Exception:
        st.warning("Could not write favorites.csv in this environment. Download the updated CSV below and commit it to GitHub.")


# ──────────────────────────────────────────────────────────────────────────────
# Morning Report helpers — Zazu mode for Favorites
# ──────────────────────────────────────────────────────────────────────────────
MORNING_SNAPSHOT_FILE = os.path.join(PROFILE_DIR, "morning_snapshot.json")


def _to_float(value, default=None):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except Exception:
        return default


def load_morning_snapshot() -> dict:
    try:
        if os.path.exists(MORNING_SNAPSHOT_FILE):
            with open(MORNING_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_morning_snapshot(results: list[dict]) -> None:
    snapshot = {
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "tickers": {},
    }
    for r in results or []:
        t = r.get("ticker")
        if not t:
            continue
        snapshot["tickers"][t] = {
            "price": r.get("price"),
            "rsi": r.get("current_rsi"),
            "setup_quality": r.get("setup_quality"),
            "swing_score": r.get("swing_score"),
            "spring_score": r.get("spring_score"),
            "spring_label": r.get("spring_label"),
            "rebound_stage_label": r.get("rebound_stage_label"),
            "overreaction_score": r.get("overreaction_score"),
            "overreaction_label": r.get("overreaction_label"),
            "opportunity_remaining_pct": r.get("opportunity_remaining_pct"),
            "news_label": r.get("news_label"),
            "news_headline": r.get("news_headline"),
            "panic_drop_pct": r.get("panic_drop_pct"),
            "panic_volume_ratio": r.get("panic_volume_ratio"),
            "red_flag_label": r.get("red_flag_label"),
        }
    try:
        with open(MORNING_SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, default=str)
    except Exception:
        # Streamlit Cloud can be read-only in some environments; if so, the report still works for this run.
        pass


def pct_change(new, old):
    new = _to_float(new)
    old = _to_float(old)
    if new is None or old in (None, 0):
        return None
    return (new / old - 1) * 100


def _changed_label(current, previous):
    if previous in (None, ""):
        return "new"
    if str(current) != str(previous):
        return "changed"
    return "same"


def build_morning_report(results: list[dict], previous_snapshot: dict | None = None) -> dict:
    """Build a Favorites-first morning briefing.

    The report is deliberately practical: it highlights new panic/overreaction situations,
    names that are becoming ready now, new stage/spring/news changes, red flags, and quiet names.
    """
    previous_snapshot = previous_snapshot or {}
    previous_tickers = previous_snapshot.get("tickers", {}) if isinstance(previous_snapshot, dict) else {}
    alerts = {
        "overreaction": [],
        "ready_now": [],
        "new_turns": [],
        "red_flags": [],
        "notable_changes": [],
        "quiet": [],
    }

    for r in results or []:
        t = r.get("ticker")
        prev = previous_tickers.get(t, {}) if t else {}
        price_chg = pct_change(r.get("price"), prev.get("price"))
        setup_delta = None
        if prev:
            setup_delta = (_to_float(r.get("setup_quality"), 0) or 0) - (_to_float(prev.get("setup_quality"), 0) or 0)
        rsi_delta = None
        if prev:
            rsi_delta = (_to_float(r.get("current_rsi"), 0) or 0) - (_to_float(prev.get("rsi"), 0) or 0)

        overreaction_score = _to_float(r.get("overreaction_score"), 0) or 0
        setup = _to_float(r.get("setup_quality"), 0) or 0
        spring = _to_float(r.get("spring_score"), 0) or 0
        remaining = _to_float(r.get("opportunity_remaining_pct"), 0) or 0
        shock = _to_float(r.get("panic_shock_score"), 0) or 0
        red_label = str(r.get("red_flag_label") or "")
        has_red_flag = "red flag" in red_label.lower() or "avoid" in red_label.lower() or "major" in red_label.lower()

        item = {
            "ticker": t,
            "price": r.get("price"),
            "price_change_pct": price_chg,
            "setup": int(round(setup)),
            "setup_delta": setup_delta,
            "swing": r.get("swing_score"),
            "spring": int(round(spring)),
            "spring_label": r.get("spring_label"),
            "stage": r.get("rebound_stage_label"),
            "overreaction": int(round(overreaction_score)),
            "overreaction_label": r.get("overreaction_label"),
            "remaining": remaining,
            "news_label": r.get("news_label"),
            "headline": r.get("news_headline"),
            "panic_drop_pct": r.get("panic_drop_pct"),
            "panic_drop_days": r.get("panic_drop_days"),
            "panic_volume_ratio": r.get("panic_volume_ratio"),
            "red_flag": r.get("red_flag_label"),
            "rsi": r.get("current_rsi"),
            "rsi_delta": rsi_delta,
        }

        # Overreaction: the Zazu headline. High selloff shock + decent narrative/overreaction + no red flag.
        if overreaction_score >= 70 and shock >= 45 and not has_red_flag:
            alerts["overreaction"].append(item)
            continue

        # Red flags should be surfaced even if a score looks tempting.
        if has_red_flag:
            alerts["red_flags"].append(item)
            continue

        # Ready now: strong setup with opportunity left.
        if setup >= 75 and remaining >= 30:
            alerts["ready_now"].append(item)
            continue

        # New turns: stage/spring changed in a useful direction or setup jumped materially.
        stage_changed = _changed_label(r.get("rebound_stage_label"), prev.get("rebound_stage_label")) == "changed"
        spring_changed = _changed_label(r.get("spring_label"), prev.get("spring_label")) == "changed"
        useful_stage = any(x in str(r.get("rebound_stage_label") or "").lower() for x in ["turn", "reversal", "stabil", "confirmed"])
        useful_spring = any(x in str(r.get("spring_label") or "").lower() for x in ["improving", "fired up", "early turn"])
        if (stage_changed and useful_stage) or (spring_changed and useful_spring) or (setup_delta is not None and setup_delta >= 10):
            alerts["new_turns"].append(item)
            continue

        # Notable but not urgent.
        if price_chg is not None and abs(price_chg) >= 3 or (rsi_delta is not None and abs(rsi_delta) >= 8):
            alerts["notable_changes"].append(item)
            continue

        alerts["quiet"].append(item)

    alerts["overreaction"].sort(key=lambda x: (x["overreaction"], x["remaining"] or 0), reverse=True)
    alerts["ready_now"].sort(key=lambda x: (x["setup"], x["remaining"] or 0), reverse=True)
    alerts["new_turns"].sort(key=lambda x: (x["setup_delta"] or 0, x["setup"]), reverse=True)
    alerts["red_flags"].sort(key=lambda x: x["overreaction"], reverse=True)
    alerts["notable_changes"].sort(key=lambda x: abs(x["price_change_pct"] or 0), reverse=True)
    return alerts


def _fmt_pct(value, digits=1):
    v = _to_float(value)
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.{digits}f}%"


def _report_line(item: dict, category: str) -> str:
    ticker = item.get("ticker") or "—"
    headline = html.escape(str(item.get("headline") or "No headline found."))
    news = html.escape(str(item.get("news_label") or "No news label"))
    stage = html.escape(str(item.get("stage") or "—"))
    spring = html.escape(str(item.get("spring_label") or "—"))
    if category == "overreaction":
        shock = _fmt_pct(item.get("panic_drop_pct"))
        days = item.get("panic_drop_days") or "?"
        return f"<li><strong>{ticker}</strong> — possible overreaction: {shock} in {days}d, Overreaction {item.get('overreaction')}/100, Remaining {_fmt_pct(item.get('remaining'),0)}.<br><span class='small-muted'>{news} · {headline}</span></li>"
    if category == "ready":
        return f"<li><strong>{ticker}</strong> — ready now: Setup {item.get('setup')}/100, Spring {item.get('spring')}/100, Remaining {_fmt_pct(item.get('remaining'),0)}.<br><span class='small-muted'>{stage} · {spring}</span></li>"
    if category == "turn":
        delta = item.get("setup_delta")
        delta_text = f" ({'+' if delta and delta > 0 else ''}{delta:.0f} vs last)" if delta is not None else ""
        return f"<li><strong>{ticker}</strong> — new turn forming: Setup {item.get('setup')}/100{delta_text}.<br><span class='small-muted'>{stage} · {spring}</span></li>"
    if category == "red":
        return f"<li><strong>{ticker}</strong> — caution: {html.escape(str(item.get('red_flag') or 'Red flag language found'))}.<br><span class='small-muted'>{headline}</span></li>"
    return f"<li><strong>{ticker}</strong> — notable move: price {_fmt_pct(item.get('price_change_pct'))}, RSI {item.get('rsi')}.<br><span class='small-muted'>{headline}</span></li>"


def render_morning_report(report: dict, favorites_count: int, previous_snapshot: dict | None = None):
    previous_time = (previous_snapshot or {}).get("saved_at")
    st.markdown("## ☕🦜 Morning Report")
    st.caption("Favorites briefing: what changed, what is actionable, and what should be ignored for now.")
    counts = {k: len(v) for k, v in (report or {}).items()}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Favorites scanned", favorites_count)
    c2.metric("Overreaction alerts", counts.get("overreaction", 0))
    c3.metric("Ready now", counts.get("ready_now", 0))
    c4.metric("New turns", counts.get("new_turns", 0))
    c5.metric("Cautions", counts.get("red_flags", 0))
    if previous_time:
        st.caption(f"Compared with last Morning Report snapshot from {previous_time}.")
    else:
        st.caption("No previous Morning Report snapshot found yet. Today becomes the baseline for future 'what changed' notes.")

    sections = [
        ("😱 Possible overreaction panic", "overreaction", "overreaction"),
        ("🔥 Ready now", "ready_now", "ready"),
        ("🌱 New turns forming", "new_turns", "turn"),
        ("⚠️ Cautions / red flags", "red_flags", "red"),
        ("👀 Notable changes", "notable_changes", "note"),
    ]
    for title, key, kind in sections:
        items = (report or {}).get(key, [])[:6]
        if not items:
            continue
        with st.container(border=True):
            st.markdown(f"#### {title}")
            html_lines = "<ul>" + "".join(_report_line(item, kind) for item in items) + "</ul>"
            st.markdown(html_lines, unsafe_allow_html=True)

    if not any(counts.get(k, 0) for k in ["overreaction", "ready_now", "new_turns", "red_flags", "notable_changes"]):
        st.success("🦜 Morning report: The kingdom is quiet. No major Favorites alerts right now.")


def parse_uploaded_tickers(uploaded_file) -> list[str]:
    """Parse a CSV upload with Ticker/Symbol column or a one-column ticker list."""
    if uploaded_file is None:
        return []
    try:
        uploaded_file.seek(0)
        df_upload = pd.read_csv(uploaded_file)
        if df_upload.empty:
            return []
        lower_cols = {str(c).strip().lower(): c for c in df_upload.columns}
        preferred = None
        for name in ["ticker", "symbol", "tickers", "symbols"]:
            if name in lower_cols:
                preferred = lower_cols[name]
                break
        if preferred is None:
            preferred = df_upload.columns[0]
        return dedupe([_normalize_ticker(v) for v in df_upload[preferred].dropna().tolist() if str(v).strip()])
    except Exception:
        try:
            uploaded_file.seek(0)
            text = uploaded_file.read().decode("utf-8", errors="ignore")
            raw = text.replace("\n", ",").replace(";", ",")
            return dedupe([_normalize_ticker(t) for t in raw.split(",") if t.strip() and t.strip().lower() not in ["ticker", "symbol"]])
        except Exception:
            return []

# ──────────────────────────────────────────────────────────────────────────────
# Universe helpers
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def read_wiki_tables(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SwingIt/3.0)"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return pd.read_html(StringIO(response.text))


@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500():
    tables = read_wiki_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = tables[0]
    return df["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()


@st.cache_data(ttl=86400, show_spinner=False)
def get_nasdaq100():
    tables = read_wiki_tables("https://en.wikipedia.org/wiki/Nasdaq-100")
    for table in tables:
        cols = [str(c).strip() for c in table.columns]
        table.columns = cols
        for col in ["Ticker", "Symbol"]:
            if col in table.columns:
                return table[col].dropna().astype(str).str.replace(".", "-", regex=False).str.upper().tolist()
    return []





def parse_market_cap(value):
    """Parse market cap values from Nasdaq screener responses."""
    if value is None or pd.isna(value):
        return 0.0
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text or text.lower() in {"nan", "none", "n/a", "--"}:
        return 0.0
    multiplier = 1.0
    last = text[-1].upper()
    if last == "T":
        multiplier = 1_000_000_000_000
        text = text[:-1]
    elif last == "B":
        multiplier = 1_000_000_000
        text = text[:-1]
    elif last == "M":
        multiplier = 1_000_000
        text = text[:-1]
    try:
        return float(text) * multiplier
    except Exception:
        return 0.0


def clean_yahoo_ticker(raw):
    """Convert common data-source ticker formats into yfinance-friendly symbols."""
    if raw is None or pd.isna(raw):
        return ""
    t = str(raw).strip().upper()
    # Nasdaq often uses BRK/A while yfinance wants BRK-A.
    t = t.replace("/", "-").replace(".", "-")
    # Remove common non-common-stock suffix clutter.
    if not t or t in {"-", "--", "N/A", "NA", "NULL"}:
        return ""
    if any(x in t for x in ["^", " "]):
        return ""
    return t


@st.cache_data(ttl=86400, show_spinner=False)
def get_nasdaq_stock_screener_df():
    """Download a broad U.S. listed-stock universe from Nasdaq as a robust fallback.

    ETF issuer holdings files can be fragile on Streamlit Cloud. This source is
    used to build Russell-style approximations by market cap so Russell 1000 and
    Russell 3000 do not collapse back to a 528-name curated fallback.
    """
    url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&download=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    # Nasdaq usually returns JSON, but this keeps us safe if it ever returns CSV.
    try:
        payload = response.json()
        rows = payload.get("data", {}).get("rows", [])
        df = pd.DataFrame(rows)
    except Exception:
        df = pd.read_csv(StringIO(response.text))

    if df.empty:
        raise RuntimeError("Nasdaq screener returned no rows.")

    # Normalize column names but keep original values.
    df.columns = [str(c).strip() for c in df.columns]
    lower_map = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}

    symbol_col = lower_map.get("symbol") or lower_map.get("ticker")
    if not symbol_col:
        raise RuntimeError(f"Could not find symbol column in Nasdaq screener columns: {list(df.columns)}")

    name_col = lower_map.get("name") or lower_map.get("companyname") or symbol_col
    market_col = lower_map.get("marketcap") or lower_map.get("marketcap") or lower_map.get("marketcapitalization")
    etf_col = lower_map.get("etf")
    country_col = lower_map.get("country")
    sector_col = lower_map.get("sector")
    industry_col = lower_map.get("industry")

    out = pd.DataFrame()
    out["Ticker"] = df[symbol_col].apply(clean_yahoo_ticker)
    out["Name"] = df[name_col].astype(str) if name_col in df.columns else out["Ticker"]
    out["MarketCap"] = df[market_col].apply(parse_market_cap) if market_col in df.columns else 0.0
    out["ETF"] = df[etf_col].astype(str).str.upper() if etf_col in df.columns else "N"
    out["Country"] = df[country_col].astype(str) if country_col in df.columns else "United States"
    out["Sector"] = df[sector_col].astype(str) if sector_col in df.columns else ""
    out["Industry"] = df[industry_col].astype(str) if industry_col in df.columns else ""

    out = out[out["Ticker"].astype(bool)].copy()
    out = out[~out["Ticker"].str.contains(r"[.$^ ]", regex=True, na=False)]
    out = out[out["Ticker"].str.len() <= 7]
    # Keep ordinary stocks; remove ETFs when Nasdaq provides the flag.
    out = out[~out["ETF"].isin(["Y", "TRUE", "1"])]
    # Common obvious non-common-stock suffixes. Conservative so we don't delete class shares like BRK-B.
    out = out[~out["Ticker"].str.endswith(("-WS", "-WT", "-W", "-U", "-R"), na=False)]
    out = out.drop_duplicates("Ticker").sort_values("MarketCap", ascending=False)
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def get_broad_us_tickers(limit=None):
    df = get_nasdaq_stock_screener_df()
    if limit:
        df = df.head(int(limit))
    return df["Ticker"].tolist()


@st.cache_data(ttl=86400, show_spinner=False)
def get_sector_tickers(sector_keywords=None, industry_keywords=None, limit=350, min_count=50, fill_with_broad=False):
    """Build a fuller ETF-style universe from Nasdaq listed-stock metadata.

    Some ETF issuer full-holdings downloads are fragile on Streamlit Cloud. For
    sector ETFs like VGT, this gives us a much more realistic full-sized universe
    than the old 38-name curated fallback while still keeping the scan relevant.
    """
    sector_keywords = [x.lower() for x in (sector_keywords or [])]
    industry_keywords = [x.lower() for x in (industry_keywords or [])]
    df = get_nasdaq_stock_screener_df().copy()
    sector = df.get("Sector", pd.Series("", index=df.index)).astype(str).str.lower()
    industry = df.get("Industry", pd.Series("", index=df.index)).astype(str).str.lower()

    mask = pd.Series(False, index=df.index)
    for kw in sector_keywords:
        mask = mask | sector.str.contains(kw, na=False)
    for kw in industry_keywords:
        mask = mask | industry.str.contains(kw, na=False)

    filtered = df[mask].sort_values("MarketCap", ascending=False)
    tickers = filtered["Ticker"].tolist()

    if fill_with_broad and len(tickers) < min_count:
        broad = df.sort_values("MarketCap", ascending=False)["Ticker"].tolist()
        tickers = dedupe(tickers + broad)

    if limit:
        tickers = tickers[: int(limit)]
    return dedupe(tickers)


@st.cache_data(ttl=86400, show_spinner=False)
def get_vgt_universe():
    """VGT-style technology universe.

    VGT currently has 300+ holdings. If an official holdings file is unavailable,
    use a full-sized technology-sector universe from Nasdaq metadata rather than
    the old top-holdings-only curated list.
    """
    try:
        tickers = get_sector_tickers(
            sector_keywords=["technology"],
            industry_keywords=["software", "semiconductor", "computer", "electronic", "information"],
            limit=325,
            min_count=250,
            fill_with_broad=False,
        )
        if len(tickers) >= 250:
            return tickers
    except Exception:
        pass
    # Fallback: curated tech leaders + broad market fill so this never collapses to 38.
    return dedupe(VGT_NAMES + GROWTH_CORE + get_broad_us_tickers(325))[:325]


@st.cache_data(ttl=86400, show_spinner=False)
def get_schg_universe():
    """SCHG-style large-cap growth universe.

    SCHG is broader than our old short curated list, so build a larger growth-like
    universe from Nasdaq-100 plus large-cap technology/communication/consumer and
    healthcare names.
    """
    try:
        growth = get_sector_tickers(
            sector_keywords=["technology", "consumer", "health", "telecommunications", "communication"],
            industry_keywords=["software", "semiconductor", "internet", "biotechnology", "pharmaceutical", "retail"],
            limit=260,
            min_count=150,
            fill_with_broad=True,
        )
        return dedupe(get_nasdaq100() + SCHG_NAMES + growth)[:260]
    except Exception:
        return dedupe(get_nasdaq100() + SCHG_NAMES + GROWTH_CORE + get_broad_us_tickers(260))[:260]


ISHARES_PRODUCTS = {
    # ticker: (product_id, product_slug)
    "IWB": ("239707", "ishares-russell-1000-etf"),
    "IWV": ("239714", "ishares-russell-3000-etf"),
    "ITOT": ("239724", "ishares-core-sp-total-us-stock-market-etf"),
    "IVV": ("239726", "ishares-core-sp-500-etf"),
}


def _extract_tickers_from_holdings_csv(text: str, ticker: str):
    """Parse an iShares-style holdings CSV response into clean Yahoo tickers."""
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "ticker" in low and ("name" in low or "issuer" in low) and ("," in line):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"Could not find holdings header for {ticker}.")

    csv_text = "\n".join(lines[header_idx:])
    df = pd.read_csv(StringIO(csv_text), engine="python")
    df.columns = [str(c).strip() for c in df.columns]

    ticker_col = None
    for col in ["Ticker", "ticker", "Local Ticker", "Trading Ticker"]:
        if col in df.columns:
            ticker_col = col
            break
    if ticker_col is None:
        for col in df.columns:
            if "ticker" in str(col).lower():
                ticker_col = col
                break
    if ticker_col is None:
        raise ValueError(f"Could not find ticker column for {ticker}.")

    out = []
    for raw_ticker in df[ticker_col].dropna().astype(str).tolist():
        t = raw_ticker.strip().upper().replace(".", "-")
        if not t or t in {"-", "--", "USD", "CASH", "US DOLLAR"}:
            continue
        if " " in t or len(t) > 7:
            continue
        # Keep ordinary U.S. tickers and common class-share tickers after . -> - conversion.
        out.append(t)
    return dedupe(out)


@st.cache_data(ttl=86400, show_spinner=False)
def get_ishares_holdings(product_id: str, ticker: str):
    """Best-effort pull of current iShares holdings CSV.

    V9 accidentally used an incomplete iShares URL, so IWB/IWV/ITOT/IVV failed
    and broad universes fell back to the ~528-name curated fallback. This version
    uses the full product slug URL and then tries the old URL as a backup.
    """
    ticker = ticker.upper().strip()
    slug = ISHARES_PRODUCTS.get(ticker, (product_id, ""))[1]

    urls = []
    if slug:
        urls.append(
            f"https://www.ishares.com/us/products/{product_id}/{slug}/"
            f"1467271812596.ajax?fileType=csv&fileName={ticker}_holdings&dataType=fund"
        )
    urls.append(
        f"https://www.ishares.com/us/products/{product_id}/"
        f"1467271812596.ajax?fileType=csv&fileName={ticker}_holdings&dataType=fund"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Safari/537.36",
        "Accept": "text/csv,application/csv,text/plain,*/*",
    }

    last_error = None
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            tickers = _extract_tickers_from_holdings_csv(response.text, ticker)
            if len(tickers) >= 25:
                return tickers
            last_error = ValueError(f"Only found {len(tickers)} holdings for {ticker}.")
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Could not download {ticker} holdings. Last error: {last_error}")


@st.cache_data(ttl=86400, show_spinner=False)
def get_russell1000():
    # Russell 1000 approximation: top 1,000 U.S. listed common stocks by market cap.
    # This is more reliable on Streamlit Cloud than fragile ETF holdings downloads.
    try:
        return get_broad_us_tickers(1000)
    except Exception:
        try:
            return get_ishares_holdings("239707", "IWB")
        except Exception:
            return dedupe(get_sp500() + get_nasdaq100() + GROWTH_CORE + HIGH_OPPORTUNITY)


@st.cache_data(ttl=86400, show_spinner=False)
def get_russell3000():
    # Russell 3000 approximation: top 3,000 U.S. listed common stocks by market cap.
    try:
        return get_broad_us_tickers(3000)
    except Exception:
        try:
            return get_ishares_holdings("239714", "IWV")
        except Exception:
            try:
                return get_ishares_holdings("239724", "ITOT")
            except Exception:
                return dedupe(get_sp500() + get_nasdaq100() + GROWTH_CORE + HIGH_OPPORTUNITY + SCHG_NAMES + VGT_NAMES + SMH_NAMES + SOXX_NAMES)


@st.cache_data(ttl=86400, show_spinner=False)
def get_total_market():
    # VTI-style broad market proxy. Keep it broad but bounded for scanning speed.
    try:
        return get_broad_us_tickers(3000)
    except Exception:
        try:
            return get_ishares_holdings("239724", "ITOT")
        except Exception:
            return get_russell3000()


@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500_etf_proxy():
    try:
        return get_ishares_holdings("239726", "IVV")
    except Exception:
        return get_sp500()


@st.cache_data(ttl=86400, show_spinner=False)
def get_company_lookup(selected_universe: str = ""):
    """Best-effort ticker → company name map for nicer score cards."""
    lookup = {}
    try:
        # S&P 500 company names
        sp = read_wiki_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        if "Symbol" in sp.columns:
            name_col = "Security" if "Security" in sp.columns else None
            if name_col:
                lookup.update(dict(zip(sp["Symbol"].astype(str).str.replace(".", "-", regex=False).str.upper(), sp[name_col].astype(str))))

        # Nasdaq 100 company names
        tables = read_wiki_tables("https://en.wikipedia.org/wiki/Nasdaq-100")
        for table in tables:
            table.columns = [str(c).strip() for c in table.columns]
            sym_col = "Ticker" if "Ticker" in table.columns else "Symbol" if "Symbol" in table.columns else None
            name_col = "Company" if "Company" in table.columns else "Name" if "Name" in table.columns else None
            if sym_col and name_col:
                lookup.update(dict(zip(table[sym_col].astype(str).str.replace(".", "-", regex=False).str.upper(), table[name_col].astype(str))))
                break
    except Exception:
        pass

    # Helpful names for ETF/sector universe names that may not be in the above tables.
    lookup.update({
        "AAPL":"Apple", "MSFT":"Microsoft", "NVDA":"NVIDIA", "AMZN":"Amazon", "META":"Meta Platforms", "GOOGL":"Alphabet Class A", "GOOG":"Alphabet Class C",
        "AVGO":"Broadcom", "TSLA":"Tesla", "AMD":"Advanced Micro Devices", "ORCL":"Oracle", "ADBE":"Adobe", "CRM":"Salesforce", "NFLX":"Netflix",
        "NOW":"ServiceNow", "PANW":"Palo Alto Networks", "CRWD":"CrowdStrike", "PLTR":"Palantir", "SNOW":"Snowflake", "MDB":"MongoDB", "NET":"Cloudflare",
        "SHOP":"Shopify", "UBER":"Uber", "ABNB":"Airbnb", "COIN":"Coinbase", "MSTR":"MicroStrategy", "SMCI":"Super Micro Computer", "MU":"Micron",
        "QCOM":"Qualcomm", "INTC":"Intel", "TXN":"Texas Instruments", "AMAT":"Applied Materials", "LRCX":"Lam Research", "KLAC":"KLA", "ASML":"ASML",
        "TSM":"Taiwan Semiconductor", "ARM":"Arm Holdings", "MRVL":"Marvell", "ON":"ON Semiconductor", "MPWR":"Monolithic Power Systems", "ADI":"Analog Devices",
        "BA":"Boeing", "CAT":"Caterpillar", "DE":"Deere", "GE":"GE Aerospace", "JPM":"JPMorgan Chase", "GS":"Goldman Sachs", "V":"Visa", "MA":"Mastercard",
        "LLY":"Eli Lilly", "UNH":"UnitedHealth", "JNJ":"Johnson & Johnson", "ABBV":"AbbVie", "MRK":"Merck", "TMO":"Thermo Fisher", "ISRG":"Intuitive Surgical",
        "COST":"Costco", "HD":"Home Depot", "WMT":"Walmart", "TGT":"Target", "NKE":"Nike", "DIS":"Disney", "CMG":"Chipotle", "SBUX":"Starbucks",
        "FDX":"FedEx", "UPS":"UPS", "DAL":"Delta Air Lines", "UAL":"United Airlines", "CCL":"Carnival", "RCL":"Royal Caribbean",
        "ETSY":"Etsy", "ROKU":"Roku", "RBLX":"Roblox", "HOOD":"Robinhood", "AFRM":"Affirm", "SOFI":"SoFi", "DKNG":"DraftKings", "CELH":"Celsius",
        "EL":"Estée Lauder", "LULU":"Lululemon", "ULTA":"Ulta Beauty", "SE":"Sea Limited", "MELI":"MercadoLibre", "SPOT":"Spotify", "DDOG":"Datadog", "ZS":"Zscaler",
    })
    return lookup


DOW30 = [
    "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
    "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
    "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WBA", "WMT"
]

# Curated ETF-style universe lists. These are intentionally compact and liquid.
# They are not meant to replace official holdings files; they give SwingIt useful scan universes without relying on fragile ETF scraping.
GROWTH_CORE = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","LLY","COST","NFLX","AMD","ADBE","CRM","ORCL","NOW","INTU","QCOM","AMAT",
    "UBER","PANW","CRWD","PLTR","SHOP","SNOW","MDB","NET","DDOG","ZS","TEAM","WDAY","ANET","MELI","SPOT","ABNB","COIN","MSTR","SMCI","ARM",
    "MU","MRVL","KLAC","LRCX","TXN","ADI","ASML","TSM","MPWR","ON","NXPI","MCHP","TER","CDNS","SNPS","ADSK","TTD","FICO","APP","DELL",
]
SCHG_NAMES = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","LLY","V","MA","COST","HD","NFLX","AMD","ADBE","CRM","ORCL","NOW","INTU","QCOM","AMAT","BKNG","ISRG","UBER","PANW","CRWD","PLTR","ANET","MELI","SPOT","SNOW","SHOP","ADSK"
]
VGT_NAMES = [
    "AAPL","MSFT","NVDA","AVGO","ORCL","CRM","AMD","ADBE","ACN","CSCO","QCOM","INTU","IBM","NOW","AMAT","TXN","PANW","ADI","MU","LRCX","KLAC","ANET","INTC","CRWD","SNPS","CDNS","ADSK","MRVL","NXPI","MCHP","FTNT","DDOG","ZS","NET","MDB","SNOW","TEAM","WDAY"
]
SMH_NAMES = [
    "NVDA","TSM","AVGO","ASML","AMD","QCOM","AMAT","TXN","LRCX","MU","INTC","ADI","KLAC","MRVL","NXPI","MCHP","MPWR","ON","TER","SWKS","ARM","SMCI","DELL"
]
SOXX_NAMES = [
    "NVDA","AVGO","AMD","QCOM","TXN","AMAT","MU","INTC","ADI","LRCX","KLAC","MRVL","NXPI","MCHP","MPWR","ON","TER","SWKS","ASML","TSM","ARM"
]
HIGH_OPPORTUNITY = [
    "TSLA","NVDA","AMD","PLTR","COIN","MSTR","SMCI","SOFI","HOOD","AFRM","RBLX","ROKU","DKNG","CELH","SHOP","SNOW","NET","DDOG","ZS","CRWD","PANW","MDB","APP","ARM","MU","MRVL","DELL","LULU","ULTA","EL","NKE","TGT","DIS","BA","CCL","RCL","DAL","UAL","FDX","UPS"
]

ETF_LISTS = {
    # ETF/mutual-fund proxies. Where possible, these use live ETF holdings instead of
    # short curated lists so broad universes do not accidentally shrink.
    "FXAIX": lambda: get_sp500(),
    "VOO": lambda: get_sp500(),
    "VTI": lambda: get_total_market(),
    "QQQM": lambda: get_nasdaq100(),
    "SCHG": lambda: get_schg_universe(),
    "VGT": lambda: get_vgt_universe(),
    "SMH": lambda: SMH_NAMES,
    "SOXX": lambda: SOXX_NAMES,
}


def dedupe(tickers):
    seen = set()
    out = []
    for t in tickers:
        t = str(t).strip().upper().replace(".", "-")
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def add_sources(source_map, tickers, source_name):
    for t in dedupe(tickers):
        source_map.setdefault(t, set()).add(source_name)


@st.cache_data(ttl=86400, show_spinner=False)
def get_universe_payload_static(selected_universe: str, custom_text: str = ""):
    """Cached universe builder for stable/public universes.

    Favorites are intentionally NOT handled here because cached functions do not
    know when a user adds/removes a favorite. Favorites are loaded live below.
    """
    source_map = {}

    def add_etf(etf):
        names = ETF_LISTS[etf]()
        add_sources(source_map, names, etf)
        return names

    if selected_universe == "📂 CSV upload":
        raw = custom_text.replace("\n", ",").replace(";", ",")
        tickers = dedupe([t for t in raw.split(",") if t.strip()])
        add_sources(source_map, tickers, "CSV Upload")
    elif selected_universe == "S&P 500":
        tickers = get_sp500(); add_sources(source_map, tickers, "S&P 500")
    elif selected_universe == "NASDAQ 100":
        tickers = get_nasdaq100(); add_sources(source_map, tickers, "NASDAQ 100")
    elif selected_universe == "Dow Jones 30":
        tickers = DOW30; add_sources(source_map, tickers, "Dow 30")
    elif selected_universe == "Russell 1000":
        tickers = get_russell1000()
        add_sources(source_map, tickers, "Russell 1000")
    elif selected_universe == "Russell 3000":
        tickers = get_russell3000()
        add_sources(source_map, tickers, "Russell 3000")
    elif selected_universe == "FXAIX / VOO Holdings":
        tickers = add_etf("VOO")
        add_sources(source_map, tickers, "FXAIX")
    elif selected_universe == "VTI Holdings":
        tickers = add_etf("VTI")
    elif selected_universe == "QQQM Holdings":
        tickers = add_etf("QQQM")
    elif selected_universe == "SCHG Holdings":
        tickers = add_etf("SCHG")
    elif selected_universe == "VGT Holdings":
        tickers = add_etf("VGT")
    elif selected_universe == "SMH Holdings":
        tickers = add_etf("SMH")
    elif selected_universe == "SOXX Holdings":
        tickers = add_etf("SOXX")
    elif selected_universe == "⭐ SwingIt Elite (Recommended)":
        tickers = dedupe(add_etf("VOO") + add_etf("VTI") + add_etf("QQQM"))
    elif selected_universe == "🧠 Institutional Favorites":
        tickers = dedupe(add_etf("VOO") + add_etf("QQQM") + add_etf("SCHG") + add_etf("VGT"))
    elif selected_universe == "🚀 AI & Semiconductors":
        tickers = dedupe(add_etf("QQQM") + add_etf("VGT") + add_etf("SMH") + add_etf("SOXX"))
    else:
        raw = custom_text.replace("\n", ",").replace(";", ",")
        tickers = dedupe([t for t in raw.split(",") if t.strip()])
        add_sources(source_map, tickers, "Custom")

    source_map = {k: sorted(v) for k, v in source_map.items()}
    return dedupe(tickers), source_map


def get_universe_payload(selected_universe: str, custom_text: str = ""):
    """Returns (tickers, source_map) for the selected universe.

    Favorites are loaded live so newly added favorites are
    immediately scan-able and do not get trapped behind Streamlit's cache.
    """
    if selected_universe == "⭐ Favorites":
        tickers = load_favorites()
        source_map = {}
        add_sources(source_map, tickers, "Favorites")
        return dedupe(tickers), {k: sorted(v) for k, v in source_map.items()}
    return get_universe_payload_static(selected_universe, custom_text)


def get_universe_tickers(selected_universe: str, custom_text: str = ""):
    return get_universe_payload(selected_universe, custom_text)[0]


def institutional_label(sources):
    sources = sources or []
    elite_sources = {"VOO", "FXAIX", "VTI", "QQQM", "SCHG", "VGT", "SMH", "SOXX", "S&P 500", "NASDAQ 100"}
    count = len([s for s in sources if s in elite_sources])
    if count >= 4:
        return f"🏛 Elite ({count})"
    if count >= 2:
        return f"🏛 Strong ({count})"
    if count == 1:
        return "🧪 Specialty (1)"
    return "—"


def institutional_score(sources):
    sources = sources or []
    count = len(sources)
    if count >= 4:
        return 100
    if count == 3:
        return 80
    if count == 2:
        return 60
    if count == 1:
        return 35
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ──────────────────────────────────────────────────────────────────────────────
def clamp(value, lo=0, hi=100):
    if value is None or pd.isna(value):
        return lo
    return max(lo, min(hi, float(value)))


def current_rsi_opportunity_score(current_rsi):
    """Scores how close the stock is to an actionable RSI rebound zone right now.

    V6.2 intentionally favors the *turn* zone (roughly RSI 30–45) rather than
    only the deepest panic. The easiest money in this strategy is often after
    the disaster stops making new lows, not the first day RSI goes under 30.
    """
    if current_rsi is None or pd.isna(current_rsi):
        return 0
    r = float(current_rsi)
    if r < 20:
        return 78       # powerful, but still knife-catch territory
    if r < 25:
        return 88
    if r < 30:
        return 94
    if r < 35:
        return 100      # early rebound zone
    if r < 40:
        return 96
    if r < 45:
        return 82
    if r < 50:
        return 55
    if r < 55:
        return 25
    if r < 60:
        return 10
    return 0


def opportunity_label(current_rsi):
    if current_rsi is None or pd.isna(current_rsi):
        return "No RSI"
    r = float(current_rsi)
    if r < 25:
        return "Panic zone"
    if r < 30:
        return "Oversold"
    if r < 35:
        return "Early rebound zone"
    if r < 40:
        return "Turn zone"
    if r < 45:
        return "Early watch"
    if r < 50:
        return "Watch"
    if r < 60:
        return "Recovered"
    return "Extended"


def opportunity_remaining_from_cycle(current_price, cycle_low_price, avg_max_bounce_pct=None, target_price=None):
    """Estimate how much of the current RSI-panic rebound remains.

    Prefer a pre-computed conservative target when supplied. This avoids projecting
    unrealistic targets from a tiny historical sample or one unusually large prior bounce.
    """
    try:
        current = float(current_price)
        low = float(cycle_low_price)
    except Exception:
        return {
            "opportunity_remaining_pct": None,
            "opportunity_remaining_score": 0,
            "opportunity_remaining_label": "⚪ No cycle target",
            "cycle_low_price": None,
            "cycle_target_price": None,
            "move_completed_pct": None,
        }

    if low <= 0:
        return {
            "opportunity_remaining_pct": None,
            "opportunity_remaining_score": 0,
            "opportunity_remaining_label": "⚪ No cycle target",
            "cycle_low_price": None,
            "cycle_target_price": None,
            "move_completed_pct": None,
        }

    try:
        if target_price is not None and float(target_price) > low:
            target = float(target_price)
        else:
            bounce = float(avg_max_bounce_pct)
            if bounce <= 0:
                raise ValueError("bad bounce")
            target = low * (1 + bounce / 100.0)
    except Exception:
        return {
            "opportunity_remaining_pct": None,
            "opportunity_remaining_score": 0,
            "opportunity_remaining_label": "⚪ No cycle target",
            "cycle_low_price": round(low, 2),
            "cycle_target_price": None,
            "move_completed_pct": None,
        }

    total_move = target - low
    if total_move <= 0:
        remaining = None
        completed = None
    else:
        remaining = ((target - current) / total_move) * 100.0
        completed = ((current - low) / total_move) * 100.0
        remaining = max(0.0, min(100.0, remaining))
        completed = max(0.0, min(100.0, completed))

    if remaining is None:
        score, label = 0, "⚪ No cycle target"
    elif remaining >= 90:
        score, label = 82, f"🟢 {remaining:.0f}% remaining · Very early"
    elif remaining >= 70:
        score, label = 100, f"🟢 {remaining:.0f}% remaining · Early"
    elif remaining >= 40:
        score, label = 90, f"🟡 {remaining:.0f}% remaining · Developing"
    elif remaining >= 20:
        score, label = 45, f"🟠 {remaining:.0f}% remaining · Late"
    else:
        score, label = 5, f"🔴 {remaining:.0f}% remaining · Extended"

    return {
        "opportunity_remaining_pct": round(remaining, 1) if remaining is not None else None,
        "opportunity_remaining_score": int(round(score)),
        "opportunity_remaining_label": label,
        "cycle_low_price": round(low, 2),
        "cycle_target_price": round(target, 2),
        "move_completed_pct": round(completed, 1) if completed is not None else None,
    }


def conservative_target_from_rebound_history(current_price, close, rebounds, profit_target=8, bounce_days=30):
    """Build a more realistic swing target from the current RSI panic cycle.

    Old behavior used average historical bounce from the *current* price, which could
    overstate targets when there was only one huge prior event. This version anchors
    the target to the current panic-cycle low and caps it by the recent pre-panic
    trading range, so a one-off 25% historical bounce cannot imply a return to
    unrealistic/all-time-high levels after a smaller current selloff.
    """
    empty = {
        "target_price": None,
        "target_gain_pct_from_current": None,
        "target_bounce_pct_from_low": None,
        "target_reason": "No reliable RSI panic-cycle target is available.",
        "target_confidence": "Low",
        "target_method": "No target",
        "cycle_low_price": None,
        "cycle_low_date": None,
        "pre_panic_high": None,
        "history_bounce_pct_used": None,
        "recent_damage_cap_pct": None,
    }
    try:
        current = float(current_price)
    except Exception:
        return empty

    events = rebounds.get("events") or []
    if not events:
        return empty

    recent_event = events[-1]
    low = recent_event.get("Low Close")
    low_date = recent_event.get("RSI Low Date")
    try:
        low = float(low)
    except Exception:
        return empty
    if low <= 0:
        return empty

    bounce_col = f"Max {int(bounce_days)}D Bounce %"
    event_bounces = []
    for e in events:
        val = e.get(bounce_col)
        try:
            if val is not None and not pd.isna(val) and float(val) > 0:
                event_bounces.append(float(val))
        except Exception:
            pass
    if not event_bounces:
        return {**empty, "cycle_low_price": round(low, 2), "cycle_low_date": low_date}

    event_count = len(event_bounces)
    avg_bounce = float(pd.Series(event_bounces).mean())
    median_bounce = float(pd.Series(event_bounces).median())

    # Sample-size shrinkage: one giant historical bounce should be treated as a clue,
    # not as a full forecast. More observations allow the history to speak louder.
    if event_count == 1:
        history_bounce = min(median_bounce, max(float(profit_target) + 2, 10.0))
        target_confidence = "Low"
        method = "single-event capped"
    elif event_count == 2:
        history_bounce = min(median_bounce, max(float(profit_target) + 5, 13.0))
        target_confidence = "Low/Medium"
        method = "two-event median capped"
    else:
        history_bounce = 0.65 * median_bounce + 0.35 * avg_bounce
        cap = max(float(profit_target) * 2.5, 18.0)
        history_bounce = min(history_bounce, cap)
        target_confidence = "High" if event_count >= 6 else "Medium"
        method = "median-weighted history"

    # Recent-damage cap: estimate the most realistic first recovery zone from the
    # high before the current panic low. This keeps the target from overshooting the
    # breakdown range when the historical sample was unusually explosive.
    pre_panic_high = None
    recent_damage_cap = None
    try:
        c = pd.Series(close).dropna().astype(float)
        if low_date is not None:
            # Convert date-like event date back to nearest index location.
            candidates = [i for i, idx in enumerate(c.index) if getattr(idx, 'date', lambda: idx)() <= low_date]
            low_pos = candidates[-1] if candidates else len(c) - 1
        else:
            low_pos = len(c) - 1
        start = max(0, low_pos - 30)
        before = c.iloc[start:low_pos + 1]
        if not before.empty:
            pre_panic_high = float(before.max())
            if pre_panic_high > low:
                recent_drop_pct = ((pre_panic_high / low) - 1) * 100.0
                # First swing target is usually below the exact pre-panic high.
                recent_damage_cap = max(float(profit_target) * 0.75, recent_drop_pct * 0.88)
    except Exception:
        pass

    target_bounce = history_bounce
    if recent_damage_cap is not None:
        target_bounce = min(target_bounce, recent_damage_cap)

    # Never let a target be below the user's selected goal if there is enough recent
    # damage to reasonably allow it; but don't force 8% if the chart only fell 4%.
    if recent_damage_cap is not None and recent_damage_cap >= float(profit_target):
        target_bounce = max(target_bounce, float(profit_target))

    target_price = low * (1 + target_bounce / 100.0)
    gain_from_current = ((target_price / current) - 1) * 100.0 if current > 0 else None

    reason_parts = [
        f"Target is anchored to the current RSI panic low (${low:.2f})",
        f"uses {method} from {event_count} historical event{'s' if event_count != 1 else ''}",
    ]
    if pre_panic_high is not None:
        reason_parts.append(f"and is capped against the recent pre-panic range near ${pre_panic_high:.2f}")
    reason = "; ".join(reason_parts) + "."

    return {
        "target_price": round(float(target_price), 2),
        "target_gain_pct_from_current": round(float(gain_from_current), 2) if gain_from_current is not None else None,
        "target_bounce_pct_from_low": round(float(target_bounce), 2),
        "target_reason": reason,
        "target_confidence": target_confidence,
        "target_method": method,
        "cycle_low_price": round(low, 2),
        "cycle_low_date": low_date,
        "pre_panic_high": round(pre_panic_high, 2) if pre_panic_high is not None else None,
        "history_bounce_pct_used": round(history_bounce, 2),
        "recent_damage_cap_pct": round(recent_damage_cap, 2) if recent_damage_cap is not None else None,
    }

def rebound_stage_from_series(close, rsi_series, spring_score=0, days_since_under_30=None):
    """Classify where the current RSI panic/rebound sits in its lifecycle.

    This is a watchlist timing label, not an entry signal.
    """
    valid_rsi = rsi_series.dropna()
    if valid_rsi.empty or close is None or len(close) < 10:
        return 0, "⚪ No stage", "Not enough history to classify the rebound stage."

    r = float(valid_rsi.iloc[-1])
    r_prev = float(valid_rsi.iloc[-2]) if len(valid_rsi) >= 2 else r
    r_3 = float(valid_rsi.iloc[-4]) if len(valid_rsi) >= 4 else r_prev
    rsi_rising = r > r_prev and r > r_3
    rsi_slope = r - r_3

    close = close.dropna().astype(float)
    current_close = float(close.iloc[-1])
    low_10 = float(close.tail(10).min())
    low_20 = float(close.tail(20).min()) if len(close) >= 20 else low_10
    broke_recent_low = current_close <= low_10 * 1.01
    lifted_from_low = current_close >= low_10 * 1.03 if low_10 else False
    lifted_from_20d_low = current_close >= low_20 * 1.04 if low_20 else False

    recent_panic = days_since_under_30 is not None and not pd.isna(days_since_under_30) and int(days_since_under_30) <= 30
    very_recent_panic = days_since_under_30 is not None and not pd.isna(days_since_under_30) and int(days_since_under_30) <= 10

    if r < 30:
        if rsi_rising and not broke_recent_low:
            score, label = 82, "🟡 Stabilizing"
            note = "RSI is still under 30, but it is rising and price is no longer pressing fresh 10-day lows."
        else:
            score, label = 65, "🔴 Panic"
            note = "RSI is under 30. Upside can be high, but the stock may still be falling."
    elif r < 45 and recent_panic and rsi_rising and (lifted_from_low or spring_score >= 60):
        score, label = 100, "🌱 Early Reversal"
        note = "This is the preferred SwingIt zone: RSI has left panic, is rising, and the stock is starting to lift from the recent low."
    elif r < 45 and recent_panic:
        score, label = 82, "🟡 Stabilizing"
        note = "RSI recently left panic but the rebound is not fully confirmed yet."
    elif r < 55 and recent_panic and (lifted_from_20d_low or spring_score >= 70):
        score, label = 76, "🔥 Confirmed Rebound"
        note = "RSI has recovered and price/momentum show the rebound has started. Some of the easiest move may already be gone."
    elif r < 60 and recent_panic:
        score, label = 55, "✅ Recovered"
        note = "RSI has recovered from panic. Still useful context, but the early rebound window may be fading."
    elif r >= 60:
        score, label = 18, "⚪ Extended"
        note = "RSI is already strong. This may be late for a fresh 1–4 week RSI rebound entry."
    elif r < 45:
        score, label = 45, "👀 Watch"
        note = "RSI is in a watchable area, but there has not been a recent RSI <30 panic event."
    else:
        score, label = 25, "⚪ Neutral"
        note = "No clear RSI panic/rebound stage right now."

    detail = (
        f"{note} Current RSI {r:.1f}; 3-bar RSI change {rsi_slope:+.1f}; "
        f"days since RSI <30: {days_since_under_30 if days_since_under_30 is not None else 'n/a'}."
    )
    return int(round(clamp(score))), label, detail




def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """Convert hourly OHLCV data to approximate 4-hour bars for tactical TTM trigger checks."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        try:
            out.index = pd.to_datetime(out.index)
        except Exception:
            return pd.DataFrame()
    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    try:
        fourh = out.resample("4h").agg(agg).dropna(subset=["Open", "High", "Low", "Close"])
        return fourh
    except Exception:
        return pd.DataFrame()


def compute_stabilization_score(close, volume, rsi_series, cycle_low_price=None, cycle_low_date=None, days_since_under_30=None):
    """Score whether a panic selloff appears to have stopped falling before a full reversal.

    This is intentionally different from Spring: stabilization is about price no longer
    making new lows, RSI improving, candle ranges calming, and volume staying constructive.
    """
    empty = {
        "stabilization_score": 0,
        "stabilization_label": "⚪ No stabilization data",
        "stabilization_reason": "Not enough recent price/RSI data to judge stabilization.",
        "days_since_panic_low": None,
        "distance_from_panic_low_pct": None,
        "new_low_last_3d": None,
    }
    try:
        close = close.dropna().astype(float)
        volume = volume.dropna().astype(float) if volume is not None else pd.Series(dtype=float)
        valid_rsi = rsi_series.dropna().astype(float)
    except Exception:
        return empty
    if len(close) < 10 or valid_rsi.empty:
        return empty

    current = float(close.iloc[-1])
    rsi_now = float(valid_rsi.iloc[-1])
    rsi_low_10 = float(valid_rsi.tail(10).min()) if len(valid_rsi) >= 10 else float(valid_rsi.min())
    rsi_3ago = float(valid_rsi.iloc[-4]) if len(valid_rsi) >= 4 else float(valid_rsi.iloc[0])
    rsi_improvement = rsi_now - rsi_low_10
    rsi_slope = rsi_now - rsi_3ago

    # Anchor on the RSI-panic cycle low if available, otherwise recent 10-day low.
    low_price = None
    try:
        if cycle_low_price is not None and not pd.isna(cycle_low_price):
            low_price = float(cycle_low_price)
    except Exception:
        low_price = None
    if not low_price or low_price <= 0:
        low_price = float(close.tail(10).min())

    distance_from_low = ((current - low_price) / low_price) * 100.0 if low_price else None
    recent_low_3 = float(close.tail(3).min())
    prior_low_7 = float(close.iloc[-10:-3].min()) if len(close) >= 10 else float(close.tail(10).min())
    new_low_last_3d = recent_low_3 < prior_low_7 * 0.995
    no_new_low_score = 0 if new_low_last_3d else 100

    # Days since panic low date if supplied; otherwise use days since RSI<30.
    days_since_low = None
    if cycle_low_date not in [None, "", "—"]:
        try:
            dt = pd.to_datetime(cycle_low_date)
            # Count trading bars after the cycle low date in available close series.
            days_since_low = int((close.index > dt).sum())
        except Exception:
            days_since_low = None
    if days_since_low is None and days_since_under_30 is not None and not pd.isna(days_since_under_30):
        try:
            days_since_low = int(days_since_under_30)
        except Exception:
            days_since_low = None

    # Ideal stabilization window: 2-10 bars after the panic low. Too new = knife; too old = already resolving.
    if days_since_low is None:
        days_score = 45
    elif days_since_low < 2:
        days_score = 20
    elif days_since_low <= 7:
        days_score = 100
    elif days_since_low <= 14:
        days_score = 75
    elif days_since_low <= 25:
        days_score = 45
    else:
        days_score = 20

    # Ideal: near low but not still collapsing. 0-8% from low is the tight watch zone.
    if distance_from_low is None:
        distance_score = 40
    elif distance_from_low < -1:
        distance_score = 5
    elif distance_from_low <= 8:
        distance_score = 100
    elif distance_from_low <= 15:
        distance_score = 65
    elif distance_from_low <= 25:
        distance_score = 30
    else:
        distance_score = 10

    rsi_score = clamp((max(rsi_improvement, 0) / 12.0) * 70 + (20 if rsi_slope > 0 else 0) + (10 if rsi_now >= 30 else 0))

    vol_score = 50
    try:
        avg_vol20 = float(volume.tail(20).mean())
        recent_vol3 = float(volume.tail(3).mean())
        if avg_vol20 > 0:
            vr = recent_vol3 / avg_vol20
            # Elevated but not absurd is ideal for post-panic digestion.
            if vr >= 1.2 and vr <= 3.5:
                vol_score = 90
            elif vr > 3.5:
                vol_score = 70
            elif vr >= 0.8:
                vol_score = 65
            else:
                vol_score = 35
    except Exception:
        vol_score = 50

    score = clamp(0.28 * days_score + 0.25 * distance_score + 0.25 * rsi_score + 0.22 * no_new_low_score)
    # Small volume confirmation bonus/penalty.
    score = clamp(0.85 * score + 0.15 * vol_score)

    if score >= 80:
        label = "🟢 Stabilizing"
        note = "Price appears to be holding after the panic low; RSI is repairing and sellers have not forced fresh lows."
    elif score >= 60:
        label = "🟡 Possible stabilization"
        note = "Some signs of selling exhaustion are present, but confirmation is still developing."
    elif score >= 35:
        label = "⚪ Unclear stabilization"
        note = "The stock may be trying to stabilize, but the evidence is mixed."
    else:
        label = "🔴 Not stabilizing"
        note = "The panic may still be active or the rebound window may already be too mature."

    reason = (
        f"{note} Days since panic low: {days_since_low if days_since_low is not None else 'n/a'}; "
        f"distance from panic low: {distance_from_low:.1f}% if known; "
        f"RSI low-to-now improvement: {rsi_improvement:+.1f}; "
        f"new low in last 3 days: {'yes' if new_low_last_3d else 'no'}."
    )
    return {
        "stabilization_score": int(round(score)),
        "stabilization_label": label,
        "stabilization_reason": reason,
        "days_since_panic_low": days_since_low,
        "distance_from_panic_low_pct": round(distance_from_low, 1) if distance_from_low is not None else None,
        "new_low_last_3d": bool(new_low_last_3d),
    }

def speed_score(days):
    if days is None or pd.isna(days):
        return 0
    d = float(days)
    if d <= 5:
        return 100
    if d <= 10:
        return 85
    if d <= 15:
        return 70
    if d <= 25:
        return 45
    return 20


def days_to_max_score(days):
    if days is None or pd.isna(days):
        return 0
    d = float(days)
    if d <= 7:
        return 100
    if d <= 14:
        return 85
    if d <= 21:
        return 65
    if d <= 30:
        return 45
    return 25


def normalize_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Handle yfinance single and multi-index outputs cleanly."""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        # yfinance may return fields by ticker. Try to select this ticker, else first level.
        if ticker in out.columns.get_level_values(-1):
            out = out.xs(ticker, axis=1, level=-1)
        else:
            out.columns = [c[0] if isinstance(c, tuple) else c for c in out.columns]

    # Keep only standard OHLCV names if possible.
    needed = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in needed if c not in out.columns]
    if missing:
        return pd.DataFrame()
    return out[needed].dropna(subset=["Close"])


# ──────────────────────────────────────────────────────────────────────────────
# RSI rebound analysis
# ──────────────────────────────────────────────────────────────────────────────
def analyze_rsi_swing_outcomes(close, rsi_series, profit_target=8, bounce_days=30, oversold_level=30):
    """Simulates what happened after each RSI <30 panic event.

    This intentionally scores trade-like outcomes instead of asking whether RSI
    eventually recovered to 50/60. A useful swing is one that produced a
    meaningful max closing-price bounce inside the chosen window.
    """
    empty = {
        "events": [],
        "event_count": 0,
        "profitable_event_count": 0,
        "swing_success_rate": None,
        "avg_max_bounce_pct": None,
        "avg_days_to_max_bounce": None,
        "avg_lowest_rsi": None,
        "avg_post_low_drawdown_pct": None,
        "avg_risk_reward": None,
        "history_score": 0,
    }

    data = pd.DataFrame({"close": close, "rsi": rsi_series}).dropna()
    if data.empty:
        return empty

    events = []
    i = 0
    n = len(data)

    while i < n:
        if data["rsi"].iloc[i] < oversold_level:
            start_pos = i
            while i + 1 < n and data["rsi"].iloc[i + 1] < oversold_level:
                i += 1
            end_pos = i

            oversold_slice = data.iloc[start_pos:end_pos + 1]
            low_date = oversold_slice["close"].idxmin()
            low_pos = data.index.get_loc(low_date)
            low_close = float(data.loc[low_date, "close"])
            lowest_rsi = float(oversold_slice["rsi"].min())

            window_end = min(n - 1, low_pos + int(bounce_days))
            bounce_slice = data.iloc[low_pos:window_end + 1]

            max_date = bounce_slice["close"].idxmax()
            max_pos = data.index.get_loc(max_date)
            max_close = float(data.loc[max_date, "close"])
            max_bounce = ((max_close / low_close) - 1) * 100 if low_close else None
            days_to_max = int(max_pos - low_pos)

            min_after = float(bounce_slice["close"].min())
            post_low_dd = ((min_after / low_close) - 1) * 100 if low_close else None

            profitable_swing = bool(max_bounce is not None and max_bounce >= profit_target)
            risk_reward = None
            if max_bounce is not None and post_low_dd is not None:
                downside = abs(min(post_low_dd, 0))
                risk_reward = max_bounce / downside if downside > 0 else max_bounce

            events.append({
                "Start Date": data.index[start_pos].date(),
                "RSI Low Date": low_date.date(),
                "Lowest RSI": round(lowest_rsi, 1),
                "Low Close": round(low_close, 2),
                "Profitable Swing": profitable_swing,
                f"Max {bounce_days}D Bounce %": round(max_bounce, 2) if max_bounce is not None else None,
                f"Days to Max {bounce_days}D Bounce": days_to_max,
                "Post-Low Drawdown %": round(post_low_dd, 2) if post_low_dd is not None else None,
                "Risk / Reward": round(risk_reward, 2) if risk_reward is not None else None,
                f"Max {bounce_days}D Date": max_date.date(),
            })
        i += 1

    event_count = len(events)
    if event_count == 0:
        return empty

    profitable_events = [e for e in events if e["Profitable Swing"]]
    success_rate = len(profitable_events) / event_count * 100

    avg_bounce = pd.Series([e[f"Max {bounce_days}D Bounce %"] for e in events]).mean()
    avg_days_max = pd.Series([e[f"Days to Max {bounce_days}D Bounce"] for e in events]).mean()
    avg_lowest_rsi = pd.Series([e["Lowest RSI"] for e in events]).mean()
    avg_dd = pd.Series([e["Post-Low Drawdown %"] for e in events]).mean()
    avg_rr = pd.Series([e["Risk / Reward"] for e in events if e["Risk / Reward"] is not None]).mean()

    # History Score = would this stock historically have rewarded buying RSI panic
    # for a 1–4 week swing? It focuses on money outcomes, not indicator recovery.
    success_component = success_rate
    bounce_component = clamp((avg_bounce / max(profit_target * 2, 1)) * 100) if not pd.isna(avg_bounce) else 0
    speed_component = days_to_max_score(avg_days_max)
    depth_component = clamp(((30 - avg_lowest_rsi) / 15) * 100) if not pd.isna(avg_lowest_rsi) else 0
    sample_component = clamp((min(event_count, 8) / 8) * 100)
    rr_component = clamp((avg_rr / 3) * 100) if not pd.isna(avg_rr) else 0

    # Penalize stocks that keep falling hard after the RSI panic low.
    drawdown_penalty = clamp(abs(min(avg_dd, 0)) * 2.2, 0, 22) if not pd.isna(avg_dd) else 0

    history_score = (
        0.28 * success_component
        + 0.25 * bounce_component
        + 0.17 * speed_component
        + 0.10 * sample_component
        + 0.08 * depth_component
        + 0.12 * rr_component
        - drawdown_penalty
    )

    return {
        "events": events,
        "event_count": event_count,
        "profitable_event_count": len(profitable_events),
        "swing_success_rate": round(success_rate, 1),
        "avg_max_bounce_pct": round(float(avg_bounce), 2) if not pd.isna(avg_bounce) else None,
        "avg_days_to_max_bounce": round(float(avg_days_max), 1) if not pd.isna(avg_days_max) else None,
        "avg_lowest_rsi": round(float(avg_lowest_rsi), 1) if not pd.isna(avg_lowest_rsi) else None,
        "avg_post_low_drawdown_pct": round(float(avg_dd), 2) if not pd.isna(avg_dd) else None,
        "avg_risk_reward": round(float(avg_rr), 2) if not pd.isna(avg_rr) else None,
        "history_score": int(round(clamp(history_score))),
    }



NEWS_POSITIVE_WORDS = [
    "beat", "beats", "upgrade", "upgraded", "raises", "raised", "record", "growth", "profit", "profits",
    "strong", "bullish", "approval", "approved", "outperform", "buy", "surge", "rallies", "rebound",
    "wins", "winner", "accelerates", "expands", "expansion", "launch", "launched", "contract", "deal"
]
NEWS_NEGATIVE_WORDS = [
    "miss", "misses", "downgrade", "downgraded", "cuts", "cut", "lawsuit", "probe", "investigation",
    "weak", "bearish", "layoffs", "recall", "decline", "falls", "slumps", "warning", "loss", "losses",
    "underperform", "sell", "debt", "concern", "concerns", "delays", "delayed", "halts", "halted"
]
CATALYST_STRONG_WORDS = [
    "earnings", "guidance", "raises guidance", "beats", "beat", "fda", "approval", "approved",
    "contract", "deal", "partnership", "acquisition", "merger", "buyout", "tender", "launch",
    "ai", "artificial intelligence", "cloud", "data center", "semiconductor", "trial", "phase 3",
    "activist", "strategic review", "spin-off", "spinoff"
]
CATALYST_MEDIUM_WORDS = [
    "upgrade", "upgraded", "price target", "outperform", "conference", "presentation", "expands",
    "expansion", "product", "analyst", "initiates", "selected", "collaboration", "award"
]


OVERREACTION_POSITIVE_WORDS = [
    "beat", "beats", "better than expected", "tops estimates", "above estimates", "raised guidance", "raises guidance",
    "maintains guidance", "reaffirms", "record revenue", "strong demand", "growth", "backlog", "contract",
    "deal", "partnership", "approval", "approved", "upgrade", "upgraded", "outperform", "ai", "cloud"
]
OVERREACTION_MISMATCH_WORDS = [
    "falls despite", "drops despite", "slumps despite", "shares fall despite", "stock falls despite",
    "selloff despite", "down despite", "profit taking", "margin concerns", "spending concerns",
    "valuation concerns", "investors worry", "overreaction", "shares slide despite"
]
OVERREACTION_RED_FLAG_WORDS = [
    "cuts guidance", "cut guidance", "lowered guidance", "lowers guidance", "misses", "missed estimates",
    "sec investigation", "investigation", "probe", "accounting", "fraud", "bankruptcy", "going concern",
    "ceo resigns", "resigns", "recall", "lawsuit", "downgrade", "downgraded", "dividend cut",
    "warns", "warning", "halts", "delayed", "delay", "weak outlook", "loss widens"
]


def _safe_news_title(item):
    """Yahoo/yfinance news shape has changed a few times, so keep this defensive."""
    if not isinstance(item, dict):
        return ""
    if item.get("title"):
        return str(item.get("title", ""))
    content = item.get("content")
    if isinstance(content, dict):
        return str(content.get("title") or content.get("headline") or "")
    return ""


def _safe_news_time(item):
    if not isinstance(item, dict):
        return None
    for key in ["providerPublishTime", "pubDate", "displayTime"]:
        value = item.get(key)
        if value:
            try:
                if isinstance(value, (int, float)):
                    return datetime.datetime.fromtimestamp(value).date()
                return pd.to_datetime(value).date()
            except Exception:
                pass
    content = item.get("content")
    if isinstance(content, dict):
        value = content.get("pubDate") or content.get("displayTime")
        if value:
            try:
                return pd.to_datetime(value).date()
            except Exception:
                return None
    return None


def _keyword_count(text: str, words: list[str]) -> int:
    return sum(1 for word in words if word in text)


def catalyst_score_from_news(headlines, dates, volume_ratio=None):
    """Scores whether recent public headlines give the stock a reason to move.

    This is intentionally lightweight: it uses Yahoo Finance headlines from yfinance,
    keyword buckets, headline recency, and volume confirmation. It is not sentiment AI
    and should be treated as a catalyst clue, not truth.
    """
    if not headlines:
        return {
            "catalyst_score": 0,
            "catalyst_label": "⚪ No catalyst",
            "catalyst_reason": "No recent headlines found.",
            "news_label": "📰 No news",
            "news_headline": "No recent Yahoo Finance headlines found.",
            "news_age_days": None,
            "news_tone": "None",
            "news_text": "",
        }

    today = datetime.date.today()
    most_recent = max(dates) if dates else None
    age_days = (today - most_recent).days if most_recent else None

    if age_days is None:
        recency_points = 15
        recency_label = "Recent"
    elif age_days <= 2:
        recency_points = 30
        recency_label = "Fresh"
    elif age_days <= 7:
        recency_points = 24
        recency_label = "Recent"
    elif age_days <= 21:
        recency_points = 14
        recency_label = "Older"
    elif age_days <= 45:
        recency_points = 7
        recency_label = "Old"
    else:
        recency_points = 0
        recency_label = "Stale"

    text = " ".join(headlines).lower()
    pos = _keyword_count(text, NEWS_POSITIVE_WORDS)
    neg = _keyword_count(text, NEWS_NEGATIVE_WORDS)
    strong = _keyword_count(text, CATALYST_STRONG_WORDS)
    medium = _keyword_count(text, CATALYST_MEDIUM_WORDS)

    strength_points = min(40, strong * 18 + medium * 9)
    if strength_points >= 30:
        strength_label = "Strong"
    elif strength_points >= 12:
        strength_label = "Medium"
    elif strength_points > 0:
        strength_label = "Light"
    else:
        strength_label = "Weak"

    if pos > neg:
        tone = "Positive"
        tone_points = 20
        tone_emoji = "🟢"
    elif neg > pos:
        tone = "Negative"
        tone_points = 0
        tone_emoji = "🔴"
    else:
        tone = "Mixed/neutral"
        tone_points = 10
        tone_emoji = "🟡"

    vr = volume_ratio or 0
    if vr >= 2.5:
        volume_points = 10
    elif vr >= 1.5:
        volume_points = 7
    elif vr >= 1.1:
        volume_points = 4
    else:
        volume_points = 0

    score = int(round(clamp(recency_points + strength_points + tone_points + volume_points)))

    if score >= 75:
        catalyst_label = f"🔥 {recency_label} / {strength_label} catalyst"
    elif score >= 50:
        catalyst_label = f"🟢 {recency_label} / {tone}"
    elif score >= 25:
        catalyst_label = f"🟡 {recency_label} / {tone}"
    else:
        catalyst_label = f"⚪ {recency_label} / weak catalyst"

    return {
        "catalyst_score": score,
        "catalyst_label": catalyst_label,
        "catalyst_reason": f"{recency_label} headline · {strength_label} catalyst keywords · {tone.lower()} tone · volume {vr:.1f}x avg" if vr else f"{recency_label} headline · {strength_label} catalyst keywords · {tone.lower()} tone",
        "news_label": f"{tone_emoji} {recency_label} / {tone}",
        "news_headline": headlines[0][:160],
        "news_age_days": age_days,
        "news_tone": tone,
        "news_text": " ".join(headlines)[:900],
    }


@st.cache_data(ttl=1800, show_spinner=False)
def get_news_snapshot(ticker: str, volume_ratio: float | None = None):
    """Returns headline snapshot plus a catalyst score. Uses Yahoo Finance via yfinance."""
    try:
        items = yf.Ticker(ticker).news or []
        headlines = []
        dates = []
        for item in items[:10]:
            title = _safe_news_title(item).strip()
            if title:
                headlines.append(title)
                d = _safe_news_time(item)
                if d:
                    dates.append(d)
        return catalyst_score_from_news(headlines, dates, volume_ratio=volume_ratio)
    except Exception:
        return {
            "catalyst_score": 0,
            "catalyst_label": "📰 News unavailable",
            "catalyst_reason": "News lookup failed or was rate-limited.",
            "news_label": "📰 News unavailable",
            "news_headline": "News lookup failed or was rate-limited.",
            "news_age_days": None,
            "news_tone": "Unavailable",
            "news_text": "",
        }



def score_price_drop(drop_pct: float, days: int) -> float:
    """Scores the size/speed of a recent selloff. drop_pct is negative for a drop."""
    try:
        d = abs(float(drop_pct))
    except Exception:
        return 0.0
    if days <= 1:
        if d >= 15: return 100.0
        if d >= 10: return 75.0
        if d >= 6: return 45.0
        return clamp((d / 6.0) * 45.0)
    if days <= 3:
        if d >= 25: return 100.0
        if d >= 15: return 78.0
        if d >= 8: return 45.0
        return clamp((d / 8.0) * 45.0)
    if d >= 30: return 100.0
    if d >= 18: return 78.0
    if d >= 10: return 45.0
    return clamp((d / 10.0) * 45.0)


def panic_shock_from_df(close: pd.Series, volume: pd.Series, lookback_days: int = 15) -> dict:
    """Finds the most meaningful recent fast selloff over 1/3/5 trading days."""
    empty = {
        "panic_shock_score": 0,
        "panic_drop_pct": None,
        "panic_drop_days": None,
        "panic_drop_date": None,
        "panic_volume_ratio": None,
        "panic_label": "⚪ No recent panic",
        "panic_reason": "No meaningful fast selloff found in the recent lookback."
    }
    if close is None or len(close.dropna()) < 30:
        return empty
    c = close.dropna().astype(float)
    v = volume.reindex(c.index).astype(float) if volume is not None else pd.Series(index=c.index, dtype=float)
    recent_idx = c.tail(lookback_days).index
    best = None
    for days in [1, 3, 5]:
        ret = (c / c.shift(days) - 1.0) * 100.0
        for idx, drop in ret.loc[ret.index.intersection(recent_idx)].dropna().items():
            if drop >= 0:
                continue
            base_score = score_price_drop(drop, days)
            # fresher panics matter more for a 1–4 week swing watchlist
            days_since = max(0, len(c) - 1 - c.index.get_loc(idx))
            recency_factor = max(0.25, 1.0 - (days_since / max(lookback_days, 1)) * 0.75)
            price_score = base_score * recency_factor
            avg_vol = v.shift(1).rolling(20).mean().loc[idx] if idx in v.index else None
            cur_vol = v.loc[idx] if idx in v.index else None
            vr = (float(cur_vol) / float(avg_vol)) if avg_vol and avg_vol > 0 and cur_vol else None
            vol_score = _volume_score_from_ratio(vr) if vr else 0
            shock_score = clamp(0.75 * price_score + 0.25 * vol_score)
            if best is None or shock_score > best["panic_shock_score"]:
                best = {
                    "panic_shock_score": int(round(shock_score)),
                    "panic_drop_pct": round(float(drop), 2),
                    "panic_drop_days": days,
                    "panic_drop_date": idx.date() if hasattr(idx, "date") else idx,
                    "panic_volume_ratio": round(float(vr), 2) if vr else None,
                    "days_since_panic": int(days_since),
                }
    if not best:
        return empty
    drop = best["panic_drop_pct"]
    days = best["panic_drop_days"]
    vr = best.get("panic_volume_ratio")
    score = best["panic_shock_score"]
    if score >= 75:
        label = f"🔴 Panic shock ({drop:.1f}%/{days}d)"
    elif score >= 45:
        label = f"🟡 Selloff shock ({drop:.1f}%/{days}d)"
    else:
        label = f"⚪ Light selloff ({drop:.1f}%/{days}d)"
    best["panic_label"] = label
    best["panic_reason"] = f"Worst recent fast selloff: {drop:.1f}% over {days} trading day(s), {best.get('days_since_panic')} trading day(s) ago" + (f", with {vr:.1f}x volume on the selloff day." if vr else ".")
    return best


def narrative_mismatch_from_news(news: dict, shock_score: float) -> dict:
    """Lightweight rules engine for: did the news look better than the selloff implied?"""
    text = str(news.get("news_text") or news.get("news_headline") or "").lower()
    if not text.strip():
        return {
            "narrative_score": 20,
            "narrative_label": "⚪ No narrative read",
            "narrative_reason": "No usable recent headline text was available, so narrative mismatch is low-confidence.",
            "red_flag_label": "⚪ No red flag scan",
            "red_flag_score_cap": 100,
        }
    pos = _keyword_count(text, OVERREACTION_POSITIVE_WORDS)
    mismatch = _keyword_count(text, OVERREACTION_MISMATCH_WORDS)
    red = _keyword_count(text, OVERREACTION_RED_FLAG_WORDS)
    tone = str(news.get("news_tone") or "").lower()
    age = news.get("news_age_days")
    fresh_bonus = 10 if age is None or age <= 7 else (4 if age <= 21 else 0)

    score = 20 + min(35, pos * 9) + min(25, mismatch * 13) + fresh_bonus
    if "positive" in tone:
        score += 10
    elif "negative" in tone:
        score -= 8
    if shock_score and shock_score >= 60 and (pos or mismatch):
        score += 10
    if red:
        score -= min(55, red * 18)
    score = int(round(clamp(score)))

    if red >= 2:
        cap = 35
        red_label = "🔴 Major red flags"
    elif red == 1:
        cap = 60
        red_label = "🟠 Possible red flag"
    else:
        cap = 100
        red_label = "🟢 No major red flags"

    if score >= 75:
        label = "🟢 Strong mismatch"
    elif score >= 50:
        label = "🟡 Possible mismatch"
    elif score >= 30:
        label = "⚪ Unclear mismatch"
    else:
        label = "🔴 News may justify drop"

    reason = f"Positive clues: {pos}; mismatch clues: {mismatch}; red flags: {red}; news tone: {news.get('news_tone', '—')}; news age: {age if age is not None else 'unknown'} days."
    return {
        "narrative_score": score,
        "narrative_label": label,
        "narrative_reason": reason,
        "red_flag_label": red_label,
        "red_flag_score_cap": cap,
    }


def overreaction_score_from_parts(shock_score, narrative_score, history_score, opportunity_remaining_score, red_flag_cap=100):
    score = clamp(
        0.30 * (shock_score or 0) +
        0.35 * (narrative_score or 0) +
        0.20 * (history_score or 0) +
        0.15 * (opportunity_remaining_score or 0)
    )
    return int(round(min(score, red_flag_cap or 100)))


# ──────────────────────────────────────────────────────────────────────────────
# V11 News Intelligence — analyst-style event classification
# ──────────────────────────────────────────────────────────────────────────────
NEWS_EARNINGS_WORDS = [
    "earnings", "quarter", "results", "eps", "revenue", "sales", "profit", "margin", "guidance", "outlook",
    "forecast", "estimates", "expectations", "miss", "beat", "beats", "tops", "raises", "cuts", "lowered"
]
NEWS_GUIDANCE_BAD_WORDS = [
    "cuts guidance", "cut guidance", "lowers guidance", "lowered guidance", "weak outlook", "warns", "warning",
    "below expectations", "disappointing guidance", "reduced outlook", "slashed forecast"
]
NEWS_GUIDANCE_GOOD_WORDS = [
    "raises guidance", "raised guidance", "lifts guidance", "boosts outlook", "above expectations", "reaffirms",
    "maintains guidance", "strong outlook", "upbeat outlook"
]
NEWS_ANALYST_WORDS = ["analyst", "upgrade", "downgrade", "price target", "initiates", "outperform", "underperform", "buy rating", "sell rating"]
NEWS_LEGAL_REG_WORDS = ["lawsuit", "probe", "investigation", "regulatory", "sec", "doj", "ftc", "antitrust", "recall", "fraud", "accounting"]
NEWS_DEAL_WORDS = ["contract", "deal", "partnership", "acquisition", "merger", "buyout", "tender", "strategic review", "spin-off", "spinoff"]
NEWS_MACRO_SECTOR_WORDS = ["sector", "industry", "market selloff", "rate", "tariff", "macro", "inflation", "valuation", "profit taking", "rotation"]
NEWS_SPENDING_MARGIN_WORDS = ["margin", "margins", "spending", "capex", "cost", "costs", "investment", "investments", "expenses"]
NEWS_DROP_WORDS = ["falls", "fall", "drops", "drop", "slumps", "slides", "tumbles", "plunges", "down"]


def _phrase_hits(text: str, phrases: list[str]) -> list[str]:
    text = (text or "").lower()
    return [phrase for phrase in phrases if phrase in text]


def _classify_event_type(text: str) -> tuple[str, str, list[str]]:
    """Return event type label, market excuse, evidence phrases from recent headlines."""
    text_l = (text or "").lower()
    evidence = []
    def add_hits(words):
        for h in _phrase_hits(text_l, words)[:5]:
            if h not in evidence:
                evidence.append(h)

    red_hits = _phrase_hits(text_l, OVERREACTION_RED_FLAG_WORDS + NEWS_GUIDANCE_BAD_WORDS + NEWS_LEGAL_REG_WORDS)
    if red_hits:
        add_hits(OVERREACTION_RED_FLAG_WORDS + NEWS_GUIDANCE_BAD_WORDS + NEWS_LEGAL_REG_WORDS)
        if any(w in text_l for w in ["guidance", "outlook", "forecast", "warn"]):
            return "🔴 Negative business event", "guidance/outlook deterioration", evidence
        if any(w in text_l for w in ["investigation", "probe", "sec", "fraud", "accounting"]):
            return "🔴 Negative business event", "legal/regulatory/accounting concern", evidence
        return "🔴 Negative business event", "fundamental red flag", evidence

    if _phrase_hits(text_l, OVERREACTION_MISMATCH_WORDS):
        add_hits(OVERREACTION_MISMATCH_WORDS)
        if _phrase_hits(text_l, NEWS_SPENDING_MARGIN_WORDS):
            add_hits(NEWS_SPENDING_MARGIN_WORDS)
            return "🟡 Mixed event", "margin/spending concern despite positives", evidence
        return "⚪ Non-fundamental selling", "selloff despite positive/mixed news", evidence

    if _phrase_hits(text_l, NEWS_GUIDANCE_GOOD_WORDS + OVERREACTION_POSITIVE_WORDS):
        add_hits(NEWS_GUIDANCE_GOOD_WORDS + OVERREACTION_POSITIVE_WORDS)
        return "🟢 Positive business event", "positive operating/catalyst news", evidence

    if _phrase_hits(text_l, NEWS_EARNINGS_WORDS):
        add_hits(NEWS_EARNINGS_WORDS)
        if _phrase_hits(text_l, NEWS_SPENDING_MARGIN_WORDS):
            add_hits(NEWS_SPENDING_MARGIN_WORDS)
            return "🟡 Mixed event", "earnings with margin/spending concern", evidence
        return "🟡 Mixed event", "earnings/results reaction", evidence

    if _phrase_hits(text_l, NEWS_ANALYST_WORDS):
        add_hits(NEWS_ANALYST_WORDS)
        if "downgrade" in text_l or "underperform" in text_l or "sell rating" in text_l:
            return "⚪ Non-fundamental selling", "analyst downgrade", evidence
        return "🟢 Positive business event", "analyst support/upgrade", evidence

    if _phrase_hits(text_l, NEWS_DEAL_WORDS):
        add_hits(NEWS_DEAL_WORDS)
        return "🟢 Positive business event", "deal/partnership/corporate action", evidence

    if _phrase_hits(text_l, NEWS_MACRO_SECTOR_WORDS):
        add_hits(NEWS_MACRO_SECTOR_WORDS)
        return "⚪ Non-fundamental selling", "sector/macro/valuation pressure", evidence

    add_hits(NEWS_POSITIVE_WORDS + NEWS_NEGATIVE_WORDS)
    return "⚪ Unclear event", "headline context unclear", evidence


def news_intelligence_from_news(news: dict, panic: dict, narrative: dict) -> dict:
    """Analyst-style interpretation of news + price reaction.

    This is a rules-based analyst read, not a guarantee. It tries to separate false panic,
    overdone bad news, appropriate selloff, and broken-story red flags.
    """
    text = str(news.get("news_text") or news.get("news_headline") or "")
    event_type, market_excuse, evidence = _classify_event_type(text)
    shock_score = _to_float(panic.get("panic_shock_score"), 0) or 0
    narrative_score = _to_float(narrative.get("narrative_score"), 0) or 0
    red_cap = narrative.get("red_flag_score_cap", 100) or 100
    red_label = narrative.get("red_flag_label", "⚪ No red flag scan")
    headline = str(news.get("news_headline") or "No headline available.")
    age = news.get("news_age_days")

    event_l = event_type.lower()
    if red_cap <= 35 or "negative business" in event_l:
        verdict = "🔴 Broken / justified risk"
        reaction = "The selloff may be fundamentally justified. Treat any bounce as higher risk until the story improves."
        intel_score = int(round(min(narrative_score, red_cap)))
    elif shock_score >= 55 and ("positive business" in event_l or "non-fundamental" in event_l) and narrative_score >= 55:
        verdict = "🟢 False panic candidate"
        reaction = "The price reaction looks more severe than the headline story. This is the type of mismatch SwingIt is built to flag."
        intel_score = int(round(clamp(0.45 * shock_score + 0.45 * narrative_score + 10)))
    elif shock_score >= 45 and "mixed event" in event_l and narrative_score >= 35:
        verdict = "🟡 Overdone bad news"
        reaction = "There are legitimate concerns, but the size or speed of the selloff may be excessive. Requires chart confirmation."
        intel_score = int(round(clamp(0.40 * shock_score + 0.45 * narrative_score + 5)))
    elif shock_score >= 45 and narrative_score < 35:
        verdict = "🟠 Selloff may be appropriate"
        reaction = "The stock sold off hard, but the headline read does not yet show enough mismatch to call it false panic."
        intel_score = int(round(clamp(0.30 * shock_score + 0.40 * narrative_score)))
    else:
        verdict = "⚪ No clear news edge"
        reaction = "There is not enough recent news/price mismatch to make the news layer a major part of the trade case."
        intel_score = int(round(clamp(0.30 * shock_score + 0.50 * narrative_score)))

    evidence_text = ", ".join(evidence[:6]) if evidence else "No strong keyword evidence found."
    age_text = f"{age} days old" if age is not None else "age unknown"
    analyst_note = (
        f"Event read: {clean_label(event_type)}. The market's excuse appears to be {market_excuse}. "
        f"Latest headline ({age_text}): {headline[:180]}. Verdict: {clean_label(verdict)} — {reaction}"
    )
    return {
        "news_intel_score": intel_score,
        "event_type": event_type,
        "market_excuse": market_excuse,
        "analyst_verdict": verdict,
        "reaction_analysis": reaction,
        "news_evidence": evidence_text,
        "analyst_note": analyst_note,
        "news_freshness": age_text,
        "red_flag_label": red_label,
    }

def confidence_from_history(event_count, recovery_rate):
    """Separate confidence from opportunity: how much evidence supports the pattern."""
    if not event_count or event_count <= 0:
        return 0, "⚪ No history"

    # Event count matters most. Consistency helps, but we do not show hit rate in the main table.
    event_component = clamp((min(event_count, 8) / 8) * 75)
    consistency_component = clamp((recovery_rate or 0) * 0.25)
    score = int(round(event_component + consistency_component))

    if event_count <= 2:
        label = f"🔴 Low ({event_count} event{'s' if event_count != 1 else ''})"
    elif event_count <= 5:
        label = f"🟡 Medium ({event_count} events)"
    else:
        label = f"🟢 High ({event_count} events)"

    return score, label


# ──────────────────────────────────────────────────────────────────────────────
# TTM Squeeze / Spring analysis
# ──────────────────────────────────────────────────────────────────────────────
def _rolling_linreg_last(values):
    """Last fitted value of a rolling linear regression window."""
    arr = pd.Series(values).dropna().to_numpy(dtype=float)
    if len(arr) < 2:
        return None
    x = list(range(len(arr)))
    try:
        slope, intercept = pd.Series(arr).pipe(lambda y: __import__("numpy").polyfit(x, y, 1))
        return float(intercept + slope * (len(arr) - 1))
    except Exception:
        return None


def compute_ttm_spring(df: pd.DataFrame) -> dict:
    """Approximate TTM Squeeze status and score for swing timing.

    Squeeze ON = Bollinger Bands are inside Keltner Channels.
    Momentum uses a common TTM-style linear-regression momentum approximation.

    V5.2 improvement: direction matters. A squeeze that fires while momentum is
    falling is labeled Fired Down instead of vague/mixed. This is meant as a
    watchlist timing clue, not a precise Thinkorswim clone.
    """
    empty = {
        "spring_score": 0,
        "spring_label": "⚪ No spring data",
        "spring_reason": "Not enough price history to calculate TTM spring setup.",
        "squeeze_on": False,
        "squeeze_recently_fired": False,
        "squeeze_bars": 0,
        "momentum_now": None,
        "momentum_trend": "Unknown",
        "momentum_3bar": "—",
        "ttm_momentum_series": pd.Series(index=df.index, dtype=float) if df is not None and not df.empty else pd.Series(dtype=float),
        "squeeze_on_series": pd.Series(index=df.index, dtype=bool) if df is not None and not df.empty else pd.Series(dtype=bool),
    }

    if df is None or df.empty or len(df) < 60:
        return empty

    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)

    length = 20
    bb_mult = 2.0
    kc_mult = 1.5

    sma = close.rolling(length).mean()
    std = close.rolling(length).std()
    upper_bb = sma + bb_mult * std
    lower_bb = sma - bb_mult * std

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(length).mean()
    kc_mid = close.ewm(span=length, adjust=False).mean()
    upper_kc = kc_mid + kc_mult * atr
    lower_kc = kc_mid - kc_mult * atr

    squeeze_on = ((lower_bb > lower_kc) & (upper_bb < upper_kc)).fillna(False)

    highest_high = high.rolling(length).max()
    lowest_low = low.rolling(length).min()
    value = close - (((highest_high + lowest_low) / 2 + sma) / 2)
    momentum = value.rolling(length).apply(lambda x: _rolling_linreg_last(x), raw=False)
    momentum_pct = (momentum / close) * 100

    valid_mom = momentum_pct.dropna()
    if valid_mom.empty:
        return empty | {"squeeze_on_series": squeeze_on, "ttm_momentum_series": momentum_pct}

    current_squeeze = bool(squeeze_on.iloc[-1])
    recent_window = squeeze_on.tail(6)
    recently_fired = bool((not current_squeeze) and recent_window.iloc[:-1].any())

    # Consecutive current squeeze bars, or the most recent completed squeeze length if it just fired.
    squeeze_bars = 0
    if current_squeeze:
        for v in reversed(squeeze_on.tolist()):
            if v:
                squeeze_bars += 1
            else:
                break
    elif recently_fired:
        prior = squeeze_on.iloc[:-1].tolist()
        for v in reversed(prior):
            if v:
                squeeze_bars += 1
            elif squeeze_bars > 0:
                break

    # Use both a 4-bar slope and a shorter 1-2 bar turn check.
    # The shorter check matters a lot on 4H charts: a setup can begin reversing
    # before the 4-bar slope has fully flipped. This keeps SwingIt from calling
    # an early 4H curl-up "Accelerating Down" simply because the broader
    # short-term trend is still negative.
    last_vals = valid_mom.tail(6).tolist()
    mom_now = float(last_vals[-1])
    mom_prev = float(last_vals[-2]) if len(last_vals) >= 2 else mom_now
    mom_2ago = float(last_vals[-3]) if len(last_vals) >= 3 else mom_prev
    mom_3ago = float(last_vals[-4]) if len(last_vals) >= 4 else mom_2ago
    slope = mom_now - mom_3ago
    one_bar_change = mom_now - mom_prev
    two_bar_change = mom_now - mom_2ago
    recent_min = min(last_vals[-6:]) if last_vals else mom_now

    improving = slope > 0 and one_bar_change >= 0
    short_turn_up = (one_bar_change > 0 and two_bar_change > 0) or (one_bar_change > 0 and mom_now > recent_min)
    worsening = slope < 0 and one_bar_change < 0 and not short_turn_up
    negative = mom_now < 0
    positive = mom_now >= 0

    if improving and negative:
        trend = "🟢 Selling fading"
    elif improving and positive:
        trend = "🟢 Momentum rising"
    elif worsening and negative:
        trend = "🔴 Down pressure increasing"
    elif worsening and positive:
        trend = "🟡 Momentum cooling"
    else:
        trend = "⚪ Flat/mixed"

    # V5.2 directional spring states.
    if recently_fired and positive and improving:
        label = "🟢 Fired Up"
        spring_score = 95
        state_note = "Squeeze released upward; momentum is positive and rising."
    elif current_squeeze and negative and improving:
        label = "🟡 Loaded & Improving"
        spring_score = 90
        state_note = "Squeeze is still on while negative momentum is improving toward zero."
    elif (not current_squeeze) and negative and (improving or short_turn_up):
        label = "🔵 Early Turn"
        spring_score = 75 if improving else 68
        state_note = "Negative momentum is beginning to curl upward; this is an early tactical turn, not full confirmation yet."
    elif current_squeeze and worsening:
        label = "🟠 Loaded but Weakening"
        spring_score = 25
        state_note = "Squeeze is on, but momentum is worsening."
    elif recently_fired and negative and worsening:
        label = "🔴 Fired Down"
        spring_score = 10
        state_note = "Squeeze released downward; sellers are accelerating."
    elif negative and worsening:
        label = "⚫ Accelerating Down"
        spring_score = 0
        state_note = "Negative momentum is expanding lower."
    elif recently_fired and positive:
        label = "🟢 Fired Up"
        spring_score = 85
        state_note = "Squeeze recently released and momentum is positive."
    elif current_squeeze:
        label = "🌀 Squeeze On"
        spring_score = 55
        state_note = "Squeeze is on, but direction is not clean yet."
    elif improving:
        label = "👀 Improving"
        spring_score = 60
        state_note = "Momentum is improving, but there is no active/recent squeeze."
    else:
        label = "⚪ Neutral"
        spring_score = 50
        state_note = "No strong spring signal right now."


    # V11.2.3 tactical curl override:
    # TTM momentum is intentionally slow, especially on 4H after a violent selloff.
    # If price/RSI are already curling up and recent lows are holding, do not keep
    # calling the tactical trigger "Accelerating Down". This better matches the
    # chart-read we care about for entries: sellers may still have the larger
    # momentum, but buyers are starting to step in on the lower timeframe.
    try:
        rsi_check = ta.momentum.RSIIndicator(close, window=14).rsi().dropna()
        recent_close = close.dropna().tail(6)
        recent_low = low.dropna().tail(8)
        if len(rsi_check) >= 5 and len(recent_close) >= 4 and len(recent_low) >= 5:
            rsi_now = float(rsi_check.iloc[-1])
            rsi_prev = float(rsi_check.iloc[-2])
            rsi_min_6 = float(rsi_check.tail(6).min())
            close_now = float(recent_close.iloc[-1])
            close_prev = float(recent_close.iloc[-2])
            close_3ago = float(recent_close.iloc[-3])
            low_last_3 = float(recent_low.tail(3).min())
            low_last_8 = float(recent_low.min())

            rsi_curling = (rsi_now > rsi_prev) or (rsi_now >= rsi_min_6 + 3)
            price_curling = (close_now > close_prev) or (close_now > close_3ago)
            lows_holding = low_last_3 >= (low_last_8 * 0.995)
            panic_area = rsi_now <= 45

            tactical_curl_up = rsi_curling and price_curling and lows_holding and panic_area
            if tactical_curl_up and label in ["⚫ Accelerating Down", "🔴 Fired Down", "🟠 Loaded but Weakening"]:
                label = "🔵 Early Turn"
                spring_score = max(int(spring_score), 68)
                state_note = (
                    "TTM momentum remains negative, but price/RSI are curling up and recent lows are holding. "
                    "This is an early tactical turn, not full confirmation yet."
                )
                trend = "🟢 Tactical curl-up"
    except Exception:
        pass

    # Small duration bonus/penalty nuance for active/recent squeeze states.
    if current_squeeze or recently_fired:
        duration_bonus = int(round(clamp((min(squeeze_bars, 12) / 12) * 5)))
        if spring_score >= 50:
            spring_score = int(round(clamp(spring_score + duration_bonus)))

    mom_3bar = " → ".join(f"{v:.2f}" for v in valid_mom.tail(3).tolist())
    reason = (
        f"{state_note} Squeeze {'ON' if current_squeeze else 'OFF'}"
        f"{' · recently fired' if recently_fired else ''} · "
        f"{squeeze_bars} squeeze bars · momentum {mom_3bar} · {trend}"
    )

    return {
        "spring_score": int(round(clamp(spring_score))),
        "spring_label": label,
        "spring_reason": reason,
        "squeeze_on": current_squeeze,
        "squeeze_recently_fired": recently_fired,
        "squeeze_bars": int(squeeze_bars),
        "momentum_now": round(mom_now, 2),
        "momentum_trend": trend,
        "momentum_3bar": mom_3bar,
        "ttm_momentum_series": momentum_pct,
        "squeeze_on_series": squeeze_on,
    }


@st.cache_data(ttl=900, show_spinner=False)
def compute_prescreen_candidate(ticker: str, profit_target: int, bounce_days: int):
    """Fast daily-only pre-screen for very large universes.

    It avoids hourly downloads and news lookups. The goal is not to produce final
    cards; it simply decides which tickers deserve the expensive deep analysis.
    """
    try:
        raw = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        df = normalize_ohlcv(raw, ticker)
        if df.empty or len(df) < 80:
            return None
        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)
        current_price = float(close.iloc[-1])
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        current_rsi = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else None
        if current_rsi is None:
            return None

        rebounds = analyze_rsi_swing_outcomes(close, rsi_series, profit_target=profit_target, bounce_days=bounce_days)
        history_score = rebounds.get("history_score", 0)
        opp_score = current_rsi_opportunity_score(current_rsi)

        valid_rsi = rsi_series.dropna()
        under_30_positions = [idx for idx, val in enumerate(rsi_series) if pd.notna(val) and val < 30]
        days_since_rsi_under_30 = None
        if under_30_positions:
            last_under_pos = under_30_positions[-1]
            days_since_rsi_under_30 = len(rsi_series) - 1 - last_under_pos

        rebound_stage_score, rebound_stage_label, _ = rebound_stage_from_series(
            close, rsi_series, 0, days_since_rsi_under_30
        )
        panic = panic_shock_from_df(close, volume, lookback_days=15)
        avg_vol_20d = float(volume.tail(20).mean()) if len(volume) else None
        current_volume = float(volume.iloc[-1]) if len(volume) else None
        volume_ratio = (current_volume / avg_vol_20d) if avg_vol_20d and avg_vol_20d > 0 and current_volume else None
        attention_score = _volume_score_from_ratio(volume_ratio)
        volume_trend_score, _, _ = volume_trend_from_series(volume)

        target_model = conservative_target_from_rebound_history(
            current_price, close, rebounds, profit_target=profit_target, bounce_days=bounce_days
        )
        opp_remaining = opportunity_remaining_from_cycle(
            current_price,
            target_model.get("cycle_low_price"),
            rebounds.get("avg_max_bounce_pct"),
            target_price=target_model.get("target_price"),
        )

        # Daily-only fast score: broad enough to keep hidden gems, strict enough to
        # avoid spending time on obvious non-candidates.
        fast_score = int(round(clamp(
            0.30 * history_score +
            0.24 * opp_score +
            0.16 * rebound_stage_score +
            0.14 * opp_remaining.get("opportunity_remaining_score", 0) +
            0.10 * panic.get("panic_shock_score", 0) +
            0.04 * attention_score +
            0.02 * volume_trend_score
        )))

        return {
            "ticker": ticker,
            "fast_score": fast_score,
            "price": round(current_price, 2),
            "current_rsi": round(current_rsi, 1),
            "history_score": history_score,
            "rebound_stage_score": int(round(rebound_stage_score)),
            "rebound_stage_label": rebound_stage_label,
            "opportunity_remaining_score": opp_remaining.get("opportunity_remaining_score", 0),
            "panic_shock_score": panic.get("panic_shock_score", 0),
            "volume_ratio": round(float(volume_ratio), 2) if volume_ratio is not None else None,
        }
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def compute_candidate(ticker: str, profit_target: int, bounce_days: int, include_news_lookup: bool = True, spring_timeframe: str = "1D"):
    try:
        raw = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        df = normalize_ohlcv(raw, ticker)
        if df.empty or len(df) < 80:
            return None

        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        sma50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()
        sma200 = ta.trend.SMAIndicator(close, window=200).sma_indicator() if len(close) >= 200 else pd.Series(index=close.index, dtype=float)

        # TTM Spring can be calculated on daily bars for swing context or hourly bars for near-term timing.
        spring_tf = spring_timeframe or "1D"
        spring_df = df
        if spring_tf == "1H":
            hourly_raw = yf.download(ticker, period="90d", interval="1h", progress=False, auto_adjust=True, threads=False)
            hourly_df = normalize_ohlcv(hourly_raw, ticker)
            if not hourly_df.empty and len(hourly_df) >= 80:
                spring_df = hourly_df
            else:
                spring_tf = "1D"
        spring = compute_ttm_spring(spring_df)

        # Tactical 4H trigger: lower timeframe confirmation for entries.
        # To keep broad scans reasonable, only calculate when the daily context is potentially watchable.
        trigger_4h = {
            "spring_score": 0,
            "spring_label": "⚪ 4H not checked",
            "spring_reason": "4H trigger is checked only for names near a watchable RSI/panic zone to keep large scans faster.",
            "momentum_3bar": "—",
            "momentum_trend": "—",
        }
        current_price = float(close.iloc[-1])
        current_rsi = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else None
        should_check_4h = current_rsi is not None and current_rsi <= 58
        opp_score = current_rsi_opportunity_score(current_rsi)
        rebounds = analyze_rsi_swing_outcomes(close, rsi_series, profit_target=profit_target, bounce_days=bounce_days)
        history_score = rebounds["history_score"]
        avg_vol_20d = float(volume.tail(20).mean()) if len(volume) else None
        current_volume = float(volume.iloc[-1]) if len(volume) else None
        volume_ratio = (current_volume / avg_vol_20d) if avg_vol_20d and avg_vol_20d > 0 and current_volume else None
        confidence_score, confidence_label = confidence_from_history(
            rebounds.get("event_count", 0),
            rebounds.get("swing_success_rate"),
        )

        # Swing Score V4 = current panic/proximity + historical rebound behavior + catalyst/news + volume confirmation.
        # This keeps the app focused on watchlist candidates: washed-out, historically bouncy, and with a reason to move.
        # News/catalyst is intentionally a smaller component so a weak headline cannot overpower poor RSI/rebound history.
        news = get_news_snapshot(ticker, volume_ratio) if include_news_lookup else {
            "catalyst_score": 0,
            "catalyst_label": "Off",
            "catalyst_reason": "Catalyst/news score is turned off.",
            "news_label": "Off",
            "news_headline": "News snapshot is turned off.",
            "news_age_days": None,
            "news_tone": "Off",
            "news_text": "",
        }
        catalyst_score = news.get("catalyst_score", 0)
        attention_score = _volume_score_from_ratio(volume_ratio)
        volume_trend_score, volume_trend_label, volume_trend_reason = volume_trend_from_series(volume)

        # Momentum proximity flags for watchlist use, not entry signals.
        # We track both:
        # - the last date RSI was <30
        # - the start date of the *current* oversold streak, if RSI is still <30 now
        days_since_rsi_under_30 = None
        last_rsi_under_30_date = None
        rsi_oversold_start_date = None

        valid_rsi = rsi_series.dropna()
        under_30_positions = [idx for idx, val in enumerate(rsi_series) if pd.notna(val) and val < 30]
        if under_30_positions:
            last_under_pos = under_30_positions[-1]
            days_since_rsi_under_30 = len(rsi_series) - 1 - last_under_pos
            try:
                last_rsi_under_30_date = rsi_series.index[last_under_pos].date()
            except Exception:
                last_rsi_under_30_date = None

        if current_rsi is not None and current_rsi < 30 and not valid_rsi.empty:
            current_label = valid_rsi.index[-1]
            current_pos = rsi_series.index.get_loc(current_label)
            start_pos = current_pos
            while start_pos > 0:
                prev_val = rsi_series.iloc[start_pos - 1]
                if pd.isna(prev_val) or prev_val >= 30:
                    break
                start_pos -= 1
            try:
                rsi_oversold_start_date = rsi_series.index[start_pos].date()
            except Exception:
                rsi_oversold_start_date = None

        if (not should_check_4h) and days_since_rsi_under_30 is not None and not pd.isna(days_since_rsi_under_30):
            should_check_4h = int(days_since_rsi_under_30) <= 45

        if should_check_4h:
            try:
                hourly_raw = yf.download(ticker, period="90d", interval="1h", progress=False, auto_adjust=True, threads=False)
                hourly_df = normalize_ohlcv(hourly_raw, ticker)
                fourh_df = resample_to_4h(hourly_df)
                if not fourh_df.empty and len(fourh_df) >= 80:
                    trigger_4h = compute_ttm_spring(fourh_df)
                else:
                    trigger_4h["spring_reason"] = "Not enough 4H history was available to calculate the tactical trigger."
            except Exception:
                trigger_4h["spring_reason"] = "4H trigger lookup failed for this ticker."

        rebound_stage_score, rebound_stage_label, rebound_stage_reason = rebound_stage_from_series(
            close, rsi_series, spring.get("spring_score", 0), days_since_rsi_under_30
        )

        # Conservative target: anchor to the most recent RSI panic low, shrink/cap tiny samples,
        # and cap against the recent pre-panic range so one huge old event cannot create an
        # unrealistic all-time-high style target.
        target_model = conservative_target_from_rebound_history(
            current_price,
            close,
            rebounds,
            profit_target=profit_target,
            bounce_days=bounce_days,
        )
        potential_sell_price = target_model.get("target_price")

        # Opportunity Remaining answers: if this is the current RSI panic cycle,
        # how much of its conservative rebound target is still left from the RSI-event low?
        recent_cycle_low_price = target_model.get("cycle_low_price")
        recent_cycle_low_date = target_model.get("cycle_low_date")

        # V10.6 fix: stabilization must be calculated BEFORE Setup Quality uses it.
        # The earlier build referenced stabilization too early, causing every candidate
        # to error inside compute_candidate() and return None, which made scans show 0 usable tickers.
        stabilization = compute_stabilization_score(
            close, volume, rsi_series, recent_cycle_low_price, recent_cycle_low_date, days_since_rsi_under_30
        )
        opp_remaining = opportunity_remaining_from_cycle(
            current_price,
            recent_cycle_low_price,
            rebounds.get("avg_max_bounce_pct"),
            target_price=target_model.get("target_price"),
        )

        # Swing Score = historical rebound candidate quality.
        # Setup Quality = right-now attention/timing quality.
        swing_score = int(round(clamp(
            0.46 * history_score +
            0.34 * opp_score +
            0.14 * catalyst_score +
            0.06 * attention_score
        )))
        setup_quality = int(round(clamp(
            0.16 * opp_score +
            0.18 * rebound_stage_score +
            0.14 * stabilization.get("stabilization_score", 0) +
            0.16 * catalyst_score +
            0.16 * spring.get("spring_score", 0) +
            0.10 * trigger_4h.get("spring_score", 0) +
            0.06 * attention_score +
            0.04 * volume_trend_score
        )))


        panic = panic_shock_from_df(close, volume, lookback_days=15)
        narrative = narrative_mismatch_from_news(news, panic.get("panic_shock_score", 0))
        news_intel = news_intelligence_from_news(news, panic, narrative)
        overreaction_score = overreaction_score_from_parts(
            panic.get("panic_shock_score", 0),
            narrative.get("narrative_score", 0),
            history_score,
            opp_remaining.get("opportunity_remaining_score", 0),
            narrative.get("red_flag_score_cap", 100),
        )
        if overreaction_score >= 75:
            overreaction_label = "🟢 Strong overreaction"
        elif overreaction_score >= 55:
            overreaction_label = "🟡 Possible overreaction"
        elif overreaction_score >= 35:
            overreaction_label = "⚪ Unclear overreaction"
        else:
            overreaction_label = "🔴 Weak overreaction"

        return {
            "ticker": ticker,
            "price": round(current_price, 2),
            "potential_sell_price": round(float(potential_sell_price), 2) if potential_sell_price is not None else None,
            "target_gain_pct_from_current": target_model.get("target_gain_pct_from_current"),
            "target_bounce_pct_from_low": target_model.get("target_bounce_pct_from_low"),
            "target_reason": target_model.get("target_reason"),
            "target_confidence": target_model.get("target_confidence"),
            "target_method": target_model.get("target_method"),
            "pre_panic_high": target_model.get("pre_panic_high"),
            "history_bounce_pct_used": target_model.get("history_bounce_pct_used"),
            "recent_damage_cap_pct": target_model.get("recent_damage_cap_pct"),
            "cycle_low_price": opp_remaining.get("cycle_low_price"),
            "cycle_low_date": recent_cycle_low_date,
            "cycle_target_price": opp_remaining.get("cycle_target_price"),
            "opportunity_remaining_pct": opp_remaining.get("opportunity_remaining_pct"),
            "opportunity_remaining_score": opp_remaining.get("opportunity_remaining_score"),
            "opportunity_remaining_label": opp_remaining.get("opportunity_remaining_label"),
            "move_completed_pct": opp_remaining.get("move_completed_pct"),
            "panic_shock_score": panic.get("panic_shock_score"),
            "panic_label": panic.get("panic_label"),
            "panic_reason": panic.get("panic_reason"),
            "panic_drop_pct": panic.get("panic_drop_pct"),
            "panic_drop_days": panic.get("panic_drop_days"),
            "panic_drop_date": panic.get("panic_drop_date"),
            "panic_volume_ratio": panic.get("panic_volume_ratio"),
            "narrative_score": narrative.get("narrative_score"),
            "narrative_label": narrative.get("narrative_label"),
            "narrative_reason": narrative.get("narrative_reason"),
            "red_flag_label": narrative.get("red_flag_label"),
            "news_intel_score": news_intel.get("news_intel_score"),
            "event_type": news_intel.get("event_type"),
            "market_excuse": news_intel.get("market_excuse"),
            "analyst_verdict": news_intel.get("analyst_verdict"),
            "reaction_analysis": news_intel.get("reaction_analysis"),
            "news_evidence": news_intel.get("news_evidence"),
            "analyst_note": news_intel.get("analyst_note"),
            "news_freshness": news_intel.get("news_freshness"),
            "overreaction_score": overreaction_score,
            "overreaction_label": overreaction_label,
            "avg_vol_20d": int(avg_vol_20d) if avg_vol_20d else None,
            "current_volume": int(current_volume) if current_volume else None,
            "volume_ratio": round(float(volume_ratio), 2) if volume_ratio is not None else None,
            "attention_score": int(round(attention_score)),
            "attention_label": attention_label_from_ratio(volume_ratio),
            "volume_trend_score": int(round(volume_trend_score)),
            "volume_trend_label": volume_trend_label,
            "volume_trend_reason": volume_trend_reason,
            "rebound_stage_score": int(round(rebound_stage_score)),
            "rebound_stage_label": rebound_stage_label,
            "rebound_stage_reason": rebound_stage_reason,
            "stabilization_score": stabilization.get("stabilization_score"),
            "stabilization_label": stabilization.get("stabilization_label"),
            "stabilization_reason": stabilization.get("stabilization_reason"),
            "days_since_panic_low": stabilization.get("days_since_panic_low"),
            "distance_from_panic_low_pct": stabilization.get("distance_from_panic_low_pct"),
            "new_low_last_3d": stabilization.get("new_low_last_3d"),
            "trigger_4h_score": trigger_4h.get("spring_score", 0),
            "trigger_4h_label": trigger_4h.get("spring_label"),
            "trigger_4h_reason": trigger_4h.get("spring_reason"),
            "trigger_4h_momentum_3bar": trigger_4h.get("momentum_3bar"),
            "trigger_4h_momentum_trend": trigger_4h.get("momentum_trend"),
            "setup_quality": setup_quality,
            "spring_timeframe": spring_tf,
            "spring_df": spring_df,
            "spring_score": spring.get("spring_score", 0),
            "spring_label": spring.get("spring_label"),
            "spring_reason": spring.get("spring_reason"),
            "squeeze_on": spring.get("squeeze_on"),
            "squeeze_recently_fired": spring.get("squeeze_recently_fired"),
            "squeeze_bars": spring.get("squeeze_bars"),
            "momentum_now": spring.get("momentum_now"),
            "momentum_trend": spring.get("momentum_trend"),
            "momentum_3bar": spring.get("momentum_3bar"),
            "ttm_momentum_series": spring.get("ttm_momentum_series"),
            "squeeze_on_series": spring.get("squeeze_on_series"),
            "catalyst_score": int(round(catalyst_score or 0)),
            "catalyst_label": news.get("catalyst_label"),
            "catalyst_reason": news.get("catalyst_reason"),
            "current_rsi": round(current_rsi, 1) if current_rsi is not None else None,
            "opportunity": opportunity_label(current_rsi),
            "opportunity_score": int(round(opp_score)),
            "history_score": history_score,
            "confidence_score": confidence_score,
            "confidence_label": confidence_label,
            "swing_score": swing_score,
            "days_since_rsi_under_30": days_since_rsi_under_30,
            "last_rsi_under_30_date": last_rsi_under_30_date,
            "rsi_oversold_start_date": rsi_oversold_start_date,
            "sma50": round(float(sma50.iloc[-1]), 2) if pd.notna(sma50.iloc[-1]) else None,
            "sma200": round(float(sma200.iloc[-1]), 2) if len(sma200) and pd.notna(sma200.iloc[-1]) else None,
            "df": df,
            "rsi_series": rsi_series,
            "sma50_series": sma50,
            "sma200_series": sma200,
            **news,
            **rebounds,
        }
    except Exception:
        return None




# ──────────────────────────────────────────────────────────────────────────────
# Ranking engine — lets the same scan answer different trader questions
# ──────────────────────────────────────────────────────────────────────────────
RANKING_MODES = [
    "🎯 8% Target Hunter",
    "⚡ Ready Now",
    "🧠 Highest Confidence",
    "🚀 Maximum Upside",
    "😱 Overreaction",
    "🧊 Stabilizing Panics",
]

RANKING_HELP = {
    "🎯 8% Target Hunter": "Ranks for the best blend of historical rebound edge, current turn-zone timing, confidence, and chance of reaching your selected profit target.",
    "⚡ Ready Now": "Ranks for names closest to a near-term trigger: strong setup quality, spring timing, RVOL/attention, fresh catalyst, and volume trend.",
    "🧠 Highest Confidence": "Ranks for the most repeatable historical pattern: more events, stronger confidence, better swing history, and cleaner risk/reward.",
    "🚀 Maximum Upside": "Ranks for the largest potential reward. This can surface more volatile names, so use confidence and drawdown carefully.",
    "😱 Overreaction": "Ranks likely overreaction selloffs: sharp price shock, possible narrative mismatch, remaining opportunity, and recovery context.",
    "🧊 Stabilizing Panics": "Ranks recent panic selloffs that appear to have stopped falling, especially when the 4H trigger is improving before the daily chart fully confirms.",
}


def _rank_num(row, col, default=0.0):
    try:
        val = row.get(col, default)
        if val is None or pd.isna(val):
            return float(default)
        return float(val)
    except Exception:
        return float(default)


def _bounce_score(avg_max_bounce, target_pct):
    """Scores how much historical upside exists relative to the user's goal."""
    try:
        b = float(avg_max_bounce)
        t = max(float(target_pct), 1.0)
    except Exception:
        return 0.0
    # Full credit around 2x the target; partial credit below target.
    return clamp((b / (t * 2.0)) * 100.0)


def _speed_score(avg_days, window_days):
    """Favors bounces that happen within the user's 1-4 week swing window."""
    try:
        d = float(avg_days)
        w = max(float(window_days), 1.0)
    except Exception:
        return 0.0
    if d <= 0:
        return 0.0
    if d <= w * 0.35:
        return 100.0
    if d <= w * 0.65:
        return 85.0
    if d <= w:
        return 65.0
    return max(0.0, 65.0 - ((d - w) / w) * 65.0)


def _risk_reward_score(rr):
    try:
        rr = float(rr)
    except Exception:
        return 35.0
    if rr <= 0:
        return 0.0
    return clamp((rr / 3.0) * 100.0)


def add_ranking_scores(frame: pd.DataFrame, target_pct: float, window_days: int) -> pd.DataFrame:
    """Adds four view-by lenses without changing the underlying scan data."""
    if frame.empty:
        return frame
    out = frame.copy()
    scores = []
    for _, row in out.iterrows():
        swing = _rank_num(row, "Swing Score")
        setup = _rank_num(row, "Setup Quality")
        spring = _rank_num(row, "Spring Score")
        confidence = _rank_num(row, "Confidence Score")
        history = _rank_num(row, "History Score")
        stage = _rank_num(row, "Rebound Stage Score")
        stabilization = _rank_num(row, "Stabilization Score")
        trigger_4h = _rank_num(row, "4H Trigger Score")
        catalyst = _rank_num(row, "Catalyst Score")
        attention = _rank_num(row, "Attention Score")
        volume_trend = _rank_num(row, "Volume Trend Score")
        opp = _rank_num(row, "Opportunity Score")
        opp_remaining = _rank_num(row, "Opportunity Remaining Score")
        overreaction = _rank_num(row, "Overreaction Score")
        shock = _rank_num(row, "Panic Shock Score")
        narrative = _rank_num(row, "Narrative Score")
        bounce = _bounce_score(_rank_num(row, "Avg Max Bounce"), target_pct)
        speed = _speed_score(_rank_num(row, "Avg Days to Max"), window_days)
        win_rate = _rank_num(row, "Win Rate")
        risk_reward = _risk_reward_score(_rank_num(row, "Risk / Reward", 1.0))

        target_hunter = clamp(
            0.22 * history +
            0.18 * bounce +
            0.14 * speed +
            0.15 * setup +
            0.12 * confidence +
            0.08 * stage +
            0.07 * opp_remaining +
            0.04 * attention
        )
        ready_now = clamp(
            0.22 * opp_remaining +
            0.20 * setup +
            0.16 * spring +
            0.14 * trigger_4h +
            0.12 * stage +
            0.08 * stabilization +
            0.04 * attention +
            0.03 * catalyst +
            0.01 * volume_trend
        )
        highest_confidence = clamp(
            0.34 * confidence +
            0.26 * history +
            0.16 * win_rate +
            0.12 * risk_reward +
            0.12 * swing
        )
        maximum_upside = clamp(
            0.36 * bounce +
            0.20 * swing +
            0.16 * opp +
            0.12 * catalyst +
            0.10 * attention +
            0.06 * spring
        )
        overreaction_rank = clamp(
            0.46 * overreaction +
            0.18 * shock +
            0.16 * narrative +
            0.10 * opp_remaining +
            0.06 * spring +
            0.04 * attention
        )
        stabilizing_panics = clamp(
            0.28 * stabilization +
            0.22 * overreaction +
            0.18 * opp_remaining +
            0.14 * trigger_4h +
            0.10 * stage +
            0.05 * attention +
            0.03 * catalyst
        )
        scores.append((target_hunter, ready_now, highest_confidence, maximum_upside, overreaction_rank, stabilizing_panics, bounce, speed))

    out["🎯 Target Hunter Score"] = [int(round(x[0])) for x in scores]
    out["⚡ Ready Now Score"] = [int(round(x[1])) for x in scores]
    out["🧠 Confidence Rank Score"] = [int(round(x[2])) for x in scores]
    out["🚀 Upside Rank Score"] = [int(round(x[3])) for x in scores]
    out["😱 Overreaction Rank Score"] = [int(round(x[4])) for x in scores]
    out["🧊 Stabilizing Panic Score"] = [int(round(x[5])) for x in scores]
    out["Target Bounce Score"] = [int(round(x[6])) for x in scores]
    out["Speed Score"] = [int(round(x[7])) for x in scores]
    return out


def ranking_column_for(mode: str) -> str:
    return {
        "🎯 8% Target Hunter": "🎯 Target Hunter Score",
        "⚡ Ready Now": "⚡ Ready Now Score",
        "🧠 Highest Confidence": "🧠 Confidence Rank Score",
        "🚀 Maximum Upside": "🚀 Upside Rank Score",
        "😱 Overreaction": "😱 Overreaction Rank Score",
        "🧊 Stabilizing Panics": "🧊 Stabilizing Panic Score",
    }.get(mode, "🎯 Target Hunter Score")


# ──────────────────────────────────────────────────────────────────────────────
# Qualified Candidate Gate — keeps the top cards from forcing weak names into view
# ──────────────────────────────────────────────────────────────────────────────
CANDIDATE_GATE_MODES = ["Balanced", "Strict", "Loose"]

CANDIDATE_GATE_HELP = {
    "Balanced": "Default. Shows stocks that are at least decent swing candidates without being too picky.",
    "Strict": "Only cleaner setups. Useful when you want fewer, higher-quality ideas.",
    "Loose": "Allows earlier/speculative setups. Useful for small Favorites lists or idea discovery.",
}


def _text_has_any(value, words):
    text = str(value or "").lower()
    return any(w.lower() in text for w in words)


def has_major_red_flag(row):
    return _text_has_any(row.get("Red Flags", ""), ["major red", "possible red flag"])


def is_extended_stage(row):
    return _text_has_any(row.get("Rebound Stage", ""), ["extended"])


def is_bad_spring(row):
    return _text_has_any(row.get("Spring", ""), ["fired down", "accelerating down", "weakening"])


def qualifies_as_candidate(row, gate_mode="Balanced"):
    """Return (qualifies, reason) for whether a ticker deserves a Top Opportunity card.

    The card grid should not force 10 names if the selected universe only has a few
    legitimate swing candidates. This gate is intentionally separate from View By:
    View By ranks candidates; this gate decides whether a stock belongs in the cards.
    """
    swing = _rank_num(row, "Swing Score")
    setup = _rank_num(row, "Setup Quality")
    opp_remaining = _rank_num(row, "Opportunity Remaining %")
    opp_remaining_score = _rank_num(row, "Opportunity Remaining Score")
    rsi = _rank_num(row, "RSI", 999)
    overreaction = _rank_num(row, "Overreaction Score")
    spring_score = _rank_num(row, "Spring Score")
    stage_score = _rank_num(row, "Rebound Stage Score")
    confidence = _rank_num(row, "Confidence Score")
    history = _rank_num(row, "History Score")

    # Fall back to the score if the percent is unavailable.
    if opp_remaining <= 0 and opp_remaining_score > 0:
        opp_remaining = opp_remaining_score

    bad_stage = is_extended_stage(row)
    bad_spring = is_bad_spring(row)
    red_flag = has_major_red_flag(row)

    if gate_mode == "Strict":
        core = swing >= 70 and opp_remaining >= 45 and rsi <= 50 and not bad_stage and history >= 55 and confidence >= 45
        ready = setup >= 78 and opp_remaining >= 40 and not bad_spring and stage_score >= 55 and spring_score >= 45
        over = overreaction >= 78 and opp_remaining >= 50 and not red_flag
    elif gate_mode == "Loose":
        core = swing >= 50 and opp_remaining >= 25 and rsi <= 60 and not bad_stage
        ready = setup >= 60 and opp_remaining >= 20 and not bad_spring
        over = overreaction >= 55 and opp_remaining >= 25 and not red_flag
    else:  # Balanced
        core = swing >= 60 and opp_remaining >= 35 and rsi <= 55 and not bad_stage
        ready = setup >= 70 and opp_remaining >= 30 and not bad_spring
        over = overreaction >= 70 and opp_remaining >= 40 and not red_flag

    if core:
        return True, "Core swing candidate"
    if ready:
        return True, "Ready-now candidate"
    if over:
        return True, "Overreaction candidate"
    return False, "Did not pass candidate gate"


def apply_candidate_gate(frame: pd.DataFrame, gate_mode="Balanced") -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    gate_results = out.apply(lambda row: qualifies_as_candidate(row, gate_mode), axis=1)
    out["Candidate Gate"] = [x[0] for x in gate_results]
    out["Candidate Type"] = [x[1] for x in gate_results]
    return out[out["Candidate Gate"]].copy()


# ──────────────────────────────────────────────────────────────────────────────
# Visual helpers
# ──────────────────────────────────────────────────────────────────────────────
def format_pct(value):
    return "—" if value is None or pd.isna(value) else f"{value:.1f}%"


def candidate_note(row):
    rsi = row.get("current_rsi")
    bounce = row.get("avg_max_bounce_pct")
    days = row.get("avg_days_to_max_bounce")
    events = row.get("event_count")
    pieces = []
    if rsi is not None:
        pieces.append(f"RSI {rsi}")
    if bounce is not None:
        pieces.append(f"avg max bounce {bounce:.1f}%")
    if days is not None:
        pieces.append(f"~{days:.0f} days to max")
    if events:
        pieces.append(f"{events} events")
    return " · ".join(pieces)


def _safe_html(value):
    return html.escape("—" if value is None or pd.isna(value) else str(value))


def clean_label(value):
    text = "—" if value is None or pd.isna(value) else str(value)
    for token in ["🔥", "👀", "😴", "🟢", "🟡", "🔴", "⚪", "⚫", "🔵", "🟠", "📰"]:
        text = text.replace(token, "")
    return " ".join(text.split()).strip() or "—"


def dot_class(value):
    text = clean_label(value).lower()

    # Numeric context first — this lets card rows like "3.6x RVOL",
    # "+8.88% in 16d", "100% remaining", and "10 events" color correctly.
    pct_match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if pct_match:
        pct = float(pct_match.group(1))
        if "remaining" in text:
            if pct >= 70:
                return "dot-green"
            if pct >= 40:
                return "dot-yellow"
            if pct >= 20:
                return "dot-yellow"
            return "dot-red"
        # Potential / bounce percent
        if pct >= 8:
            return "dot-green"
        if pct >= 5:
            return "dot-yellow"
        if pct > 0:
            return "dot-gray"
        return "dot-red"

    rvol_match = re.search(r"(\d+(?:\.\d+)?)\s*x", text)
    if rvol_match:
        rvol = float(rvol_match.group(1))
        if rvol >= 1.5:
            return "dot-green"
        if rvol >= 1.0:
            return "dot-yellow"
        if rvol >= 0.8:
            return "dot-gray"
        return "dot-red"

    events_match = re.search(r"(\d+)\s*events?", text)
    if events_match:
        events = int(events_match.group(1))
        if events >= 6:
            return "dot-green"
        if events >= 3:
            return "dot-yellow"
        if events >= 1:
            return "dot-red"
        return "dot-gray"

    # Analyst verdict labels
    if "prime candidate" in text:
        return "dot-green"
    if "watch closely" in text:
        return "dot-yellow"
    if "too early" in text:
        return "dot-yellow"
    if "recovery underway" in text or "too late" in text:
        return "dot-red"
    if "avoid" in text:
        return "dot-red"

    # Market Read / News Intelligence verdicts
    if "false panic" in text:
        return "dot-green"
    if "overdone" in text or "possible overreaction" in text:
        return "dot-yellow"
    if "fundamental damage" in text or "broken story" in text or "likely appropriate" in text:
        return "dot-red"
    if "no clear news" in text or "no meaningful" in text or "unclear event" in text:
        return "dot-gray"

    if any(w in text for w in [
        "high", "positive", "fresh", "fired up", "loaded & improving",
        "building fast", "building", "improving", "oversold", "turn zone",
        "very early", "early reversal"
    ]):
        return "dot-green"
    if any(w in text for w in [
        "negative", "fired down", "accelerating down", "falling", "weakening",
        "fading", "low", "extended"
    ]):
        return "dot-red"
    if any(w in text for w in [
        "medium", "watch", "neutral", "early", "mixed", "recent", "panic",
        "developing", "slight build", "flat"
    ]):
        return "dot-yellow"
    return "dot-gray"


def hover_item(title, value, tip, dot=False):
    safe_title = _safe_html(title)
    safe_value = _safe_html(clean_label(value))
    safe_tip = tip if isinstance(tip, str) else _safe_html(tip)
    dot_html = f"<span class='dot {dot_class(value)}'></span>" if dot else ""
    return (
        f"<div class='card-item hover-tip'>"
        f"{dot_html}<span class='item-title'>{safe_title}:</span> "
        f"<span class='card-value'>{safe_value}</span>"
        f"<div class='tip-box'>{safe_tip}</div>"
        f"</div>"
    )

def _numeric_from_row(row, key, default=0):
    try:
        value = row.get(key, default)
        if value in [None, "", "—"] or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def analyst_verdict_from_row(row):
    """V11.2.1: translate all SwingIt evidence into a calibrated analyst-style action label.

    Calibration goal:
    - ORCL-style false-panic setups should be eligible for Prime Candidate.
    - A weak 1D spring alone should NOT mean Avoid.
    - Avoid should be rare and reserved for clear fundamental/news damage or red flags.
    """
    market_read = clean_label(row.get("Analyst Verdict", "")).lower()
    event_type = clean_label(row.get("Event Type", "")).lower()
    red_flags = clean_label(row.get("Red Flags", "")).lower()
    daily_spring = clean_label(row.get("Spring", "")).lower()
    trigger_4h = clean_label(row.get("4H Trigger", "")).lower()
    stabilization = clean_label(row.get("Stabilization", "")).lower()
    rebound_stage = clean_label(row.get("Rebound Stage", "")).lower()
    news_note = clean_label(row.get("Analyst Note", "")).lower()

    swing = _numeric_from_row(row, "Swing Score")
    setup = _numeric_from_row(row, "Setup Quality")
    spring_score = _numeric_from_row(row, "Spring Score")
    overreaction = _numeric_from_row(row, "Overreaction Score")
    remaining = _numeric_from_row(row, "Opportunity Remaining %")
    stab_score = _numeric_from_row(row, "Stabilization Score")
    trigger_score = _numeric_from_row(row, "4H Trigger Score")
    news_score = _numeric_from_row(row, "Market Read Score")
    confidence_score = _numeric_from_row(row, "Confidence Score")
    rsi = _numeric_from_row(row, "RSI", 50)

    # Only true story-breaking items should produce Avoid.
    hard_red_flag_terms = [
        "fraud", "sec investigation", "accounting", "bankruptcy", "liquidity",
        "going concern", "guidance cut", "cuts guidance", "lowered guidance",
        "suspension", "delisting", "criminal", "lawsuit risk"
    ]
    has_hard_red_flag = any(x in red_flags for x in hard_red_flag_terms) or any(x in news_note for x in hard_red_flag_terms)
    fundamental_damage = any(x in market_read for x in ["fundamental damage", "broken"]) or any(x in event_type for x in ["negative business event"])
    justified_risk = "justified" in market_read and overreaction < 70 and news_score < 55

    false_panic = any(x in market_read for x in ["false panic", "overdone", "possible overreaction"])
    positive_story = any(x in event_type for x in ["positive business event", "mixed event", "non-fundamental"])

    too_late = remaining < 25
    extended = ("extended" in rebound_stage) or rsi >= 63
    short_turn = trigger_score >= 65 or any(x in trigger_4h for x in ["fired up", "improving", "early turn", "loaded"])
    stable = stab_score >= 65 or any(x in stabilization for x in ["stabilizing", "high", "strong", "possible stabilization"])
    daily_bad = any(x in daily_spring for x in ["accelerating down", "fired down"])
    daily_ok = not daily_bad or spring_score >= 35

    # ORCL-style setup: good/mixed story + ugly selloff + enough room left + at least some timing evidence.
    prime_like_orcl = (
        (false_panic or positive_story or news_score >= 65)
        and overreaction >= 65
        and remaining >= 50
        and setup >= 55
        and (stable or short_turn)
        and not has_hard_red_flag
        and not (fundamental_damage and news_score < 55)
    )

    if has_hard_red_flag or (fundamental_damage and news_score < 45 and overreaction < 70):
        verdict = "🚨 Avoid"
        confidence = "High" if has_hard_red_flag or news_score >= 50 else "Moderate"
        summary = "The decline appears tied to meaningful business or headline damage. Treat technical rebound signals cautiously until the underlying story improves."
    elif too_late or extended:
        verdict = "😴 Recovery Underway"
        confidence = "High" if remaining < 20 else "Moderate"
        summary = "The rebound has already progressed substantially. Momentum may still be positive, but much of the usual historical opportunity appears captured."
    elif prime_like_orcl and (short_turn or stab_score >= 75) and not (daily_bad and trigger_score < 70):
        verdict = "🔥 Prime Candidate"
        confidence = "High" if confidence_score >= 70 and news_score >= 60 and (stable and short_turn) else "Moderate"
        summary = "This has the ORCL-style profile we like: the selloff may be overdone, the opportunity is still meaningful, and stabilization or lower-timeframe buying is beginning to show."
    elif (false_panic or overreaction >= 60 or swing >= 65 or setup >= 65) and remaining >= 35 and (stable or short_turn or rsi <= 40):
        verdict = "👀 Watch Closely"
        confidence = "High" if confidence_score >= 70 and (stable or short_turn) else "Moderate"
        if daily_bad and short_turn:
            summary = "The short-term setup is improving while the daily trend is still damaged. This is worth watching closely, but daily confirmation is not here yet."
        else:
            summary = "The panic may be ending and the setup has enough remaining upside to deserve attention, but one or more confirmations are still missing."
    elif (overreaction >= 55 or swing >= 60 or setup >= 55 or rsi <= 35) and remaining >= 30:
        verdict = "⏳ Too Early"
        confidence = "Moderate"
        summary = "The idea is interesting, but timing is still immature. Let selling pressure exhaust and wait for stabilization or a cleaner 4H trigger."
    elif justified_risk:
        verdict = "🚨 Avoid"
        confidence = "Moderate"
        summary = "The market's reaction may be justified by the headline or business context. This is not a clean false-panic setup yet."
    else:
        verdict = "⚪ No Clear Edge"
        confidence = "Low"
        summary = "The current evidence does not show a strong swing-trade edge yet. Keep it in the table, but it does not deserve top-card attention on its own."

    details = (
        f"Swing: {swing:.0f}/100 · Setup: {setup:.0f}/100 · Overreaction: {overreaction:.0f}/100 · "
        f"Stabilization: {stab_score:.0f}/100 · 4H Trigger: {trigger_score:.0f}/100 · "
        f"Daily Spring: {spring_score:.0f}/100 · Opportunity remaining: {remaining:.0f}% · "
        f"Market Read: {clean_label(row.get('Analyst Verdict', '—'))}"
    )
    return verdict, confidence, summary, details

def _volume_score_from_ratio(volume_ratio):
    vr = volume_ratio or 0
    if vr >= 2.5:
        return 100
    if vr >= 1.5:
        return 70
    if vr >= 1.1:
        return 40
    return 0


def attention_label_from_ratio(volume_ratio):
    vr = volume_ratio or 0
    if vr >= 3.0:
        return f"🔥 {vr:.1f}x RVOL"
    if vr >= 2.0:
        return f"🟢 {vr:.1f}x RVOL"
    if vr >= 1.1:
        return f"🟡 {vr:.1f}x RVOL"
    if vr > 0:
        return f"😴 {vr:.1f}x RVOL"
    return "⚪ RVOL n/a"



def volume_trend_from_series(volume):
    """Scores whether volume interest is building over the last week."""
    if volume is None or len(volume.dropna()) < 15:
        return 0, "⚪ Volume trend n/a", "Not enough volume history to calculate a volume trend."
    v = volume.dropna().astype(float)
    recent_5 = float(v.tail(5).mean())
    prior_20 = float(v.iloc[-25:-5].mean()) if len(v) >= 25 else float(v.iloc[:-5].mean())
    if not prior_20 or pd.isna(prior_20):
        return 0, "⚪ Volume trend n/a", "Not enough prior volume history to compare against."
    ratio = recent_5 / prior_20
    if ratio >= 1.8:
        score, label = 100, f"🟢 Building fast ({ratio:.1f}x)"
    elif ratio >= 1.35:
        score, label = 80, f"🟢 Building ({ratio:.1f}x)"
    elif ratio >= 1.05:
        score, label = 55, f"🟡 Slight build ({ratio:.1f}x)"
    elif ratio >= 0.8:
        score, label = 35, f"⚪ Flat ({ratio:.1f}x)"
    else:
        score, label = 10, f"🔴 Fading ({ratio:.1f}x)"
    reason = f"Average volume over the last 5 trading days is {ratio:.2f}x the prior baseline. This asks whether interest is building, not just whether today's volume is high."
    return int(score), label, reason


def hot_card(rank, row):
    rank_label = f"#{rank + 1}"
    ticker = _safe_html(row.get("Ticker"))
    company = clean_label(row.get("Company", ""))
    company_html = f"<span class='company-name'>{_safe_html(company)}</span>" if company and company != "—" else ""

    analyst_action, analyst_confidence, analyst_summary, analyst_details = analyst_verdict_from_row(row)

    swing_score = row.get("Swing Score", "—")
    setup_quality = row.get("Setup Quality", "—")
    spring_score = row.get("Spring Score", "—")

    current_price = row.get("Price", "—")
    potential_price = row.get("Potential Swing Price", "—")
    target_gain_pct = row.get("Target Gain %", None)
    cycle_low_price = row.get("Cycle Low Price", "—")
    cycle_low_date = row.get("Cycle Low Date", "—")
    cycle_target_price = row.get("Cycle Target Price", "—")
    opportunity_remaining = row.get("Opportunity Remaining", "—")
    overreaction = row.get("Overreaction", "—")
    overreaction_score = row.get("Overreaction Score", "—")
    panic_shock = row.get("Panic Shock", "—")
    panic_shock_score = row.get("Panic Shock Score", "—")
    panic_reason = _safe_html(row.get("Panic Reason", "No panic-shock details available."))
    narrative = row.get("Narrative", "—")
    narrative_score = row.get("Narrative Score", "—")
    narrative_reason = _safe_html(row.get("Narrative Reason", "No narrative details available."))
    red_flags = row.get("Red Flags", "—")
    opportunity_remaining_pct = row.get("Opportunity Remaining %", "—")
    opportunity_remaining_score = row.get("Opportunity Remaining Score", "—")
    move_completed_pct = row.get("Move Completed %", "—")
    avg_max = row.get("Avg Max Bounce", "—")
    avg_days = row.get("Avg Days to Max", "—")
    rsi = row.get("RSI", "—")
    oversold_since = row.get("Oversold Since", None)
    last_under_30_date = row.get("Last RSI <30 Date", None)
    days_since_under_30 = row.get("Days Since RSI <30", None)
    history = row.get("History", "—")
    confidence = row.get("Confidence", "—")
    opportunity = row.get("Opportunity", "—")
    rebound_stage = row.get("Rebound Stage", "—")
    rebound_stage_score = row.get("Rebound Stage Score", "—")
    rebound_stage_reason = _safe_html(row.get("Rebound Stage Reason", "No rebound stage details available."))
    stabilization = row.get("Stabilization", "—")
    stabilization_score = row.get("Stabilization Score", "—")
    stabilization_reason = _safe_html(row.get("Stabilization Reason", "No stabilization details available."))
    trigger_4h = row.get("4H Trigger", "—")
    trigger_4h_score = row.get("4H Trigger Score", "—")
    trigger_4h_reason = _safe_html(row.get("4H Trigger Reason", "No 4H trigger details available."))
    attention = row.get("Attention", "—")
    volume_trend = row.get("Volume Trend", "—")
    volume_trend_score = row.get("Volume Trend Score", "—")
    volume_trend_reason = _safe_html(row.get("Volume Trend Reason", "No volume trend details available."))
    catalyst = row.get("Catalyst", "—")
    spring = row.get("Spring", "—")
    spring_tf = row.get("Spring TF", "—")
    institution = row.get("Institution", "—")
    sources = row.get("Sources", "—")
    institution_score = row.get("Institution Score", 0)

    history_score = row.get("History Score", "—")
    opp_score = row.get("Opportunity Score", "—")
    catalyst_score = row.get("Catalyst Score", "—")
    volume_ratio = row.get("Volume Ratio")
    attention_score = row.get("Attention Score", _volume_score_from_ratio(volume_ratio))
    spring_reason = _safe_html(row.get("Spring Reason", "No spring details available."))
    catalyst_reason = _safe_html(row.get("Catalyst Reason", "No catalyst details available."))
    headline = _safe_html(row.get("Headline", "No headline available."))
    news = _safe_html(row.get("News", ""))
    event_type = row.get("Event Type", "⚪ Unclear event")
    market_excuse = row.get("Market Excuse", "headline context unclear")
    analyst_verdict = row.get("Analyst Verdict", "⚪ No clear news edge")
    news_intel_score = row.get("News Intel Score", "—")
    reaction_analysis = _safe_html(row.get("Reaction Analysis", "No reaction analysis available."))
    news_evidence = _safe_html(row.get("News Evidence", "No keyword evidence available."))
    analyst_note = _safe_html(row.get("Analyst Note", "No analyst note available."))
    news_freshness = _safe_html(row.get("News Freshness", "age unknown"))

    analyst_tip = f"""
        <strong>Analyst Verdict</strong><br>
        Verdict: {_safe_html(clean_label(analyst_action))}<br>
        Confidence: {_safe_html(analyst_confidence)}<br><br>
        <strong>Why</strong><br>
        {_safe_html(analyst_summary)}<br><br>
        <strong>Evidence snapshot</strong><br>
        {_safe_html(analyst_details)}
    """

    swing_tip = f"""
        <strong>Swing Score</strong><br>
        This asks: is this historically a good RSI panic rebound candidate?<br><br>
        Historical swing behavior: {history_score}/100 × 46%<br>
        Current RSI opportunity: {opp_score}/100 × 34%<br>
        Catalyst/news: {catalyst_score}/100 × 14%<br>
        Attention/RVOL: {attention_score}/100 × 6%
    """
    setup_tip = f"""
        <strong>Setup Quality</strong><br>
        This asks: is this worth opening in ThinkorSwim right now?<br><br>
        RSI opportunity: {opp_score}/100 × 20%<br>
        Rebound stage: {rebound_stage_score}/100 × 18%<br>
        Stabilization: {stabilization_score}/100 × 14%<br>
        Catalyst/news: {catalyst_score}/100 × 16%<br>
        Daily TTM Spring: {spring_score}/100 × 16%<br>
        4H Trigger: {trigger_4h_score}/100 × 10%<br>
        Attention/RVOL: {attention_score}/100 × 6%<br>
        Volume trend: {volume_trend_score}/100 × 4%
    """
    spring_score_tip = f"""
        <strong>Spring Score</strong><br>
        Timeframe: {_safe_html(spring_tf)}<br>
        Spring Score: {spring_score}/100<br><br>
        {spring_reason}
    """
    price_tip = f"""
        <strong>Price / target</strong><br>
        Current close: {_safe_html(current_price)}<br>
        Conservative swing target: {_safe_html(potential_price)}<br>
        Cycle target from RSI panic low: {_safe_html(cycle_target_price)}<br>
        Target confidence: {_safe_html(row.get("Target Confidence", "—"))}<br><br>
        {_safe_html(row.get("Target Reason", "Target is anchored to the current RSI panic low and capped to reduce single-event outliers."))}
    """
    remaining_tip = f"""
        <strong>Opportunity remaining</strong><br>
        {_safe_html(clean_label(opportunity_remaining))}<br>
        Score: {_safe_html(opportunity_remaining_score)}/100<br><br>
        RSI panic low: {_safe_html(cycle_low_price)} on {_safe_html(cycle_low_date)}<br>
        Current price: {_safe_html(current_price)}<br>
        Cycle target: {_safe_html(cycle_target_price)}<br>
        Move completed: {_safe_html(move_completed_pct)}%<br><br>
        This estimates how much of the stock's usual post-RSI-panic move may still be left. It helps avoid names that already made most of their historical rebound.
    """
    if oversold_since not in [None, "", "—"] and not pd.isna(oversold_since):
        oversold_line = f"RSI became oversold this streak: {_safe_html(oversold_since)}"
    elif last_under_30_date not in [None, "", "—"] and not pd.isna(last_under_30_date):
        oversold_line = f"Last RSI &lt;30 date: {_safe_html(last_under_30_date)}"
        if days_since_under_30 not in [None, "", "—"] and not pd.isna(days_since_under_30):
            oversold_line += f" ({_safe_html(days_since_under_30)} trading days ago)"
    else:
        oversold_line = "No RSI &lt;30 date found in the current lookback."

    rsi_tip = f"""
        <strong>RSI opportunity</strong><br>
        Current RSI: {_safe_html(rsi)}<br>
        Opportunity label: {_safe_html(clean_label(opportunity))}<br>
        {oversold_line}<br><br>
        This helps you compare the current selloff age against the stock's average days to max rebound. Lower RSI can be powerful, but it is not an entry signal by itself.
    """
    bounce_tip = f"""
        <strong>Conservative target / historical bounce</strong><br>
        Target gain from current: {_safe_html(row.get("Target Gain %", "—"))}%<br>
        Target confidence: {_safe_html(row.get("Target Confidence", "—"))}<br>
        Target method: {_safe_html(row.get("Target Method", "—"))}<br><br>
        Historical avg max bounce: {_safe_html(avg_max)}%<br>
        Avg days to max bounce: {_safe_html(avg_days)} trading days<br><br>
        {_safe_html(row.get("Target Reason", "Target is anchored to the current RSI panic low and capped to reduce single-event outliers."))}
    """

    stage_tip = f"""
        <strong>Rebound stage</strong><br>
        {_safe_html(clean_label(rebound_stage))}: {rebound_stage_score}/100<br><br>
        {rebound_stage_reason}<br><br>
        The ideal zone for this app is often Early Reversal: recently oversold, RSI rising, and price starting to lift from the low.
    """
    stabilization_tip = f"""
        <strong>Stabilization</strong><br>
        {_safe_html(clean_label(stabilization))}: {stabilization_score}/100<br><br>
        {stabilization_reason}<br><br>
        This asks whether the panic appears to have stopped falling before the daily chart fully confirms — your WLTH-style watch zone.
    """
    trigger_4h_tip = f"""
        <strong>4H trigger</strong><br>
        {_safe_html(clean_label(trigger_4h))}: {trigger_4h_score}/100<br><br>
        {trigger_4h_reason}<br><br>
        This is the tactical lower-timeframe check: daily may show the setup, while 4H can show whether buyers are starting to step in.
    """
    history_tip = f"""
        <strong>Sample size</strong><br>
        { _safe_html(history) } were found in the lookback period.<br><br>
        More events means the pattern is easier to trust. One event is interesting, not proof.
    """
    attention_tip = f"""
        <strong>Attention / RVOL</strong><br>
        Relative volume: {_safe_html(clean_label(attention))}<br>
        Attention score: {attention_score}/100<br><br>
        This asks whether the market is actually paying attention right now.
    """
    volume_trend_tip = f"""
        <strong>Volume trend</strong><br>
        {_safe_html(clean_label(volume_trend))}: {volume_trend_score}/100<br><br>
        {volume_trend_reason}
    """
    news_tip = f"""
        <strong>Market Read</strong><br>
        Event type: {_safe_html(clean_label(event_type))}<br>
        Market's excuse: {_safe_html(market_excuse)}<br>
        Analyst verdict: {_safe_html(clean_label(analyst_verdict))}<br>
        News intelligence score: {_safe_html(news_intel_score)}/100<br>
        Freshness: {news_freshness}<br><br>
        <strong>Reaction analysis</strong><br>
        {reaction_analysis}<br><br>
        <strong>Evidence clues</strong><br>
        {news_evidence}<br><br>
        <strong>Top headline</strong><br>
        {headline}<br><br>
        <strong>Catalyst score detail</strong><br>
        {catalyst_reason}<br><br>
        
    """
    overreaction_tip = f"""
        <strong>Overreaction</strong><br>
        Score: {_safe_html(overreaction_score)}/100<br><br>
        <strong>Panic shock</strong><br>
        {_safe_html(clean_label(panic_shock))}: {_safe_html(panic_shock_score)}/100<br>
        {panic_reason}<br><br>
        <strong>Narrative mismatch</strong><br>
        {_safe_html(clean_label(narrative))}: {_safe_html(narrative_score)}/100<br>
        {narrative_reason}<br><br>
        Red flag scan: {_safe_html(clean_label(red_flags))}
    """
    confidence_tip = f"""
        <strong>Confidence</strong><br>
        {_safe_html(clean_label(confidence))}<br><br>
        Confidence is mainly based on the number of historical RSI panic events. It is separate from how attractive the setup looks.
    """
    institution_tip = f"""
        <strong>Institutional presence</strong><br>
        {_safe_html(clean_label(institution))}<br>
        Score: {institution_score}/100<br><br>
        <strong>Included in</strong><br>
        {_safe_html(sources)}<br><br>
        This does not make a trade good by itself. It simply tells you whether the setup is appearing in a stock that belongs to higher-quality index/ETF-style universes.
    """

    return f"""
    <div class="hot-card">
        <div class="hot-title">{rank_label} {ticker}{company_html}</div>
        <div class="analyst-verdict-box hover-tip">
            <div class="verdict-line"><span class="dot {dot_class(analyst_action)}"></span>{_safe_html(clean_label(analyst_action))}<span class="verdict-confidence">Confidence: {_safe_html(analyst_confidence)}</span></div>
            <div class="verdict-summary">{_safe_html(analyst_summary)}</div>
            <div class="tip-box">{analyst_tip}</div>
        </div>
        <div class="score-row">
            <div class="score-tile hover-tip"><div class="score-num">{swing_score}</div><div class="score-label">Swing</div><div class="tip-box">{swing_tip}</div></div>
            <div class="score-tile hover-tip"><div class="score-num">{setup_quality}</div><div class="score-label">Setup</div><div class="tip-box">{setup_tip}</div></div>
            <div class="score-tile hover-tip"><div class="score-num">{spring_score}</div><div class="score-label">Spring</div><div class="tip-box">{spring_score_tip}</div></div>
        </div>
        <div class="hot-meta">
            {hover_item('Price', f'{current_price} → {potential_price}', price_tip, dot=True)}
            {hover_item('RSI', f'{rsi} · {clean_label(opportunity)}', rsi_tip, dot=True)}
            {hover_item('Stage', clean_label(rebound_stage), stage_tip, dot=True)}
            {hover_item('Stabilization', clean_label(stabilization), stabilization_tip, dot=True)}
            {hover_item('4H Trigger', clean_label(trigger_4h), trigger_4h_tip, dot=True)}
            {hover_item('Potential', (f'+{target_gain_pct}% to target' if target_gain_pct is not None and not pd.isna(target_gain_pct) else f'+{avg_max}% in {avg_days}d avg'), bounce_tip, dot=True)}
            {hover_item('Remaining', clean_label(opportunity_remaining), remaining_tip, dot=True)}
            {hover_item('Overreaction', clean_label(overreaction), overreaction_tip, dot=True)}
            {hover_item('History', history, history_tip, dot=True)}
            {hover_item('Attention', clean_label(attention), attention_tip, dot=True)}
            {hover_item('Volume trend', clean_label(volume_trend), volume_trend_tip, dot=True)}
            {hover_item('Spring', f'{spring_tf} · {clean_label(spring)}', spring_score_tip, dot=True)}
            {hover_item('Market Read', f'{clean_label(event_type)} · {clean_label(analyst_verdict)}', news_tip, dot=True)}
            {hover_item('Confidence', clean_label(confidence), confidence_tip, dot=True)}
            {hover_item('Institution', clean_label(institution), institution_tip, dot=True)}
        </div>
    </div>
    """

def mini_chart(data):
    df = data["df"].copy()
    dates = df.index
    close = df["Close"].astype(float)
    spring_df = data.get("spring_df", df).copy() if data.get("spring_df") is not None else df.copy()
    spring_dates = spring_df.index

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=False,
        row_heights=[0.56, 0.24, 0.20],
        vertical_spacing=0.05,
        subplot_titles=("Price + moving averages", "RSI (14)", f"TTM momentum + squeeze dots ({data.get('spring_timeframe', '1D')})"),
    )

    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing_fillcolor="#16803c",
            decreasing_fillcolor="#b42318",
            increasing_line_color="#16803c",
            decreasing_line_color="#b42318",
        ),
        row=1,
        col=1,
    )

    if data.get("sma50_series") is not None:
        fig.add_trace(go.Scatter(x=dates, y=data["sma50_series"], name="SMA 50", line=dict(color="#2563eb", width=1.5)), row=1, col=1)
    if data.get("sma200_series") is not None:
        fig.add_trace(go.Scatter(x=dates, y=data["sma200_series"], name="SMA 200", line=dict(color="#b7791f", width=1.5)), row=1, col=1)

    fig.add_trace(go.Scatter(x=dates, y=data["rsi_series"], name="RSI", line=dict(color="#7c3aed", width=1.7)), row=2, col=1)
    fig.add_hline(y=70, line=dict(color="#b42318", dash="dot", width=1), row=2, col=1)
    fig.add_hline(y=50, line=dict(color="#64748b", dash="dot", width=1), row=2, col=1)
    fig.add_hline(y=30, line=dict(color="#16803c", dash="dot", width=1), row=2, col=1)


    ttm_mom = data.get("ttm_momentum_series")
    squeeze_series = data.get("squeeze_on_series")
    if ttm_mom is not None and not ttm_mom.dropna().empty:
        mom = ttm_mom.reindex(spring_dates)
        fig.add_trace(
            go.Bar(x=spring_dates, y=mom, name="TTM momentum", marker_color=["#16803c" if (pd.notna(v) and v >= 0) else "#b42318" for v in mom], opacity=0.65),
            row=3, col=1,
        )
        dot_y = pd.Series(0, index=spring_dates)
        if squeeze_series is not None and len(squeeze_series):
            sq = squeeze_series.reindex(spring_dates).fillna(False)
            dot_colors = ["#b42318" if bool(v) else "#16803c" for v in sq]
            fig.add_trace(
                go.Scatter(x=spring_dates, y=dot_y, mode="markers", marker=dict(size=5, color=dot_colors), name="Squeeze dots"),
                row=3, col=1,
            )

    fig.update_layout(
        height=650,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#334155", size=11),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#e2e8f0", row=i, col=1)
        fig.update_yaxes(gridcolor="#e2e8f0", row=i, col=1)
    return fig



# ──────────────────────────────────────────────────────────────────────────────
# V12 Portfolio Command Center helpers
# ──────────────────────────────────────────────────────────────────────────────
PORTFOLIO_CSV_FILE = "portfolio.csv"
PORTFOLIO_COLUMNS = ["Ticker", "Entry Price", "Entry Date", "Shares", "Profit Goal %", "Entry Thesis"]


def portfolio_to_csv_text(rows: list[dict]) -> str:
    df = pd.DataFrame(rows, columns=PORTFOLIO_COLUMNS)
    return df.to_csv(index=False)


def load_portfolio() -> list[dict]:
    key = "portfolio_rows_single_user"
    if key in st.session_state:
        return st.session_state[key]
    rows = []
    try:
        if os.path.exists(PORTFOLIO_CSV_FILE):
            df = pd.read_csv(PORTFOLIO_CSV_FILE)
            for col in PORTFOLIO_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            for _, r in df.iterrows():
                t = _normalize_ticker(r.get("Ticker", ""))
                if not t:
                    continue
                rows.append({
                    "Ticker": t,
                    "Entry Price": float(r.get("Entry Price", 0) or 0),
                    "Entry Date": str(r.get("Entry Date", ""))[:10],
                    "Shares": float(r.get("Shares", 0) or 0),
                    "Profit Goal %": float(r.get("Profit Goal %", 8) or 8),
                    "Entry Thesis": str(r.get("Entry Thesis", r.get("Thesis", "")) or ""),
                })
    except Exception:
        rows = []
    st.session_state[key] = rows
    return rows


def save_portfolio(rows: list[dict]) -> None:
    clean = []
    seen = set()
    for r in rows:
        t = _normalize_ticker(r.get("Ticker", ""))
        if not t or t in seen:
            continue
        seen.add(t)
        try:
            entry = float(r.get("Entry Price", 0) or 0)
        except Exception:
            entry = 0
        try:
            shares = float(r.get("Shares", 0) or 0)
        except Exception:
            shares = 0
        try:
            goal = float(r.get("Profit Goal %", 8) or 8)
        except Exception:
            goal = 8
        clean.append({
            "Ticker": t,
            "Entry Price": entry,
            "Entry Date": str(r.get("Entry Date", ""))[:10],
            "Shares": shares,
            "Profit Goal %": goal,
            "Entry Thesis": str(r.get("Entry Thesis", r.get("Thesis", "")) or ""),
        })
    st.session_state["portfolio_rows_single_user"] = clean
    try:
        with open(PORTFOLIO_CSV_FILE, "w", encoding="utf-8") as f:
            f.write(portfolio_to_csv_text(clean))
    except Exception:
        st.warning("Could not write portfolio.csv in this environment. Download the updated CSV and commit it to GitHub if you want it permanent.")


def load_portfolio_from_upload(uploaded_file) -> list[dict]:
    if uploaded_file is None:
        return []
    try:
        df = pd.read_csv(uploaded_file)
        ticker_col = None
        for c in df.columns:
            if str(c).strip().lower() in ["ticker", "symbol"]:
                ticker_col = c
                break
        if ticker_col is None:
            ticker_col = df.columns[0]
        rows = []
        for _, r in df.iterrows():
            t = _normalize_ticker(r.get(ticker_col, ""))
            if not t:
                continue
            rows.append({
                "Ticker": t,
                "Entry Price": float(r.get("Entry Price", r.get("Entry", 0)) or 0),
                "Entry Date": str(r.get("Entry Date", r.get("Date", "")))[:10],
                "Shares": float(r.get("Shares", 0) or 0),
                "Profit Goal %": float(r.get("Profit Goal %", r.get("Goal", 8)) or 8),
                "Entry Thesis": str(r.get("Entry Thesis", r.get("Thesis", "")) or ""),
            })
        return rows
    except Exception:
        return []


def timeframe_read(label: str, spring: dict, rsi_value=None) -> str:
    s_label = clean_label(spring.get("spring_label", "No data"))
    score = _to_float(spring.get("spring_score"), 0)
    if score >= 80:
        tone = "healthy / constructive"
    elif score >= 60:
        tone = "improving"
    elif score >= 35:
        tone = "mixed"
    else:
        tone = "weak"
    rsi_txt = f" RSI is {rsi_value:.1f}." if isinstance(rsi_value, (float, int)) and not pd.isna(rsi_value) else ""
    return f"{label}: {s_label} ({score:.0f}/100), currently {tone}.{rsi_txt} {spring.get('spring_reason', '')}"


def _download_intraday_spring(ticker: str, interval_label: str) -> dict:
    try:
        raw = yf.download(ticker, period="60d", interval="1h", progress=False, auto_adjust=True, threads=False)
        df = normalize_ohlcv(raw, ticker)
        if df.empty:
            return {"df": pd.DataFrame(), "spring": {"spring_score": 0, "spring_label": f"⚪ {interval_label} no data", "spring_reason": "No intraday data available."}, "rsi": None}
        if interval_label == "4H":
            tf_df = resample_to_4h(df)
        else:
            tf_df = df
        spring = compute_ttm_spring(tf_df) if len(tf_df) >= 60 else {"spring_score": 0, "spring_label": f"⚪ {interval_label} no data", "spring_reason": "Not enough intraday history."}
        try:
            rsi = float(ta.momentum.RSIIndicator(tf_df["Close"].astype(float), window=14).rsi().dropna().iloc[-1])
        except Exception:
            rsi = None
        return {"df": tf_df, "spring": spring, "rsi": rsi}
    except Exception as e:
        return {"df": pd.DataFrame(), "spring": {"spring_score": 0, "spring_label": f"⚪ {interval_label} failed", "spring_reason": f"Could not calculate {interval_label}: {e}"}, "rsi": None}


def portfolio_chart(df: pd.DataFrame, title: str, entry_price=None, target_price=None):
    if df is None or df.empty:
        return None
    chart_df = df.tail(90).copy()
    close = chart_df["Close"].astype(float).squeeze()
    dates = chart_df.index
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32], vertical_spacing=0.06, subplot_titles=(title, "RSI (14)"))
    fig.add_trace(go.Candlestick(x=dates, open=chart_df["Open"].squeeze(), high=chart_df["High"].squeeze(), low=chart_df["Low"].squeeze(), close=close, name="Price"), row=1, col=1)
    if entry_price and entry_price > 0:
        fig.add_hline(y=entry_price, line=dict(color="#64748b", dash="dot", width=1), annotation_text="Entry", row=1, col=1)
    if target_price and target_price > 0:
        fig.add_hline(y=target_price, line=dict(color="#16803c", dash="dot", width=1), annotation_text="Target", row=1, col=1)
    try:
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
        fig.add_trace(go.Scatter(x=dates, y=rsi, name="RSI", line=dict(width=1.5)), row=2, col=1)
        fig.add_hline(y=70, line=dict(color="#b42318", dash="dot", width=1), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="#16803c", dash="dot", width=1), row=2, col=1)
    except Exception:
        pass
    fig.update_layout(height=430, paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font=dict(color="#334155", size=10), xaxis_rangeslider_visible=False, margin=dict(l=8, r=8, t=36, b=8), showlegend=False)
    for i in range(1, 3):
        fig.update_xaxes(gridcolor="#e2e8f0", row=i, col=1)
        fig.update_yaxes(gridcolor="#e2e8f0", row=i, col=1)
    return fig



def thesis_monitor(candidate: dict, position: dict, fourh: dict, oneh: dict) -> dict:
    """Portfolio thesis monitor.

    This is separate from Trade Health. Trade Health asks: is the chart working now?
    Thesis Health asks: is the original reason for owning the stock still valid?
    """
    entry_thesis = str(position.get("Entry Thesis", "") or "").strip()
    analyst_verdict = clean_label(candidate.get("analyst_verdict", ""))
    analyst_note = str(candidate.get("analyst_note", "") or "")
    event_type = clean_label(candidate.get("event_type", "")) or "Recent market/news event"
    market_excuse = clean_label(candidate.get("market_excuse", "")) or "No specific market excuse detected."
    reaction = clean_label(candidate.get("reaction_analysis", ""))
    red_flag = clean_label(candidate.get("red_flag_label", ""))
    market_text = f"{analyst_verdict} {analyst_note} {event_type} {market_excuse} {reaction} {red_flag}".lower()

    # Separate legal headline risk from actual business/fundamental damage.
    legal_terms = ["lawsuit", "class action", "shareholder", "investigation", "legal"]
    legal_risk = any(t in market_text for t in legal_terms)
    hard_damage_terms = [
        "sec enforcement", "accounting irregular", "restatement", "fraud proven", "bankruptcy",
        "liquidity crisis", "going concern", "guidance cut", "cut guidance", "customer loss",
        "fundamental damage", "broken story", "demand collapse"
    ]
    hard_damage = any(t in market_text for t in hard_damage_terms)
    mixed_terms = ["miss", "slowing", "margin", "weaker", "lower", "downgrade", "concern"]
    mixed_risk = any(t in market_text for t in mixed_terms)
    positive_terms = ["beat", "raised", "strong demand", "record", "growth", "contract", "buyback", "approval"]
    positive_support = any(t in market_text for t in positive_terms)

    fourh_score = _to_float(fourh.get("spring", {}).get("spring_score"), 0)
    oneh_score = _to_float(oneh.get("spring", {}).get("spring_score"), 0)
    daily_score = _to_float(candidate.get("spring_score"), 0)
    price_vote = "🟢 Buyers are currently supporting the trade" if fourh_score >= 60 and oneh_score >= 50 else ("🟡 Market response is mixed" if fourh_score >= 40 else "🔴 The market is not confirming the trade yet")
    volume_score = _to_float(candidate.get("volume_trend_score"), 50)
    volume_vote = "🟢 Volume trend is supportive" if volume_score >= 65 else ("🟡 Volume trend is neutral/mixed" if volume_score >= 40 else "🔴 Volume trend is not supportive")
    market_vote_score = round(clamp(fourh_score*0.38 + oneh_score*0.22 + daily_score*0.22 + volume_score*0.18))
    if market_vote_score >= 70:
        market_vote_label = "🟢 Market rejecting worst-case interpretation"
    elif market_vote_score >= 45:
        market_vote_label = "🟡 Market still deciding"
    else:
        market_vote_label = "🔴 Market still validating caution"

    if hard_damage:
        thesis_health = "🔴 Thesis Broken"
        thesis_class = "decision-red"
        severity = "High"
        thesis_summary = "New information appears to challenge the original reason for owning the stock. Treat technical rebounds with caution until the business/story damage is resolved."
    elif legal_risk or mixed_risk:
        if market_vote_score >= 65:
            thesis_health = "🟡 Thesis Challenged"
            thesis_class = "decision-yellow"
            severity = "Moderate"
            thesis_summary = "News or legal headlines increase risk, but the market is currently absorbing the concern and the trade is still technically constructive."
        else:
            thesis_health = "🟠 Thesis Weakening"
            thesis_class = "decision-yellow"
            severity = "Moderate-High"
            thesis_summary = "The original thesis is being tested and price action has not fully rejected the negative interpretation yet. Keep a tighter leash."
    elif positive_support or "false panic" in market_text or "overreaction" in market_text:
        thesis_health = "🟢 Thesis Intact"
        thesis_class = "decision-green"
        severity = "Low-Moderate"
        thesis_summary = "The available news does not appear to invalidate the original trade thesis. Current evidence is consistent with a recoverable overreaction."
    else:
        thesis_health = "🟡 Thesis Unproven"
        thesis_class = "decision-blue"
        severity = "Unknown/Moderate"
        thesis_summary = "There is not enough news context to strongly confirm or reject the thesis, so the chart and risk plan should carry more weight."

    if legal_risk and not hard_damage:
        event = "Legal/shareholder investigation headline"
        fear = "Investors may fear management knew about slowing growth or business issues before the market did."
        reality = "These announcements often follow large post-earnings stock drops and do not by themselves prove wrongdoing. They matter more if followed by SEC action, accounting issues, restatements, or fresh business deterioration."
        changes = "SEC enforcement action; accounting restatement; confirmed misleading disclosures; another major guidance cut; evidence that customer demand is weakening."
    elif hard_damage:
        event = event_type or "Potential fundamental damage event"
        fear = "The market may be reacting to a real deterioration in the business or disclosure quality."
        reality = "This type of event can make historical rebound patterns less reliable because the original business story may have changed."
        changes = "Clear company clarification; improved guidance; evidence customers/demand remain healthy; price reclaiming key levels on strong volume."
    elif mixed_risk:
        event = event_type or "Mixed earnings/outlook event"
        fear = market_excuse or "Investors may be worried that growth or margins are weakening."
        reality = "The concern may be real but not necessarily fatal. The key is whether buyers continue to defend the stock after the market has had time to digest the news."
        changes = "Further guidance weakness; analyst target cuts tied to fundamentals; failed 4H trend; loss of recent support on heavy volume."
    else:
        event = event_type or "No major damaging event detected"
        fear = market_excuse or "No obvious thesis-breaking fear detected."
        reality = analyst_note or "The news read does not currently show a clear business-breakdown signal."
        changes = "New negative company-specific news; loss of 4H momentum; daily rollover; opportunity remaining becoming too low."

    return {
        "entry_thesis": entry_thesis or "No entry thesis provided yet.",
        "thesis_health": thesis_health,
        "thesis_class": thesis_class,
        "thesis_severity": severity,
        "thesis_summary": thesis_summary,
        "event": event,
        "market_fear": fear,
        "reality_check": reality,
        "what_changes_my_mind": changes,
        "market_vote_label": market_vote_label,
        "market_vote_score": market_vote_score,
        "price_vote": price_vote,
        "volume_vote": volume_vote,
        "legal_risk": legal_risk,
        "hard_damage": hard_damage,
    }

def portfolio_exit_analysis(candidate: dict, position: dict, fourh: dict, oneh: dict) -> dict:
    """Portfolio-specific exit logic.

    The scanner decides whether something is worth entering. Portfolio mode decides
    whether an existing position should keep working. News still matters, but once
    price/momentum are confirming the trade, old negative headlines should not by
    themselves force an emergency exit.
    """
    entry = float(position.get("Entry Price", 0) or 0)
    goal = float(position.get("Profit Goal %", 8) or 8)
    price = _to_float(candidate.get("price"), 0)
    gain_pct = ((price - entry) / entry * 100) if entry > 0 and price > 0 else 0
    progress = clamp((gain_pct / goal) * 100) if goal > 0 else 0
    opp_remaining = _to_float(candidate.get("opportunity_remaining_pct"), 0)
    current_rsi = _to_float(candidate.get("current_rsi"), 0)
    daily_score = _to_float(candidate.get("spring_score"), 0)
    fourh_score = _to_float(fourh.get("spring", {}).get("spring_score"), 0)
    oneh_score = _to_float(oneh.get("spring", {}).get("spring_score"), 0)
    volume_trend_score = _to_float(candidate.get("volume_trend_score"), 50)
    setup_score = _to_float(candidate.get("setup_quality"), 0)
    market_read = clean_label(candidate.get("market_read_label", candidate.get("analyst_verdict", "")))
    red_flag = clean_label(candidate.get("red_flag_label", ""))
    thesis_info = thesis_monitor(candidate, position, fourh, oneh)

    # Trade Health = what the position is doing now.
    # This is intentionally more important than the original entry/news thesis once we own it.
    trade_health = round(clamp(
        (fourh_score * 0.35) +
        (oneh_score * 0.20) +
        (daily_score * 0.20) +
        (volume_trend_score * 0.15) +
        (min(max(current_rsi, 0), 70) / 70 * 100 * 0.10)
    ))

    # Thesis risk = true story damage, not merely "the news was scary."
    # A portfolio exit should require real thesis damage, not merely a scary old headline.
    thesis_text = f"{market_read} {red_flag} {thesis_info.get('thesis_health','')}".lower()
    hard_red_flag = bool(thesis_info.get("hard_damage"))
    broken = ("thesis broken" in thesis_text or hard_red_flag)

    # The 1H should only become important near the harvest zone or when 4H starts weakening.
    exit_assistant_active = progress >= 80 or opp_remaining <= 25 or fourh_score < 45

    # Strong current confirmation should override old/scary news unless there is a hard red flag.
    current_confirmation_strong = (fourh_score >= 65 and oneh_score >= 55 and trade_health >= 60)
    current_confirmation_weak = (fourh_score < 40 and oneh_score < 45 and daily_score < 35)

    if hard_red_flag and current_confirmation_weak:
        verdict = "🚨 Exit Early"
        klass = "decision-red"
        confidence = "High"
        reason = "A hard red-flag headline is present and the current trade health is weak. The thesis may be breaking, not merely digesting bad news."
        window = "Now / next session"
    elif broken and not current_confirmation_strong and gain_pct < goal:
        verdict = "⚠️ Reassess Thesis"
        klass = "decision-yellow"
        confidence = "Moderate"
        reason = "The market/news read contains a fundamental warning, but this is not an automatic exit unless price and momentum confirm weakness."
        window = "Watch next 1–2 sessions"
    elif gain_pct >= goal and (oneh_score < 45 or opp_remaining <= 20 or current_rsi >= 70):
        verdict = "🔴 Take Profit"
        klass = "decision-red"
        confidence = "High"
        reason = "Your profit goal has been reached and the 1H/remaining-opportunity read suggests the easy part of the move may be ending."
        window = "Today to next 1 trading day"
    elif gain_pct >= goal and fourh_score >= 65 and oneh_score >= 60:
        verdict = "🚀 Let Winner Run"
        klass = "decision-blue"
        confidence = "Moderate"
        reason = "The goal has been reached, but 4H and 1H momentum still look constructive. Consider trailing rather than selling blindly."
        window = "1–4 trading days, if momentum holds"
    elif progress >= 80 and (oneh_score < 60 or fourh_score < 55 or opp_remaining <= 30):
        verdict = "🟡 Trim Soon"
        klass = "decision-yellow"
        confidence = "Moderate"
        reason = "The trade is entering the harvest zone. Use the 1H chart to fine-tune whether to exit this morning, afternoon, or next session."
        window = "0–2 trading days"
    elif current_confirmation_strong and opp_remaining >= 20:
        verdict = "🟢 Hold Strong"
        klass = "decision-green"
        confidence = "Moderate"
        reason = "Current price action and momentum are confirming the trade. News risk remains worth monitoring, but the market is not currently validating an exit."
        window = "2–7 trading days, if the setup continues"
    elif fourh_score >= 55 and oneh_score >= 50 and opp_remaining >= 25:
        verdict = "👀 Hold / Monitor"
        klass = "decision-blue"
        confidence = "Moderate"
        reason = "The position is still constructive enough to let it work, but it needs continued 4H/1H confirmation."
        window = "Reassess daily"
    elif current_confirmation_weak and gain_pct < 0:
        verdict = "⚠️ Reassess Thesis"
        klass = "decision-yellow"
        confidence = "Moderate"
        reason = "The position is under entry and momentum is not confirming yet. Watch closely for a failed setup rather than forcing an immediate exit."
        window = "Next 1–2 sessions"
    else:
        verdict = "👀 Monitor"
        klass = "decision-blue"
        confidence = "Moderate"
        reason = "The trade is still developing. Watch whether 4H momentum improves or rolls over before changing the plan."
        window = "Reassess daily"

    if not exit_assistant_active and verdict in ["🟢 Hold Strong", "👀 Hold / Monitor", "👀 Monitor"]:
        oneh_note = "1H Exit Assistant is not fully active yet because the trade is not near the profit goal or exhaustion zone."
    else:
        oneh_note = "1H Exit Assistant is active: use the 1H read to fine-tune sell timing."

    trade_story = (
        f"You entered at ${entry:.2f}; current price is about ${price:.2f}, a {gain_pct:+.2f}% move toward your {goal:.1f}% goal. "
        f"Trade Health is {trade_health}/100. Opportunity remaining is estimated near {opp_remaining:.0f}%. "
        f"Daily spring is {clean_label(candidate.get('spring_label','—'))}; "
        f"4H is {clean_label(fourh.get('spring',{}).get('spring_label','—'))}; "
        f"1H is {clean_label(oneh.get('spring',{}).get('spring_label','—'))}."
    )

    return {
        "verdict": verdict,
        "klass": klass,
        "confidence": confidence,
        "reason": reason,
        "window": window,
        "gain_pct": gain_pct,
        "progress_pct": progress,
        "trade_health": trade_health,
        "oneh_note": oneh_note,
        "exit_assistant_active": exit_assistant_active,
        "trade_story": trade_story,
        "thesis_info": thesis_info,
    }



def compute_portfolio_fallback_candidate(ticker: str, entry_price: float, goal_pct: float) -> dict | None:
    """Lightweight Portfolio fallback.

    Portfolio mode should still work even if the full scanner candidate engine
    fails for a ticker because of a news/universe/scanner-specific edge case.
    This fallback only needs enough fields to manage an existing position.
    """
    try:
        raw = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        df = normalize_ohlcv(raw, ticker)
        if df.empty or len(df) < 40:
            return None

        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(index=df.index, dtype=float)
        current_price = float(close.iloc[-1])
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        current_rsi = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else None
        spring = compute_ttm_spring(df)
        avg_vol_20d = float(volume.tail(20).mean()) if len(volume.dropna()) else None
        current_volume = float(volume.iloc[-1]) if len(volume.dropna()) else None
        volume_ratio = (current_volume / avg_vol_20d) if avg_vol_20d and avg_vol_20d > 0 and current_volume else None
        volume_trend_score, volume_trend_label, volume_trend_reason = volume_trend_from_series(volume) if len(volume.dropna()) else (50, "⚪ Unknown", "No volume trend data.")

        # Entry-goal target is the safest portfolio fallback target.
        goal = float(goal_pct or 8)
        target_price = float(entry_price or current_price) * (1 + goal / 100.0) if (entry_price or current_price) else current_price
        if target_price <= 0:
            target_price = current_price
        gain_from_current = ((target_price - current_price) / current_price * 100) if current_price else 0
        if entry_price and target_price > entry_price:
            completed = clamp(((current_price - entry_price) / (target_price - entry_price)) * 100)
        else:
            completed = 0
        remaining = clamp(100 - completed)

        news = get_news_snapshot(ticker, volume_ratio)
        panic = panic_shock_from_df(close, volume, lookback_days=15)
        narrative = narrative_mismatch_from_news(news, panic.get("panic_shock_score", 0))
        news_intel = news_intelligence_from_news(news, panic, narrative)

        company_name = ticker
        try:
            info = yf.Ticker(ticker).fast_info
            # fast_info won't usually have longName, but keep this non-fatal.
        except Exception:
            pass

        return {
            "ticker": ticker,
            "company_name": company_name,
            "price": round(current_price, 2),
            "potential_sell_price": round(float(target_price), 2),
            "target_gain_pct_from_current": gain_from_current,
            "target_reason": "Portfolio fallback target: entry price plus your selected profit goal.",
            "target_confidence": "Fallback",
            "opportunity_remaining_pct": remaining,
            "opportunity_remaining_score": int(round(remaining)),
            "opportunity_remaining_label": ("🟢 Early" if remaining >= 70 else "🟡 Developing" if remaining >= 40 else "🟠 Late" if remaining >= 20 else "🔴 Extended"),
            "move_completed_pct": completed,
            "avg_vol_20d": int(avg_vol_20d) if avg_vol_20d else None,
            "current_volume": int(current_volume) if current_volume else None,
            "volume_ratio": round(float(volume_ratio), 2) if volume_ratio is not None else None,
            "attention_score": int(round(_volume_score_from_ratio(volume_ratio))),
            "attention_label": attention_label_from_ratio(volume_ratio),
            "volume_trend_score": int(round(volume_trend_score)),
            "volume_trend_label": volume_trend_label,
            "volume_trend_reason": volume_trend_reason,
            "current_rsi": round(current_rsi, 1) if current_rsi is not None else None,
            "opportunity": opportunity_label(current_rsi),
            "spring_score": spring.get("spring_score", 0),
            "spring_label": spring.get("spring_label"),
            "spring_reason": spring.get("spring_reason"),
            "momentum_3bar": spring.get("momentum_3bar"),
            "momentum_trend": spring.get("momentum_trend"),
            "analyst_verdict": news_intel.get("analyst_verdict"),
            "analyst_note": news_intel.get("analyst_note"),
            "event_type": news_intel.get("event_type"),
            "market_excuse": news_intel.get("market_excuse"),
            "reaction_analysis": news_intel.get("reaction_analysis"),
            "red_flag_label": narrative.get("red_flag_label"),
            "df": df,
            "rsi_series": rsi_series,
            "fallback_candidate": True,
        }
    except Exception as e:
        return None

@st.cache_data(ttl=900, show_spinner=False)
def compute_portfolio_deep(ticker: str, entry_price: float, entry_date: str, goal_pct: float, entry_thesis: str = ""):
    candidate = compute_candidate(ticker, goal_pct or 8, 30, True, "1D")
    fallback_used = False
    if not candidate:
        candidate = compute_portfolio_fallback_candidate(ticker, entry_price, goal_pct)
        fallback_used = bool(candidate)
    if not candidate:
        return None

    # Portfolio target should always be based on YOUR trade plan, not the scanner's
    # conservative RSI-cycle target. Scanner targets estimate a possible setup;
    # portfolio targets manage an active position.
    try:
        goal = float(goal_pct or 8)
        entry = float(entry_price or 0)
        current_price = _to_float(candidate.get("price"), 0)
        if entry > 0:
            portfolio_target = entry * (1 + goal / 100.0)
            target_gain_from_current = ((portfolio_target - current_price) / current_price * 100.0) if current_price > 0 else None
            move_completed = clamp(((current_price - entry) / (portfolio_target - entry)) * 100.0) if portfolio_target > entry else 0
            remaining = clamp(100.0 - move_completed)

            candidate["potential_sell_price"] = round(float(portfolio_target), 2)
            candidate["target_gain_pct_from_current"] = round(float(target_gain_from_current), 2) if target_gain_from_current is not None else None
            candidate["target_bounce_pct_from_low"] = None
            candidate["target_reason"] = f"Portfolio target: entry price (${entry:.2f}) plus your selected {goal:.1f}% profit goal."
            candidate["target_confidence"] = "Trade plan"
            candidate["target_method"] = "Entry + profit goal"
            candidate["opportunity_remaining_pct"] = round(float(remaining), 1)
            candidate["opportunity_remaining_score"] = int(round(remaining))
            candidate["move_completed_pct"] = round(float(move_completed), 1)
            candidate["opportunity_remaining_label"] = (
                "🟢 Early" if remaining >= 70 else
                "🟡 Developing" if remaining >= 40 else
                "🟠 Late" if remaining >= 20 else
                "🔴 Extended"
            )
            candidate["cycle_target_price"] = round(float(portfolio_target), 2)
    except Exception:
        pass

    fourh = _download_intraday_spring(ticker, "4H")
    oneh = _download_intraday_spring(ticker, "1H")
    analysis = portfolio_exit_analysis(candidate, {"Entry Price": entry_price, "Entry Date": entry_date, "Profit Goal %": goal_pct, "Entry Thesis": entry_thesis}, fourh, oneh)
    return {"candidate": candidate, "fourh": fourh, "oneh": oneh, "analysis": analysis, "fallback_used": fallback_used}


def render_portfolio_command_center():
    st.markdown("## 👑 My Portfolio Command Center")
    st.caption("Manage active swing positions. Scanner finds entries; Portfolio tracks Trade Health, Thesis Health, Market Vote, and exit timing.")

    rows = load_portfolio()
    with st.container(border=True):
        st.markdown("### Portfolio List")
        edit_df = pd.DataFrame(rows, columns=PORTFOLIO_COLUMNS)
        if edit_df.empty:
            edit_df = pd.DataFrame(columns=PORTFOLIO_COLUMNS)
        edited = st.data_editor(
            edit_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ticker": st.column_config.TextColumn(required=True),
                "Entry Price": st.column_config.NumberColumn(format="$%.2f", min_value=0.0),
                "Entry Date": st.column_config.TextColumn(help="YYYY-MM-DD"),
                "Shares": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                "Profit Goal %": st.column_config.NumberColumn(format="%.1f%%", min_value=1.0, max_value=100.0),
                "Entry Thesis": st.column_config.TextColumn(help="Why you entered this trade. Example: Earnings overreaction; market likely too pessimistic."),
            },
            key="portfolio_editor",
        )
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("💾 Save Portfolio", use_container_width=True):
                save_portfolio(edited.to_dict("records"))
                st.success("Portfolio saved for this app session/file.")
                st.rerun()
        with c2:
            uploaded = st.file_uploader("Import portfolio CSV", type=["csv"], label_visibility="collapsed")
            if uploaded is not None:
                save_portfolio(load_portfolio_from_upload(uploaded))
                st.success("Imported portfolio.csv")
                st.rerun()
        with c3:
            st.download_button("⬇ Download portfolio.csv", data=portfolio_to_csv_text(edited.to_dict("records")), file_name="portfolio.csv", mime="text/csv", use_container_width=True)

    rows = load_portfolio()
    if not rows:
        st.info("Add 1–5 active swing positions above. Example columns: Ticker, Entry Price, Entry Date, Shares, Profit Goal %. Then save and refresh the analysis.")
        return

    st.markdown("### Active Position Deep Dives")
    for pos in rows[:8]:
        ticker = _normalize_ticker(pos.get("Ticker", ""))
        if not ticker:
            continue
        with st.spinner(f"Deep-diving {ticker}…"):
            data = compute_portfolio_deep(ticker, float(pos.get("Entry Price", 0) or 0), str(pos.get("Entry Date", "")), float(pos.get("Profit Goal %", 8) or 8), str(pos.get("Entry Thesis", "") or ""))
        if not data:
            st.warning(f"Could not analyze {ticker}.")
            continue
        c = data["candidate"]
        analysis = data["analysis"]
        fourh = data["fourh"]
        oneh = data["oneh"]
        fallback_used = data.get("fallback_used", False)
        company = c.get("company_name") or ticker
        with st.container():
            st.markdown("<div class='portfolio-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='portfolio-title'>{ticker} <span class='company-name'>{html.escape(str(company))}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='portfolio-subtitle'>Entry ${float(pos.get('Entry Price',0) or 0):.2f} · Goal {float(pos.get('Profit Goal %',8) or 8):.1f}% · Entry date {html.escape(str(pos.get('Entry Date','—') or '—'))}</div>", unsafe_allow_html=True)
            st.markdown(f"<span class='decision-pill {analysis['klass']}'>{analysis['verdict']} · Confidence {analysis['confidence']}</span>", unsafe_allow_html=True)
            if fallback_used:
                st.caption("Using lightweight portfolio analysis for this ticker because the full scanner read was unavailable.")
            st.markdown(f"<div class='read-box'><div class='read-title'>🧠 Trade Story</div><div class='read-text'>{html.escape(analysis['trade_story'])}</div></div>", unsafe_allow_html=True)
            thesis = analysis.get("thesis_info", {})
            st.markdown(
                f"<div class='read-box'>"
                f"<div class='read-title'>🧾 Entry Thesis</div>"
                f"<div class='read-text'>{html.escape(str(thesis.get('entry_thesis','No entry thesis provided yet.')))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='read-box'>"
                f"<div class='read-title'>🧠 Thesis Health: <span class='decision-pill {html.escape(str(thesis.get('thesis_class','decision-blue')))}'>{html.escape(str(thesis.get('thesis_health','—')))} · {html.escape(str(thesis.get('thesis_severity','')))}</span></div>"
                f"<div class='read-text'>{html.escape(str(thesis.get('thesis_summary','')))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"<div class='read-box'><div class='read-title'>⏳ Exit Window</div><div class='read-text'><strong>{html.escape(analysis['window'])}</strong><br>{html.escape(analysis['reason'])}<br>{html.escape(analysis['oneh_note'])}</div></div>", unsafe_allow_html=True)
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Current", f"${c.get('price', 0):.2f}")
            m2.metric("Gain", f"{analysis['gain_pct']:+.2f}%")
            m3.metric("Goal progress", f"{analysis['progress_pct']:.0f}%")
            m4.metric("Target", f"${c.get('potential_sell_price') or 0:.2f}")
            m5.metric("Remaining", f"{_to_float(c.get('opportunity_remaining_pct'),0):.0f}%")

            st.markdown("#### Timeframe Reads")
            r1, r2, r3 = st.columns(3)
            with r1:
                st.markdown("<div class='read-box'><div class='read-title'>🌎 1D Thesis Health</div><div class='read-text'>" + html.escape(timeframe_read("Daily", {"spring_score": c.get("spring_score", 0), "spring_label": c.get("spring_label"), "spring_reason": c.get("spring_reason")}, c.get("current_rsi"))) + "</div></div>", unsafe_allow_html=True)
            with r2:
                st.markdown("<div class='read-box'><div class='read-title'>🎯 4H Trade Management</div><div class='read-text'>" + html.escape(timeframe_read("4H", fourh.get("spring", {}), fourh.get("rsi"))) + "</div></div>", unsafe_allow_html=True)
            with r3:
                st.markdown("<div class='read-box'><div class='read-title'>⏱️ 1H Exit Timing</div><div class='read-text'>" + html.escape(timeframe_read("1H", oneh.get("spring", {}), oneh.get("rsi"))) + "</div></div>", unsafe_allow_html=True)

            st.markdown("#### Market + News Read")
            thesis = analysis.get("thesis_info", {})
            st.markdown(
                f"<div class='read-box'>"
                f"<div class='read-title'>📰 Event: {html.escape(str(thesis.get('event','—')))}</div>"
                f"<div class='read-text'><strong>Market Fear:</strong> {html.escape(str(thesis.get('market_fear','—')))}<br>"
                f"<strong>Reality Check:</strong> {html.escape(str(thesis.get('reality_check','—')))}<br>"
                f"<strong>What Changes My Mind:</strong> {html.escape(str(thesis.get('what_changes_my_mind','—')))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='read-box'>"
                f"<div class='read-title'>📈 Market Vote: {html.escape(str(thesis.get('market_vote_label','—')))} ({_to_float(thesis.get('market_vote_score'),0):.0f}/100)</div>"
                f"<div class='read-text'>{html.escape(str(thesis.get('price_vote','')))}<br>{html.escape(str(thesis.get('volume_vote','')))}<br>"
                f"Original Market Read: {html.escape(clean_label(c.get('analyst_verdict','—')))} — {html.escape(str(c.get('analyst_note','No analyst note available.')))}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            with st.expander(f"Charts for {ticker}: 1D, 4H, 1H", expanded=False):
                ca, cb, cc = st.columns(3)
                with ca:
                    fig = portfolio_chart(c.get("df"), f"{ticker} 1D", float(pos.get("Entry Price",0) or 0), c.get("potential_sell_price"))
                    if fig: st.plotly_chart(fig, use_container_width=True)
                with cb:
                    fig = portfolio_chart(fourh.get("df"), f"{ticker} 4H", float(pos.get("Entry Price",0) or 0), c.get("potential_sell_price"))
                    if fig: st.plotly_chart(fig, use_container_width=True)
                with cc:
                    fig = portfolio_chart(oneh.get("df"), f"{ticker} 1H", float(pos.get("Entry Price",0) or 0), c.get("potential_sell_price"))
                    if fig: st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)




# ──────────────────────────────────────────────────────────────────────────────
# V13.1 Entry Hunter engine
# ──────────────────────────────────────────────────────────────────────────────
def _safe_float(x, default=None):
    try:
        if x is None or pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


@st.cache_data(ttl=900, show_spinner=False)
def get_market_cap_estimate(ticker: str):
    """Best-effort market cap lookup for Entry Hunter quality gate."""
    try:
        t = yf.Ticker(ticker)
        fi = getattr(t, "fast_info", {}) or {}
        for key in ["market_cap", "marketCap"]:
            try:
                val = fi.get(key) if hasattr(fi, "get") else fi[key]
                val = _safe_float(val)
                if val and val > 0:
                    return val
            except Exception:
                pass
        info = getattr(t, "info", {}) or {}
        val = _safe_float(info.get("marketCap"))
        if val and val > 0:
            return val
    except Exception:
        pass
    return None


def recent_fast_drop(close: pd.Series, lookback: int = 12, max_days: int = 7):
    """Find the sharpest recent peak-to-trough close drop inside the lookback window."""
    try:
        c = close.dropna().astype(float)
        if len(c) < max(lookback, 8):
            return {"drop_pct": 0, "drop_days": None, "peak_date": None, "trough_date": None, "trough_price": None}
        recent = c.tail(lookback)
        best = {"drop_pct": 0, "drop_days": None, "peak_date": None, "trough_date": None, "trough_price": None}
        vals = list(recent.values)
        idxs = list(recent.index)
        for i in range(len(vals)):
            peak = vals[i]
            if peak <= 0:
                continue
            for j in range(i + 1, min(len(vals), i + max_days + 1)):
                trough = vals[j]
                drop = (peak - trough) / peak * 100.0
                if drop > best["drop_pct"]:
                    best = {
                        "drop_pct": float(drop),
                        "drop_days": int(j - i),
                        "peak_date": idxs[i].date() if hasattr(idxs[i], "date") else idxs[i],
                        "trough_date": idxs[j].date() if hasattr(idxs[j], "date") else idxs[j],
                        "trough_price": float(trough),
                    }
        return best
    except Exception:
        return {"drop_pct": 0, "drop_days": None, "peak_date": None, "trough_date": None, "trough_price": None}


def macd_entry_state(close: pd.Series):
    try:
        c = close.dropna().astype(float)
        if len(c) < 40:
            return 0, "⚪ Not enough MACD data", "MACD needs more daily history."
        macd_ind = ta.trend.MACD(c)
        macd = macd_ind.macd()
        sig = macd_ind.macd_signal()
        diff = (macd - sig).dropna()
        if len(diff) < 5:
            return 0, "⚪ Not enough MACD data", "MACD signal is unavailable."
        now = float(diff.iloc[-1])
        prev = float(diff.iloc[-2])
        crossed_recent = any(float(diff.iloc[-k-1]) <= 0 and float(diff.iloc[-k]) > 0 for k in range(1, min(4, len(diff))))
        improving_3 = float(diff.iloc[-1]) > float(diff.iloc[-2]) > float(diff.iloc[-3]) if len(diff) >= 3 else False
        price = float(c.iloc[-1])
        near_cross = now <= 0 and abs(now) / max(price, 1) < 0.006 and now > prev
        if crossed_recent:
            return 100, "🟢 Fresh bullish MACD cross", "MACD crossed bullish within the last few daily bars."
        if near_cross and improving_3:
            return 85, "🟢 MACD nearly crossed", "MACD is still slightly negative but converging upward quickly."
        if improving_3:
            return 65, "🟡 MACD improving", "MACD momentum is improving but has not reached a clean trigger."
        if now > 0:
            return 55, "🟡 MACD positive", "MACD is positive, but the freshest crossover may have already passed."
        return 20, "🔴 MACD weak", "MACD is not converging upward yet."
    except Exception:
        return 0, "⚪ MACD unavailable", "MACD calculation failed."


def ema_entry_state(close: pd.Series):
    """Early momentum read using EMA 9/15 compression.

    Entry Hunter should not require the 9 EMA to already be above the 15 EMA,
    because that is often late. This scores whether the 9 EMA is closing the
    gap toward the 15 EMA, while still giving credit for a fresh cross.
    """
    try:
        c = close.dropna().astype(float)
        if len(c) < 25:
            return 0, "⚪ Not enough EMA data", "EMA compression needs more daily history."
        ema9 = ta.trend.EMAIndicator(c, window=9).ema_indicator()
        ema15 = ta.trend.EMAIndicator(c, window=15).ema_indicator()
        diff = (ema9 - ema15).dropna()
        if len(diff) < 6:
            return 0, "⚪ EMA unavailable", "EMA compression signal is unavailable."

        now = float(diff.iloc[-1])
        prev = float(diff.iloc[-2])
        prev3 = float(diff.iloc[-4]) if len(diff) >= 4 else prev
        price = float(c.iloc[-1])
        price = max(price, 1)

        # Negative gap means EMA9 is below EMA15. We want that gap to shrink.
        gap_now_pct = abs(now) / price * 100.0
        gap_prev_pct = abs(prev) / price * 100.0
        gap_prev3_pct = abs(prev3) / price * 100.0
        crossed_recent = any(float(diff.iloc[-k-1]) <= 0 and float(diff.iloc[-k]) > 0 for k in range(1, min(5, len(diff))))
        closing_1 = now > prev
        closing_3 = now > prev and prev > float(diff.iloc[-3]) if len(diff) >= 3 else closing_1
        gap_shrunk_meaningfully = now <= 0 and gap_now_pct < gap_prev3_pct * 0.75 and closing_1
        very_close = now <= 0 and gap_now_pct <= 0.75 and closing_1
        close_enough = now <= 0 and gap_now_pct <= 1.5 and closing_1

        if gap_shrunk_meaningfully and very_close and closing_3:
            return 100, "🟢 EMA gap closing fast", f"EMA 9 is still below EMA 15, but the gap has compressed to {gap_now_pct:.2f}% and is closing quickly."
        if crossed_recent:
            return 88, "🟢 Fresh EMA cross", "EMA 9 recently crossed above EMA 15. This confirms the turn, though it may be slightly later than compression."
        if gap_shrunk_meaningfully:
            return 85, "🟢 EMA compression", f"EMA 9 is closing the gap on EMA 15. Gap moved from about {gap_prev3_pct:.2f}% to {gap_now_pct:.2f}%."
        if close_enough and closing_3:
            return 75, "🟡 EMA close and improving", f"EMA 9 is near EMA 15 with a {gap_now_pct:.2f}% gap and improving."
        if now > 0 and closing_1:
            return 70, "🟡 EMA bullish", "EMA 9 is above EMA 15 and still improving, but the earlier entry may have already appeared."
        if now > 0:
            return 55, "🟡 EMA crossed already", "EMA 9 is above EMA 15, but the crossover no longer looks fresh."
        if closing_1:
            return 45, "🟠 EMA starting to close", f"EMA 9 is below EMA 15, but the gap is starting to shrink ({gap_now_pct:.2f}%)."
        return 15, "🔴 EMA gap widening", "EMA 9 is moving farther below EMA 15, so short-term price structure is not improving yet."
    except Exception:
        return 0, "⚪ EMA unavailable", "EMA compression calculation failed."


def entry_ttm_is_rebounding(spring: dict) -> bool:
    """Entry Hunter tactical TTM gate.

    We do not require a perfect positive TTM. We want the lower timeframe to
    be curling/rebounding: Early Turn, Fired Up, Loaded & Improving, or a
    constructive spring score.
    """
    try:
        label = str(spring.get("spring_label", "")).lower()
        score = float(spring.get("spring_score", 0) or 0)
        positive_words = ["early turn", "fired up", "loaded & improving", "loaded and improving", "improving", "tactical curl"]
        bad_words = ["accelerating down", "fired down", "weakening"]
        if any(w in label for w in bad_words):
            return False
        if any(w in label for w in positive_words):
            return True
        return score >= 60
    except Exception:
        return False

def entry_ttm_rebound_strength(spring: dict) -> float:
    try:
        label = str(spring.get("spring_label", "")).lower()
        score = float(spring.get("spring_score", 0) or 0)
        if "fired up" in label:
            return max(score, 92)
        if "early turn" in label or "tactical curl" in label:
            return max(score, 78)
        if "loaded" in label and "improving" in label:
            return max(score, 82)
        if "improving" in label:
            return max(score, 72)
        return score
    except Exception:
        return 0


@st.cache_data(ttl=900, show_spinner=False)
def compute_entry_hunter_candidate(ticker: str, profit_target: int, bounce_days: int, include_news_lookup: bool = True):
    """Entry Hunter: intentionally picky weekly swing-entry detector.

    It first checks the actual entry recipe cheaply, then pulls the deeper
    scanner/news read only for stocks that have a real shot.
    """
    try:
        market_cap = get_market_cap_estimate(ticker)
        if market_cap is not None and market_cap < 2_000_000_000:
            return None

        raw = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        df = normalize_ohlcv(raw, ticker)
        if df.empty or len(df) < 90:
            return None
        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(index=df.index, dtype=float)
        current_price = float(close.iloc[-1])

        drop = recent_fast_drop(close, lookback=12, max_days=7)
        drop_pct = float(drop.get("drop_pct") or 0)
        drop_days = drop.get("drop_days")
        if drop_pct < 5 or drop_pct > 30:
            return None

        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        valid_rsi = rsi_series.dropna()
        if valid_rsi.empty:
            return None
        current_rsi = float(valid_rsi.iloc[-1])
        under_positions = [i for i, v in enumerate(rsi_series) if pd.notna(v) and v < 30]
        if not under_positions:
            return None
        days_since_under = len(rsi_series) - 1 - under_positions[-1]
        rsi_low_recent = float(rsi_series.iloc[max(0, len(rsi_series)-45):].min())
        rsi_recovered = days_since_under <= 35 and current_rsi > 30 and current_rsi <= 55
        if not rsi_recovered:
            return None
        # Sweet spot is above oversold but not already hot.
        if 35 <= current_rsi <= 45:
            rsi_score = 100
        elif 30 < current_rsi < 35:
            rsi_score = 85
        elif 45 < current_rsi <= 50:
            rsi_score = 80
        else:
            rsi_score = 55

        macd_score, macd_label, macd_reason = macd_entry_state(close)
        ema_score, ema_label, ema_reason = ema_entry_state(close)

        # Entry Hunter timing layer: 1H and 4H must both be rebounding.
        # 4H is the main swing-entry trigger; 1H confirms that the turn is active now.
        oneh = _download_intraday_spring(ticker, "1H")
        oneh_spring = oneh.get("spring", {}) if isinstance(oneh, dict) else {}
        oneh_score = entry_ttm_rebound_strength(oneh_spring)
        oneh_label = oneh_spring.get("spring_label", "⚪ 1H unavailable")
        oneh_reason = oneh_spring.get("spring_reason", "1H trigger unavailable.")

        fourh = _download_intraday_spring(ticker, "4H")
        fourh_spring = fourh.get("spring", {}) if isinstance(fourh, dict) else {}
        fourh_score = entry_ttm_rebound_strength(fourh_spring)
        fourh_label = fourh_spring.get("spring_label", "⚪ 4H unavailable")
        fourh_reason = fourh_spring.get("spring_reason", "4H trigger unavailable.")

        # Daily TTM is a bonus, not a gate. Daily often lags your entry.
        daily_spring = compute_ttm_spring(df) if len(df) >= 60 else {"spring_score": 0, "spring_label": "⚪ 1D unavailable", "spring_reason": "Not enough daily history."}
        daily_score = entry_ttm_rebound_strength(daily_spring)
        daily_label = daily_spring.get("spring_label", "⚪ 1D unavailable")
        daily_reason = daily_spring.get("spring_reason", "1D trigger unavailable.")

        # Entry Hunter is intentionally picky: the shorter and tactical timeframes
        # must be turning upward. The daily can still be repairing.
        if not entry_ttm_is_rebounding(oneh_spring):
            return None
        if not entry_ttm_is_rebounding(fourh_spring):
            return None

        # Panic quality favors larger quick drops because you only aim to capture
        # a piece of the rebound. Too small = not enough meat; too huge = possible broken story.
        if 10 <= drop_pct <= 22 and drop_days is not None and drop_days <= 5:
            panic_quality = 100
        elif 8 <= drop_pct < 10 and drop_days is not None and drop_days <= 5:
            panic_quality = 88
        elif 5 <= drop_pct < 8 and drop_days is not None and drop_days <= 7:
            panic_quality = 72
        elif 22 < drop_pct <= 25 and drop_days is not None and drop_days <= 7:
            panic_quality = 82
        else:
            panic_quality = 55

        daily_bonus = 100 if entry_ttm_is_rebounding(daily_spring) else max(0, min(daily_score, 55))

        entry_score = int(round(clamp(
            0.25 * fourh_score +
            0.15 * oneh_score +
            0.30 * panic_quality +
            0.15 * rsi_score +
            0.10 * ema_score +
            0.03 * macd_score +
            0.02 * daily_bonus
        )))
        if entry_score < 70:
            return None

        deep = compute_candidate(ticker, profit_target, bounce_days, include_news_lookup, "1D") or {}
        result = dict(deep) if deep else {"ticker": ticker, "price": round(current_price, 2), "df": df, "rsi_series": rsi_series}

        if entry_score >= 92:
            grade = "A+"
        elif entry_score >= 85:
            grade = "A"
        elif entry_score >= 78:
            grade = "B+"
        else:
            grade = "B"

        setup_age_bits = []
        setup_age_bits.append(f"RSI recovered {int(days_since_under)} trading days ago" if days_since_under is not None else "RSI recovery age unknown")
        if "Fresh" in macd_label:
            setup_age_bits.append("MACD crossed recently")
        elif "nearly" in macd_label.lower():
            setup_age_bits.append("MACD nearly crossed")
        if "gap closing fast" in ema_label.lower() or "compression" in ema_label.lower():
            setup_age_bits.append("EMA gap compressing")
        elif "Fresh" in ema_label:
            setup_age_bits.append("EMA crossed recently")
        elif "close" in ema_label.lower():
            setup_age_bits.append("EMA gap closing")
        setup_age_bits.append(f"1H trigger: {clean_label(oneh_label)}")
        setup_age_bits.append(f"4H trigger: {clean_label(fourh_label)}")
        setup_age_bits.append(f"1D spring: {clean_label(daily_label)}")

        why = (
            f"-{drop_pct:.1f}% panic drop in {drop_days or '?'} trading days; RSI recovered from {rsi_low_recent:.1f} to {current_rsi:.1f}; "
            f"1H {clean_label(oneh_label)}; 4H {clean_label(fourh_label)}; 1D {clean_label(daily_label)}; "
            f"{clean_label(ema_label)}; {clean_label(macd_label)}."
        )

        result.update({
            "ticker": ticker,
            "price": round(current_price, 2),
            "market_cap": market_cap,
            "entry_score": entry_score,
            "entry_grade": grade,
            "entry_match_label": f"🏹 Entry Match {grade}",
            "entry_why": why,
            "entry_setup_age": " · ".join(setup_age_bits),
            "entry_drop_pct": round(-abs(drop_pct), 2),
            "entry_drop_abs_pct": round(abs(drop_pct), 2),
            "entry_drop_days": drop_days,
            "entry_drop_trough_date": drop.get("trough_date"),
            "entry_rsi_low_recent": round(rsi_low_recent, 1),
            "entry_current_rsi": round(current_rsi, 1),
            "entry_rsi_score": int(round(rsi_score)),
            "entry_panic_quality": int(round(panic_quality)),
            "entry_macd_score": int(round(macd_score)),
            "entry_macd_label": macd_label,
            "entry_macd_reason": macd_reason,
            "entry_ema_score": int(round(ema_score)),
            "entry_ema_label": ema_label,
            "entry_ema_reason": ema_reason,
            "entry_1h_score": int(round(oneh_score)),
            "entry_1h_label": oneh_label,
            "entry_1h_reason": oneh_reason,
            "entry_4h_score": int(round(fourh_score)),
            "entry_4h_label": fourh_label,
            "entry_4h_reason": fourh_reason,
            "entry_1d_score": int(round(daily_score)),
            "entry_1d_label": daily_label,
            "entry_1d_reason": daily_reason,
            "oneh_entry_df": oneh.get("df") if isinstance(oneh, dict) else None,
            "fourh_entry_df": fourh.get("df") if isinstance(fourh, dict) else None,
        })
        return result
    except Exception:
        return None


def render_entry_hunter_workspace(results: list, universe_name: str, meta: dict | None = None):
    st.markdown("## ⚡ Entry Hunter")
    st.caption("A picky weekly-entry workspace: fast panic drop → RSI recovery → 1H+4H TTM rebound → EMA compression/MACD confirmation. Maximum 5 elite entries.")

    if not results:
        st.info("🦜 The kingdom is quiet. No elite Entry Hunter setups passed today. That can be the correct answer — patience protects the account.")
        return

    top = sorted(results, key=lambda r: float(r.get("entry_score", 0)), reverse=True)[:5]
    st.markdown(f"### 🏹 Today's Elite Entries ({len(top)})")

    for i, r in enumerate(top, start=1):
        ticker = r.get("ticker", "—")
        name = r.get("company_name") or r.get("shortName") or ticker
        with st.container(border=True):
            h1, h2, h3 = st.columns([2.2, 1, 1])
            with h1:
                st.markdown(f"### #{i} {ticker} — {name}")
                st.markdown(f"**{r.get('entry_match_label', '🏹 Entry Match')}** · Score **{int(float(r.get('entry_score', 0)))}**")
            with h2:
                st.metric("Price", f"${_to_float(r.get('price'),0):.2f}")
            with h3:
                tgt = r.get("potential_sell_price")
                st.metric("Target", f"${_to_float(tgt,0):.2f}" if tgt else "—")

            st.markdown(f"**Why it qualifies:** {r.get('entry_why','—')}")
            st.caption(f"Setup age: {r.get('entry_setup_age','—')}")

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Panic Drop", f"{_to_float(r.get('entry_drop_pct'),0):.1f}%", f"{r.get('entry_drop_days') or '?'} days")
            c2.metric("RSI", f"{_to_float(r.get('entry_current_rsi'),0):.1f}", f"low {_to_float(r.get('entry_rsi_low_recent'),0):.1f}")
            c3.metric("1H TTM", f"{int(_to_float(r.get('entry_1h_score'),0))}", clean_label(r.get('entry_1h_label','—'))[:20])
            c4.metric("4H TTM", f"{int(_to_float(r.get('entry_4h_score'),0))}", clean_label(r.get('entry_4h_label','—'))[:20])
            c5.metric("1D TTM", f"{int(_to_float(r.get('entry_1d_score'),0))}", clean_label(r.get('entry_1d_label','—'))[:20])
            c6.metric("EMA/MACD", f"{int(_to_float(r.get('entry_macd_score'),0))}/{int(_to_float(r.get('entry_ema_score'),0))}", f"{clean_label(r.get('entry_ema_label','—'))[:10]} · {clean_label(r.get('entry_macd_label','—'))[:10]}")

            st.markdown("#### Market Read")
            event = r.get("event_type") or "No major event detected"
            excuse = r.get("market_excuse") or r.get("catalyst_reason") or "No clear market excuse found."
            verdict = r.get("analyst_verdict") or "Market read unavailable"
            note = r.get("analyst_note") or r.get("reaction_analysis") or "No deeper news note available."
            st.markdown(f"**Event:** {event}  \n**Market's Excuse:** {excuse}  \n**Verdict:** {verdict}  \n{note}")

            with st.expander("Deep entry details", expanded=False):
                st.write({
                    "Entry Score": r.get("entry_score"),
                    "Panic Quality": r.get("entry_panic_quality"),
                    "RSI Score": r.get("entry_rsi_score"),
                    "1H Trigger": r.get("entry_1h_reason"),
                    "4H Trigger": r.get("entry_4h_reason"),
                    "1D Trigger": r.get("entry_1d_reason"),
                    "MACD": r.get("entry_macd_reason"),
                    "EMA": r.get("entry_ema_reason"),
                    "Opportunity Remaining": r.get("opportunity_remaining_pct"),
                    "History Events": r.get("event_count"),
                    "Analyst Verdict": r.get("analyst_verdict"),
                })
                fig = portfolio_chart(r.get("df"), f"{ticker} 1D", 0, r.get("potential_sell_price"))
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                fig4 = portfolio_chart(r.get("fourh_entry_df"), f"{ticker} 4H", 0, r.get("potential_sell_price"))
                if fig4:
                    st.plotly_chart(fig4, use_container_width=True)
                fig1h = portfolio_chart(r.get("oneh_entry_df"), f"{ticker} 1H", 0, r.get("potential_sell_price"))
                if fig1h:
                    st.plotly_chart(fig1h, use_container_width=True)

    df = pd.DataFrame([{k: v for k, v in r.items() if k not in ["df", "rsi_series", "spring_df", "fourh_entry_df", "oneh_entry_df", "ttm_momentum_series", "squeeze_on_series"]} for r in top])
    keep_cols = [c for c in ["ticker", "entry_grade", "entry_score", "price", "potential_sell_price", "entry_drop_pct", "entry_drop_days", "entry_current_rsi", "entry_1h_label", "entry_4h_label", "entry_1d_label", "entry_macd_label", "entry_ema_label", "analyst_verdict"] if c in df.columns]
    if keep_cols:
        st.markdown("### Compact Entry Table")
        st.dataframe(df[keep_cols], use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
# Main UI — stateful so ticker dropdowns/sorting do NOT wipe scan results
# ──────────────────────────────────────────────────────────────────────────────
# Portfolio workspace short-circuits the scanner UI.
if st.session_state.get("workspace_selector") == "👑 My Portfolio":
    render_portfolio_command_center()
    st.stop()


# Entry Hunter workspace short-circuits the broad research scanner UI.
if st.session_state.get("workspace_selector") == "⚡ Entry Hunter":
    if "entry_hunter_results" not in st.session_state:
        st.session_state.entry_hunter_results = None
    if "entry_hunter_meta" not in st.session_state:
        st.session_state.entry_hunter_meta = None

    if not run and st.session_state.entry_hunter_results is None:
        with st.container(border=True):
            st.markdown("## ⚡ Entry Hunter")
            st.markdown(
                "Find the few stocks that match your actual weekly-entry recipe: $2B+ market cap, a fast 5–25% panic drop, RSI recovery from oversold, EMA/MACD turn, and 1H + 4H TTM rebound triggers."
            )
            st.caption("Choose a universe above, then click Run Swing Scan. This workspace is intentionally picky; zero results can be the correct answer.")
        st.stop()

    if run:
        universe_text = custom_input
        if universe == "📂 CSV upload":
            uploaded_tickers = parse_uploaded_tickers(csv_uploaded)
            universe_text = ",".join(uploaded_tickers)
        all_tickers, source_map = get_universe_payload(universe, universe_text)
        if not all_tickers:
            st.warning("No tickers found. Check your custom list or choose another universe.")
            st.stop()
        st.info(f"⚡ Entry Hunter scanning {len(all_tickers):,} tickers from {universe}…")
        progress = st.progress(0)
        status = st.empty()
        leaders_box = st.empty()
        results = []
        completed = 0
        with ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
            future_map = {
                executor.submit(compute_entry_hunter_candidate, ticker, profit_target, bounce_window, include_news): ticker
                for ticker in all_tickers
            }
            for future in as_completed(future_map):
                ticker = future_map[future]
                completed += 1
                try:
                    candidate = future.result()
                except Exception:
                    candidate = None
                if candidate:
                    results.append(candidate)
                progress.progress(min(completed / max(len(all_tickers), 1), 1.0))
                status.caption(f"Entry Hunter · scanned {completed:,} / {len(all_tickers):,} · latest: {ticker} · elite entries: {len(results):,}")
                if results and (completed % 50 == 0 or completed == len(all_tickers)):
                    preview = sorted(results, key=lambda r: float(r.get('entry_score', 0)), reverse=True)[:5]
                    leaders_box.info("Live Entry Hunter leaders: " + " · ".join([f"{r.get('ticker')} {r.get('entry_grade')} {r.get('entry_score')}" for r in preview]))
        progress.empty(); status.empty(); leaders_box.empty()
        st.session_state.entry_hunter_results = sorted(results, key=lambda r: float(r.get("entry_score", 0)), reverse=True)
        st.session_state.entry_hunter_meta = {
            "universe": universe,
            "tickers_scanned": len(all_tickers),
            "run_date": datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        }

    meta_e = st.session_state.entry_hunter_meta or {"universe": universe, "tickers_scanned": 0, "run_date": "current session"}
    st.markdown(
        f"<div class='small-muted'>Entry Hunter scan: {html.escape(str(meta_e.get('universe')))} · {int(meta_e.get('tickers_scanned', 0)):,} tickers · {html.escape(str(meta_e.get('run_date','')))}</div>",
        unsafe_allow_html=True,
    )
    render_entry_hunter_workspace(st.session_state.entry_hunter_results or [], meta_e.get("universe", universe), meta_e)
    st.stop()

# Morning Report landing action
run_morning_report = False
if st.session_state.scan_results is None and not run:
    fav_count = len(load_favorites())
    st.markdown(
        "<div class='small-muted'>Choose a universe in the top toolbar, run a custom scan, or start with your Favorites Morning Report.</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    with st.container(border=True):
        st.markdown("### ☕🦜 Morning Report")
        st.markdown(
            "Your Zazu-style Favorites briefing: overreaction panic alerts, ready-now candidates, new turns, and red flags."
        )
        col_a, col_b = st.columns([1, 2])
        with col_a:
            if st.button("☕ Give me the Morning Report", use_container_width=True, disabled=(fav_count == 0), key="morning_report_button"):
                run_morning_report = True
        with col_b:
            if fav_count == 0:
                st.warning("Add Favorites first, then Morning Report can watch them for changes.")
            else:
                st.caption(f"Will scan {fav_count} Favorites and compare against the last Morning Report snapshot.")
        st.markdown("---")
        st.markdown("### 📈 Custom Scan")
        st.caption("Use the toolbar above to choose a universe, model settings, and run a normal Swing Scan.")
    if not run_morning_report:
        st.stop()

# When the button is clicked, run the scan once and store the result.
if run or run_morning_report:
    st.session_state.cancel_scan_requested = False
    previous_morning_snapshot = load_morning_snapshot() if run_morning_report else None
    scan_universe = "⭐ Favorites" if run_morning_report else universe
    universe_text = ""
    if not run_morning_report:
        universe_text = custom_input
        if universe == "📂 CSV upload":
            uploaded_tickers = parse_uploaded_tickers(csv_uploaded)
            universe_text = ",".join(uploaded_tickers)
    all_tickers, source_map = get_universe_payload(scan_universe, universe_text)
    if not all_tickers:
        st.warning("No tickers found. Check your custom list or choose another universe.")
        st.stop()

    tickers = all_tickers
    st.session_state.scan_meta = {
        "profile": "Single User",
        "universe": scan_universe,
        "morning_report": bool(run_morning_report),
        "previous_morning_snapshot": previous_morning_snapshot,
        "profit_target": profit_target,
        "bounce_window": bounce_window,
        "include_news": include_news,
        "spring_timeframe": spring_timeframe,
        "scan_speed": max_workers,
        "deep_scan_top_n": deep_scan_top_n,
        "tickers_scanned": len(tickers),
        "source_map": {t: source_map.get(t, []) for t in tickers},
        "run_date": datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    }

    if run_morning_report:
        st.info(f"☕🦜 Building Morning Report: scanning {len(tickers)} Favorites…")
    else:
        st.info(f"Scanning full universe: {len(tickers)} tickers from {scan_universe}…")
    progress = st.progress(0)
    status = st.empty()
    leaders_box = st.empty()
    cancel_box = st.empty()
    cancel_box.caption("Tip: to stop a very large scan, use Streamlit's stop control or refresh the app. V8 stores completed results after the scan finishes.")

    results = []

    # V11.3 Fast Scan Engine:
    # Pass 1 scans the full universe with cheap daily-only calculations.
    # Pass 2 runs expensive 4H/news/full-card analysis only on the best candidates.
    use_fast_scan = len(tickers) > int(deep_scan_top_n)
    deep_tickers = tickers

    if use_fast_scan:
        prescreen = []
        completed = 0
        status.caption("Pass 1/2: fast daily pre-screen…")
        with ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
            future_map = {
                executor.submit(compute_prescreen_candidate, ticker, profit_target, bounce_window): ticker
                for ticker in tickers
            }
            for future in as_completed(future_map):
                ticker = future_map[future]
                completed += 1
                try:
                    fast = future.result()
                except Exception:
                    fast = None
                if fast:
                    prescreen.append(fast)

                status.caption(f"Pass 1/2 · Fast-scanned {completed:,} / {len(tickers):,} · Latest: {ticker} · Candidates: {len(prescreen):,}")
                progress.progress(min((completed / len(tickers)) * 0.45, 0.45))

                if prescreen and (completed % 50 == 0 or completed == len(tickers)):
                    preview = sorted(prescreen, key=lambda r: float(r.get('fast_score', 0)), reverse=True)[:5]
                    preview_text = " · ".join([f"{r.get('ticker')} {int(r.get('fast_score', 0))}" for r in preview])
                    leaders_box.info(f"Fast-screen leaders: {preview_text}")

        prescreen_sorted = sorted(prescreen, key=lambda r: float(r.get('fast_score', 0)), reverse=True)
        deep_tickers = [r.get("ticker") for r in prescreen_sorted[:int(deep_scan_top_n)] if r.get("ticker")]
        if not deep_tickers:
            deep_tickers = tickers[:min(len(tickers), int(deep_scan_top_n))]
        leaders_box.info(f"Pass 2/2: deep-analyzing top {len(deep_tickers):,} candidates from {len(tickers):,} scanned…")

    completed = 0
    total_deep = len(deep_tickers)
    with ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
        future_map = {
            executor.submit(compute_candidate, ticker, profit_target, bounce_window, include_news, spring_timeframe): ticker
            for ticker in deep_tickers
        }
        for future in as_completed(future_map):
            ticker = future_map[future]
            completed += 1
            try:
                candidate = future.result()
            except Exception:
                candidate = None
            if candidate:
                results.append(candidate)

            if use_fast_scan:
                progress.progress(min(0.45 + (completed / max(total_deep, 1)) * 0.55, 1.0))
                status.caption(f"Pass 2/2 · Deep-analyzed {completed:,} / {total_deep:,} · Latest: {ticker} · Usable: {len(results):,}")
            else:
                progress.progress(min(completed / max(total_deep, 1), 1.0))
                status.caption(f"Scanned {completed:,} / {total_deep:,} tickers · Latest: {ticker} · Usable: {len(results):,}")

            if results and (completed % 25 == 0 or completed == total_deep):
                preview = sorted(results, key=lambda r: float(r.get('setup_quality', 0)), reverse=True)[:5]
                preview_text = " · ".join([f"{r.get('ticker')} {int(r.get('setup_quality', 0))}" for r in preview])
                leaders_box.info(f"Live leaders by Setup Quality: {preview_text}")

    progress.empty()
    status.empty()
    leaders_box.empty()
    cancel_box.empty()
    st.session_state.scan_results = results
    st.session_state.leaderboard_filter = "All"
    if run_morning_report:
        report = build_morning_report(results, previous_morning_snapshot)
        st.session_state.last_morning_report = report
        save_morning_snapshot(results)

# If no scan has been run yet, the landing card above should have stopped execution.
if st.session_state.scan_results is None:
    st.stop()

results = st.session_state.scan_results or []
meta = st.session_state.scan_meta or {
    "universe": universe,
    "profit_target": profit_target,
    "bounce_window": bounce_window,
    "tickers_scanned": 0,
    "run_date": "current session",
}
active_universe = meta.get("universe", universe)
active_profit_target = meta.get("profit_target", profit_target)
active_bounce_window = meta.get("bounce_window", bounce_window)
active_spring_timeframe = meta.get("spring_timeframe", spring_timeframe)
active_tickers_scanned = meta.get("tickers_scanned", 0)

st.markdown(
    f"<div class='small-muted'>Latest scan: {active_universe} · Profit goal {active_profit_target}% · Swing window {active_bounce_window} trading days · TTM {active_spring_timeframe} · {meta.get('run_date', '')}</div>",
    unsafe_allow_html=True,
)
if meta.get("morning_report") and st.session_state.get("last_morning_report"):
    render_morning_report(
        st.session_state.last_morning_report,
        favorites_count=active_tickers_scanned or len(results),
        previous_snapshot=meta.get("previous_morning_snapshot"),
    )
st.divider()

if not results:
    st.warning("No usable price/RSI data came back. Try a smaller custom list or rerun in a minute.")
    st.stop()

# Compact model output table.
company_lookup = get_company_lookup(active_universe)
active_source_map = meta.get("source_map", {}) or {}
favorites_now = set(load_favorites())
rows = []
for r in results:
    ticker_sources = active_source_map.get(r["ticker"], [])
    rows.append({
        "Ticker": r["ticker"],
        "Favorite": "★" if r["ticker"] in favorites_now else "",
        "Company": company_lookup.get(r["ticker"], ""),
        "Institution": institutional_label(ticker_sources),
        "Institution Score": institutional_score(ticker_sources),
        "Sources": " • ".join(ticker_sources) if ticker_sources else "—",
        "Swing Score": r["swing_score"],
        "Setup Quality": r.get("setup_quality"),
        "RSI": r["current_rsi"],
        "Opportunity": r["opportunity"],
        "Rebound Stage": r.get("rebound_stage_label"),
        "Rebound Stage Score": r.get("rebound_stage_score"),
        "Rebound Stage Reason": r.get("rebound_stage_reason"),
        "Stabilization": r.get("stabilization_label"),
        "Stabilization Score": r.get("stabilization_score"),
        "Stabilization Reason": r.get("stabilization_reason"),
        "Days Since Panic Low": r.get("days_since_panic_low"),
        "Distance From Panic Low %": r.get("distance_from_panic_low_pct"),
        "New Low Last 3D": r.get("new_low_last_3d"),
        "4H Trigger": r.get("trigger_4h_label"),
        "4H Trigger Score": r.get("trigger_4h_score"),
        "4H Trigger Reason": r.get("trigger_4h_reason"),
        "4H Momentum 3-Bar": r.get("trigger_4h_momentum_3bar"),
        "Price": r["price"],
        "Potential Swing Price": r.get("potential_sell_price"),
        "Target Gain %": r.get("target_gain_pct_from_current"),
        "Target Bounce From Low %": r.get("target_bounce_pct_from_low"),
        "Target Confidence": r.get("target_confidence"),
        "Target Method": r.get("target_method"),
        "Target Reason": r.get("target_reason"),
        "Pre-Panic High": r.get("pre_panic_high"),
        "History Bounce Used %": r.get("history_bounce_pct_used"),
        "Recent Damage Cap %": r.get("recent_damage_cap_pct"),
        "Cycle Low Price": r.get("cycle_low_price"),
        "Cycle Low Date": r.get("cycle_low_date"),
        "Cycle Target Price": r.get("cycle_target_price"),
        "Opportunity Remaining": r.get("opportunity_remaining_label"),
        "Opportunity Remaining %": r.get("opportunity_remaining_pct"),
        "Opportunity Remaining Score": r.get("opportunity_remaining_score"),
        "Move Completed %": r.get("move_completed_pct"),
        "Overreaction Score": r.get("overreaction_score"),
        "Overreaction": r.get("overreaction_label"),
        "Panic Shock Score": r.get("panic_shock_score"),
        "Panic Shock": r.get("panic_label"),
        "Panic Reason": r.get("panic_reason"),
        "Panic Drop %": r.get("panic_drop_pct"),
        "Panic Drop Days": r.get("panic_drop_days"),
        "Panic Drop Date": r.get("panic_drop_date"),
        "Panic Volume Ratio": r.get("panic_volume_ratio"),
        "Narrative Score": r.get("narrative_score"),
        "Narrative": r.get("narrative_label"),
        "Narrative Reason": r.get("narrative_reason"),
        "Red Flags": r.get("red_flag_label"),
        "Market Read Score": r.get("news_intel_score"),
        "Event Type": r.get("event_type"),
        "Market Excuse": r.get("market_excuse"),
        "Analyst Verdict": r.get("analyst_verdict"),
        "Reaction Analysis": r.get("reaction_analysis"),
        "News Evidence": r.get("news_evidence"),
        "Analyst Note": r.get("analyst_note"),
        "News Freshness": r.get("news_freshness"),
        "Avg Max Bounce": r.get("avg_max_bounce_pct"),
        "Avg Days to Max": r.get("avg_days_to_max_bounce"),
        "Successful Swings": r.get("profitable_event_count"),
        "Win Rate": r.get("swing_success_rate"),
        "Risk / Reward": r.get("avg_risk_reward"),
        "History": f"{r.get('event_count', 0)} events",
        "Confidence": r.get("confidence_label"),
        "Confidence Score": r.get("confidence_score"),
        "Spring": r.get("spring_label"),
        "Spring TF": r.get("spring_timeframe"),
        "Spring Score": r.get("spring_score"),
        "Spring Reason": r.get("spring_reason"),
        "Squeeze Bars": r.get("squeeze_bars"),
        "Momentum Trend": r.get("momentum_trend"),
        "Momentum 3-Bar": r.get("momentum_3bar"),
        "Catalyst": r.get("catalyst_label"),
        "Catalyst Score": r.get("catalyst_score"),
        "Catalyst Reason": r.get("catalyst_reason"),
        "Attention": r.get("attention_label"),
        "Attention Score": r.get("attention_score"),
        "Volume Trend": r.get("volume_trend_label"),
        "Volume Trend Score": r.get("volume_trend_score"),
        "Volume Trend Reason": r.get("volume_trend_reason"),
        "Volume Ratio": r.get("volume_ratio"),
        "Volume Score": _volume_score_from_ratio(r.get("volume_ratio")),
        "Headline": r.get("news_headline"),
        "History Score": r.get("history_score"),
        "Opportunity Score": r.get("opportunity_score"),
        "Days Since RSI <30": r.get("days_since_rsi_under_30"),
        "Last RSI <30 Date": r.get("last_rsi_under_30_date"),
        "Oversold Since": r.get("rsi_oversold_start_date"),
        "Avg Lowest RSI": r.get("avg_lowest_rsi"),
        "Avg Drawdown After Low": r.get("avg_post_low_drawdown_pct"),
    })

df = pd.DataFrame(rows)
df = add_ranking_scores(df, active_profit_target, active_bounce_window)

# Top summary metrics — clickable filter cards
rsi_under_40_count = int((pd.to_numeric(df["RSI"], errors="coerce") < 40).sum())
high_conf_count = int(df["Confidence"].astype(str).str.contains("High", na=False).sum())
setup_75_count = int((pd.to_numeric(df["Setup Quality"], errors="coerce") >= 75).sum())

st.markdown("### 📊 Market Snapshot")
st.caption("Click a number card to filter the current scan. Click the active card again to clear it.")

def set_quick_filter(filter_name: str):
    current = st.session_state.get("leaderboard_filter", "All")
    st.session_state.leaderboard_filter = "All" if current == filter_name else filter_name


def quick_filter_button(label: str, value, filter_name: str, key: str):
    is_active = st.session_state.get("leaderboard_filter", "All") == filter_name
    active_badge = "  ✓" if is_active else ""
    button_label = f"{label}{active_badge} | {value}"
    if st.button(button_label, use_container_width=True, key=key):
        set_quick_filter(filter_name)
        st.rerun()

fc1, fc2, fc3, fc4, fc5 = st.columns(5)
with fc1:
    quick_filter_button("Scanned", active_tickers_scanned or len(results), "All", "qf_all_scanned")
with fc2:
    quick_filter_button("Usable results", len(df), "All", "qf_all_usable")
with fc3:
    quick_filter_button("RSI < 40 now", rsi_under_40_count, "RSI < 40", "qf_rsi40")
with fc4:
    quick_filter_button("High-confidence patterns", high_conf_count, "High confidence", "qf_highconf")
with fc5:
    quick_filter_button("Setup ≥75", setup_75_count, "Setup ≥75", "qf_setup75")

st.markdown("### 🎯 View By")
rank_col_ui, rank_help_col = st.columns([1.4, 2.6])
with rank_col_ui:
    ranking_mode = st.selectbox(
        "Choose how to rank the watchlist",
        RANKING_MODES,
        index=RANKING_MODES.index(st.session_state.get("ranking_mode_selector", "🎯 8% Target Hunter")) if st.session_state.get("ranking_mode_selector") in RANKING_MODES else 0,
        key="ranking_mode_selector",
        help="Choose how SwingIt ranks your watchlist without rerunning the scan.",
    )
with rank_help_col:
    st.markdown(
        f"<div class='small-muted' style='padding-top:1.9rem;'>{_safe_html(RANKING_HELP.get(ranking_mode, ''))}</div>",
        unsafe_allow_html=True,
    )

st.markdown("### ✅ Candidate Quality Gate")
gate_col, gate_help_col = st.columns([1.2, 2.8])
with gate_col:
    candidate_gate_mode = st.selectbox(
        "Top card quality",
        CANDIDATE_GATE_MODES,
        index=CANDIDATE_GATE_MODES.index(st.session_state.get("candidate_gate_mode", "Balanced")) if st.session_state.get("candidate_gate_mode") in CANDIDATE_GATE_MODES else 0,
        key="candidate_gate_mode",
        help="Prevents weak names from being forced into the Best Swing Opportunities cards.",
    )
with gate_help_col:
    st.markdown(
        f"<div class='small-muted' style='padding-top:1.9rem;'>{_safe_html(CANDIDATE_GATE_HELP.get(candidate_gate_mode, ''))}</div>",
        unsafe_allow_html=True,
    )

rank_col = ranking_column_for(ranking_mode)
df_sorted = df.sort_values([rank_col, "Setup Quality", "Swing Score", "RSI"], ascending=[False, False, False, True], na_position="last").reset_index(drop=True)
df_sorted["Active Rank Score"] = pd.to_numeric(df_sorted[rank_col], errors="coerce").fillna(0).round(0).astype(int)


active_filter = st.session_state.get("leaderboard_filter", "All")

def apply_leaderboard_filter(frame: pd.DataFrame, filter_name: str) -> pd.DataFrame:
    if filter_name == "RSI < 40":
        return frame[pd.to_numeric(frame["RSI"], errors="coerce") < 40].copy()
    if filter_name == "High confidence":
        return frame[frame["Confidence"].astype(str).str.contains("High", na=False)].copy()
    if filter_name == "Setup ≥75":
        return frame[pd.to_numeric(frame["Setup Quality"], errors="coerce") >= 75].copy()
    return frame.copy()

filtered_df = apply_leaderboard_filter(df_sorted, active_filter).reset_index(drop=True)
if active_filter != "All":
    info_col, clear_col = st.columns([4, 1])
    with info_col:
        st.info(f"Showing **{len(filtered_df)}** tickers for filter: **{active_filter}**")
    with clear_col:
        if st.button("Clear filter", use_container_width=True, key="clear_leaderboard_filter"):
            st.session_state.leaderboard_filter = "All"
            st.rerun()

st.markdown("## 🔥 Best Swing Opportunities")
qualified_df = apply_candidate_gate(filtered_df, candidate_gate_mode).reset_index(drop=True)
st.caption(
    f"Showing up to 10 **qualified** candidates viewed by **{ranking_mode}**. "
    f"Gate: **{candidate_gate_mode}** · {len(qualified_df)} of {len(filtered_df)} visible tickers qualify."
)
top = qualified_df.head(10)
if not top.empty:
    for start in range(0, len(top), 5):
        row_slice = top.iloc[start:start + 5]
        card_cols = st.columns(5)
        for offset, (_, row) in enumerate(row_slice.iterrows()):
            with card_cols[offset]:
                st.markdown(hot_card(start + offset, row), unsafe_allow_html=True)
else:
    st.info(
        "No qualified swing candidates passed the current gate. "
        "Try **Loose**, scan a broader universe, or review the full leaderboard below."
    )

st.divider()
st.markdown("## Watchlist Leaderboard")

sort_a, sort_b, sort_c = st.columns([1.4, 1, 1])
with sort_a:
    default_sort = "Active Rank Score" if "Active Rank Score" in df_sorted.columns else (rank_col if rank_col in df_sorted.columns else df_sorted.columns[0])
    sort_by = st.selectbox(
        "Sort by",
        df_sorted.columns.tolist(),
        index=df_sorted.columns.tolist().index(default_sort),
        key="leaderboard_sort_by",
    )
with sort_b:
    sort_direction = st.selectbox("Direction", ["Descending", "Ascending"], index=0, key="leaderboard_sort_direction")
with sort_c:
    view_mode = st.selectbox("View", ["Compact", "Research"], index=0, key="leaderboard_view_mode")

ascending = sort_direction == "Ascending"
display = filtered_df.sort_values(sort_by, ascending=ascending, na_position="last").reset_index(drop=True)

compact_cols = [
    "Ticker", "Favorite", "Active Rank Score", "Setup Quality", "Swing Score", "Rebound Stage", "Stabilization", "4H Trigger", "Spring TF", "Spring", "Spring Score", "Attention", "Volume Trend", "RSI", "Opportunity", "Price", "Potential Swing Price", "Avg Max Bounce", "Avg Days to Max", "History", "Confidence", "Catalyst"
]
research_cols = compact_cols + [
    "🎯 Target Hunter Score", "⚡ Ready Now Score", "🧠 Confidence Rank Score", "🚀 Upside Rank Score", "😱 Overreaction Rank Score", "🧊 Stabilizing Panic Score", "Target Bounce Score", "Speed Score", "Rebound Stage Score", "Rebound Stage Reason", "Stabilization Score", "Stabilization Reason", "Days Since Panic Low", "Distance From Panic Low %", "New Low Last 3D", "4H Trigger Score", "4H Trigger Reason", "4H Momentum 3-Bar", "Spring Reason", "Squeeze Bars", "Momentum Trend", "Momentum 3-Bar", "Catalyst Score", "Catalyst Reason", "Attention Score", "Volume Trend Score", "Volume Trend Reason", "Volume Ratio", "Volume Score", "Headline", "Successful Swings", "Win Rate", "Risk / Reward", "History Score", "Confidence Score", "Opportunity Score", "Opportunity Remaining Score", "Opportunity Remaining %", "Move Completed %", "Cycle Low Price", "Cycle Target Price", "Days Since RSI <30", "Last RSI <30 Date", "Oversold Since", "Avg Lowest RSI", "Avg Drawdown After Low"
]
show_cols = compact_cols if view_mode == "Compact" else research_cols

if display.empty:
    st.warning("No tickers match the active quick filter. Clear the filter or rerun with different settings.")
    st.stop()

st.dataframe(
    display[show_cols],
    use_container_width=True,
    hide_index=True,
    height=440,
    column_config={
        "Setup Quality": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Swing Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Spring Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Stabilization Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "4H Trigger Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Attention Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Confidence Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Catalyst Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Volume Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "RSI": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        "Price": st.column_config.NumberColumn(format="$%.2f"),
        "Potential Swing Price": st.column_config.NumberColumn(format="$%.2f"),
        "Avg Max Bounce": st.column_config.NumberColumn(format="%.1f%%"),
        "Win Rate": st.column_config.NumberColumn(format="%.1f%%"),
        "Risk / Reward": st.column_config.NumberColumn(format="%.2f"),
        "Volume Ratio": st.column_config.NumberColumn(format="%.2fx"),
        "Avg Drawdown After Low": st.column_config.NumberColumn(format="%.1f%%"),
    },
)


with st.expander("⭐ Favorites Manager", expanded=False):
    favs = load_favorites()
    st.caption("Favorites are loaded from `favorites.csv`. For permanent Streamlit Cloud storage, keep that CSV committed in your GitHub repo. In-app add/remove updates this running session and writes the file when possible; use the download button to update your repo copy.")
    st.write(", ".join(favs) if favs else "No favorites saved yet.")
    add_text = st.text_input("Add tickers to Favorites", placeholder="ORCL, ADBE, META", key="favorites_add_text")
    fav_a, fav_b, fav_c = st.columns([1, 1, 2])
    with fav_a:
        if st.button("Add", key="favorites_add_button", use_container_width=True):
            raw = add_text.replace("\n", ",").replace(";", ",")
            additions = [_normalize_ticker(t) for t in raw.split(",") if t.strip()]
            save_favorites(favs + additions)
            st.success("Favorites updated")
            st.rerun()
    with fav_b:
        if st.button("Clear", key="favorites_clear_button", use_container_width=True):
            save_favorites([])
            st.success("Favorites cleared")
            st.rerun()
    with fav_c:
        st.download_button(
            "⬇ Download favorites.csv",
            data=favorites_to_csv_text(load_favorites()),
            file_name="favorites.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_favorites_csv",
        )


with st.expander("What the Swing Score means"):
    st.markdown(f"""
    **Swing Score V6.2** is a historical rebound score: *is this stock washed out, historically bouncy, and does it have a reason to move?*

    **Spring Score** is separate. It uses the selected TTM timeframe from Model Settings (1D or 1H) and a TTM Squeeze-style calculation to ask: *is volatility compressed or recently released, and is momentum improving right now?* A high Spring Score is not a buy signal by itself, but it can help you prioritize which high Swing Score names are closest to becoming actionable.

    It combines:

    **1. Current opportunity score** — how close the stock is to an actionable RSI rebound zone right now. V6.2 favors the turn zone around RSI 30–45, because the best swing entries often happen after panic starts stabilizing.

    **2. Historical swing outcome score** — what happened after prior RSI&lt;30 panic events. The model asks: *within {active_bounce_window} trading days after the panic low, did this stock create a tradeable bounce?*

    **3. Catalyst score** — lightweight recent-news scoring from Yahoo Finance headlines. It looks at recency, positive/negative tone keywords, catalyst-type keywords such as earnings, guidance, contracts, AI, approvals, launches, analyst upgrades, and whether volume is above normal.

    **4. Volume confirmation** — higher current volume versus the 20-day average can add confirmation that the market is actually paying attention.

    The historical score uses:
    - **Win rate**: how often prior panic events reached at least the selected {active_profit_target}% swing profit goal.
    - **Average max bounce**: average best closing-price rebound within the selected window.
    - **Average days to max bounce**: faster rebounds score better for a 1–4 week swing style.
    - **Risk / reward**: average bounce compared with additional drawdown after the panic low.
    - **Oversold depth**: deeper RSI washouts that recovered can add strength.
    - **Sample size**: more events improve the evidence quality.
    - **Drawdown penalty**: stocks that kept falling hard after RSI panic lose points.

    **Panic zone** means current RSI is below 25. It is the most washed-out bucket in the model. It can be powerful, but it can also still be falling, so it should be treated as “high alert,” not an automatic buy.

    **Confidence** is separate from Swing Score. Low confidence means only 1–2 prior RSI&lt;30 events, Medium means 3–5 events, and High means 6+ events.

    **Potential Swing Price** is a conservative RSI panic-cycle target, not an analyst target. It anchors to the most recent RSI panic low, shrinks tiny historical samples, and caps against the recent pre-panic range so one huge prior event does not create an unrealistic target.

    Current V11.1 uses multiple view-by lenses plus two core scores: **Swing Score** (46% historical swing behavior, 34% current RSI opportunity, 14% catalyst/news, 6% attention/RVOL) and **Setup Quality** (RSI opportunity, rebound stage, stabilization, catalyst/news, daily TTM spring, 4H trigger, attention/RVOL, and volume trend).

    **View By** defines what #1 means. 🎯 Target Hunter is the default for your 8% swing goal; ⚡ Ready Now is for what to open in ThinkorSwim first; 🧠 Highest Confidence is the safest historical pattern; 🚀 Maximum Upside is the biggest reward lens; 😱 Overreaction hunts likely false-panic selloffs; 🧊 Stabilizing Panics finds names where the panic may have stopped but the daily chart has not fully confirmed yet. **Opportunity Remaining** estimates how much of the usual RSI-panic rebound may still be left from the most recent panic-cycle low.

**Setup ≥75** is the “open this in ThinkorSwim now” bucket. Stocks in the high 60s/low 70s are often the almost-there names — they may need one more thing, such as RSI slipping lower, a stronger spring turn, fresh news, or higher relative volume.

    This is meant to produce a **watchlist**, not a buy signal. Entries should still come from price action, VWAP, volume, support/reclaim behavior, and your 5m/15m process.
    """)
st.divider()
st.markdown("## Ticker Detail")
selected = st.selectbox("Inspect ticker", display["Ticker"].tolist(), key="ticker_detail_select")
detail = next((r for r in results if r["ticker"] == selected), None)

if detail:
    favs = load_favorites()
    fav_col1, fav_col2, fav_col3 = st.columns([1, 1, 5])
    if selected in favs:
        with fav_col1:
            if st.button("★ In Favorites", key=f"remove_favorite_{selected}", use_container_width=True):
                save_favorites([t for t in favs if t != selected])
                st.success(f"Removed {selected} from Favorites")
                st.rerun()
    else:
        with fav_col1:
            if st.button("☆ Add Favorite", key=f"add_favorite_{selected}", use_container_width=True):
                save_favorites(favs + [selected])
                st.success(f"Added {selected} to Favorites")
                st.rerun()
    with fav_col2:
        st.caption(f"Favorites: {len(load_favorites())}")

    a, b, c, d, e, f, g = st.columns(7)
    a.metric("Setup Quality", f"{detail.get('setup_quality', 0)}/100")
    b.metric("Swing Score", f"{detail['swing_score']}/100")
    c.metric("Stage", clean_label(detail.get("rebound_stage_label", "—")))
    d.metric("Spring Score", f"{detail.get('spring_score', 0)}/100")
    e.metric("RSI", detail.get("current_rsi", "—"))
    f.metric("Price", f"${detail['price']}")
    f_price = detail.get("potential_sell_price")
    g.metric("Potential Swing Price", f"${f_price}" if f_price is not None else "—")

    tags = []
    opp = detail.get("opportunity", "")
    if "Panic" in opp or "Oversold" in opp:
        tags.append(f"<span class='tag tag-red'>{opp}</span>")
    elif "Near" in opp or "Watch" in opp:
        tags.append(f"<span class='tag tag-amber'>{opp}</span>")
    else:
        tags.append(f"<span class='tag tag-blue'>{opp}</span>")
    if detail.get("rebound_stage_label"):
        tags.append(f"<span class='tag tag-green'>Stage: {detail.get('rebound_stage_label')} · {detail.get('rebound_stage_score', 0)}/100</span>")
    if detail.get("stabilization_label"):
        tags.append(f"<span class='tag tag-yellow'>Stabilization: {detail.get('stabilization_label')} · {detail.get('stabilization_score', 0)}/100</span>")
    if detail.get("trigger_4h_label"):
        tags.append(f"<span class='tag tag-blue'>4H Trigger: {detail.get('trigger_4h_label')} · {detail.get('trigger_4h_score', 0)}/100</span>")
    tags.append(f"<span class='tag tag-green'>{detail.get('event_count', 0)} historical RSI&lt;30 events</span>")
    if detail.get("confidence_label"):
        tags.append(f"<span class='tag tag-blue'>{detail.get('confidence_label')}</span>")
    tags.append(f"<span class='tag tag-blue'>Setup Quality {detail.get('setup_quality', 0)}/100</span>")
    if detail.get("attention_label"):
        tags.append(f"<span class='tag tag-blue'>{detail.get('attention_label')}</span>")
    if detail.get("volume_trend_label"):
        tags.append(f"<span class='tag tag-blue'>Volume trend: {detail.get('volume_trend_label')}</span>")
    if detail.get("spring_label"):
        tags.append(f"<span class='tag tag-amber'>TTM {detail.get('spring_timeframe', '1D')} · {detail.get('spring_label')} · {detail.get('spring_score', 0)}/100</span>")
    if detail.get("catalyst_label"):
        tags.append(f"<span class='tag tag-blue'>{detail.get('catalyst_label')} · {detail.get('catalyst_score', 0)}/100</span>")
    st.markdown("".join(tags), unsafe_allow_html=True)
    if detail.get("rebound_stage_reason"):
        st.caption(f"Rebound stage: {detail['rebound_stage_reason']}")
    if detail.get("stabilization_reason"):
        st.caption(f"Stabilization: {detail['stabilization_reason']}")
    if detail.get("trigger_4h_reason"):
        st.caption(f"4H trigger: {detail['trigger_4h_reason']}")
    if detail.get("volume_trend_reason"):
        st.caption(f"Volume trend: {detail['volume_trend_reason']}")
    if detail.get("spring_reason"):
        st.caption(f"TTM spring read ({detail.get('spring_timeframe', '1D')}): {detail['spring_reason']}")
    if detail.get("catalyst_reason"):
        st.caption(f"Catalyst read: {detail['catalyst_reason']}")
    if detail.get("news_headline"):
        st.caption(f"Top headline: {detail['news_headline']}")

    st.plotly_chart(mini_chart(detail), use_container_width=True)

    st.markdown("### Historical swing outcomes after RSI panic")
    events = detail.get("events", [])
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True, height=260)
    else:
        st.info("No RSI <30 events in the past year for this ticker. It may still be interesting, but the model has less evidence to score it.")

st.divider()
export = display.copy()
csv = export.to_csv(index=False)
st.download_button(
    "Download watchlist CSV",
    data=csv,
    file_name=f"swingit_v5_3_{datetime.date.today()}.csv",
    mime="text/csv",
)
