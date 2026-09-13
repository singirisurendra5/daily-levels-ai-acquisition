import re
import hashlib
import pandas as pd

MARKETS = {
    "India (NIFTY)": [r"\bnifty(?:\s*50)?\b"],
    "India (Bank Nifty)": [r"\bbank\s*nifty\b", r"\bbanknifty\b"],
    "India (Sensex)": [r"\bsensex\b"],
    "India (Options)": [r"\bindian\s+options?\b", r"\bnifty\s+(?:options?|calls?|puts?)\b", r"\bbank\s*nifty\s+(?:options?|calls?|puts?)\b"],
    "Crypto (BTC)": [r"\bbtc\b", r"\bbitcoin\b"],
    "Crypto (ETH)": [r"\bethereum\b", r"\beth\b(?=.*(?:crypto|ethereum|usdt|usd|price|trade|trading))"],
    "Crypto": [r"\bcrypto\b", r"\bcryptocurrency\b"],
    "US (S&P 500)": [r"\bs&p\s*500\b", r"\bspx\b"],
    "US (Nasdaq)": [r"\bnasdaq\b", r"\bqqq\b"],
    "US (Dow)": [r"\bdow\b(?=.*(?:jones|index|futures|trade|trading))"],
    "US Stocks": [r"\bus\s+stocks?\b", r"\bnyse\b", r"\bnasdaq\b"],
    "Forex (EUR/USD)": [r"\beur\s*/?\s*usd\b", r"\beurusd\b"],
    "Forex (GBP/USD)": [r"\bgbp\s*/?\s*usd\b", r"\bgbpusd\b"],
    "Gold / XAUUSD": [r"\bxau\s*/?\s*usd\b", r"\bxauusd\b", r"\bgold\b"],
    "Forex": [r"\bforex\b"],
}
SUPPORTED_MARKETS = set(MARKETS)

# V3.5 separates three concepts: relevance, buying intent, and product fit.
# This prevents a trader recap that mentions levels from looking like a buyer.
EXPLICIT_REQUEST = [
    r"\b(?:where|what are|what's|whats|need|give me|share|show me|tell me|can someone|anyone know|help me|how do i)\b.{0,120}\b(?:support|resistance|levels?)\b",
    r"\blooking for\s+(?:reliable|accurate|key|clear|daily|predefined)\b.{0,100}\b(?:support|resistance|levels?)\b",
    r"\b(?:support|resistance)(?:\s+and\s+(?:support|resistance))?\b.{0,50}\bfor\s+(?:today|tomorrow|next session|the next session)\b\s*\?",
]
TRADING_ACTION = [r"\b(?:enter|entry|buy|sell|long|short|target|stop[- ]?loss|position|trade|trading)\b"]
SHORT_TERM = [r"\b(?:today|tomorrow|intraday|day trade|next session|next trading day|opening|market open)\b"]
DIRECT_REQUEST = [r"\?", r"\b(?:can someone|anyone know|please|help me|how do i|where can i|what should i|need|looking for|want|give me|share|show me|tell me)\b"]
GENERIC_MARKERS = [r"\bdaily discussion\b", r"\bdaily thread\b", r"\bweekly discussion\b", r"\bmegathread\b", r"\btechnical analysis (?:guide|intro|introduction)\b", r"\bwhat is technical analysis\b", r"\bmarket news\b", r"\bfor educational purposes\b"]
AUTOMATED_MARKERS = [r"\bautomoderator\b", r"\bmod(erator)?\b", r"\bthis is the daily discussion\b", r"\bposted automatically\b", r"\bweekly thread\b"]
SPAM_RULES = [r"\bgiveaway\b", r"\bpromo code\b", r"\bairdrop\b", r"\bfree money\b", r"\bcasino\b", r"\bbetting\b", r"\bsubscribe\s+to\s+my\s+channel\b", r"\baffiliate\b"]
COMPETITOR_RULES = [
    r"\bsource\s+(?:for|of)\s+(?:the\s+)?levels?\s*[:=-]\s*[^\n]{2,80}",
    r"\b(?:using|use|from)\s+(?:gammawalls|tradingview|investing\.com|zerodha|upstox|sensibull|opstra)\b",
    r"\b(?:my|our)\s+(?:levels|support|resistance)\s+(?:come|comes|are)\s+from\b",
]
PROBLEM_RULES = [
    ("Needs predefined support/resistance levels", [r"support", r"resistance", r"levels?", r"key level"]),
    ("Needs a trading entry/target reference", [r"entry", r"target", r"where.*enter", r"where.*buy", r"where.*sell", r"stop[- ]?loss"]),
    ("Needs short-term/session planning", [r"today", r"tomorrow", r"next session", r"intraday", r"day trade", r"opening"]),
]


def clean(x):
    return "" if pd.isna(x) else str(x).strip()

def found_any(text, patterns):
    return any(re.search(p, text, re.I | re.S) for p in patterns)

