"""
Signal Screener — US Equities
Pulls S&P 500 tickers from Wikipedia, computes technicals with yfinance + ta.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime
from io import StringIO

st.set_page_config(page_title="Signal Screener", page_icon="📡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    :root { --bg:#0d1117; --surface:#161b22; --border:#21262d; --accent:#58a6ff; --green:#3fb950; --red:#f85149; --muted:#8b949e; --text:#e6edf3; }
    html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"] { background:var(--bg)!important; color:var(--text)!important; }
    [data-testid="stSidebar"] { background:var(--surface)!important; border-right:1px solid var(--border); }
    h1,h2,h3 { color:var(--text)!important; }
    [data-testid="stMetric"] { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:14px 18px; }
    [data-testid="stMetricLabel"] { color:var(--muted)!important; font-size:0.75rem; text-transform:uppercase; }
    [data-testid="stMetricValue"] { color:var(--text)!important; font-size:1.4rem; font-weight:700; }
    [data-testid="stDataFrame"] { border:1px solid var(--border)!important; border-radius:8px; overflow:hidden; }
    .stButton>button { background:var(--accent)!important; color:#000!important; border:none!important; border-radius:6px!important; font-weight:600!important; }
    hr { border-color:var(--border)!important; }
    .pill { display:inline-block; background:#1f3a5a; color:var(--accent); border-radius:20px; padding:2px 10px; font-size:0.72rem; font-weight:600; margin-right:4px; }
    .pill-green { background:#1a3a2a; color:var(--green); }
    .pill-red { background:#3a1a1a; color:var(--red); }
</style>
""", unsafe_allow_html=True)

# ── Sidebar
with st.sidebar:
    st.markdown("## 📡 Signal Screener")
    st.markdown("*US Equities — Technical*")
    st.divider()

    st.markdown("#### Universe")
    universe = st.selectbox("Stock universe", ["S&P 500", "NASDAQ 100", "Dow Jones 30", "Custom list"])
    if universe == "Custom list":
        custom_input = st.text_area("Enter tickers (comma or newline separated)", placeholder="AAPL, MSFT, TSLA")

    st.divider()
    st.markdown("#### Price & Volume")
    price_min, price_max = st.slider("Price range ($)", 1, 2000, (1, 2000))
    vol_min = st.select_slider("Min avg volume", options=[0, 100_000, 500_000, 1_000_000, 5_000_000], value=0, format_func=lambda x: "Any" if x == 0 else f"{x:,.0f}")

    st.divider()
    st.markdown("#### RSI (14-day)")
    rsi_min, rsi_max = st.slider("RSI range", 0, 100, (0, 100))

    st.divider()
    st.markdown("#### Moving Averages")
    ma_signal = st.selectbox("MA signal", ["Any", "Bullish (50 > 200)", "Bearish (50 < 200)", "Price above 50-day", "Price above 200-day"])

    st.divider()
    st.markdown("#### MACD")
    macd_signal = st.selectbox("MACD signal", ["Any", "Bullish cross", "Bearish cross"])

    st.divider()
    max_results = st.slider("Max tickers to scan", 10, 500, 100, step=10)

# ── Ticker lists
@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    df = tables[0]

    return df["Symbol"].str.replace(".", "-", regex=False).tolist()

@st.cache_data(ttl=86400, show_spinner=False)
def get_nasdaq100():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(url)
    for t in tables:
        if "Ticker" in t.columns:
            return t["Ticker"].tolist()
        if "Symbol" in t.columns:
            return t["Symbol"].tolist()
    return []

DOW30 = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT"
]

def get_universe_tickers(universe, custom_input=""):
    if universe == "S&P 500":
        return get_sp500()
    elif universe == "NASDAQ 100":
        return get_nasdaq100()
    elif universe == "Dow Jones 30":
        return DOW30
    elif universe == "Custom list":
        raw = custom_input.replace("\n", ",").replace(";", ",")
        return [t.strip().upper() for t in raw.split(",") if t.strip()]
    return []

