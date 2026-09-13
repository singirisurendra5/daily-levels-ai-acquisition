# Daily Levels — AI Customer Acquisition MVP V3.6 FINAL

Sales-ready public-signal lead qualification for Daily Levels.

## Core qualification
- Relevance: does the signal have a problem Daily Levels can solve?
- True unmet need: is the person actually looking for support/resistance levels rather than merely discussing them?
- Buying intent: evidence of active solution seeking.
- Product fit: how directly Daily Levels solves the expressed need.
- Sales-ready: true unmet need + strong buying intent + strong product fit + high priority.

The engine deliberately does **not** treat generic questions, trade recaps, educational posts, moderator posts, or mentions of support/resistance as buyer intent. Existing sources such as GammaWalls/TradingView/Sensibull/Opstra/Zerodha are detected and reduce qualification when they indicate the trader already has a solution.

## Workflow
Public source → Fetch → Normalize → Deduplicate → Relevance → True unmet need → Buying intent → Product fit → Sales-ready gate → Priority → HOT/WARM/POSSIBLE/LOW → Human review → Educational response/content → Website visit → Signup → Purchase → Conversion analytics

## Responsible use
Only use public sources you are permitted to access. No private data, automated unsolicited messaging, scraping behind access controls, or bypassing platform restrictions. Human review is required before outreach or sales action.

## Run
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```