def signal_id(platform, url, text):
    key = f"{clean(platform).lower()}|{clean(url).lower()}|{re.sub(r'\s+', ' ', clean(text).lower())}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def near_duplicate_key(text):
    value = re.sub(r"[^a-z0-9]+", " ", clean(text).lower()).strip()
    return hashlib.sha256(value.encode()).hexdigest()[:16]

def _market_hits(text):
    return [m for m, pats in MARKETS.items() if found_any(text, pats)]

def analyze(text):
    text = clean(text)
    market_hits = _market_hits(text)
    explicit = found_any(text, EXPLICIT_REQUEST)
    if explicit and found_any(text, [r"\bcurious how others\b", r"\banyone else seeing\b", r"\bmy plan\b"]):
        explicit = False
    direct = found_any(text, DIRECT_REQUEST)
    trading_action = found_any(text, TRADING_ACTION)
    short_term = found_any(text, SHORT_TERM)
    generic = found_any(text, GENERIC_MARKERS)
    automated = found_any(text, AUTOMATED_MARKERS)
    spam = found_any(text, SPAM_RULES)
    competitor = found_any(text, COMPETITOR_RULES)
    existing_levels = found_any(text, [
        r"\bsource\s*[:=-]\s*(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}\b",
        r"\bsource\s+(?:for|of)\s+(?:the\s+)?levels?\b",
        r"\b(?:my|our|these)\s+levels?\b",
        r"\b(?:call|put)\s+wall\b",
    ])

    # V3.6: separate a true Daily Levels need from a post that merely mentions
    # support/resistance.  A genuine problem statement can qualify even without
    # an explicit "give me levels" request, but generic trading questions cannot.
    unmet_need = found_any(text, [
        r"\b(?:need|needs|looking for|searching for|trying to find|can't find|cannot find|unable to find|where can i get|where do i get)\b.{0,100}\b(?:support|resistance|levels?)\b",
        r"\b(?:struggl(?:e|ing)|difficulty|difficult|problem|issue|confused|not sure|unsure|unclear)\b.{0,100}\b(?:support|resistance|levels?)\b",
        r"\b(?:reliable|accurate|consistent|clear|predefined|daily)\s+(?:support|resistance|levels?)\b",
        r"\b(?:support|resistance|levels?)\b.{0,80}\b(?:hard to find|difficult to find|can't find|cannot find|need|looking for|reliable|accurate|consistent|predefined)\b",
    ])
    # Explicit request is only a true need when it asks for levels, not merely
    # when a question happens to contain the word support/resistance.
    true_need = bool(explicit or unmet_need)
    if generic or automated or spam:
        true_need = bool(explicit and not (generic or automated))
    if competitor and not explicit:
        true_need = False
    if existing_levels and not explicit:
        true_need = False

    recap_markers = [
        r"\bhere(?:'s| is) (?:my|the) levels?\b",
        r"\blevels? (?:for|at)\s+\d",
        r"\bmy trade recap\b",
        r"\btrade recap\b",
        r"\bmarket recap\b",
    ]
    recap = found_any(text, recap_markers) and not explicit

    problem = "No clear Daily Levels problem detected"
    if true_need:
        problem = "Needs predefined support/resistance levels"
    elif found_any(text, [r"\b(?:entry|target|where.*enter|where.*buy|where.*sell|stop[- ]?loss)\b"]) and (explicit or unmet_need):
        problem = "Needs a trading entry/target reference"
    elif short_term and true_need:
        problem = "Needs short-term/session planning"

    # Relevance measures whether Daily Levels plausibly addresses an actual need.
    relevance = 0
    if true_need: relevance += 65
    elif problem != "No clear Daily Levels problem detected": relevance += 30
    if market_hits: relevance += 20
    if short_term: relevance += 5
    if generic or automated: relevance -= 35
    if spam: relevance -= 40
    if competitor and not explicit: relevance -= 25
    if recap and not explicit: relevance -= 25
    relevance = max(0, min(100, relevance))

    # Buying intent: explicit demand is strongest; problem-aware signals are
    # qualified opportunities but are not sales-ready without stronger intent.
    buying = 0
    if explicit: buying += 65
    elif unmet_need: buying += 45
    if direct and true_need and not (generic or automated): buying += 10
    if short_term and true_need: buying += 10
    if market_hits and true_need: buying += 10
    if competitor: buying -= 35
    if existing_levels and not explicit: buying -= 30
    if generic: buying -= 40
    if automated: buying -= 45
    if spam: buying -= 50
    if recap: buying -= 30
    buying = max(0, min(100, buying))

    fit = 0
    if true_need: fit += 65
    elif problem == "Needs a trading entry/target reference": fit += 25
    if market_hits: fit += 20
    if short_term and true_need: fit += 5
    if competitor: fit -= 20
    if existing_levels and not explicit: fit -= 20
    if generic or automated: fit -= 35
    if spam: fit -= 50
    if problem == "No clear Daily Levels problem detected": fit = 0
    fit = max(0, min(100, fit))

    # Sales-ready requires a true unmet need, strong buying intent, and strong fit.
    sales_ready = bool(true_need and explicit and buying >= 70 and fit >= 75 and not generic and not automated and not spam)

    priority_score = round((0.40 * buying) + (0.30 * relevance) + (0.30 * fit))
    if not sales_ready:
        priority_score = min(priority_score, 89 if (true_need and buying >= 45 and fit >= 60) else 74)
    if buying < 25 or relevance < 30:
        priority_score = min(priority_score, 59)
    if not true_need:
        priority_score = min(priority_score, 39 if competitor or existing_levels else 59)
    if competitor and buying < 70:
        priority_score = min(priority_score, 59)
    if existing_levels and not explicit:
        priority_score = min(priority_score, 39)
    if spam or automated:
        priority_score = min(priority_score, 24)

    if sales_ready:
        category = "HOT"
    elif true_need and buying >= 45 and fit >= 60:
        category = "WARM"
    elif relevance >= 45 and fit >= 45:
        category = "POSSIBLE"
    else:
        category = "LOW"

    if spam or automated or priority_score < 25:
        action = "Do not contact"
    elif sales_ready:
        action = "Review manually"
    elif true_need and buying >= 45:
        action = "Reply with educational information"
    elif relevance >= 45:
        action = "Create relevant content"
    else:
        action = "Do not contact"

    if true_need:
        solution = "Daily Levels can provide predefined daily support and resistance levels from the opening price."
    else:
        solution = "No direct Daily Levels solution match until a specific unmet levels need is expressed."

    reasons = []
    if explicit: reasons.append("Explicit levels request")
    elif unmet_need: reasons.append("Problem-aware levels need")
    if trading_action: reasons.append("Trading action language")
    if short_term: reasons.append("Short-term context")
    if direct: reasons.append("Direct question/request")
    if market_hits: reasons.append("Supported market detected")
    if competitor: reasons.append("Alternative level source detected")
    flags = []
    if generic: flags.append("Generic discussion/educational content")
    if automated: flags.append("Automated/moderator content")
    if recap: flags.append("Trade/market recap without explicit request")
    if competitor: flags.append("Existing alternative/competitor source")
    elif existing_levels and not explicit: flags.append("Already has or cites existing levels")
    if spam: flags.append("Promotional/spam indicators")
    if not true_need: flags.append("No concrete Daily Levels need")

    signal_type = "Automated/moderator" if automated else ("Generic discussion" if generic else "User-intent signal")
    confidence = 0.45 + (0.15 if market_hits else 0) + (0.15 if true_need else 0) + (0.15 if explicit else 0)
    if generic or automated or recap: confidence -= 0.20
    if competitor: confidence += 0.05
    confidence = max(0.25, min(0.95, confidence))

    matched = []
    if explicit: matched.append("levels request")
    elif unmet_need: matched.append("problem-aware need")
    if trading_action: matched.append("trade/action")
    if short_term: matched.append("short-term")
    if direct: matched.append("question/request")
    if competitor: matched.append("alternative source")

    explanation = " | ".join(reasons) if reasons else "No strong Daily Levels need detected"
    if flags: explanation += " | Qualification flags: " + ", ".join(flags)

    buyer_stage = "Ready to review" if sales_ready else ("Problem-aware" if true_need else ("Exploring" if relevance >= 45 else "Not a lead"))
    lead_reason = (
        "Explicit unmet Daily Levels need with strong fit and buying intent." if sales_ready else
        "Concrete support/resistance need is present, but buying intent is not yet strong enough for sales-ready." if true_need else
        "No concrete unmet Daily Levels need; content is better suited for education or filtering."
    )
    content_angle = "Daily support/resistance from the opening price" if true_need else "Educational content about identifying reliable daily levels"

    return {
        "intent_score": int(priority_score), "category": category,
        "market": ", ".join(market_hits) if market_hits else "Unknown",
        "matched_terms": ", ".join(matched), "signal_explanation": explanation,
        "customer_fit_score": int(fit), "problem": problem,
        "daily_levels_solution": solution, "recommended_action": action,
        "spam_probability": round(0.8 if spam else (0.35 if automated else (0.20 if generic else 0.03)), 2),
        "confidence": round(confidence, 2), "signal_type": signal_type,
        "explicit_need": bool(explicit), "quality_flags": "; ".join(flags),
        "relevance_score": int(relevance), "buying_intent_score": int(buying),
        "product_fit_score": int(fit), "priority_score": int(priority_score),
        "competition_detected": bool(competitor or existing_levels),
        "sales_ready": bool(sales_ready), "buyer_stage": buyer_stage,
        "lead_reason": lead_reason, "content_angle": content_angle,
        "unmet_need": bool(true_need), "qualification_version": "3.6",
    }
