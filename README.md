# Daily Levels — AI Customer Acquisition

MVP V3.5.2: live public-signal acquisition with persistent local workflow and human-in-the-loop review.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## V3.3 workflow

Public RSS/Atom, public Reddit RSS and public YouTube channel feeds → normalization → duplicate detection → V2 intent/market intelligence → Daily Levels fit → opportunity queue → human review → conversion events.

The app does not access private data, bypass access controls, or automatically message users.

## First run

1. Open **Source Manager**.
2. Click **Load recommended public RSS sources**.
3. Click **Fetch live signals now**.
4. Use the filters and opportunity queue to review results.
5. Record human-reviewed actions and conversion events when appropriate.

Recommended sources are public RSS search feeds and are provided as a starting point. Verify that each source is permitted for your intended use and follow its terms and platform policies.

## Storage

Signals, source runs, and conversion events are stored in `data/daily_levels.db`. On hosted environments, local filesystem persistence depends on the hosting provider's storage model; for durable production persistence, move the storage layer to a managed database in a later release.


## V3.3.1 changes
- Fresh deployments automatically seed the recommended public community sources.
- One-click `Start live acquisition` fetches enabled sources.
- Last-fetch metrics are read from persistent run history.
- Recommended sources focus on public Reddit search feeds for trading-intent discovery; no private data or automated outreach.
- Demo/sample data remains separate from live acquisition mode.


## V3.5.2 Lead Qualification Engine
V3.5.2 separates **Relevance**, **Buying Intent**, and **Product Fit**. Priority is a composite qualification score, so generic trading discussions, moderator posts, personal recaps, and existing alternative level sources do not automatically become HOT leads.

Qualification fields: `relevance_score`, `buying_intent_score`, `product_fit_score`, `priority_score`, `competition_detected`. Use **Re-qualify stored signals** after upgrading an existing deployment so older records receive the V3.5.2 scoring model.

Target funnel: Raw signals → Relevant → High-intent → High-fit → true HOT opportunities.


## V3.5.2 — Qualification Consistency Fix

V3.5.2 enforces a single qualification chain: **Relevance → Buying Intent → Product Fit → Priority**. Priority is calculated only from those displayed qualification scores and is protected by hard gates: weak buying intent, no explicit user need, generic/automated/recap content, weak relevance/fit, and detected alternative sources cannot become HOT opportunities.

Existing stored signals are automatically re-qualified once to remove legacy V3.4/V3.5 category/score inconsistencies. The queue is ordered by true priority, and missing quality flags are normalized instead of displaying `nan`.


## V3.5.2 — False-positive & competition detection
- Separates genuine user requests from trade recaps and discussion questions.
- Detects stated/existing level sources and reduces qualification when the trader already has levels.
- Strongly downgrades signals that cite an alternative level provider.
- HOT requires explicit need, strong buying intent, relevance, and product fit.


### V3.6.3
Lead Recall + Evidence Quality Fix: sentence-level evidence, cleaned HTML/URLs, evidence strength (Strong/Moderate/Weak), tighter problem-aware detection, and consistent qualification versioning.
