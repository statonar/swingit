"""
SwingIt V3 — RSI Rebound Probability Engine
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
    page_title="SwingIt V3",
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
# Sidebar — intentionally pared back
# ──────────────────────────────────────────────────────────────────────────────
custom_input = ""
with st.sidebar:
    st.markdown("## 🔥 SwingIt V3")
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
    rsi_target = st.select_slider(
        "Rebound target RSI",
        options=[45, 50, 55, 60],
        value=50,
        help="50 is a practical neutral-momentum target. 55/60 are stricter and favor stronger rebound histories."
    )
    bounce_window = st.select_slider(
        "Bounce window",
        options=[10, 15, 20, 30, 45, 60],
        value=30,
        help="How many trading days after the oversold low to measure the best closing-price bounce."
    )

    include_news = st.toggle(
        "Add news snapshot",
        value=True,
        help="Adds a lightweight Yahoo Finance news read. It can slow the scan a little, so turn it off if the app feels laggy."
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
def analyze_rsi_rebounds(close, rsi_series, target_level=50, bounce_days=30, oversold_level=30):
    empty = {
        "events": [],
        "event_count": 0,
        "target_recovery_rate": None,
        "avg_days_to_target": None,
        "avg_gain_to_target_pct": None,
        "avg_max_bounce_pct": None,
        "avg_days_to_max_bounce": None,
        "avg_lowest_rsi": None,
        "avg_post_low_drawdown_pct": None,
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

            target_pos = None
            for j in range(end_pos + 1, n):
                if data["rsi"].iloc[j] >= target_level:
                    target_pos = j
                    break

            hit_target = target_pos is not None
            target_date = data.index[target_pos] if hit_target else None
            target_close = float(data["close"].iloc[target_pos]) if hit_target else None
            days_to_target = int(target_pos - low_pos) if hit_target else None
            gain_to_target = ((target_close / low_close) - 1) * 100 if hit_target and low_close else None

            window_end = min(n - 1, low_pos + int(bounce_days))
            bounce_slice = data.iloc[low_pos:window_end + 1]
            max_date = bounce_slice["close"].idxmax()
            max_pos = data.index.get_loc(max_date)
            max_close = float(data.loc[max_date, "close"])
            max_bounce = ((max_close / low_close) - 1) * 100 if low_close else None
            days_to_max = int(max_pos - low_pos)

            drawdown_end = target_pos if hit_target else window_end
            dd_slice = data.iloc[low_pos:drawdown_end + 1]
            min_after = float(dd_slice["close"].min())
            post_low_dd = ((min_after / low_close) - 1) * 100 if low_close else None

            events.append({
                "Start Date": data.index[start_pos].date(),
                "RSI Low Date": low_date.date(),
                "Lowest RSI": round(lowest_rsi, 1),
                "Low Close": round(low_close, 2),
                f"Hit RSI {target_level}": hit_target,
                f"Days to RSI {target_level}": days_to_target,
                f"Gain to RSI {target_level} %": round(gain_to_target, 2) if gain_to_target is not None else None,
                f"Max {bounce_days}D Bounce %": round(max_bounce, 2) if max_bounce is not None else None,
                f"Days to Max {bounce_days}D Bounce": days_to_max,
                "Post-Low Drawdown %": round(post_low_dd, 2) if post_low_dd is not None else None,
                "Target Date": target_date.date() if target_date is not None else None,
                f"Max {bounce_days}D Date": max_date.date(),
            })
        i += 1

    event_count = len(events)
    if event_count == 0:
        return empty

    hits = [e for e in events if e[f"Hit RSI {target_level}"]]
    recovery_rate = len(hits) / event_count * 100

    avg_days = pd.Series([e[f"Days to RSI {target_level}"] for e in hits]).mean() if hits else None
    avg_gain = pd.Series([e[f"Gain to RSI {target_level} %"] for e in hits]).mean() if hits else None
    avg_bounce = pd.Series([e[f"Max {bounce_days}D Bounce %"] for e in events]).mean()
    avg_days_max = pd.Series([e[f"Days to Max {bounce_days}D Bounce"] for e in events]).mean()
    avg_lowest_rsi = pd.Series([e["Lowest RSI"] for e in events]).mean()
    avg_dd = pd.Series([e["Post-Low Drawdown %"] for e in events]).mean()

    recovery_component = recovery_rate
    bounce_component = clamp((avg_bounce / 15) * 100) if not pd.isna(avg_bounce) else 0
    target_gain_component = clamp((avg_gain / 10) * 100) if avg_gain is not None and not pd.isna(avg_gain) else 0
    speed_component = speed_score(avg_days)
    days_max_component = days_to_max_score(avg_days_max)
    depth_component = clamp(((30 - avg_lowest_rsi) / 15) * 100) if not pd.isna(avg_lowest_rsi) else 0
    sample_component = clamp((min(event_count, 6) / 6) * 100)
    drawdown_penalty = clamp(abs(min(avg_dd, 0)) * 2.5, 0, 15) if not pd.isna(avg_dd) else 0

    history_score = (
        0.20 * recovery_component
        + 0.22 * bounce_component
        + 0.13 * target_gain_component
        + 0.13 * speed_component
        + 0.12 * days_max_component
        + 0.08 * depth_component
        + 0.12 * sample_component
        - drawdown_penalty
    )

    return {
        "events": events,
        "event_count": event_count,
        "target_recovery_rate": round(recovery_rate, 1),
        "avg_days_to_target": round(float(avg_days), 1) if avg_days is not None and not pd.isna(avg_days) else None,
        "avg_gain_to_target_pct": round(float(avg_gain), 2) if avg_gain is not None and not pd.isna(avg_gain) else None,
        "avg_max_bounce_pct": round(float(avg_bounce), 2) if not pd.isna(avg_bounce) else None,
        "avg_days_to_max_bounce": round(float(avg_days_max), 1) if not pd.isna(avg_days_max) else None,
        "avg_lowest_rsi": round(float(avg_lowest_rsi), 1) if not pd.isna(avg_lowest_rsi) else None,
        "avg_post_low_drawdown_pct": round(float(avg_dd), 2) if not pd.isna(avg_dd) else None,
        "history_score": int(round(clamp(history_score))),
    }



NEWS_POSITIVE_WORDS = [
    "beat", "beats", "upgrade", "upgraded", "raises", "raised", "record", "growth", "profit", "profits",
    "strong", "bullish", "partnership", "contract", "approval", "launch", "expands", "outperform",
    "buy", "guidance", "surge", "rallies", "rebound"
]
NEWS_NEGATIVE_WORDS = [
    "miss", "misses", "downgrade", "downgraded", "cuts", "cut", "lawsuit", "probe", "investigation",
    "weak", "bearish", "layoffs", "recall", "decline", "falls", "slumps", "warning", "loss", "losses",
    "guidance cut", "underperform", "sell", "debt", "concern", "concerns"
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


@st.cache_data(ttl=1800, show_spinner=False)
def get_news_snapshot(ticker: str):
    """Returns a simple, non-trading news label. Uses headline keywords only."""
    try:
        items = yf.Ticker(ticker).news or []
        headlines = []
        dates = []
        for item in items[:8]:
            title = _safe_news_title(item).strip()
            if title:
                headlines.append(title)
                d = _safe_news_time(item)
                if d:
                    dates.append(d)

        if not headlines:
            return {"news_label": "📰 No news", "news_headline": "No recent Yahoo Finance headlines found."}

        text = " ".join(headlines).lower()
        pos = sum(1 for word in NEWS_POSITIVE_WORDS if word in text)
        neg = sum(1 for word in NEWS_NEGATIVE_WORDS if word in text)

        most_recent = max(dates) if dates else None
        if most_recent:
            age_days = (datetime.date.today() - most_recent).days
            recency = "Recent" if age_days <= 7 else "Older"
        else:
            recency = "Recent"

        if pos > neg:
            tone = "Positive"
            emoji = "🟢"
        elif neg > pos:
            tone = "Negative"
            emoji = "🔴"
        else:
            tone = "Mixed/neutral"
            emoji = "🟡"

        return {
            "news_label": f"{emoji} {recency} / {tone}",
            "news_headline": headlines[0][:140],
        }
    except Exception:
        return {"news_label": "📰 News unavailable", "news_headline": "News lookup failed or was rate-limited."}


@st.cache_data(ttl=300, show_spinner=False)
def compute_candidate(ticker: str, target_level: int, bounce_days: int, include_news_lookup: bool = True):
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

        current_price = float(close.iloc[-1])
        current_rsi = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else None
        opp_score = current_rsi_opportunity_score(current_rsi)
        rebounds = analyze_rsi_rebounds(close, rsi_series, target_level=target_level, bounce_days=bounce_days)
        history_score = rebounds["history_score"]

        # Swing score = historical edge + current opportunity.
        # This prevents stocks that already fully recovered from dominating the watchlist.
        swing_score = int(round(clamp(0.58 * history_score + 0.42 * opp_score)))

        # Momentum proximity flags for watchlist use, not entry signals.
        days_since_rsi_under_30 = None
        under_30_positions = [idx for idx, val in enumerate(rsi_series) if pd.notna(val) and val < 30]
        if under_30_positions:
            days_since_rsi_under_30 = len(rsi_series) - 1 - under_30_positions[-1]

        news = get_news_snapshot(ticker) if include_news_lookup else {"news_label": "Off", "news_headline": "News snapshot is turned off."}
        potential_sell_price = None
        if rebounds.get("avg_max_bounce_pct") is not None:
            potential_sell_price = current_price * (1 + float(rebounds["avg_max_bounce_pct"]) / 100)

        return {
            "ticker": ticker,
            "price": round(current_price, 2),
            "potential_sell_price": round(float(potential_sell_price), 2) if potential_sell_price is not None else None,
            "avg_vol_20d": int(volume.tail(20).mean()) if len(volume) else None,
            "current_rsi": round(current_rsi, 1) if current_rsi is not None else None,
            "opportunity": opportunity_label(current_rsi),
            "opportunity_score": int(round(opp_score)),
            "history_score": history_score,
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


def hot_card(rank, row):
    medal = ["🥇", "🥈", "🥉"][rank] if rank < 3 else f"#{rank + 1}"
    potential_price = row.get("Potential Swing Price", "—")
    current_price = row.get("Price", "—")
    return f"""
    <div class="hot-card">
        <div class="hot-title">{medal} {row['Ticker']}</div>
        <div class="hot-score">{row['Swing Score']}</div>
        <div class="small-muted">Swing Score</div>
        <div class="hot-meta">
            {row['Opportunity']}<br>
            Current {current_price} → Swing target {potential_price}<br>
            RSI {row['RSI']} · Potential {row['Avg Max Bounce']}<br>
            Avg max in {row['Avg Days to Max']} days · {row['History']}
        </div>
    </div>
    """


def mini_chart(data):
    df = data["df"].copy()
    dates = df.index
    close = df["Close"].astype(float)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.68, 0.32],
        vertical_spacing=0.06,
        subplot_titles=("Price + moving averages", "RSI (14)"),
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

    fig.update_layout(
        height=560,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#334155", size=11),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    for i in range(1, 3):
        fig.update_xaxes(gridcolor="#e2e8f0", row=i, col=1)
        fig.update_yaxes(gridcolor="#e2e8f0", row=i, col=1)
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Main UI
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("# 🔥 SwingIt V3")
st.markdown(
    f"<div class='small-muted'>Ranking {universe} for 1–4 week RSI rebound swing candidates · Target RSI {rsi_target} · Max bounce window {bounce_window} trading days</div>",
    unsafe_allow_html=True,
)
st.divider()

if not run:
    st.markdown(
        """
        <div style="background:#ffffff;border:1px solid #d8dee6;border-radius:18px;padding:36px;text-align:center;">
            <div style="font-size:3rem;">📈</div>
            <h3>Run the scan to build today's rebound watchlist.</h3>
            <p class="small-muted">This version removes the extra filters and ranks stocks by current RSI opportunity + historical rebound behavior.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

