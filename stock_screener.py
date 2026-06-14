"""
SwingIt V10 — Morning Report + Trading Terminal UI
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
    page_title="SwingIt V10",
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
    "⭐ SwingIt Elite (Recommended)": "VOO + VTI/ITOT + QQQM style quality universe",
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
    "VTI Holdings": "Total-market style holdings via ITOT proxy",
    "QQQM Holdings": "Nasdaq-100 ETF holdings",
    "SCHG Holdings": "Large-cap growth ETF holdings",
    "VGT Holdings": "Technology ETF holdings",
    "SMH Holdings": "Semiconductor ETF holdings",
    "SOXX Holdings": "Semiconductor ETF holdings",
    "Custom list": "Paste tickers manually",
}

with st.container(border=True):
    top_title_col, top_universe_col, top_model_col, top_run_col = st.columns(
        [1.35, 2.35, 1.65, 1.25],
        vertical_alignment="center",
    )

    with top_title_col:
        st.markdown(
            """
            <div class="terminal-title">🔥 SwingIt V10</div>
            <div class="terminal-subtitle">RSI panic rebound candidates.</div>
            """,
            unsafe_allow_html=True,
        )

    with top_universe_col:
        st.markdown("<div class='toolbar-label'>Universe</div>", unsafe_allow_html=True)
        universe = st.selectbox(
            "Universe",
            UNIVERSE_OPTIONS,
            index=0,
            label_visibility="collapsed",
            help="Choose the group to scan. The app scans the full selected universe by default.",
            key="top_universe",
        )
        st.markdown(f"<div class='toolbar-help'>{html.escape(UNIVERSE_HINTS.get(universe, ''))}</div>", unsafe_allow_html=True)

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
        run = st.button("🚀 Run Swing Scan", use_container_width=True)
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

st.markdown("---")


# ──────────────────────────────────────────────────────────────────────────────
# Favorites + uploaded universe helpers
# ──────────────────────────────────────────────────────────────────────────────
FAVORITES_FILE = "swingit_favorites.json"


def _normalize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper().replace(".", "-")


def load_favorites() -> list[str]:
    """Load persistent favorites from a small JSON file in the app directory."""
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return dedupe([_normalize_ticker(t) for t in data if str(t).strip()])
    except Exception:
        pass
    return []


def save_favorites(tickers: list[str]) -> None:
    try:
        clean = dedupe([_normalize_ticker(t) for t in tickers if str(t).strip()])
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2)
    except Exception:
        st.warning("Could not save favorites to disk in this environment. They will still work during this session.")




# ──────────────────────────────────────────────────────────────────────────────
# Morning Report helpers — Zazu mode for Favorites
# ──────────────────────────────────────────────────────────────────────────────
MORNING_SNAPSHOT_FILE = "swingit_morning_snapshot.json"


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
    st.caption("Favorites-first briefing: what changed, what is actionable, and what should be ignored for now.")
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

    out = pd.DataFrame()
    out["Ticker"] = df[symbol_col].apply(clean_yahoo_ticker)
    out["Name"] = df[name_col].astype(str) if name_col in df.columns else out["Ticker"]
    out["MarketCap"] = df[market_col].apply(parse_market_cap) if market_col in df.columns else 0.0
    out["ETF"] = df[etf_col].astype(str).str.upper() if etf_col in df.columns else "N"
    out["Country"] = df[country_col].astype(str) if country_col in df.columns else "United States"

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
    "FXAIX": lambda: get_sp500_etf_proxy(),
    "VOO": lambda: get_sp500_etf_proxy(),
    "VTI": lambda: get_total_market(),
    "QQQM": lambda: get_nasdaq100(),
    "SCHG": lambda: SCHG_NAMES,
    "VGT": lambda: VGT_NAMES,
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
def get_universe_payload(selected_universe: str, custom_text: str = ""):
    """Returns (tickers, source_map) for the selected universe."""
    source_map = {}

    def add_etf(etf):
        names = ETF_LISTS[etf]()
        add_sources(source_map, names, etf)
        return names

    if selected_universe == "⭐ Favorites":
        tickers = load_favorites(); add_sources(source_map, tickers, "Favorites")
    elif selected_universe == "📂 CSV upload":
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
        add_sources(source_map, tickers, "Russell 1000 / IWB")
    elif selected_universe == "Russell 3000":
        tickers = get_russell3000()
        add_sources(source_map, tickers, "Russell 3000 / IWV")
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

    # Convert sets to sorted lists for caching/session-state friendliness.
    source_map = {k: sorted(v) for k, v in source_map.items()}
    return dedupe(tickers), source_map


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


def opportunity_remaining_from_cycle(current_price, cycle_low_price, avg_max_bounce_pct):
    """Estimate how much of the historical rebound move remains in the current RSI panic cycle.

    Anchor = most recent RSI<30 event low close.
    Target = anchor low close plus the stock's average max rebound after prior RSI panic events.
    This avoids ranking names that already made most of their usual move.
    """
    try:
        current = float(current_price)
        low = float(cycle_low_price)
        bounce = float(avg_max_bounce_pct)
    except Exception:
        return {
            "opportunity_remaining_pct": None,
            "opportunity_remaining_score": 0,
            "opportunity_remaining_label": "⚪ No cycle target",
            "cycle_low_price": None,
            "cycle_target_price": None,
            "move_completed_pct": None,
        }

    if low <= 0 or bounce <= 0:
        return {
            "opportunity_remaining_pct": None,
            "opportunity_remaining_score": 0,
            "opportunity_remaining_label": "⚪ No cycle target",
            "cycle_low_price": low if low > 0 else None,
            "cycle_target_price": None,
            "move_completed_pct": None,
        }

    target = low * (1 + bounce / 100.0)
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

    last_vals = valid_mom.tail(4).tolist()
    mom_now = float(last_vals[-1])
    mom_prev = float(last_vals[-2]) if len(last_vals) >= 2 else mom_now
    mom_3ago = float(last_vals[0]) if len(last_vals) >= 4 else mom_prev
    slope = mom_now - mom_3ago
    one_bar_change = mom_now - mom_prev

    improving = slope > 0 and one_bar_change >= 0
    worsening = slope < 0 and one_bar_change < 0
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
    elif (not current_squeeze) and (not recently_fired) and negative and improving:
        label = "🔵 Early Turn"
        spring_score = 75
        state_note = "No active squeeze, but negative momentum is improving."
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

        current_price = float(close.iloc[-1])
        current_rsi = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else None
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

        rebound_stage_score, rebound_stage_label, rebound_stage_reason = rebound_stage_from_series(
            close, rsi_series, spring.get("spring_score", 0), days_since_rsi_under_30
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
            0.20 * opp_score +
            0.25 * rebound_stage_score +
            0.20 * catalyst_score +
            0.20 * spring.get("spring_score", 0) +
            0.10 * attention_score +
            0.05 * volume_trend_score
        )))

        potential_sell_price = None
        if rebounds.get("avg_max_bounce_pct") is not None:
            potential_sell_price = current_price * (1 + float(rebounds["avg_max_bounce_pct"]) / 100)

        # Opportunity Remaining answers: if this is the current RSI panic cycle,
        # how much of its usual historical rebound is still left from the RSI-event low?
        recent_cycle_low_price = None
        recent_cycle_low_date = None
        if rebounds.get("events"):
            recent_event = rebounds["events"][-1]
            recent_cycle_low_price = recent_event.get("Low Close")
            recent_cycle_low_date = recent_event.get("RSI Low Date")
        opp_remaining = opportunity_remaining_from_cycle(
            current_price,
            recent_cycle_low_price,
            rebounds.get("avg_max_bounce_pct"),
        )


        panic = panic_shock_from_df(close, volume, lookback_days=15)
        narrative = narrative_mismatch_from_news(news, panic.get("panic_shock_score", 0))
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
]

RANKING_HELP = {
    "🎯 8% Target Hunter": "Ranks for the best blend of historical rebound edge, current turn-zone timing, confidence, and chance of reaching your selected profit target.",
    "⚡ Ready Now": "Ranks for names closest to a near-term trigger: strong setup quality, spring timing, RVOL/attention, fresh catalyst, and volume trend.",
    "🧠 Highest Confidence": "Ranks for the most repeatable historical pattern: more events, stronger confidence, better swing history, and cleaner risk/reward.",
    "🚀 Maximum Upside": "Ranks for the largest potential reward. This can surface more volatile names, so use confidence and drawdown carefully.",
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
            0.25 * opp_remaining +
            0.22 * setup +
            0.20 * spring +
            0.14 * stage +
            0.09 * attention +
            0.06 * catalyst +
            0.04 * volume_trend
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
        scores.append((target_hunter, ready_now, highest_confidence, maximum_upside, overreaction_rank, bounce, speed))

    out["🎯 Target Hunter Score"] = [int(round(x[0])) for x in scores]
    out["⚡ Ready Now Score"] = [int(round(x[1])) for x in scores]
    out["🧠 Confidence Rank Score"] = [int(round(x[2])) for x in scores]
    out["🚀 Upside Rank Score"] = [int(round(x[3])) for x in scores]
    out["😱 Overreaction Rank Score"] = [int(round(x[4])) for x in scores]
    out["Target Bounce Score"] = [int(round(x[5])) for x in scores]
    out["Speed Score"] = [int(round(x[6])) for x in scores]
    return out


def ranking_column_for(mode: str) -> str:
    return {
        "🎯 8% Target Hunter": "🎯 Target Hunter Score",
        "⚡ Ready Now": "⚡ Ready Now Score",
        "🧠 Highest Confidence": "🧠 Confidence Rank Score",
        "🚀 Maximum Upside": "🚀 Upside Rank Score",
        "😱 Overreaction": "😱 Overreaction Rank Score",
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

    swing_score = row.get("Swing Score", "—")
    setup_quality = row.get("Setup Quality", "—")
    spring_score = row.get("Spring Score", "—")

    current_price = row.get("Price", "—")
    potential_price = row.get("Potential Swing Price", "—")
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
        Rebound stage: {rebound_stage_score}/100 × 25%<br>
        Catalyst/news: {catalyst_score}/100 × 20%<br>
        TTM Spring timing: {spring_score}/100 × 20%<br>
        Attention/RVOL: {attention_score}/100 × 10%<br>
        Volume trend: {volume_trend_score}/100 × 5%
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
        Potential swing price from current: {_safe_html(potential_price)}<br>
        Cycle target from RSI panic low: {_safe_html(cycle_target_price)}<br><br>
        The potential swing price uses the stock's average historical max bounce from the current price. The cycle target anchors the move to the most recent RSI panic low.
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
        <strong>Historical bounce behavior</strong><br>
        Avg max bounce: {_safe_html(avg_max)}%<br>
        Avg days to max bounce: {_safe_html(avg_days)} trading days<br><br>
        This is based on prior RSI &lt;30 panic events and your selected swing window.
    """

    stage_tip = f"""
        <strong>Rebound stage</strong><br>
        {_safe_html(clean_label(rebound_stage))}: {rebound_stage_score}/100<br><br>
        {rebound_stage_reason}<br><br>
        The ideal zone for this app is often Early Reversal: recently oversold, RSI rising, and price starting to lift from the low.
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
        <strong>News / catalyst</strong><br>
        {catalyst_reason}<br><br>
        <strong>Top headline</strong><br>
        {headline}<br><br>
        News label: {news}
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
        <div class="score-row">
            <div class="score-tile hover-tip"><div class="score-num">{swing_score}</div><div class="score-label">Swing</div><div class="tip-box">{swing_tip}</div></div>
            <div class="score-tile hover-tip"><div class="score-num">{setup_quality}</div><div class="score-label">Setup</div><div class="tip-box">{setup_tip}</div></div>
            <div class="score-tile hover-tip"><div class="score-num">{spring_score}</div><div class="score-label">Spring</div><div class="tip-box">{spring_score_tip}</div></div>
        </div>
        <div class="hot-meta">
            {hover_item('Price', f'{current_price} → {potential_price}', price_tip, dot=True)}
            {hover_item('RSI', f'{rsi} · {clean_label(opportunity)}', rsi_tip, dot=True)}
            {hover_item('Stage', clean_label(rebound_stage), stage_tip, dot=True)}
            {hover_item('Potential', f'+{avg_max}% in {avg_days}d avg', bounce_tip, dot=True)}
            {hover_item('Remaining', clean_label(opportunity_remaining), remaining_tip, dot=True)}
            {hover_item('Overreaction', clean_label(overreaction), overreaction_tip, dot=True)}
            {hover_item('History', history, history_tip, dot=True)}
            {hover_item('Attention', clean_label(attention), attention_tip, dot=True)}
            {hover_item('Volume trend', clean_label(volume_trend), volume_trend_tip, dot=True)}
            {hover_item('Spring', f'{spring_tf} · {clean_label(spring)}', spring_score_tip, dot=True)}
            {hover_item('News', clean_label(catalyst), news_tip, dot=True)}
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
# Main UI — stateful so ticker dropdowns/sorting do NOT wipe scan results
# ──────────────────────────────────────────────────────────────────────────────
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
                st.caption(f"Will scan {fav_count} Favorites and compare against your last Morning Report snapshot.")
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
        "universe": scan_universe,
        "morning_report": bool(run_morning_report),
        "previous_morning_snapshot": previous_morning_snapshot,
        "profit_target": profit_target,
        "bounce_window": bounce_window,
        "include_news": include_news,
        "spring_timeframe": spring_timeframe,
        "scan_speed": max_workers,
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
    completed = 0

    # Parallel scan: keeps the UI responsive enough to show progress while reducing long universe waits.
    # If a provider throttles requests, lower Scan speed in Model settings.
    with ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
        future_map = {
            executor.submit(compute_candidate, ticker, profit_target, bounce_window, include_news, spring_timeframe): ticker
            for ticker in tickers
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

            status.caption(f"Scanned {completed:,} / {len(tickers):,} tickers · Latest: {ticker} · Usable: {len(results):,}")
            progress.progress(min(completed / len(tickers), 1.0))

            if results and (completed % 25 == 0 or completed == len(tickers)):
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
        "Price": r["price"],
        "Potential Swing Price": r.get("potential_sell_price"),
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
        "News": r.get("news_label"),
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
        index=0,
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
        index=0,
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
    "Ticker", "Favorite", "Active Rank Score", "Setup Quality", "Swing Score", "Rebound Stage", "Spring TF", "Spring", "Spring Score", "Attention", "Volume Trend", "RSI", "Opportunity", "Price", "Potential Swing Price", "Avg Max Bounce", "Avg Days to Max", "History", "Confidence", "Catalyst"
]
research_cols = compact_cols + [
    "🎯 Target Hunter Score", "⚡ Ready Now Score", "🧠 Confidence Rank Score", "🚀 Upside Rank Score", "Target Bounce Score", "Speed Score", "Rebound Stage Score", "Rebound Stage Reason", "Spring Reason", "Squeeze Bars", "Momentum Trend", "Momentum 3-Bar", "Catalyst Score", "Catalyst Reason", "Attention Score", "Volume Trend Score", "Volume Trend Reason", "Volume Ratio", "Volume Score", "Headline", "Successful Swings", "Win Rate", "Risk / Reward", "History Score", "Confidence Score", "Opportunity Score", "Opportunity Remaining Score", "Opportunity Remaining %", "Move Completed %", "Cycle Low Price", "Cycle Target Price", "Days Since RSI <30", "Last RSI <30 Date", "Oversold Since", "Avg Lowest RSI", "Avg Drawdown After Low"
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
    st.caption("Favorites are a saved universe. Choose ⭐ Favorites in the Universe menu to scan only these tickers.")
    st.write(", ".join(favs) if favs else "No favorites saved yet.")
    add_text = st.text_input("Add tickers to Favorites", placeholder="ORCL, ADBE, META", key="favorites_add_text")
    fav_a, fav_b, fav_c = st.columns([1, 1, 3])
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

    **Potential Swing Price** is not an analyst target. It is simply current price plus the stock’s average max bounce after prior RSI&lt;30 events within the selected swing window.

    Current V6.4 uses multiple view-by lenses plus two core scores: **Swing Score** (46% historical swing behavior, 34% current RSI opportunity, 14% catalyst/news, 6% attention/RVOL) and **Setup Quality** (20% current RSI opportunity, 25% Rebound Stage, 20% catalyst/news, 20% TTM Spring, 10% attention/RVOL, 5% volume trend).

    **View By** defines what #1 means. 🎯 Target Hunter is the default for your 8% swing goal; ⚡ Ready Now is for what to open in ThinkorSwim first; 🧠 Highest Confidence is the safest historical pattern; 🚀 Maximum Upside is the biggest reward lens. V6.4 also adds **Opportunity Remaining**, which estimates how much of the usual RSI-panic rebound may still be left from the most recent panic-cycle low.

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
