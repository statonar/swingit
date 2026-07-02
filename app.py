import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="SwingIT 1.0",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def load_css():
    css_path = Path("styles.css")
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_css()

opportunities = [
    {
        "rank": "🥇",
        "ticker": "ADSK",
        "company": "Autodesk",
        "thesis_type": "Premium Opportunity",
        "conviction": "91%",
        "action": "Sell Cash Secured Put",
        "why_today": "Selling pressure appears exhausted while option premium remains elevated.",
        "expected_hold": "5–10 days",
        "assessment": "Recovery is beginning while volatility remains attractive for premium sellers.",
        "evidence": ["Momentum improving", "Selling pressure fading", "Excellent business quality", "Historical recoveries above average", "Attractive option premium"],
        "risks": ["Still below the 50 EMA", "Needs confirmation above resistance"],
        "trade_plan": ["Strategy: Sell CSP", "Target DTE: 14–21 days", "Exit: Buy back around 60–70% premium captured"],
        "money_take": "I’d sell the put rather than buy shares today. The premium compensates me while I wait.",
    },
    {
        "rank": "🥈",
        "ticker": "META",
        "company": "Meta Platforms",
        "thesis_type": "Recovery Swing",
        "conviction": "88%",
        "action": "Sell Cash Secured Put",
        "why_today": "High-quality company pulling back into an area where premium selling may be more attractive than chasing shares.",
        "expected_hold": "7–14 days",
        "assessment": "The pullback looks orderly rather than broken, making it a strong candidate for patient entry.",
        "evidence": ["Large-cap quality", "Healthy options liquidity", "Pullback near support", "Recovery history strong"],
        "risks": ["Could need more time to base", "Premium must justify capital commitment"],
        "trade_plan": ["Strategy: Sell CSP if strike aligns with buy zone", "Exit: Close at 50–70% premium captured"],
        "money_take": "I’d only sell the put at a price where I’d be happy owning 100 shares.",
    },
    {
        "rank": "🥉",
        "ticker": "MU",
        "company": "Micron",
        "thesis_type": "Watch / Event Risk",
        "conviction": "78%",
        "action": "Wait",
        "why_today": "Momentum is interesting, but earnings or event risk may make patience the better capital decision.",
        "expected_hold": "Watchlist",
        "assessment": "The setup has potential, but the cleanest trade may come after the event risk clears.",
        "evidence": ["Semiconductor strength", "Potential post-event recovery candidate", "Options premium may be elevated"],
        "risks": ["Earnings can override technicals", "Gap risk is elevated"],
        "trade_plan": ["Strategy: Wait", "Reassess after event risk clears"],
        "money_take": "I’d protect capital and wait for a cleaner pitch.",
    },
]

st.markdown("""
<div class="hero">
    <div>
        <div class="eyebrow">SwingIT 1.0</div>
        <h1>Good Morning, Amber ☀️</h1>
        <p class="subtitle">Today's Playbook is focused on fewer, higher-conviction capital decisions.</p>
    </div>
    <div class="market-box">
        <div class="mini-label">Market Pulse</div>
        <div class="market-status">🟡 Neutral</div>
        <div class="mini-label">Theme of the Day</div>
        <div class="theme">Quality pullbacks with attractive premium</div>
    </div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
metrics = [("Opportunities", "3"), ("Primary Objective", "Preserve Capital"), ("Best Use", "Sell Premium"), ("Mode", "Calm & Selective")]
for col, (label, value) in zip((c1, c2, c3, c4), metrics):
    with col:
        st.markdown(f'<div class="metric-card"><span>{label}</span><strong>{value}</strong></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Today’s Best Opportunities</div>', unsafe_allow_html=True)

for opp in opportunities:
    st.markdown(f"""
    <div class="briefing-card">
        <div class="briefing-top">
            <div>
                <div class="rank">{opp['rank']} {opp['ticker']}</div>
                <div class="company">{opp['company']}</div>
            </div>
            <div class="pill">{opp['thesis_type']}</div>
        </div>
        <div class="briefing-grid">
            <div>
                <div class="label">Recommended Action</div>
                <div class="action">{opp['action']}</div>
            </div>
            <div>
                <div class="label">Conviction</div>
                <div class="value">{opp['conviction']}</div>
            </div>
            <div>
                <div class="label">Expected Hold</div>
                <div class="value">{opp['expected_hold']}</div>
            </div>
        </div>
        <div class="why"><strong>Why today:</strong> {opp['why_today']}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"Expand thesis for {opp['ticker']}"):
        st.markdown(f"### Investment Thesis — {opp['ticker']}")
        st.markdown(f"**Assessment:** {opp['assessment']}")
        left, mid, right = st.columns(3)
        with left:
            st.markdown("#### Supporting Evidence")
            for item in opp["evidence"]:
                st.markdown(f"- ✅ {item}")
        with mid:
            st.markdown("#### Risks")
            for item in opp["risks"]:
                st.markdown(f"- ⚠️ {item}")
        with right:
            st.markdown("#### Trade Plan")
            for item in opp["trade_plan"]:
                st.markdown(f"- {item}")
        st.markdown(f'<div class="money-box"><strong>If this were my money:</strong><br>{opp["money_take"]}</div>', unsafe_allow_html=True)
        with st.expander("Evidence details"):
            st.info("Charts, news, options, financials, and historical recovery details plug in here next.")

st.markdown("""
<div class="footer-box">
    <strong>Not worth your time today:</strong> Most tickers were filtered out because they did not present a clean thesis, strong enough risk/reward, or a capital-efficient implementation.
</div>
""", unsafe_allow_html=True)
