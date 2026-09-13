import json
import re
from pathlib import Path
import pandas as pd
import streamlit as st

from services.intelligence import analyze, signal_id
from services.dedupe import deduplicate_signals
from services.ingestion import fetch_rss, fetch_reddit_rss, fetch_youtube_channel, combine_frames

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "data" / "sources.json"
SAMPLE_PATH = ROOT / "data" / "sample_signals.csv"

st.set_page_config(page_title="Daily Levels — AI Customer Acquisition", page_icon="📈", layout="wide")
st.title("Daily Levels — AI Customer Acquisition")
st.caption("MVP V3.1 • Live public-signal ingestion • V2 intelligence retained • Human-in-the-loop")


def clean(x):
    return "" if pd.isna(x) else str(x).strip()


def validate(df):
    required = {"platform", "url", "text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))


def load_sources():
    try:
        return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"rss_feeds": [], "reddit": [], "youtube_channels": []}


def score_frame(raw):
    if raw.empty:
        return raw.copy()
    work = raw.copy()
    for c in ["platform", "url", "text"]:
        if c not in work:
            work[c] = ""
        work[c] = work[c].map(clean)
    if "date" not in work:
        work["date"] = ""
    analysis = work["text"].apply(lambda x: pd.Series(analyze(x)))
    result = pd.concat([work.reset_index(drop=True), analysis.reset_index(drop=True)], axis=1)
    result["signal_id"] = [signal_id(p, u, t) for p, u, t in zip(result.platform, result.url, result.text)]
    return result


def run_configured_sources():
    cfg = load_sources()
    frames = []
    errors = []
    for item in cfg.get("rss_feeds", []):
        try:
            frames.append(fetch_rss(item["url"], item.get("platform", "RSS")))
        except Exception as e:
            errors.append(f"RSS {item.get('url')}: {e}")
    for item in cfg.get("reddit", []):
        try:
            frames.append(fetch_reddit_rss(item["subreddit"], item.get("query", ""), item.get("sort", "new"), item.get("limit", 25)))
        except Exception as e:
            errors.append(f"Reddit r/{item.get('subreddit')}: {e}")
    for item in cfg.get("youtube_channels", []):
        try:
            frames.append(fetch_youtube_channel(item["channel_id"], item.get("limit", 15)))
        except Exception as e:
            errors.append(f"YouTube {item.get('channel_id')}: {e}")
    return combine_frames(frames), errors


if "live_raw" not in st.session_state:
    st.session_state.live_raw = pd.DataFrame()
if "last_errors" not in st.session_state:
    st.session_state.last_errors = []

# ---- Source control ----
st.subheader("1. Live public signal ingestion")
left, right = st.columns([2, 1])
with left:
    st.info("V3.1 uses only configured public RSS/Atom feeds plus public Reddit/YouTube feed endpoints. No private data or automated outreach.")
with right:
    if st.button("🔄 Run configured ingestion", type="primary", use_container_width=True):
        with st.spinner("Fetching configured public sources…"):
            live, errors = run_configured_sources()
        st.session_state.live_raw = live
        st.session_state.last_errors = errors
        st.rerun()

cfg = load_sources()
configured = sum(len(cfg.get(k, [])) for k in ["rss_feeds", "reddit", "youtube_channels"])
st.caption(f"Configured source definitions: {configured} • Last fetched rows: {len(st.session_state.live_raw)}")
if st.session_state.last_errors:
    with st.expander("Ingestion warnings"):
        for err in st.session_state.last_errors:
            st.warning(err)

# ---- Manual + sample input ----
uploaded = st.file_uploader("Optional: upload additional public-signal CSV", type=["csv"])
manual = pd.DataFrame()
if uploaded:
    try:
        manual = pd.read_csv(uploaded)
        validate(manual)
    except Exception as e:
        st.error(str(e))
        st.stop()

try:
    sample = pd.read_csv(SAMPLE_PATH)
except Exception:
    sample = pd.DataFrame(columns=["platform", "url", "text", "date"])

frames = [sample]
if not st.session_state.live_raw.empty:
    frames.append(st.session_state.live_raw)
if not manual.empty:
    frames.append(manual)
raw = combine_frames(frames)

# ---- Normalize + deduplicate ----
st.subheader("2. Normalize + duplicate detection")
validated = score_frame(raw)
deduped, duplicate_count = deduplicate_signals(validated)
# Keep the first occurrence for acquisition prioritization; retain duplicate metadata for audit/export.
results = deduped[~deduped["is_duplicate"]].copy()

st.caption(f"Signals loaded: {len(validated)} • near/exact duplicates detected: {duplicate_count} • unique opportunities analyzed: {len(results)}")

