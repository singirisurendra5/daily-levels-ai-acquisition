import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Daily Levels — AI Customer Acquisition",
    page_icon="📊",
    layout="wide",
)

st.title("Daily Levels — AI Customer Acquisition")
st.caption("CSV-based public trading-signal analysis • Rule-based MVP • No automated outreach")

INTENT_TERMS = {
    "support": 10,
    "resistance": 10,
    "support/resistance": 12,
    "levels": 8,
    "today": 5,
    "tomorrow": 5,
    "next level": 8,
    "key level": 8,
    "entry": 5,
    "target": 5,
    "trade": 4,
    "trading": 4,
    "trader": 4,
    "position": 3,
    "long": 3,
    "short": 3,
    "calculate": 6,
    "where": 2,
}

MARKETS = {
    "India": [
        "nifty", "nifty 50", "bank nifty", "banknifty", "sensex",
        "indian options", "options"
    ],
    "Crypto": ["btc", "bitcoin", "eth", "ethereum", "crypto"],
    "US": ["s&p", "s&p 500", "spx", "nasdaq", "qqq", "dow", "nyse", "us stocks"],
    "Forex": ["forex", "eurusd", "eur/usd", "gbpusd", "gbp/usd", "xauusd", "gold"],
}

REQUEST_PATTERNS = [
    r"\bwhat(?:'s| is)\b",
    r"\bwhere\b",
    r"\bhow do\b",
    r"\bcan someone\b",
    r"\bplease\b",
    r"\bfor tomorrow\b",
    r"\bfor today\b",
    r"\bnext\b",
    r"\bkey level\b",
]

REQUIRED_COLUMNS = ["platform", "url", "text"]


def normalize(value):
    return re.sub(r"\s+", " ", str(value).strip().lower())


def contains_term(text, term):
    text = normalize(text)
    term = normalize(term)
    if "/" in term or " " in term or "&" in term:
        return term in text
    return bool(re.search(rf"\b{re.escape(term)}\b", text))


def detect_markets(text):
    found = []
    for market, terms in MARKETS.items():
        matched = [term for term in terms if contains_term(text, term)]
        if matched:
            found.append((market, matched))
    return found


def analyze_signal(text):
    raw_text = str(text)
    normalized = normalize(raw_text)
    reasons = []
    score = 0

    matched_intent = []
    for term, points in INTENT_TERMS.items():
        if contains_term(normalized, term):
            score += points
            matched_intent.append(term)

    # Prevent repeated synonyms from inflating the score excessively.
    if matched_intent:
        reasons.append("Intent terms: " + ", ".join(matched_intent))

    markets = detect_markets(normalized)
    if markets:
        score += min(15, 5 * len(markets))
        reasons.append(
            "Market detected: " + "; ".join(
                f"{market} ({', '.join(terms)})" for market, terms in markets
            )
        )

    request_matches = [
        pattern for pattern in REQUEST_PATTERNS
        if re.search(pattern, normalized)
    ]
    if request_matches:
        score += min(12, 3 * len(request_matches))
        reasons.append("Question/request language detected")

    if "support" in normalized and "resistance" in normalized:
        score += 8
        reasons.append("Explicit support-and-resistance combination")

    if len(normalized.split()) < 3:
        score -= 5
        reasons.append("Very short text; context may be limited")

    score = max(0, min(100, int(score)))

    if score >= 75:
        category = "HOT"
    elif score >= 60:
        category = "WARM"
    else:
        category = "LOW"

    market_names = [market for market, _ in markets]
    market = ", ".join(market_names) if market_names else "Unknown"

    if not reasons:
        reasons.append("No strong rule-based signals detected")

    return {
        "market": market,
        "intent_score": score,
        "category": category,
        "signal_explanation": " | ".join(reasons),
        "matched_keywords": ", ".join(matched_intent),
    }


def analyze_dataframe(df):
    output = df.copy()
    analysis = output["text"].apply(analyze_signal).apply(pd.Series)
    return pd.concat([output, analysis], axis=1)


def sample_dataframe():
    return pd.DataFrame([
        {
            "platform": "YouTube",
            "url": "https://example.com/video1",
            "text": "NIFTY support for tomorrow?",
        },
        {
            "platform": "Reddit",
            "url": "https://example.com/post1",
            "text": "BTC next resistance?",
        },
        {
            "platform": "YouTube",
            "url": "https://example.com/video2",
            "text": "How do you calculate Bank Nifty levels?",
        },
        {
            "platform": "Reddit",
            "url": "https://example.com/post2",
            "text": "I trade stocks and want to learn more.",
        },
        {
            "platform": "X",
            "url": "https://example.com/post3",
            "text": "What is the key level for tomorrow on gold?",
        },
    ])


