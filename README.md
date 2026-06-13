# 📡 Signal Screener

A personal stock screener for US equities (NYSE/NASDAQ) built with Streamlit.
Uses **Finviz** for the initial ticker universe and **yfinance + pandas-ta**
for precise technical indicator calculation.

## Features
- **RSI (14-day)** — filter by overbought/oversold range
- **Moving Averages** — SMA 50 & 200, golden/death cross detection
- **MACD** — bullish or bearish signal-line crossover detection
- **Candlestick chart** with overlaid MAs, RSI panel, and MACD histogram
- **CSV export** of screener results

## Setup

```bash
# 1. Clone or copy files into a folder
# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run stock_screener.py
```

The app opens automatically at http://localhost:8501

## Usage
1. Set your filters in the left sidebar (exchange, price, volume, RSI range, MA signal, MACD signal)
2. Click **▶ Run Screen**
3. Browse the results table, click any ticker to see its full chart
4. Export to CSV with the download button

## Notes
- Finviz scraping is free but rate-limited — keep `Max tickers to screen` ≤ 100 for reliability
- Technical indicators are computed on 1 year of daily data pulled from Yahoo Finance
- Results are cached for 5 minutes to avoid redundant API calls
- No API keys required
