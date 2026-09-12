# Daily Levels — AI Customer Acquisition MVP v2

This version fixes the scoring layer and makes the score transparent.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## CSV

Required:
- platform
- url
- text

Optional:
- date

## Scoring

Maximum 100:
- +45 explicit support/resistance or levels request
- +25 active trading language
- +15 short-term/session context
- +5 direct question/request
- +10 market detected
- -25 possible promotional/spam language

Categories:
- HOT: 90–100
- WARM: 75–89
- POSSIBLE: 60–74
- LOW: below 60

The score is an intent/fit prioritization heuristic. It does not prove that someone is a buyer.

## Folder

```text
daily_levels_ai_acquisition_mvp_v2/
├── app.py
├── requirements.txt
├── README.md
└── data/
    └── sample_signals.csv
```

## Future-ready design

Keep the dashboard's normalized output contract:

- intent_score
- category
- market
- matched_terms
- signal_explanation

A future AI classifier can replace `analyze()` while returning these fields plus:
- problem
- buying_intent
- daily_levels_fit
- spam_probability
- duplicate_probability
- confidence

Then add approved public-data ingestion adapters for YouTube/Reddit.

## Responsible use

Only use public, permitted data. Follow platform API/automation rules. Do not access private watch history, private WhatsApp/Telegram chats, credentials, prohibited data, or use mass unsolicited messaging.
