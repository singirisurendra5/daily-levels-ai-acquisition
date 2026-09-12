import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Daily Levels — AI Customer Acquisition", page_icon="📈", layout="wide")

st.title("Daily Levels — AI Customer Acquisition")
st.caption("MVP v2 • Public-signal analysis • Transparent scoring • No automated outreach")

# ---------- Dictionaries ----------
MARKETS = {
    "India (NIFTY)": [r"\bnifty\b", r"\bnifty\s*50\b"],
    "India (Bank Nifty)": [r"\bbank\s*nifty\b", r"\bbanknifty\b"],
    "India (Sensex)": [r"\bsensex\b"],
    "India (Options)": [r"\bindian\s+options?\b"],
    "Crypto (BTC)": [r"\bbtc\b", r"\bbitcoin\b"],
    "Crypto (ETH)": [r"\beth\b", r"\bethereum\b"],
    "Crypto": [r"\bcrypto\b", r"\bcryptocurrency\b"],
    "US (S&P 500)": [r"\bs&p\b", r"\bspx\b", r"\bs&p\s*500\b"],
    "US (Nasdaq)": [r"\bnasdaq\b", r"\bqqq\b"],
    "US (Dow)": [r"\bdow\b"],
    "US Stocks": [r"\bus\s+stocks?\b", r"\bnyse\b"],
    "Forex (EUR/USD)": [r"\beur\s*/?\s*usd\b", r"\beurusd\b"],
    "Forex (GBP/USD)": [r"\bgbp\s*/?\s*usd\b", r"\bgbpusd\b"],
    "Gold / XAUUSD": [r"\bxau\s*/?\s*usd\b", r"\bxauusd\b", r"\bgold\b"],
    "Forex": [r"\bforex\b"],
}

# Transparent point system. Max = 100.
RULES = [
    ("Explicit support/resistance or levels request", 45, [
        r"\bsupport\s*(?:and|&|/)\s*resistance\b",
        r"\bsupport\b", r"\bresistance\b", r"\blevels?\b",
        r"\bkey level\b", r"\bnext level\b",
    ]),
    ("Active trading language", 25, [
        r"\btrade\b", r"\btrading\b", r"\btrader\b", r"\bentry\b",
        r"\bposition\b", r"\blong\b", r"\bshort\b", r"\btarget\b",
        r"\bcall\b", r"\bput\b",
    ]),
    ("Short-term/session context", 15, [
        r"\btoday\b", r"\btomorrow\b", r"\bnext\b",
        r"\bthis session\b", r"\bfor tomorrow\b", r"\bfor today\b",
    ]),
    ("Direct question/request", 5, [
        r"\?", r"\bwhere\b", r"\bwhat\b", r"\bhow\b", r"\bcan someone\b",
        r"\banyone\b",
    ]),
    ("Market detected", 10, []),
]

SPAM_RULES = [
    ("Possible promotional/spam language", -25, [
        r"\bgiveaway\b", r"\bpromo code\b", r"\bairdrop\b",
        r"\bfree money\b", r"\bcasino\b", r"\bbetting\b",
        r"\bsubscribe\s+to\s+my\s+channel\b",
    ])
]

def clean(x):
    return "" if pd.isna(x) else str(x).strip()

def found_any(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)

def analyze(text):
    text = clean(text)
    points = 0
    reasons = []
    matched_terms = []

    for label, weight, patterns in RULES:
        if label == "Market detected":
            continue
        hits = [p for p in patterns if re.search(p, text, re.I)]
        if hits:
            points += weight
            reasons.append(f"+{weight} {label}")
            matched_terms.extend([p.strip(r"\b").replace(r"\s*", " ") for p in hits])

    market_hits = []
    for market, patterns in MARKETS.items():
        if found_any(text, patterns):
            market_hits.append(market)

    if market_hits:
        points += 10
        reasons.append("+10 Market detected")

    spam_hits = []
    for label, weight, patterns in SPAM_RULES:
        hits = [p for p in patterns if re.search(p, text, re.I)]
        if hits:
            points += weight
            reasons.append(f"{weight} {label}")
            spam_hits.extend(hits)

    score = max(0, min(100, points))
    if score >= 90:
        category = "HOT"
    elif score >= 75:
        category = "WARM"
    elif score >= 60:
        category = "POSSIBLE"
    else:
        category = "LOW"

    explanation = " | ".join(reasons) if reasons else "No strong trading-intent signals detected"
    if matched_terms:
        term_text = ", ".join(dict.fromkeys(matched_terms))
        explanation = f"Intent terms: {term_text} | {explanation}"

    return pd.Series({
        "intent_score": score,
        "category": category,
        "market": ", ".join(market_hits) if market_hits else "Unknown",
        "matched_terms": ", ".join(dict.fromkeys(matched_terms)),
        "signal_explanation": explanation,
    })

