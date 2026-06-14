"""
SwingIt V5.1 — RSI Panic + Catalyst + Multi-Timeframe TTM Spring Engine
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
import math

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
    page_title="SwingIt V5.1",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
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
        border-radius:18px;
        padding:18px 18px 14px 18px;
        box-shadow:0 8px 22px rgba(15,23,42,.06);
        min-height:185px;
    }
    .hot-title { font-size:1.05rem; font-weight:900; margin-bottom:3px; }
    .hot-score { font-size:2.0rem; font-weight:950; color:var(--accent); line-height:1.1; }
    .hot-meta { color:var(--muted); font-size:.86rem; margin-top:8px; line-height:1.45; }
    .hover-tip {
        position:relative;
        display:inline-block;
        cursor:help;
        border-bottom:1px dotted rgba(37,99,235,.45);
    }
    .hover-tip .tip-box {
        visibility:hidden;
        opacity:0;
        transition:opacity .15s ease;
        position:absolute;
        z-index:9999;
        left:0;
        top:125%;
        width:310px;
        background:#111827;
        color:#f9fafb!important;
        border-radius:12px;
        padding:12px 14px;
        box-shadow:0 14px 35px rgba(15,23,42,.25);
        font-size:.78rem;
        line-height:1.35;
        font-weight:500;
        text-align:left;
        border:1px solid rgba(255,255,255,.12);
    }
    .hover-tip .tip-box strong, .hover-tip .tip-box span { color:#f9fafb!important; }
    .hover-tip:hover .tip-box { visibility:visible; opacity:1; }
    .hot-card:nth-child(3) .hover-tip .tip-box { right:0; left:auto; }
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

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar — intentionally pared back
# ──────────────────────────────────────────────────────────────────────────────
custom_input = ""
with st.sidebar:
    st.markdown("## 🔥 SwingIt V5.1")
    st.markdown("*RSI rebound watchlist engine*")
    st.divider()

    universe = st.selectbox(
        "Universe",
        ["S&P 500", "NASDAQ 100", "Dow Jones 30", "Custom list"],
        help="Choose the stock universe to rank. The app ranks candidates rather than filtering them out."
    )
    if universe == "Custom list":
        custom_input = st.text_area(
            "Enter tickers",
            placeholder="ORCL, ADBE, AMZN, MSFT",
            help="Comma, semicolon, or newline separated."
        )

    max_results = st.slider("Max tickers to scan", 10, 500, 100, step=10)

    st.divider()
    st.markdown("#### Model settings")
    profit_target = st.select_slider(
        "Swing profit goal",
        options=[5, 8, 10, 12, 15, 20],
        value=8,
        help="A historical RSI panic event counts as a useful swing if the stock reached at least this max closing-price bounce within the selected window."
    )
    bounce_window = st.select_slider(
        "Swing window",
        options=[10, 15, 20, 30, 45, 60],
        value=30,
        help="How many trading days after the oversold low to measure the best closing-price bounce. For your 1–4 week style, 20–30 is usually the sweet spot."
    )

    include_news = st.toggle(
        "Add catalyst/news score",
        value=True,
        help="Adds a lightweight Yahoo Finance headline catalyst score. It can slow the scan a little, so turn it off if the app feels laggy."
    )

    spring_timeframe = st.selectbox(
        "TTM Spring timeframe",
        ["1D", "1H"],
        index=0,
        help="1D is better for 1–4 week swing context. 1H is better for near-term timing/watchlist urgency."
    )

    st.divider()
    run = st.button("Run Swing Scan", use_container_width=True)
    st.caption("Tip: this app is designed to find stocks worth watching, not to make entry decisions for you.")


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


DOW30 = [
    "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
    "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
    "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WBA", "WMT"
]


def get_universe_tickers(selected_universe: str, custom_text: str = ""):
    if selected_universe == "S&P 500":
        return get_sp500()
    if selected_universe == "NASDAQ 100":
        return get_nasdaq100()
    if selected_universe == "Dow Jones 30":
        return DOW30
    raw = custom_text.replace("\n", ",").replace(";", ",")
    return [t.strip().upper().replace(".", "-") for t in raw.split(",") if t.strip()]


# ──────────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ──────────────────────────────────────────────────────────────────────────────
def clamp(value, lo=0, hi=100):
    if value is None or pd.isna(value):
        return lo
    return max(lo, min(hi, float(value)))


def current_rsi_opportunity_score(current_rsi):
    """Scores how close the stock is to an actionable rebound zone right now."""
    if current_rsi is None or pd.isna(current_rsi):
        return 0
    r = float(current_rsi)
    if r < 20:
        return 95       # very washed out, but may still be falling
    if r < 25:
        return 100      # ideal panic zone
    if r < 30:
        return 92
    if r < 35:
        return 82
    if r < 40:
        return 68
    if r < 45:
        return 48
    if r < 50:
        return 28
    if r < 55:
        return 12
    return 0


def opportunity_label(current_rsi):
    if current_rsi is None or pd.isna(current_rsi):
        return "No RSI"
    r = float(current_rsi)
    if r < 25:
        return "🔥 Panic zone"
    if r < 30:
        return "🔥 Oversold"
    if r < 35:
        return "👀 Near oversold"
    if r < 40:
        return "Watch"
    if r < 50:
        return "Early watch"
    return "Already recovered"


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
    """Approximate TTM Squeeze status and score for daily swing timing.

    Squeeze ON = Bollinger Bands are inside Keltner Channels.
    Momentum uses a common TTM-style linear-regression momentum approximation.
    This is meant as a watchlist timing clue, not a precise Thinkorswim clone.
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

    squeeze_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    squeeze_on = squeeze_on.fillna(False)

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
    fading_down = slope > 0 and mom_now < 0
    worsening = slope < 0 and one_bar_change < 0

    if improving and mom_now < 0:
        trend = "🟢 Selling fading"
    elif improving and mom_now >= 0:
        trend = "🟢 Momentum rising"
    elif worsening and mom_now < 0:
        trend = "🔴 Pressure building"
    elif worsening:
        trend = "🟡 Cooling"
    else:
        trend = "⚪ Flat/mixed"

    # 0-100 Spring Score: separate from Swing Score so it acts as timing context.
    if current_squeeze:
        squeeze_component = 30
    elif recently_fired:
        squeeze_component = 18
    else:
        squeeze_component = 0

    if slope >= 1.0:
        momentum_component = 40
    elif slope >= 0.45:
        momentum_component = 32
    elif slope > 0:
        momentum_component = 22
    elif not worsening:
        momentum_component = 10
    else:
        momentum_component = 0

    abs_mom = abs(mom_now)
    if mom_now < 0 and abs_mom <= 1.0:
        zero_component = 20          # sellers fading and close to zero line
    elif mom_now < 0 and abs_mom <= 2.0:
        zero_component = 14
    elif mom_now >= 0 and abs_mom <= 2.0:
        zero_component = 16          # fired / early positive
    elif mom_now >= 0:
        zero_component = 10          # already running
    else:
        zero_component = 5           # deeply negative

    duration_component = clamp((min(squeeze_bars, 12) / 12) * 10)
    spring_score = int(round(clamp(squeeze_component + momentum_component + zero_component + duration_component)))

    if current_squeeze and fading_down and spring_score >= 70:
        label = "🟡 Loaded spring"
    elif current_squeeze:
        label = "🌀 Squeeze on"
    elif recently_fired and improving:
        label = "🟢 Fired upward"
    elif recently_fired:
        label = "🟡 Fired/mixed"
    elif worsening and mom_now < 0:
        label = "🔴 Falling"
    elif improving:
        label = "👀 Improving"
    else:
        label = "⚪ No squeeze"

    mom_3bar = " → ".join(f"{v:.2f}" for v in valid_mom.tail(3).tolist())
    reason = (
        f"Squeeze {'ON' if current_squeeze else 'OFF'}"
        f"{' · recently fired' if recently_fired else ''} · "
        f"{squeeze_bars} squeeze bars · momentum {mom_3bar} · {trend}"
    )

    return {
        "spring_score": spring_score,
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
        }
        catalyst_score = news.get("catalyst_score", 0)
        volume_score = 100 if (volume_ratio or 0) >= 2.5 else 70 if (volume_ratio or 0) >= 1.5 else 40 if (volume_ratio or 0) >= 1.1 else 0
        swing_score = int(round(clamp(
            0.40 * history_score +
            0.32 * opp_score +
            0.18 * catalyst_score +
            0.10 * volume_score
        )))

        # Momentum proximity flags for watchlist use, not entry signals.
        days_since_rsi_under_30 = None
        under_30_positions = [idx for idx, val in enumerate(rsi_series) if pd.notna(val) and val < 30]
        if under_30_positions:
            days_since_rsi_under_30 = len(rsi_series) - 1 - under_30_positions[-1]

        potential_sell_price = None
        if rebounds.get("avg_max_bounce_pct") is not None:
            potential_sell_price = current_price * (1 + float(rebounds["avg_max_bounce_pct"]) / 100)

        return {
            "ticker": ticker,
            "price": round(current_price, 2),
            "potential_sell_price": round(float(potential_sell_price), 2) if potential_sell_price is not None else None,
            "avg_vol_20d": int(avg_vol_20d) if avg_vol_20d else None,
            "current_volume": int(current_volume) if current_volume else None,
            "volume_ratio": round(float(volume_ratio), 2) if volume_ratio is not None else None,
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


def _volume_score_from_ratio(volume_ratio):
    vr = volume_ratio or 0
    if vr >= 2.5:
        return 100
    if vr >= 1.5:
        return 70
    if vr >= 1.1:
        return 40
    return 0


def hot_card(rank, row):
    medal = ["🥇", "🥈", "🥉"][rank] if rank < 3 else f"#{rank + 1}"
    ticker = _safe_html(row.get("Ticker"))
    score = row.get("Swing Score", "—")
    potential_price = row.get("Potential Swing Price", "—")
    current_price = row.get("Price", "—")
    history_score = row.get("History Score", "—")
    opp_score = row.get("Opportunity Score", "—")
    catalyst_score = row.get("Catalyst Score", "—")
    volume_ratio = row.get("Volume Ratio")
    volume_score = _volume_score_from_ratio(volume_ratio)
    catalyst = _safe_html(row.get("Catalyst", ""))
    spring = _safe_html(row.get("Spring", ""))
    spring_tf = _safe_html(row.get("Spring TF", ""))
    spring_score = row.get("Spring Score", "—")
    spring_reason = _safe_html(row.get("Spring Reason", "No spring details available."))
    catalyst_reason = _safe_html(row.get("Catalyst Reason", "No catalyst details available."))
    headline = _safe_html(row.get("Headline", "No headline available."))
    news = _safe_html(row.get("News", ""))

    score_tip = f"""
        <strong>Swing Score ingredients</strong><br>
        🧠 Historical swing behavior: {history_score}/100 × 40%<br>
        🎯 Current RSI opportunity: {opp_score}/100 × 32%<br>
        📰 Catalyst/news: {catalyst_score}/100 × 18%<br>
        📊 Volume confirmation: {volume_score}/100 × 10%<br><br>
        This is a watchlist score, not an entry signal.
    """
    news_tip = f"""
        <strong>News/catalyst read</strong><br>
        {catalyst_reason}<br><br>
        <strong>Top headline</strong><br>
        {headline}<br><br>
        Label: {news}
    """
    spring_tip = f"""
        <strong>TTM Spring read</strong><br>
        Timeframe: {spring_tf}<br>
        Spring Score: {spring_score}/100<br>
        {spring_reason}<br><br>
        Best use: high Swing Score + strong Catalyst + high Spring Score = stock worth watching closely for your 5m/15m entry process.
    """

    return f"""
    <div class="hot-card">
        <div class="hot-title">{medal} {ticker}</div>
        <div class="hot-score hover-tip">{score}
            <div class="tip-box">{score_tip}</div>
        </div>
        <div class="small-muted">Swing Score</div>
        <div class="hot-meta">
            {_safe_html(row.get('Opportunity'))}<br>
            Current {current_price} → Swing target {potential_price}<br>
            RSI {_safe_html(row.get('RSI'))} · Potential {_safe_html(row.get('Avg Max Bounce'))}<br>
            Avg max in {_safe_html(row.get('Avg Days to Max'))} days · {_safe_html(row.get('History'))}<br>
            <span class="hover-tip">{spring_tf} {spring} {spring_score}/100<div class="tip-box">{spring_tip}</div></span><br>
            <span class="hover-tip">{catalyst}<div class="tip-box">{news_tip}</div></span><br>
            {_safe_html(row.get('Confidence', ''))}
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
st.markdown("# 🔥 SwingIt V5.1")

# When the button is clicked, run the scan once and store the result.
if run:
    all_tickers = get_universe_tickers(universe, custom_input)
    if not all_tickers:
        st.warning("No tickers found. Check your custom list or choose another universe.")
        st.stop()

    tickers = all_tickers[:max_results]
    st.session_state.scan_meta = {
        "universe": universe,
        "max_results": max_results,
        "profit_target": profit_target,
        "bounce_window": bounce_window,
        "include_news": include_news,
        "spring_timeframe": spring_timeframe,
        "tickers_scanned": len(tickers),
        "run_date": datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    }

    st.info(f"Scanning {len(tickers)} tickers from {universe}…")
    progress = st.progress(0)
    status = st.empty()

    results = []
    for i, ticker in enumerate(tickers):
        status.caption(f"Checking {ticker}…")
        candidate = compute_candidate(ticker, profit_target, bounce_window, include_news, spring_timeframe)
        if candidate:
            results.append(candidate)
        progress.progress((i + 1) / len(tickers))

    progress.empty()
    status.empty()
    st.session_state.scan_results = results

# If no scan has been run yet, show landing state.
if st.session_state.scan_results is None:
    st.markdown(
        f"<div class='small-muted'>Choose a universe, then run the scan to rank 1–4 week RSI panic swing candidates.</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown(
        """
        <div style="background:#ffffff;border:1px solid #d8dee6;border-radius:18px;padding:36px;text-align:center;">
            <div style="font-size:3rem;">📈</div>
            <h3>Run the scan to build today's rebound watchlist.</h3>
            <p class="small-muted">This version keeps your results alive when you sort, change ticker detail, or interact with the page.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
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
st.divider()

if not results:
    st.warning("No usable price/RSI data came back. Try a smaller custom list or rerun in a minute.")
    st.stop()

# Compact model output table.
rows = []
for r in results:
    rows.append({
        "Ticker": r["ticker"],
        "Swing Score": r["swing_score"],
        "RSI": r["current_rsi"],
        "Opportunity": r["opportunity"],
        "Price": r["price"],
        "Potential Swing Price": r.get("potential_sell_price"),
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
        "Volume Ratio": r.get("volume_ratio"),
        "Volume Score": _volume_score_from_ratio(r.get("volume_ratio")),
        "News": r.get("news_label"),
        "Headline": r.get("news_headline"),
        "History Score": r.get("history_score"),
        "Opportunity Score": r.get("opportunity_score"),
        "Days Since RSI <30": r.get("days_since_rsi_under_30"),
        "Avg Lowest RSI": r.get("avg_lowest_rsi"),
        "Avg Drawdown After Low": r.get("avg_post_low_drawdown_pct"),
    })

df = pd.DataFrame(rows)
df_sorted = df.sort_values(["Swing Score", "RSI"], ascending=[False, True], na_position="last").reset_index(drop=True)

# Top summary metrics
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Scanned", active_tickers_scanned or len(results))
c2.metric("Usable results", len(df_sorted))
c3.metric("RSI < 40 now", int((pd.to_numeric(df_sorted["RSI"], errors="coerce") < 40).sum()))
c4.metric("High-confidence patterns", int(df_sorted["Confidence"].astype(str).str.contains("High", na=False).sum()))
c5.metric("Spring ≥70", int((pd.to_numeric(df_sorted["Spring Score"], errors="coerce") >= 70).sum()))

st.markdown("## 🔥 Best Swing Opportunities")
top = df_sorted.head(3)
if not top.empty:
    card_cols = st.columns(len(top))
    for idx, (_, row) in enumerate(top.iterrows()):
        with card_cols[idx]:
            st.markdown(hot_card(idx, row), unsafe_allow_html=True)

st.divider()
st.markdown("## Watchlist Leaderboard")

sort_a, sort_b, sort_c = st.columns([1.4, 1, 1])
with sort_a:
    default_sort = "Swing Score" if "Swing Score" in df_sorted.columns else df_sorted.columns[0]
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
display = df_sorted.sort_values(sort_by, ascending=ascending, na_position="last").reset_index(drop=True)

compact_cols = [
    "Ticker", "Swing Score", "Spring TF", "Spring Score", "Spring", "RSI", "Opportunity", "Price", "Potential Swing Price", "Avg Max Bounce", "Avg Days to Max", "History", "Confidence", "Catalyst", "Catalyst Score"
]
research_cols = compact_cols + [
    "Spring Reason", "Squeeze Bars", "Momentum Trend", "Momentum 3-Bar", "Catalyst Reason", "Volume Ratio", "Volume Score", "Headline", "Successful Swings", "Win Rate", "Risk / Reward", "History Score", "Confidence Score", "Opportunity Score", "Days Since RSI <30", "Avg Lowest RSI", "Avg Drawdown After Low"
]
show_cols = compact_cols if view_mode == "Compact" else research_cols

st.dataframe(
    display[show_cols],
    use_container_width=True,
    hide_index=True,
    height=440,
    column_config={
        "Swing Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "Spring Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
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

with st.expander("What the Swing Score means"):
    st.markdown(f"""
    **Swing Score V5** is a watchlist score: *is this stock washed out, historically bouncy, and does it have a reason to move?*

    **Spring Score** is separate. It uses the selected TTM timeframe from the sidebar (1D or 1H) and a TTM Squeeze-style calculation to ask: *is volatility compressed or recently released, and is momentum improving right now?* A high Spring Score is not a buy signal by itself, but it can help you prioritize which high Swing Score names are closest to becoming actionable.

    It combines:

    **1. Current opportunity score** — how close the stock is to an actionable RSI rebound zone right now. RSI under 30 scores highest; RSI 30–40 is still watchable; RSI above 50 scores low because it may have already recovered.

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

    Current V5.1 Swing Score weighting: 40% historical swing behavior, 32% current RSI opportunity, 18% catalyst/news, 10% volume confirmation. Spring Score is shown separately so timing does not overpower the historical/catalyst watchlist model.

    This is meant to produce a **watchlist**, not a buy signal. Entries should still come from price action, VWAP, volume, support/reclaim behavior, and your 5m/15m process.
    """)
st.divider()
st.markdown("## Ticker Detail")
selected = st.selectbox("Inspect ticker", display["Ticker"].tolist(), key="ticker_detail_select")
detail = next((r for r in results if r["ticker"] == selected), None)

if detail:
    a, b, c, d, e, f, g = st.columns(7)
    a.metric("Swing Score", f"{detail['swing_score']}/100")
    b.metric("Spring Score", f"{detail.get('spring_score', 0)}/100")
    c.metric("RSI", detail.get("current_rsi", "—"))
    d.metric("Price", f"${detail['price']}")
    f_price = detail.get("potential_sell_price")
    e.metric("Potential Swing Price", f"${f_price}" if f_price is not None else "—")
    f.metric("Avg Max Bounce", format_pct(detail.get("avg_max_bounce_pct")))
    g.metric("Avg Days to Max", detail.get("avg_days_to_max_bounce", "—"))

    tags = []
    opp = detail.get("opportunity", "")
    if "Panic" in opp or "Oversold" in opp:
        tags.append(f"<span class='tag tag-red'>{opp}</span>")
    elif "Near" in opp or "Watch" in opp:
        tags.append(f"<span class='tag tag-amber'>{opp}</span>")
    else:
        tags.append(f"<span class='tag tag-blue'>{opp}</span>")
    tags.append(f"<span class='tag tag-green'>{detail.get('event_count', 0)} historical RSI&lt;30 events</span>")
    if detail.get("confidence_label"):
        tags.append(f"<span class='tag tag-blue'>{detail.get('confidence_label')}</span>")
    if detail.get("spring_label"):
        tags.append(f"<span class='tag tag-amber'>TTM {detail.get('spring_timeframe', '1D')} · {detail.get('spring_label')} · {detail.get('spring_score', 0)}/100</span>")
    if detail.get("catalyst_label"):
        tags.append(f"<span class='tag tag-blue'>{detail.get('catalyst_label')} · {detail.get('catalyst_score', 0)}/100</span>")
    st.markdown("".join(tags), unsafe_allow_html=True)
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
    file_name=f"swingit_v5_1_{datetime.date.today()}.csv",
    mime="text/csv",
)
