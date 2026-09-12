# Daily Levels — AI Customer Acquisition MVP

A local Streamlit dashboard for analyzing **public trading-intent signals** from a CSV.

## What it does

- Uploads a CSV containing `platform`, `url`, and `text`
- Detects rule-based trading intent
- Detects broad market categories:
  - India
  - Crypto
  - US
  - Forex
- Produces an intent score from 0–100
- Classifies each row:
  - `HOT`: 75–100
  - `WARM`: 60–74
  - `LOW`: 0–59
- Explains matched signals and keywords
- Filters by platform, market, category, minimum score, and keyword
- Exports filtered results to CSV
- Includes a sample CSV

## Important scope

This is an initial rule-based MVP. The score is an intent/fit indicator, not proof that a person will buy.

The project intentionally does **not** include:

- Private watch-history tracking
- Private WhatsApp access
- Private Telegram access
- Private-group scraping
- Automated unsolicited messaging
- Mass outreach
- Claims about personal financial behavior

Use only data that you are permitted to collect and process under each platform's current rules.

## Folder structure

```text
daily_levels_ai_acquisition_mvp/
├── app.py
├── requirements.txt
├── sample_signals.csv
├── README.md
└── .gitignore
```

## Installation

Python 3.9+ is recommended.

```bash
python -m venv .venv
```

Activate the environment.

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Streamlit will open the dashboard in your browser.

## CSV format

Your CSV must contain these columns:

```csv
platform,url,text
YouTube,https://example.com/video1,"NIFTY support for tomorrow?"
Reddit,https://example.com/post1,"BTC next resistance?"
YouTube,https://example.com/video2,"How do you calculate Bank Nifty levels?"
```

## Suggested next steps

1. Test with 100 manually collected, permitted public signals.
2. Review false positives and false negatives.
3. Adjust the rule weights.
4. Add duplicate detection.
5. Add dates and source identifiers.
6. Add an abstraction layer for approved YouTube/Reddit APIs.
7. Replace or supplement rules with an AI classifier.
8. Add human approval before any public response or campaign action.