all_tickers = get_universe_tickers(universe, custom_input)
if not all_tickers:
    st.warning("No tickers found. Check your custom list or choose another universe.")
    st.stop()

tickers = all_tickers[:max_results]
st.info(f"Scanning {len(tickers)} tickers from {universe}…")
progress = st.progress(0)
status = st.empty()

results = []
for i, ticker in enumerate(tickers):
    status.caption(f"Checking {ticker}…")
    candidate = compute_candidate(ticker, rsi_target, bounce_window, include_news)
    if candidate:
        results.append(candidate)
    progress.progress((i + 1) / len(tickers))

progress.empty()
status.empty()

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
        f"Avg Gain to RSI {rsi_target}": r.get("avg_gain_to_target_pct"),
        f"Avg Days to RSI {rsi_target}": r.get("avg_days_to_target"),
        "History": f"{r.get('event_count', 0)} events",
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
c1, c2, c3, c4 = st.columns(4)
c1.metric("Scanned", len(tickers))
c2.metric("Usable results", len(df_sorted))
c3.metric("RSI < 40 now", int((pd.to_numeric(df_sorted["RSI"], errors="coerce") < 40).sum()))
c4.metric("Score 80+", int((pd.to_numeric(df_sorted["Swing Score"], errors="coerce") >= 80).sum()))

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
    sort_by = st.selectbox("Sort by", df_sorted.columns.tolist(), index=df_sorted.columns.tolist().index("Swing Score"))