# ---- Filters ----
st.sidebar.header("Opportunity filters")
platform_options = ["All"] + sorted(results["platform"].dropna().unique().tolist())
market_options = ["All"] + sorted(results["market"].dropna().unique().tolist())
problem_options = ["All"] + sorted(results["problem"].dropna().unique().tolist())
category_options = ["All", "HOT", "WARM", "POSSIBLE", "LOW"]
platform = st.sidebar.selectbox("Platform", platform_options)
market = st.sidebar.selectbox("Market", market_options)
category = st.sidebar.selectbox("Priority", category_options)
problem = st.sidebar.selectbox("Problem", problem_options)
min_score = st.sidebar.slider("Minimum intent score", 0, 100, 0)
min_fit = st.sidebar.slider("Minimum Daily Levels fit", 0, 100, 0)
keyword = st.sidebar.text_input("Keyword contains", "")

filtered = results.copy()
if platform != "All": filtered = filtered[filtered.platform == platform]
if market != "All": filtered = filtered[filtered.market.str.contains(re.escape(market), case=False, na=False)]
if category != "All": filtered = filtered[filtered.category == category]
if problem != "All": filtered = filtered[filtered.problem == problem]
filtered = filtered[(filtered.intent_score >= min_score) & (filtered.customer_fit_score >= min_fit)]
if keyword.strip(): filtered = filtered[filtered.text.str.contains(re.escape(keyword.strip()), case=False, na=False)]
filtered = filtered.sort_values(["customer_fit_score", "intent_score"], ascending=False)

# ---- KPI dashboard ----
st.subheader("3. Acquisition dashboard")
total = len(results)
hot = int((results.category == "HOT").sum())
warm = int((results.category == "WARM").sum())
possible = int((results.category == "POSSIBLE").sum())
low = int((results.category == "LOW").sum())
high_fit = int((results.customer_fit_score >= 80).sum())
cols = st.columns(6)
for col, label, value in zip(cols, ["Signals", "HOT", "WARM", "POSSIBLE", "LOW", "High-fit"], [total, hot, warm, possible, low, high_fit]):
    col.metric(label, value)

if total:
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("**Top platforms**")
        st.dataframe(results.platform.value_counts().head(5).rename("signals"), use_container_width=True)
    with p2:
        st.markdown("**Top markets**")
        st.dataframe(results.market.value_counts().head(5).rename("signals"), use_container_width=True)
    with p3:
        st.markdown("**Top problems**")
        st.dataframe(results.problem.value_counts().head(5).rename("signals"), use_container_width=True)

# ---- Opportunity queue ----
st.subheader("4. Opportunity queue")
st.caption(f"Showing {len(filtered)} of {len(results)} unique signals")
queue_cols = ["platform", "text", "market", "intent_score", "customer_fit_score", "category", "problem", "recommended_action", "url"]
display = filtered[queue_cols].copy()
st.dataframe(display, use_container_width=True, hide_index=True, column_config={
    "url": st.column_config.LinkColumn("Source", display_text="Open"),
    "intent_score": st.column_config.NumberColumn("Intent", min_value=0, max_value=100),
    "customer_fit_score": st.column_config.NumberColumn("Fit", min_value=0, max_value=100),
})

# ---- Detail ----
st.subheader("5. Signal detail")
if not filtered.empty:
    selected = st.selectbox("Select an opportunity", filtered.signal_id.tolist(), format_func=lambda x: f"{x} — {filtered.loc[filtered.signal_id == x, 'category'].iloc[0]} — {filtered.loc[filtered.signal_id == x, 'text'].iloc[0][:100]}")
    row = filtered[filtered.signal_id == selected].iloc[0]
    a, b, c, d = st.columns(4)
    a.metric("Intent", int(row.intent_score))
    b.metric("Daily Levels Fit", int(row.customer_fit_score))
    c.metric("Priority", row.category)
    d.metric("Confidence", f"{float(row.confidence):.0%}")
    st.write(f"**Problem:** {row.problem}")
    st.write(f"**Suggested Daily Levels solution:** {row.daily_levels_solution}")
    st.write(f"**Recommended action:** {row.recommended_action}")
    st.write(f"**Signal:** {row.text}")
    st.write(f"**Source:** {row.url}")
else:
    st.info("No opportunities match the current filters.")

# ---- Export ----
st.subheader("6. Export")
csv_bytes = results.to_csv(index=False).encode("utf-8")
st.download_button("Download V3.1 opportunity dataset", csv_bytes, "daily_levels_v3_1_opportunities.csv", "text/csv")

st.subheader("7. V3.1 architecture")
st.markdown("""
**Public sources → ingestion adapters → normalization → duplicate detection → V2 intelligence → fit scoring → opportunity queue → human-approved action**

Configured ingestion is deliberately opt-in. Add only sources you are permitted to access. The system does not send messages, contact users automatically, access private data, or bypass platform restrictions.
""")