if "results" not in st.session_state:
    st.session_state.results = None

with st.sidebar:
    st.header("Input")
    uploaded = st.file_uploader("Upload public signals CSV", type=["csv"])
    st.write("Required columns:")
    st.code("platform,url,text", language="text")

    if st.button("Load sample CSV", use_container_width=True):
        st.session_state.results = analyze_dataframe(sample_dataframe())
        st.success("Sample data loaded.")

    st.divider()
    st.header("Scoring bands")
    st.write("HOT: 75–100")
    st.write("WARM: 60–74")
    st.write("LOW: 0–59")
    st.caption("Scores indicate rule-based intent/fit signals, not buying probability.")

if uploaded is not None:
    try:
        incoming = pd.read_csv(uploaded)
        missing = [column for column in REQUIRED_COLUMNS if column not in incoming.columns]
        if missing:
            st.error("Missing required column(s): " + ", ".join(missing))
        elif st.button("Analyze uploaded CSV", type="primary"):
            clean = incoming[REQUIRED_COLUMNS].fillna("")
            st.session_state.results = analyze_dataframe(clean)
            st.success(f"Analyzed {len(clean):,} public signals.")
    except Exception as exc:
        st.error(f"Could not read the CSV: {exc}")

results = st.session_state.results

if results is None:
    st.info("Upload a CSV or load the sample CSV to begin.")
    st.subheader("Expected CSV format")
    st.dataframe(sample_dataframe(), use_container_width=True, hide_index=True)
    st.stop()

st.subheader("Overview")
metric_cols = st.columns(6)
metric_cols[0].metric("Total Signals", len(results))
metric_cols[1].metric("HOT", int((results["category"] == "HOT").sum()))
metric_cols[2].metric("WARM", int((results["category"] == "WARM").sum()))
metric_cols[3].metric("LOW", int((results["category"] == "LOW").sum()))
metric_cols[4].metric("Markets Detected", int((results["market"] != "Unknown").sum()))
metric_cols[5].metric(
    "Potential Leads",
    int(results["category"].isin(["HOT", "WARM"]).sum()),
)

st.divider()
st.subheader("Filter results")

filter_cols = st.columns(5)
platform_options = ["All"] + sorted(results["platform"].astype(str).unique().tolist())
market_options = ["All"] + sorted(results["market"].astype(str).unique().tolist())
category_options = ["All", "HOT", "WARM", "LOW"]

selected_platform = filter_cols[0].selectbox("Platform", platform_options)
selected_market = filter_cols[1].selectbox("Market", market_options)
selected_category = filter_cols[2].selectbox("Category", category_options)
minimum_score = filter_cols[3].slider("Minimum score", 0, 100, 0)
keyword_filter = filter_cols[4].text_input("Keyword contains", "")

filtered = results.copy()
if selected_platform != "All":
    filtered = filtered[filtered["platform"].astype(str) == selected_platform]
if selected_market != "All":
    filtered = filtered[filtered["market"].astype(str) == selected_market]
if selected_category != "All":
    filtered = filtered[filtered["category"] == selected_category]
filtered = filtered[filtered["intent_score"] >= minimum_score]
if keyword_filter.strip():
    mask = filtered.apply(
        lambda row: keyword_filter.lower() in (
            str(row["text"]) + " " +
            str(row["matched_keywords"]) + " " +
            str(row["signal_explanation"])
        ).lower(),
        axis=1,
    )
    filtered = filtered[mask]

st.caption(f"Showing {len(filtered):,} of {len(results):,} signals")

display_columns = [
    "platform", "text", "market", "intent_score", "category",
    "signal_explanation", "url"
]
st.dataframe(
    filtered[display_columns],
    use_container_width=True,
    hide_index=True,
    column_config={
        "url": st.column_config.LinkColumn("URL"),
        "intent_score": st.column_config.NumberColumn("Intent Score", min_value=0, max_value=100),
    },
)

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download scored CSV",
    data=csv_bytes,
    file_name="daily_levels_scored_signals.csv",
    mime="text/csv",
)

with st.expander("Scoring methodology"):
    st.markdown(
        """
        This MVP uses transparent heuristics:

        - Matches trading-intent terms such as support, resistance, levels, entry, target, and trading.
        - Detects market terms across India, Crypto, US, and Forex categories.
        - Adds points for question/request language.
        - Adds a bonus for explicit support-and-resistance combinations.
        - Applies a small penalty to extremely short text.
        - Caps the final score at 100.

        The score is an **intent/fit indicator**, not a prediction of purchase,
        profitability, or personal financial behavior.
        """
    )

st.caption("MVP only: no private-data access, scraping, messaging, or automated outreach.")