with sort_b:
    sort_direction = st.selectbox("Direction", ["Descending", "Ascending"], index=0)
with sort_c:
    view_mode = st.selectbox("View", ["Compact", "Research"], index=0)

ascending = sort_direction == "Ascending"
display = df_sorted.sort_values(sort_by, ascending=ascending, na_position="last").reset_index(drop=True)

compact_cols = [
    "Ticker", "Swing Score", "RSI", "Opportunity", "Price", "Potential Swing Price", "Avg Max Bounce", "Avg Days to Max", "History", "News"
]
research_cols = compact_cols + [
    "Headline", f"Avg Gain to RSI {rsi_target}", f"Avg Days to RSI {rsi_target}", "History Score", "Opportunity Score", "Days Since RSI <30", "Avg Lowest RSI", "Avg Drawdown After Low"
]
show_cols = compact_cols if view_mode == "Compact" else research_cols

st.dataframe(
    display[show_cols],
    use_container_width=True,
    hide_index=True,
    height=440,
    column_config={
        "Swing Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        "RSI": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        "Price": st.column_config.NumberColumn(format="$%.2f"),
        "Potential Swing Price": st.column_config.NumberColumn(format="$%.2f"),
        "Avg Max Bounce": st.column_config.NumberColumn(format="%.1f%%"),
        f"Avg Gain to RSI {rsi_target}": st.column_config.NumberColumn(format="%.1f%%"),
        "Avg Drawdown After Low": st.column_config.NumberColumn(format="%.1f%%"),
    },
)

