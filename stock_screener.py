"""
SwingIt V6.5 — Compact Sidebar + Full Universe Scan
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
    page_title="SwingIt V6.5",
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

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar — intentionally pared back
# ──────────────────────────────────────────────────────────────────────────────
custom_input = ""
with st.sidebar:
    st.markdown("### 🔥 SwingIt")

    universe = st.selectbox(
        "Universe",
        [
            "⭐ SwingIt Elite (Recommended)",
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
        ],
        help="Choose the group to scan. The app now scans the full selected universe by default."
    )
    if universe == "Custom list":
        custom_input = st.text_area(
            "Custom tickers",
            placeholder="ORCL, ADBE, AMZN, MSFT",
            height=80,
            help="Comma, semicolon, or newline separated."
        )

    st.caption("Scans the full selected universe. Larger universes may take longer.")

    with st.expander("Model settings", expanded=True):
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

    run = st.button("Run Swing Scan", use_container_width=True)
    st.caption("Watchlist engine only — use ToS for entry/exit decisions.")


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
    "FXAIX": lambda: get_sp500(),
    "VOO": lambda: get_sp500(),
    "VTI": lambda: dedupe(get_sp500() + get_nasdaq100() + GROWTH_CORE + HIGH_OPPORTUNITY),
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

    if selected_universe == "S&P 500":
        tickers = get_sp500(); add_sources(source_map, tickers, "S&P 500")
    elif selected_universe == "NASDAQ 100":
        tickers = get_nasdaq100(); add_sources(source_map, tickers, "NASDAQ 100")
    elif selected_universe == "Dow Jones 30":
        tickers = DOW30; add_sources(source_map, tickers, "Dow 30")
    elif selected_universe == "Russell 1000":
        tickers = dedupe(get_sp500() + get_nasdaq100() + GROWTH_CORE + HIGH_OPPORTUNITY)
        add_sources(source_map, tickers, "Russell 1000-style")
    elif selected_universe == "Russell 3000":
        tickers = dedupe(get_sp500() + get_nasdaq100() + GROWTH_CORE + HIGH_OPPORTUNITY + SCHG_NAMES + VGT_NAMES + SMH_NAMES + SOXX_NAMES)
        add_sources(source_map, tickers, "Russell 3000-style")
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
    """Adds four ranking lenses without changing the underlying scan data."""
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
        scores.append((target_hunter, ready_now, highest_confidence, maximum_upside, bounce, speed))

    out["🎯 Target Hunter Score"] = [int(round(x[0])) for x in scores]
    out["⚡ Ready Now Score"] = [int(round(x[1])) for x in scores]
    out["🧠 Confidence Rank Score"] = [int(round(x[2])) for x in scores]
    out["🚀 Upside Rank Score"] = [int(round(x[3])) for x in scores]
    out["Target Bounce Score"] = [int(round(x[4])) for x in scores]
    out["Speed Score"] = [int(round(x[5])) for x in scores]
    return out


def ranking_column_for(mode: str) -> str:
    return {
        "🎯 8% Target Hunter": "🎯 Target Hunter Score",
        "⚡ Ready Now": "⚡ Ready Now Score",
        "🧠 Highest Confidence": "🧠 Confidence Rank Score",
        "🚀 Maximum Upside": "🚀 Upside Rank Score",
    }.get(mode, "🎯 Target Hunter Score")


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
st.markdown("# 🔥 SwingIt V6.5")

# When the button is clicked, run the scan once and store the result.
if run:
    all_tickers, source_map = get_universe_payload(universe, custom_input)
    if not all_tickers:
        st.warning("No tickers found. Check your custom list or choose another universe.")
        st.stop()

    tickers = all_tickers
    st.session_state.scan_meta = {
        "universe": universe,
        "profit_target": profit_target,
        "bounce_window": bounce_window,
        "include_news": include_news,
        "spring_timeframe": spring_timeframe,
        "tickers_scanned": len(tickers),
        "source_map": {t: source_map.get(t, []) for t in tickers},
        "run_date": datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    }

    st.info(f"Scanning full universe: {len(tickers)} tickers from {universe}…")
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
    st.session_state.leaderboard_filter = "All"

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
company_lookup = get_company_lookup(active_universe)
active_source_map = meta.get("source_map", {}) or {}
rows = []
for r in results:
    ticker_sources = active_source_map.get(r["ticker"], [])
    rows.append({
        "Ticker": r["ticker"],
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

st.markdown("### Ranking mode")
rank_col_ui, rank_help_col = st.columns([1.4, 2.6])
with rank_col_ui:
    ranking_mode = st.selectbox(
        "What should #1 mean?",
        RANKING_MODES,
        index=0,
        key="ranking_mode_selector",
        help="Change the lens without rerunning the scan.",
    )
with rank_help_col:
    st.markdown(
        f"<div class='small-muted' style='padding-top:1.9rem;'>{_safe_html(RANKING_HELP.get(ranking_mode, ''))}</div>",
        unsafe_allow_html=True,
    )

rank_col = ranking_column_for(ranking_mode)
df_sorted = df.sort_values([rank_col, "Setup Quality", "Swing Score", "RSI"], ascending=[False, False, False, True], na_position="last").reset_index(drop=True)
df_sorted["Active Rank Score"] = pd.to_numeric(df_sorted[rank_col], errors="coerce").fillna(0).round(0).astype(int)

# Top summary metrics — clickable filter cards
rsi_under_40_count = int((pd.to_numeric(df["RSI"], errors="coerce") < 40).sum())
high_conf_count = int(df["Confidence"].astype(str).str.contains("High", na=False).sum())
setup_75_count = int((pd.to_numeric(df["Setup Quality"], errors="coerce") >= 75).sum())

st.markdown("### Quick filters")
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
with fc1:
    st.metric("Scanned", active_tickers_scanned or len(results))
    if st.button("Show scanned", use_container_width=True, key="filter_scanned"):
        st.session_state.leaderboard_filter = "All"
with fc2:
    st.metric("Usable results", len(df_sorted))
    if st.button("Show usable", use_container_width=True, key="filter_usable"):
        st.session_state.leaderboard_filter = "All"
with fc3:
    st.metric("RSI < 40 now", rsi_under_40_count)
    if st.button("Show RSI < 40", use_container_width=True, key="filter_rsi40"):
        st.session_state.leaderboard_filter = "RSI < 40"
with fc4:
    st.metric("High-confidence patterns", high_conf_count)
    if st.button("Show high confidence", use_container_width=True, key="filter_highconf"):
        st.session_state.leaderboard_filter = "High confidence"
with fc5:
    st.metric("Setup ≥75", setup_75_count)
    if st.button("Show setup ≥75", use_container_width=True, key="filter_setup75"):
        st.session_state.leaderboard_filter = "Setup ≥75"

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
st.caption(f"Top 10 ranked by **{ranking_mode}**. Change the ranking mode above to ask a different question.")
top = filtered_df.head(10)
if not top.empty:
    for start in range(0, len(top), 5):
        row_slice = top.iloc[start:start + 5]
        card_cols = st.columns(5)
        for offset, (_, row) in enumerate(row_slice.iterrows()):
            with card_cols[offset]:
                st.markdown(hot_card(start + offset, row), unsafe_allow_html=True)

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
    "Ticker", "Active Rank Score", "Setup Quality", "Swing Score", "Rebound Stage", "Spring TF", "Spring", "Spring Score", "Attention", "Volume Trend", "RSI", "Opportunity", "Price", "Potential Swing Price", "Avg Max Bounce", "Avg Days to Max", "History", "Confidence", "Catalyst"
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

with st.expander("What the Swing Score means"):
    st.markdown(f"""
    **Swing Score V6.2** is a historical rebound score: *is this stock washed out, historically bouncy, and does it have a reason to move?*

    **Spring Score** is separate. It uses the selected TTM timeframe from the sidebar (1D or 1H) and a TTM Squeeze-style calculation to ask: *is volatility compressed or recently released, and is momentum improving right now?* A high Spring Score is not a buy signal by itself, but it can help you prioritize which high Swing Score names are closest to becoming actionable.

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

    Current V6.4 uses multiple ranking lenses plus two core scores: **Swing Score** (46% historical swing behavior, 34% current RSI opportunity, 14% catalyst/news, 6% attention/RVOL) and **Setup Quality** (20% current RSI opportunity, 25% Rebound Stage, 20% catalyst/news, 20% TTM Spring, 10% attention/RVOL, 5% volume trend).

    **Ranking Mode** defines what #1 means. 🎯 Target Hunter is the default for your 8% swing goal; ⚡ Ready Now is for what to open in ThinkorSwim first; 🧠 Highest Confidence is the safest historical pattern; 🚀 Maximum Upside is the biggest reward lens. V6.4 also adds **Opportunity Remaining**, which estimates how much of the usual RSI-panic rebound may still be left from the most recent panic-cycle low.

**Setup ≥75** is the “open this in ThinkorSwim now” bucket. Stocks in the high 60s/low 70s are often the almost-there names — they may need one more thing, such as RSI slipping lower, a stronger spring turn, fresh news, or higher relative volume.

    This is meant to produce a **watchlist**, not a buy signal. Entries should still come from price action, VWAP, volume, support/reclaim behavior, and your 5m/15m process.
    """)
st.divider()
st.markdown("## Ticker Detail")
selected = st.selectbox("Inspect ticker", display["Ticker"].tolist(), key="ticker_detail_select")
detail = next((r for r in results if r["ticker"] == selected), None)

if detail:
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
