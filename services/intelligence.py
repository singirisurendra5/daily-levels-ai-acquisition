import re
import hashlib
import pandas as pd

MARKETS = {
    "India (NIFTY)": [r"\bnifty\b", r"\bnifty\s*50\b"],
    "India (Bank Nifty)": [r"\bbank\s*nifty\b", r"\bbanknifty\b"],
    "India (Sensex)": [r"\bsensex\b"],
    "India (Options)": [r"\bindian\s+options?\b", r"\boptions?\b"],
    "Crypto (BTC)": [r"\bbtc\b", r"\bbitcoin\b"],
    "Crypto (ETH)": [r"\beth\b", r"\bethereum\b"],
    "Crypto": [r"\bcrypto\b", r"\bcryptocurrency\b"],
    "US (S&P 500)": [r"\bs&p\b", r"\bspx\b", r"\bs&p\s*500\b"],
    "US (Nasdaq)": [r"\bnasdaq\b", r"\bqqq\b"],
    "US (Dow)": [r"\bdow\b"],
    "US Stocks": [r"\bus\s+stocks?\b", r"\bnyse\b"],
    "Forex (EUR/USD)": [r"\beur\s*/?\s*usd\b", r"\beurusd\b"],
    "Forex (GBP/USD)": [r"\bgbp\s*/?\s*usd\b", r"\bgbpusd\b"],
    "Gold / XAUUSD": [r"\bxau\s*/?\s*usd\b", r"\bxauusd\b", r"\bgold\b"],
    "Forex": [r"\bforex\b"],
}

SUPPORTED_MARKETS = set(MARKETS)

RULES = [
    ("Explicit support/resistance or levels request", 45, [
        r"\bsupport\s*(?:and|&|/)\s*resistance\b", r"\bsupport\b", r"\bresistance\b",
        r"\blevels?\b", r"\bkey level\b", r"\bnext level\b",
    ]),
    ("Active trading language", 25, [
        r"\btrade\b", r"\btrading\b", r"\btrader\b", r"\bentry\b", r"\bposition\b",
        r"\blong\b", r"\bshort\b", r"\btarget\b", r"\bcall\b", r"\bput\b",
    ]),
    ("Short-term/session context", 15, [
        r"\btoday\b", r"\btomorrow\b", r"\bnext\b", r"\bthis session\b",
        r"\bfor tomorrow\b", r"\bfor today\b",
    ]),
    ("Direct question/request", 5, [
        r"\?", r"\bwhere\b", r"\bwhat\b", r"\bhow\b", r"\bcan someone\b", r"\banyone\b",
    ]),
]

SPAM_RULES = [
    ("Possible promotional/spam language", -25, [
        r"\bgiveaway\b", r"\bpromo code\b", r"\bairdrop\b", r"\bfree money\b",
        r"\bcasino\b", r"\bbetting\b", r"\bsubscribe\s+to\s+my\s+channel\b",
    ]),
]

PROBLEM_RULES = [
    ("Needs predefined support/resistance levels", [r"support", r"resistance", r"levels?", r"key level"]),
    ("Needs a trading entry/target reference", [r"entry", r"target", r"where.*enter", r"where.*buy", r"where.*sell"]),
    ("Needs short-term/session planning", [r"today", r"tomorrow", r"next session", r"intraday"]),
]


def clean(x):
    return "" if pd.isna(x) else str(x).strip()


def found_any(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)


def signal_id(platform, url, text):
    key = f"{clean(platform).lower()}|{clean(url).lower()}|{re.sub(r'\s+', ' ', clean(text).lower())}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def near_duplicate_key(text):
    value = re.sub(r"[^a-z0-9]+", " ", clean(text).lower()).strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def analyze(text):
    text = clean(text)
    points = 0
    reasons = []
    matched_terms = []
    for label, weight, patterns in RULES:
        hits = [p for p in patterns if re.search(p, text, re.I)]
        if hits:
            points += weight
            reasons.append(f"+{weight} {label}")
            matched_terms.extend([p.strip(r"\b").replace(r"\s*", " ") for p in hits])

    market_hits = [market for market, patterns in MARKETS.items() if found_any(text, patterns)]
    if market_hits:
        points += 10
        reasons.append("+10 Market detected")

    spam_hits = []
    for label, weight, patterns in SPAM_RULES:
        hits = [p for p in patterns if re.search(p, text, re.I)]
        if hits:
            points += weight
            reasons.append(f"{weight} {label}")
            spam_hits.extend(hits)

    score = max(0, min(100, points))
    if score >= 90:
        category = "HOT"
    elif score >= 75:
        category = "WARM"
    elif score >= 60:
        category = "POSSIBLE"
    else:
        category = "LOW"

    problem = "No clear Daily Levels problem detected"
    for label, patterns in PROBLEM_RULES:
        if found_any(text, patterns):
            problem = label
            break

    fit = 0
    if market_hits:
        fit += 50
    if problem != "No clear Daily Levels problem detected":
        fit += 40
    if category in {"HOT", "WARM"}:
        fit += 10
    daily_levels_fit = min(100, fit)

    if daily_levels_fit >= 80:
        action = "Review manually"
        solution = "Daily Levels can provide predefined daily support and resistance levels from the opening price."
    elif daily_levels_fit >= 50:
        action = "Create relevant content"
        solution = "Create educational content showing how Daily Levels addresses this trading-level problem."
    elif category in {"HOT", "WARM"}:
        action = "Invite to learn more"
        solution = "Explain the relevant Daily Levels workflow without unsolicited automation."
    else:
        action = "Do not contact"
        solution = "No strong Daily Levels fit identified."

    spam_probability = min(1.0, 0.25 if spam_hits else 0.02)
    confidence = min(1.0, 0.35 + (0.15 if market_hits else 0) + (0.2 if matched_terms else 0) + (0.2 if problem != "No clear Daily Levels problem detected" else 0))
    explanation = " | ".join(reasons) if reasons else "No strong trading-intent signals detected"
    if matched_terms:
        explanation = f"Intent terms: {', '.join(dict.fromkeys(matched_terms))} | {explanation}"

    return {
        "intent_score": score,
        "category": category,
        "market": ", ".join(market_hits) if market_hits else "Unknown",
        "matched_terms": ", ".join(dict.fromkeys(matched_terms)),
        "signal_explanation": explanation,
        "customer_fit_score": daily_levels_fit,
        "problem": problem,
        "daily_levels_solution": solution,
        "recommended_action": action,
        "spam_probability": round(spam_probability, 2),
        "confidence": round(confidence, 2),
    }