with st.expander("What the Swing Score means"):
    st.markdown(f"""
    **Swing Score** combines two ideas:

    **1. Current opportunity score** — how close the stock is to an actionable RSI rebound zone right now. RSI under 30 scores highest; RSI 30–40 is still watchable; RSI above 50 scores low because it may have already recovered.

    **2. Historical rebound score** — what happened the last times this stock fell below RSI 30. It uses recovery frequency to RSI {rsi_target}, average gain to RSI {rsi_target}, average max bounce within {bounce_window} trading days, speed of recovery, days to max bounce, oversold depth, sample size, and a drawdown penalty.

    **Panic zone** means current RSI is below 25. It is the most washed-out bucket in the model. It can be powerful, but it can also still be falling, so it should be treated as “high alert,” not an automatic buy.

    **Potential Swing Price** is not a price target from an analyst. It is simply current price plus the stock’s own average max bounce after prior RSI&lt;30 events within the selected bounce window.

    **News** is a lightweight headline keyword snapshot from Yahoo Finance. It is useful context, but it is not a real sentiment model. Click into the news before trusting the label.

    This is meant to produce a **watchlist**, not a buy signal. Entries should still come from price action, VWAP, volume, support/reclaim behavior, and your 5m/15m process.
    """)

st.divider()
st.markdown("## Ticker Detail")
selected = st.selectbox("Inspect ticker", display["Ticker"].tolist())
detail = next((r for r in results if r["ticker"] == selected), None)

if detail:
    a, b, c, d, e, f = st.columns(6)
    a.metric("Swing Score", f"{detail['swing_score']}/100")
    b.metric("RSI", detail.get("current_rsi", "—"))
    c.metric("Price", f"${detail['price']}")
    f_price = detail.get("potential_sell_price")
    d.metric("Potential Swing Price", f"${f_price}" if f_price is not None else "—")
    e.metric("Avg Max Bounce", format_pct(detail.get("avg_max_bounce_pct")))
    f.metric("Avg Days to Max", detail.get("avg_days_to_max_bounce", "—"))

    tags = []
    opp = detail.get("opportunity", "")
    if "Panic" in opp or "Oversold" in opp:
        tags.append(f"<span class='tag tag-red'>{opp}</span>")
    elif "Near" in opp or "Watch" in opp:
        tags.append(f"<span class='tag tag-amber'>{opp}</span>")
    else:
        tags.append(f"<span class='tag tag-blue'>{opp}</span>")
    tags.append(f"<span class='tag tag-green'>{detail.get('event_count', 0)} historical RSI&lt;30 events</span>")
    news_label = detail.get("news_label")
    if news_label:
        tags.append(f"<span class='tag tag-blue'>{news_label}</span>")
    st.markdown("".join(tags), unsafe_allow_html=True)
    if detail.get("news_headline"):
        st.caption(f"Top headline: {detail['news_headline']}")

    st.plotly_chart(mini_chart(detail), use_container_width=True)

    st.markdown("### RSI <30 rebound history")
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
    file_name=f"swingit_v3_{datetime.date.today()}.csv",
    mime="text/csv",
)
