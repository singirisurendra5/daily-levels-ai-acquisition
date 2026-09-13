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

INTENT_RULES = [
    ("Explicit levels request", 45, [r"\bsupport\s*(?:and|&|/)\s*resistance\b", r"\b(?:support|resistance)\s+(?:level|levels)\b", r"\b(?:key|important|major|next)\s+levels?\b", r"\b(?:give|share|show|tell|need|looking for|what are|where are)\b.{0,80}\blevels?\b"]),
    ("Trading action language", 20, [r"\b(?:enter|entry|buy|sell|long|short|target|stop[- ]?loss|position|trade|trading)\b"]),
    ("Short-term context", 10, [r"\b(?:today|tomorrow|intraday|day trade|next session|next trading day)\b"]),
    ("Direct question/request", 10, [r"\?", r"\b(?:can someone|anyone know|please|help me|how do i|where can i|what should i)\b"]),
]
SPAM_RULES = [
    ("Promotional/spam language", -30, [r"\bgiveaway\b", r"\bpromo code\b", r"\bairdrop\b", r"\bfree money\b", r"\bcasino\b", r"\bbetting\b", r"\bsubscribe\s+to\s+my\s+channel\b", r"\baffiliate\b"]),
]
PROBLEM_RULES = [
    ("Needs predefined support/resistance levels", [r"support", r"resistance", r"levels?", r"key level"]),
    ("Needs a trading entry/target reference", [r"entry", r"target", r"where.*enter", r"where.*buy", r"where.*sell", r"stop[- ]?loss"]),
    ("Needs short-term/session planning", [r"today", r"tomorrow", r"next session", r"intraday", r"day trade"]),
]
GENERIC_MARKERS = [
    r"\bdaily discussion\b", r"\bdaily thread\b", r"\bweekly discussion\b", r"\bmegathread\b",
    r"\btechnical analysis (?:guide|intro|introduction)\b", r"\bwhat is technical analysis\b",
    r"\bnews\b.{0,50}\bmarket\b", r"\bmarket news\b", r"\bfor educational purposes\b",
]
AUTOMATED_MARKERS = [r"\bautomoderator\b", r"\bmod(erator)?\b", r"\bthis is the daily discussion\b", r"\bposted automatically\b", r"\bweekly thread\b"]


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

def analyze(text):
    text = clean(text)
    points = 0; reasons=[]; matched=[]
    for label, weight, patterns in INTENT_RULES:
        hits=[p for p in patterns if re.search(p,text,re.I|re.S)]
        if hits:
            points += weight; reasons.append(f"+{weight} {label}"); matched.extend(hits)
    market_hits=[m for m,pats in MARKETS.items() if found_any(text,pats)]
    if market_hits:
        points += 10; reasons.append("+10 Supported market detected")
    spam_hits=[]
    for label,weight,patterns in SPAM_RULES:
        hits=[p for p in patterns if re.search(p,text,re.I|re.S)]
        if hits:
            points += weight; reasons.append(f"{weight} {label}"); spam_hits.extend(hits)

    automated = found_any(text, AUTOMATED_MARKERS)
    generic = found_any(text, GENERIC_MARKERS)
    direct_need = bool(re.search(r"\?|\b(?:need|looking for|want|where|what are|can someone|please|help me|give me|share|show me|tell me)\b", text, re.I))
    explicit_levels_need = bool(re.search(r"(?:where|what|need|looking for|give|share|show|tell).{0,80}(?:support|resistance|levels?)|(?:support|resistance).{0,40}(?:level|levels)|\bkey levels?\b", text, re.I|re.S))
    problem = "No clear Daily Levels problem detected"
    for label,patterns in PROBLEM_RULES:
        if found_any(text,patterns): problem=label; break

    # Precision adjustments: generic/automated threads are useful context but are not themselves purchase-intent leads.
    quality_penalty = 0
    quality_flags=[]
    if automated:
        quality_penalty += 30; quality_flags.append("Automated/moderator content")
    if generic:
        quality_penalty += 20; quality_flags.append("Generic discussion/educational content")
    if not direct_need and not explicit_levels_need:
        quality_penalty += 15; quality_flags.append("No explicit user need")
    if spam_hits:
        quality_penalty += 20; quality_flags.append("Promotional/spam indicators")
    adjusted=max(0,min(100,points-quality_penalty))

    # Strong intent requires an actual need, not merely trading terminology.
    if problem == "No clear Daily Levels problem detected":
        fit = 0 if not explicit_levels_need else 35
    else:
        fit = 40
    if market_hits: fit += 35
    if direct_need or explicit_levels_need: fit += 20
    if adjusted >= 75 and not automated and not generic: fit += 10
    fit=max(0,min(100,fit))

    if spam_hits or adjusted < 40:
        action="Do not contact" if spam_hits or adjusted < 25 else "Review manually"
    elif fit >= 80 and (direct_need or explicit_levels_need): action="Review manually"
    elif fit >= 55: action="Reply with educational information"
    else: action="Create relevant content"

    if problem != "No clear Daily Levels problem detected":
        solution="Daily Levels can provide predefined daily support and resistance levels from the opening price."
    else:
        solution="No direct Daily Levels solution match until a specific levels, entry, or short-term planning need is expressed."

    if adjusted>=90: category="HOT"
    elif adjusted>=75: category="WARM"
    elif adjusted>=60: category="POSSIBLE"
    else: category="LOW"
    spam_probability=min(1.0,0.5 if spam_hits else (0.2 if automated else 0.03))
    confidence=min(1.0,0.35+(0.15 if market_hits else 0)+(0.2 if problem!="No clear Daily Levels problem detected" else 0)+(0.15 if direct_need else 0)+(0.1 if explicit_levels_need else 0))
    if automated or generic: confidence=max(0.25,confidence-0.15)
    explanation=" | ".join(reasons) if reasons else "No strong trading-intent signals detected"
    if quality_flags: explanation += " | Quality flags: " + ", ".join(quality_flags)
    return {
        "intent_score": adjusted, "category": category, "market": ", ".join(market_hits) if market_hits else "Unknown",
        "matched_terms": ", ".join(dict.fromkeys([p.strip(r"\b").replace(r"\s*"," ") for p in matched])),
        "signal_explanation": explanation, "customer_fit_score": fit, "problem": problem,
        "daily_levels_solution": solution, "recommended_action": action,
        "spam_probability": round(spam_probability,2), "confidence": round(confidence,2),
        "signal_type": "Automated/moderator" if automated else ("Generic discussion" if generic else "User-intent signal"),
        "explicit_need": bool(direct_need or explicit_levels_need), "quality_flags": "; ".join(quality_flags),
    }
