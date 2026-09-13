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
UNMET_NEED_RULES = [
    r"\b(?:need|looking for|want|searching for|trying to find|where can i get|how can i get)\b.{0,100}\b(?:support|resistance|levels?)\b",
    r"\b(?:support|resistance|levels?)\b.{0,80}\b(?:for today|for tomorrow|for the next session|next session)\b",
    r"\b(?:reliable|accurate|clear|predefined|daily|key)\b.{0,80}\b(?:support|resistance|levels?)\b.{0,40}\?",
]
DISCUSSION_ONLY = [
    r"\b(?:do you|does anyone|anyone else|curious|interested|what do you think|share your|let\'s talk|discussion|experiences?)\b",
    r"\b(?:i\'m curious|i am curious|i\'d like to hear|i would like to hear)\b",
]
EXISTING_SOLUTION = [
    r"\bsource\s*[:=-]", r"\bsource\s+(?:for|of)\s+(?:the\s+)?levels?\b",
    r"\b(?:using|use|from)\s+(?:gammawalls|tradingview|investing\.com|zerodha|upstox|sensibull|opstra)\b",
    r"\b(?:my|our|these)\s+(?:levels|support|resistance)\b",
    r"\b(?:call|put)\s+wall\b",
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

    recap_markers = [
        r"\bhere(?:'s| is) (?:my|the) levels?\b",
        r"\blevels? (?:for|at)\s+\d",
        r"\bmy trade recap\b",
        r"\btrade recap\b",
        r"\bmarket recap\b",
    ]
    recap = found_any(text, recap_markers) and not explicit

    unmet_need = found_any(text, UNMET_NEED_RULES)
    discussion_only = found_any(text, DISCUSSION_ONLY)
    existing_solution = found_any(text, EXISTING_SOLUTION)
    # A question is not automatically a buying signal. It must express a concrete
    # unmet need for the type of levels Daily Levels provides.
    true_need = bool(explicit and unmet_need and not discussion_only)

    # Generic/automated content that merely mentions levels is not treated as a
    # concrete Daily Levels problem unless there is a clear user need.
    problem = "No clear Daily Levels problem detected"
    if not (generic or automated) or explicit:
        for label, patterns in PROBLEM_RULES:
            if found_any(text, patterns):
                problem = label
                break

    # Sales qualification: mention/relevance is deliberately weaker than true buyer need.
    relevance = 0
    if problem != "No clear Daily Levels problem detected": relevance += 30
    if market_hits: relevance += 20
    if short_term: relevance += 10
    if true_need: relevance += 40
    elif explicit: relevance += 5
    if existing_solution: relevance -= 20
    if generic or automated or discussion_only: relevance -= 30
    if spam: relevance -= 50
    if recap and not true_need: relevance -= 20
    relevance = max(0, min(100, relevance))

    buying = 0
    if true_need: buying += 60
    if unmet_need and not discussion_only: buying += 15
    if short_term and true_need: buying += 10
    if market_hits and true_need: buying += 10
    if competitor: buying -= 30
    if existing_solution and not true_need: buying -= 35
    if discussion_only: buying -= 35
    if generic: buying -= 30
    if automated: buying -= 45
    if spam: buying -= 60
    if recap and not true_need: buying -= 35
    buying = max(0, min(100, buying))

    fit = 0
    if true_need and problem == "Needs predefined support/resistance levels": fit += 65
    elif true_need and problem == "Needs a trading entry/target reference": fit += 35
    elif true_need and problem == "Needs short-term/session planning": fit += 30
    if market_hits and true_need: fit += 20
    if short_term and true_need: fit += 10
    if competitor: fit -= 20
    if existing_solution and not true_need: fit -= 25
    if generic or automated or discussion_only: fit -= 35
    if spam: fit -= 60
    if not true_need: fit = min(fit, 35)
    fit = max(0, min(100, fit))

    # Priority is sales-readiness, not just topical relevance.
    priority_score = round((0.45 * buying) + (0.25 * relevance) + (0.30 * fit))
    if not true_need: priority_score = min(priority_score, 59)
    if buying < 40 or relevance < 45 or fit < 45: priority_score = min(priority_score, 74)
    if buying < 25 or relevance < 30: priority_score = min(priority_score, 39)
    if competitor: priority_score = min(priority_score, 59)
    if existing_solution and not true_need: priority_score = min(priority_score, 39)
    if spam or automated: priority_score = min(priority_score, 19)
    if generic or discussion_only or recap: priority_score = min(priority_score, 49)

    if priority_score >= 90:
        category = "HOT"
    elif priority_score >= 75:
        category = "WARM"
    elif priority_score >= 60:
        category = "POSSIBLE"
    else:
        category = "LOW"

    if spam or automated or priority_score < 25:
        action = "Do not contact"
    elif competitor and buying >= 60:
        action = "Review manually"
    elif buying >= 70 and fit >= 75 and true_need:
        action = "Review manually"
    elif true_need and buying >= 50:
        action = "Reply with educational information"
    elif relevance >= 55 and not discussion_only:
        action = "Create relevant content"
    else:
        action = "Do not contact"

    if problem != "No clear Daily Levels problem detected":
        solution = "Daily Levels can provide predefined daily support and resistance levels from the opening price."
    else:
        solution = "No direct Daily Levels solution match until a specific levels, entry, or short-term planning need is expressed."

    reasons = []
    if explicit: reasons.append("Explicit levels request")
    if true_need: reasons.append("Concrete unmet need for levels")
    if discussion_only: reasons.append("Discussion/question without purchase need")
    if existing_solution: reasons.append("Existing level source or method detected")
    if trading_action: reasons.append("Trading action language")
    if short_term: reasons.append("Short-term context")
    if direct: reasons.append("Direct question/request")
    if market_hits: reasons.append("Supported market detected")
    if competitor: reasons.append("Alternative level source detected")
    flags = []
    if generic: flags.append("Generic discussion/educational content")
    if automated: flags.append("Automated/moderator content")
    if recap: flags.append("Trade/market recap without explicit request")
    if discussion_only: flags.append("Discussion-only signal")
    if existing_solution: flags.append("Existing solution/level source")
    if competitor: flags.append("Existing alternative/competitor source")
    elif existing_levels and not explicit: flags.append("Already has or cites existing levels")
    if spam: flags.append("Promotional/spam indicators")
    if not direct and not explicit: flags.append("No explicit user request")

    signal_type = "Automated/moderator" if automated else ("User-intent signal" if true_need else "Generic discussion")
    confidence = 0.45 + (0.15 if market_hits else 0) + (0.15 if problem != "No clear Daily Levels problem detected" else 0) + (0.15 if explicit else 0)
    if generic or automated or recap: confidence -= 0.20
    confidence = max(0.25, min(0.95, confidence))

    matched = []
    if explicit: matched.append("levels request")
    if trading_action: matched.append("trade/action")
    if short_term: matched.append("short-term")
    if direct: matched.append("question/request")
    if competitor: matched.append("alternative source")

    explanation = " | ".join(reasons) if reasons else "No strong buying-intent signals detected"
    if flags: explanation += " | Qualification flags: " + ", ".join(flags)

    return {
        "intent_score": int(priority_score),
        "category": category,
        "market": ", ".join(market_hits) if market_hits else "Unknown",
        "matched_terms": ", ".join(matched),
        "signal_explanation": explanation,
        "customer_fit_score": int(fit),
        "problem": problem,
        "daily_levels_solution": solution,
        "recommended_action": action,
        "spam_probability": round(0.8 if spam else (0.35 if automated else (0.20 if generic else 0.03)), 2),
        "confidence": round(confidence, 2),
        "signal_type": signal_type,
        "explicit_need": bool(true_need),
        "unmet_need": bool(unmet_need),
        "sales_ready": bool(true_need and buying >= 70 and fit >= 75 and priority_score >= 90),
        "lead_reason": "; ".join(reasons) if reasons else "No strong sales-intent evidence",
        "quality_flags": "; ".join(flags),
        "relevance_score": int(relevance),
        "buying_intent_score": int(buying),
        "product_fit_score": int(fit),
        "priority_score": int(priority_score),
        "competition_detected": bool(competitor or existing_levels),
        "qualification_version": "3.6-final",
    }