def validate(df):
    required = {"platform", "url", "text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))

# ---------- Input ----------
st.subheader("1. Load public signals")
uploaded = st.file_uploader("Upload CSV", type=["csv"])

if uploaded:
    try:
        raw = pd.read_csv(uploaded)
        validate(raw)
    except Exception as e:
        st.error(str(e))
        st.stop()
else:
    raw = pd.read_csv(Path(__file__).parent / "data" / "sample_signals.csv")
    st.info("Using the included 30-signal sample dataset. Upload your own CSV to test real public signals.")

for c in ["platform", "url", "text"]:
    raw[c] = raw[c].map(clean)

analysis = raw["text"].apply(analyze)
results = pd.concat([raw.reset_index(drop=True), analysis.reset_index(drop=True)], axis=1)

if "date" not in results:
    results["date"] = ""

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")
platform_options = ["All"] + sorted(results["platform"].dropna().unique().tolist())
market_options = ["All"] + sorted(results["market"].dropna().unique().tolist())
category_options = ["All", "HOT", "WARM", "POSSIBLE", "LOW"]

platform = st.sidebar.selectbox("Platform", platform_options)
market = st.sidebar.selectbox("Market", market_options)
category = st.sidebar.selectbox("Category", category_options)
min_score = st.sidebar.slider("Minimum score", 0, 100, 0)
keyword = st.sidebar.text_input("Keyword contains", "")

filtered = results.copy()
if platform != "All":
    filtered = filtered[filtered["platform"] == platform]
if market != "All":
    filtered = filtered[filtered["market"].str.contains(re.escape(market), case=False, na=False)]
if category != "All":
    filtered = filtered[filtered["category"] == category]
filtered = filtered[filtered["intent_score"] >= min_score]
if keyword.strip():
    filtered = filtered[filtered["text"].str.contains(re.escape(keyword.strip()), case=False, na=False)]

# ---------- Overview ----------
st.subheader("2. Overview")
total = len(results)
hot = int((results["category"] == "HOT").sum())
warm = int((results["category"] == "WARM").sum())
possible = int((results["category"] == "POSSIBLE").sum())
low = int((results["category"] == "LOW").sum())
detected = int((results["market"] != "Unknown").sum())
potential = hot + warm

cols = st.columns(6)
for col, label, value in zip(
    cols,
    ["Total Signals", "HOT", "WARM", "POSSIBLE", "LOW", "Potential Leads"],
    [total, hot, warm, possible, low, potential],
):
    col.metric(label, value)

st.caption(f"Market detected in {detected} of {total} signals.")

# ---------- Score legend ----------
st.subheader("3. Score model")
st.markdown(
    """
**Maximum score = 100**

- **+45** Explicit support/resistance or levels request
- **+25** Active trading language
- **+15** Short-term/session context
- **+5** Direct question/request
- **+10** Market detected
- **−25** Possible promotional/spam language

**Classification:** 🔥 HOT 90–100 · 🟠 WARM 75–89 · 🟡 POSSIBLE 60–74 · ⚪ LOW <60

The score measures **public trading-intent/fit**, not probability of purchase.
"""
)

# ---------- Results ----------
st.subheader("4. Scored public signals")
st.caption(f"Showing {len(filtered)} of {total} signals")

display = filtered[
    ["platform", "date", "text", "market", "intent_score", "category",
     "matched_terms", "signal_explanation", "url"]
].copy()

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "url": st.column_config.LinkColumn("Source URL", display_text="Open"),
        "intent_score": st.column_config.NumberColumn("Intent Score", min_value=0, max_value=100),
    },
)

# ---------- Download ----------
csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download scored CSV",
    data=csv_bytes,
    file_name="daily_levels_scored_signals.csv",
    mime="text/csv",
)

# ---------- Architecture ----------
st.subheader("5. Next architecture")
st.markdown(
    """
**Current:** CSV → rule-based scoring → dashboard

**Next:** approved YouTube/Reddit public ingestion → normalized signal records → AI classifier → fit/intent scoring → dashboard → compliant content/outreach suggestions → UTM conversion tracking.

No private watch history, private WhatsApp/Telegram access, prohibited scraping, or mass unsolicited messaging.
"""
)
