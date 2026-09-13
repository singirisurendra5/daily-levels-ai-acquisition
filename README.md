# Daily Levels — AI Customer Acquisition

## MVP V3.2
This version continues the existing MVP V2/V3.1 workflow and adds:
- Live public RSS/Atom, Reddit public-feed, and YouTube public-feed ingestion
- In-app Source Manager
- Live / uploaded / demo dataset modes
- Persistent SQLite signal store
- Source-run history and health
- Duplicate-safe opportunity persistence
- Human review status tracking
- Conversion event tracking (content → visit → signup → purchase)
- CSV exports

### Run
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

### Public source configuration
Sources can be added from the **Source Manager** in the app. Only use public feeds you are permitted to access. No automated messages are sent.

### Important deployment note
SQLite is included for a simple single-instance workflow. For durable multi-instance production storage, move the `Store` layer to a managed database such as Postgres/Supabase and keep the same schema/API. Streamlit Community Cloud should be treated as the UI layer rather than a guaranteed durable database filesystem.

### Workflow
Public source → Fetch → Normalize → Deduplicate → Intent + market detection → Daily Levels fit → Priority → Human review → Content/educational action → Website visit → Signup → Purchase → Analytics.
