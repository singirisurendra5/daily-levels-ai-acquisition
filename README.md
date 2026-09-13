# Daily Levels — AI Customer Acquisition MVP V3.1

V3.1 builds on MVP V2. It does not replace the V2 scoring model; it adds a live public-signal ingestion layer and an acquisition opportunity queue.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## V3.1 additions

- Configurable public RSS/Atom ingestion
- Public Reddit RSS ingestion
- Public YouTube channel feed ingestion
- Source errors surfaced in the UI
- Normalized signal records
- Exact/near-duplicate detection
- Customer-fit score
- Problem detection
- Daily Levels solution matching
- Recommended human action
- Opportunity queue sorted by fit and intent
- Top platform/market/problem summaries
- V3.1 export

## Configure sources

Edit `data/sources.json`:

```json
{
  "rss_feeds": [
    {"platform": "Example", "url": "https://example.com/feed.xml"}
  ],
  "reddit": [
    {"subreddit": "stocks", "query": "NIFTY support resistance", "sort": "new", "limit": 25}
  ],
  "youtube_channels": [
    {"channel_id": "UCxxxxxxxxxxxxxxxx", "limit": 15}
  ]
}
```

Only configure public sources and endpoints that your use complies with. This project intentionally does not implement private-data access or automated outreach.

## V2 compatibility

The V2 normalized fields remain available, including `intent_score`, `category`, `market`, `matched_terms`, and `signal_explanation`. V3.1 adds `customer_fit_score`, `problem`, `daily_levels_solution`, `recommended_action`, `spam_probability`, `confidence`, `signal_id`, and duplicate metadata.
