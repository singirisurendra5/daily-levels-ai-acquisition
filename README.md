# Daily Levels — AI Customer Acquisition

MVP V3.3.1: live public-signal acquisition with persistent local workflow and human-in-the-loop review.

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