# ── Technicals
@st.cache_data(ttl=300, show_spinner=False)
def compute_technicals(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df is None or len(df) < 60:
            return None
        df = df.copy()
        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()

        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        rsi = float(rsi_series.iloc[-1]) if rsi_series is not None else None

        sma50_series = ta.trend.SMAIndicator(close, window=50).sma_indicator()
        sma200_series = ta.trend.SMAIndicator(close, window=200).sma_indicator()
        sma50 = float(sma50_series.iloc[-1]) if sma50_series is not None else None
        sma200 = float(sma200_series.iloc[-1]) if sma200_series is not None else None

        macd_obj = ta.trend.MACD(close)
        macd_line = macd_obj.macd()
        signal_line = macd_obj.macd_signal()
        macd_hist = macd_obj.macd_diff()

        macd_val = float(macd_line.iloc[-1])
        sig_val = float(signal_line.iloc[-1])
        macd_cross = (
            "bullish" if float(macd_line.iloc[-2]) < float(signal_line.iloc[-2]) and macd_val > sig_val else
            "bearish" if float(macd_line.iloc[-2]) > float(signal_line.iloc[-2]) and macd_val < sig_val else
            "none"
        )

        avg_vol = float(volume.tail(20).mean())
        price = float(close.iloc[-1])

        return {
            "ticker": ticker, "price": round(price, 2),
            "avg_vol": int(avg_vol),
            "rsi": round(rsi, 1) if rsi else None,
            "sma50": round(sma50, 2) if sma50 else None,
            "sma200": round(sma200, 2) if sma200 else None,
            "macd_cross": macd_cross,
            "rsi_series": rsi_series, "sma50_series": sma50_series,
            "sma200_series": sma200_series, "macd_line_series": macd_line,
            "macd_signal_series": signal_line, "macd_hist": macd_hist, "df": df,
        }
    except Exception:
        return None

def passes_filters(row):
    price = row.get("price", 0)
    avg_vol = row.get("avg_vol", 0)
    rsi = row.get("rsi")

    if not (price_min <= price <= price_max): return False
    if vol_min > 0 and avg_vol < vol_min: return False
    if rsi is not None and not (rsi_min <= rsi <= rsi_max): return False

    sma50, sma200 = row.get("sma50"), row.get("sma200")
    if ma_signal == "Bullish (50 > 200)" and not (sma50 and sma200 and sma50 > sma200): return False
    if ma_signal == "Bearish (50 < 200)" and not (sma50 and sma200 and sma50 < sma200): return False
    if ma_signal == "Price above 50-day" and not (sma50 and price > sma50): return False
    if ma_signal == "Price above 200-day" and not (sma200 and price > sma200): return False

    cross = row.get("macd_cross", "none")
    if macd_signal == "Bullish cross" and cross != "bullish": return False
    if macd_signal == "Bearish cross" and cross != "bearish": return False
    return True

def signal_pills(row):
    pills = []
    rsi = row.get("rsi")
    if rsi:
        if rsi < 30: pills.append("<span class='pill pill-green'>Oversold RSI</span>")
        elif rsi > 70: pills.append("<span class='pill pill-red'>Overbought RSI</span>")
    sma50, sma200 = row.get("sma50"), row.get("sma200")
    if sma50 and sma200:
        pills.append("<span class='pill pill-green'>Golden Cross</span>" if sma50 > sma200 else "<span class='pill pill-red'>Death Cross</span>")
    cross = row.get("macd_cross", "none")
    if cross == "bullish": pills.append("<span class='pill pill-green'>MACD ↑</span>")
    elif cross == "bearish": pills.append("<span class='pill pill-red'>MACD ↓</span>")
    return "".join(pills) if pills else "<span class='pill'>—</span>"

def mini_chart(data):
    df = data["df"].copy()
    close = df["Close"].squeeze()
    dates = df.index
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.55, 0.22, 0.23],
                        vertical_spacing=0.04, subplot_titles=("Price + MAs", "RSI (14)", "MACD"))
    fig.add_trace(go.Candlestick(x=dates, open=df["Open"].squeeze(), high=df["High"].squeeze(),
        low=df["Low"].squeeze(), close=close, name="Price",
        increasing_fillcolor="#3fb950", decreasing_fillcolor="#f85149",
        increasing_line_color="#3fb950", decreasing_line_color="#f85149"), row=1, col=1)
    if data.get("sma50_series") is not None:
        fig.add_trace(go.Scatter(x=dates, y=data["sma50_series"], line=dict(color="#58a6ff", width=1.5), name="SMA 50"), row=1, col=1)
    if data.get("sma200_series") is not None:
        fig.add_trace(go.Scatter(x=dates, y=data["sma200_series"], line=dict(color="#e3b341", width=1.5), name="SMA 200"), row=1, col=1)
    if data.get("rsi_series") is not None:
        fig.add_trace(go.Scatter(x=dates, y=data["rsi_series"], line=dict(color="#a371f7", width=1.5), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line=dict(color="#f85149", dash="dot", width=1), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="#3fb950", dash="dot", width=1), row=2, col=1)
    hist = data.get("macd_hist")
    if hist is not None:
        fig.add_trace(go.Bar(x=dates, y=hist, marker_color=["#3fb950" if v >= 0 else "#f85149" for v in hist], name="Histogram", opacity=0.7), row=3, col=1)
    if data.get("macd_line_series") is not None:
        fig.add_trace(go.Scatter(x=dates, y=data["macd_line_series"], line=dict(color="#58a6ff", width=1.5), name="MACD"), row=3, col=1)
    if data.get("macd_signal_series") is not None:
        fig.add_trace(go.Scatter(x=dates, y=data["macd_signal_series"], line=dict(color="#e3b341", width=1.5), name="Signal"), row=3, col=1)
    fig.update_layout(height=520, paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#8b949e", size=11), xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=8, r=8, t=32, b=8))
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#21262d", row=i, col=1)
        fig.update_yaxes(gridcolor="#21262d", row=i, col=1)
    return fig

# ── Main
st.markdown("## 📡 Signal Screener")
st.markdown(f"Universe: **{universe}** · Price **${price_min}–${price_max}** · RSI **{rsi_min}–{rsi_max}** · MA **{ma_signal}** · MACD **{macd_signal}**")
st.divider()

run_col, _ = st.columns([1, 5])
with run_col:
    run = st.button("▶ Run Screen")

if run:
    custom_input = custom_input if universe == "Custom list" else ""
    all_tickers = get_universe_tickers(universe, custom_input)

    if not all_tickers:
        st.warning("No tickers found. Check your custom list or try a different universe.")
        st.stop()

    tickers = all_tickers[:max_results]
    st.info(f"Scanning **{len(tickers)}** tickers from {universe}…")

    progress = st.progress(0)
    status = st.empty()
    results = []
    for i, t in enumerate(tickers):
        status.caption(f"Checking {t}…")
        data = compute_technicals(t)
        if data and passes_filters(data):
            results.append(data)
        progress.progress((i + 1) / len(tickers))

    progress.empty()
    status.empty()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tickers Scanned", len(tickers))
    m2.metric("Passed Filters", len(results))
    m3.metric("Bullish MACD Cross", sum(1 for r in results if r.get("macd_cross") == "bullish"))
    m4.metric("Oversold RSI (<30)", sum(1 for r in results if r.get("rsi") and r["rsi"] < 30))
    st.divider()

    if not results:
        st.warning("No stocks matched your filters. Try widening the RSI range or MA signal.")
        st.stop()

    st.markdown("### Results")
    table_rows = []
    for r in results:
        sma50, sma200 = r.get("sma50"), r.get("sma200")
        ma_trend = "🟢 50 > 200" if sma50 and sma200 and sma50 > sma200 else "🔴 50 < 200" if sma50 and sma200 else "—"
        cross = r.get("macd_cross", "none")
        macd_label = "🟢 Bullish" if cross == "bullish" else ("🔴 Bearish" if cross == "bearish" else "—")
        table_rows.append({
            "Ticker": r["ticker"], "Price ($)": r["price"],
            "Avg Vol": f"{r.get('avg_vol', 0):,}",
            "RSI (14)": r.get("rsi"), "SMA 50": r.get("sma50"),
            "SMA 200": r.get("sma200"), "MA Trend": ma_trend, "MACD Cross": macd_label
        })

    df_results = pd.DataFrame(table_rows)
    st.dataframe(df_results, use_container_width=True, hide_index=True,
        column_config={
            "Price ($)": st.column_config.NumberColumn(format="$%.2f"),
            "RSI (14)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        })

    st.divider()
    st.markdown("### Chart Detail")
    selected = st.selectbox("Select a ticker to inspect", [r["ticker"] for r in results])
    detail = next((r for r in results if r["ticker"] == selected), None)
    if detail:
        ca, cb, cc, cd = st.columns(4)
        ca.metric("Price", f"${detail['price']}")
        cb.metric("RSI (14)", f"{detail.get('rsi', '—')}")
        cc.metric("SMA 50", f"${detail.get('sma50', '—')}")
        cd.metric("SMA 200", f"${detail.get('sma200', '—')}")
        st.markdown(signal_pills(detail), unsafe_allow_html=True)
        st.plotly_chart(mini_chart(detail), use_container_width=True)

    st.divider()
    csv = df_results.drop(columns=["MA Trend", "MACD Cross"]).to_csv(index=False)
    st.download_button("⬇ Export Results CSV", data=csv, file_name=f"screener_{datetime.date.today()}.csv", mime="text/csv")

else:
    st.markdown("""
    <div style="text-align:center; padding:80px 0; color:#8b949e;">
        <div style="font-size:3rem; margin-bottom:12px;">📡</div>
        <div style="font-size:1.1rem; font-weight:600; color:#e6edf3;">Configure your filters in the sidebar</div>
        <div style="margin-top:6px;">Then click <strong>▶ Run Screen</strong> to find your setups.</div>
    </div>
    """, unsafe_allow_html=True)
