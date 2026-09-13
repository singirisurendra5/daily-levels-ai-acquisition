# Daily Levels — Automatic Trader Finder V4

V4 simplifies acquisition to the actual workflow:

**Public sources → find trader → identify market → prepare Daily Levels landing-page opportunity**

Landing page: https://dailylevels-app.vercel.app/

## What is automatic
- Fetches enabled public RSS/Reddit/YouTube feeds on first app load.
- Deduplicates public signals.
- Identifies likely traders and supported markets.
- Classifies signals as HIGH / MEDIUM / LOW.
- Shows the evidence and the Daily Levels landing page for HIGH/MEDIUM opportunities.
- Stores signals in SQLite so the opportunity list persists.

## Levels
- **HIGH**: clear public request for support/resistance/levels.
- **MEDIUM**: active trader + levels context, without a direct request.
- **LOW**: not enough evidence of a relevant trader.

This version does not try to predict purchases or create complex sales qualification.

## Compliance
Only permitted public information is used. The app does not access private chats, private groups, private watch history, access-controlled data, or bypass platform restrictions. It does not automatically send unsolicited messages; a human must perform any outreach in accordance with the platform's rules.

## Run
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```
