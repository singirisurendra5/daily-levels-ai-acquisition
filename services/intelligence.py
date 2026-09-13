import re
import hashlib
import html
import pandas as pd

QUALIFICATION_VERSION = "3.6.4"

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

# Evidence-first qualification. Patterns intentionally require the request/problem
# and the levels object to be close together, or in the same sentence.
DIRECT_LEVEL_REQUEST = [
    r"\b(?:where\s+(?:can|do)\s+i\s+(?:get|find)|where\s+(?:are|can\s+i\s+get|do\s+i\s+get)|what\s+(?:are|is)|what's|whats|need|give\s+me|share|show\s+me|tell\s+me|can\s+someone|anyone\s+(?:know|have)|does\s+anyone\s+(?:know|have)|help\s+me|how\s+do\s+i\s+(?:get|find|calculate)|recommend(?:\s+a)?\s+(?:source|way)|best\s+(?:source|way))\b.{0,65}\b(?:support|resistance|levels?)\b",
    r"\b(?:support|resistance|levels?)\b.{0,35}\bfor\s+(?:today|tomorrow|next\s+session|the\s+next\s+session)\b\s*\?",
    r"\b(?:need|looking\s+for|want|trying\s+to\s+get|trying\s+to\s+find)\b.{0,65}\b(?:today|tomorrow|next\s+session)\b.{0,65}\b(?:support|resistance|levels?)\b",
    r"\blooking\s+for\s+(?:reliable|accurate|key|clear|daily|predefined)\b.{0,90}\b(?:support|resistance|levels?)\b",
]

# Problem-aware evidence is deliberately narrower than V3.6.1. The complaint must
# be about finding/quality of levels, not merely a trading problem later mentioning levels.
PROBLEM_AWARE = [
    # The difficulty/complaint must directly point to finding or obtaining levels.
    r"\b(?:i(?:'m|\s+am)?\s+)?(?:struggl(?:e|ing)|having\s+(?:a\s+)?(?:hard|difficult)\s+time|difficulty|hard)\s+(?:to\s+)?(?:find|finding|get|getting)\s+(?:reliable\s+|accurate\s+|consistent\s+|clear\s+|predefined\s+|daily\s+)?(?:[a-z0-9&/-]+\s+){0,3}(?:support|resistance|levels?)\b",
    r"\b(?:can't|cannot|unable)\s+(?:to\s+)?(?:find|get)\s+(?:reliable\s+|accurate\s+|consistent\s+|clear\s+|predefined\s+|daily\s+)?(?:[a-z0-9&/-]+\s+){0,3}(?:support|resistance|levels?)\b",
    r"\b(?:need|looking\s+for|searching\s+for|trying\s+to\s+find)\s+(?:reliable\s+|accurate\s+|consistent\s+|clear\s+|predefined\s+|daily\s+)?(?:[a-z0-9&/-]+\s+){0,3}(?:support|resistance|levels?)\b",
    r"\b(?:support|resistance|levels?)\b\s+(?:are\s+)?(?:hard\s+to\s+find|difficult\s+to\s+find|unreliable|inconsistent|unclear)\b",
]
TRADING_ACTION = [r"\b(?:enter|entry|buy|sell|long|short|target|stop[- ]?loss|position|trade|trading)\b"]
SHORT_TERM = [r"\b(?:today|tomorrow|intraday|day trade|next session|next trading day|opening|market open)\b"]
DIRECT_REQUEST = [r"\?", r"\b(?:can someone|anyone know|please|help me|how do i|where can i|what should i|need|looking for|want|give me|share|show me|tell me)\b"]
GENERIC_MARKERS = [r"\bdaily discussion\b", r"\brisk[- ]?reward\b", r"\bdo you actually follow\b", r"\bcurious:?.{0,80}\b(?:traders|trading)\b", r"\bdaily thread\b", r"\bweekly discussion\b", r"\bmegathread\b", r"\btechnical analysis (?:guide|intro|introduction)\b", r"\bwhat is technical analysis\b", r"\bmarket news\b", r"\bfor educational purposes\b"]
AUTOMATED_MARKERS = [r"\bautomoderator\b", r"\bmod(?:erator)?\b", r"\bthis is the daily discussion\b", r"\bposted automatically\b", r"\bweekly thread\b"]
SPAM_RULES = [r"\bgiveaway\b", r"\bpromo code\b", r"\bairdrop\b", r"\bfree money\b", r"\bcasino\b", r"\bbetting\b", r"\bsubscribe\s+to\s+my\s+channel\b", r"\baffiliate\b"]
COMPETITOR_RULES = [
    r"\bsource\s+(?:for|of)\s+(?:the\s+)?levels?\s*[:=-]\s*[^\n]{2,80}",
    r"\b(?:using|use|from)\s+(?:gammawalls|tradingview|investing\.com|zerodha|upstox|sensibull|opstra)\b",
    r"\b(?:my|our)\s+(?:levels|support|resistance)\s+(?:come|comes|are)\s+from\b",
]
EXISTING_LEVELS = [
    r"\bsource\s*[:=-]\s*(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}\b",
    r"\bsource\s+(?:for|of)\s+(?:the\s+)?levels?\b",
    r"\b(?:my|our|these)\s+levels?\b",
]
RECAP_MARKERS = [r"\bhere(?:'s| is) (?:my|the) levels?\b", r"\blevels? (?:for|at)\s+\d", r"\bmy trade recap\b", r"\btrade recap\b", r"\bmarket recap\b"]


def clean(x):
    if pd.isna(x):
        return ""
    text = str(x)
    # Reddit feeds can contain HTML markup and escaped attributes. Strip tags
    # before evidence extraction so reviewers see human-readable sentences.
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def found_any(text, patterns):
    return any(re.search(p, text, re.I | re.S) for p in patterns)


def first_match_sentence(text, patterns):
    # Evidence must come from one sentence; never combine unrelated parts of a post.
    parts = re.split(r"(?<=[.!?])\s+|\n+", clean(text))
    for sentence in parts:
        s = re.sub(r"\s+", " ", sentence).strip(" -•")
        if s and found_any(s, patterns):
            return s[:280]
    return ""

def evidence_strength(evidence_type, explicit, unmet_need, competitor, existing_levels):
    if evidence_type == "Direct request":
        return "Strong"
    if evidence_type == "Problem-aware":
        return "Moderate"
    if evidence_type == "Existing solution":
        return "Moderate" if competitor else "Weak"
    return "Weak"


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
    generic = found_any(text, GENERIC_MARKERS)
    automated = found_any(text, AUTOMATED_MARKERS)
    spam = found_any(text, SPAM_RULES)
    competitor = found_any(text, COMPETITOR_RULES)
    existing_levels = found_any(text, EXISTING_LEVELS)
    direct = found_any(text, DIRECT_REQUEST)
    trading_action = found_any(text, TRADING_ACTION)
    short_term = found_any(text, SHORT_TERM)
    recap = found_any(text, RECAP_MARKERS)

    # Search sentence-by-sentence so an unrelated phrase later in a long post cannot
    # turn a context mention into a lead. Prefer direct demand over problem evidence.
    explicit_sentence = first_match_sentence(text, DIRECT_LEVEL_REQUEST)
    problem_sentence = first_match_sentence(text, PROBLEM_AWARE)
    explicit = bool(explicit_sentence)
    unmet_need = bool(problem_sentence)

    # Recall-friendly question patterns: these capture natural public requests such
    # as “does anyone have good NIFTY levels?” without matching “where price faces
    # resistance” inside an unrelated educational post.
    if not explicit:
        q_patterns = [
            r"\b(?:does\s+anyone|can\s+anyone|anyone)\b.{0,45}\b(?:support|resistance|levels?)\b",
            r"\b(?:good|reliable|accurate|best)\s+(?:source|way)\b.{0,45}\b(?:support|resistance|levels?)\b",
            r"\b(?:support|resistance|levels?)\b.{0,30}\b(?:today|tomorrow|next\s+session)\b.{0,10}\?",
        ]
        q_sentence = first_match_sentence(text, q_patterns)
        if q_sentence:
            explicit_sentence = q_sentence
            explicit = True

    # Negative intent phrases override accidental regex matches.
    if found_any(text, [r"\bcurious how others\b", r"\banyone else seeing\b", r"\bmy plan\b"]):
        explicit = False
        explicit_sentence = ""

    if generic or automated or spam:
        # Generic/automated material can only qualify if it contains a clean direct
        # request; otherwise it is context, not a lead.
        unmet_need = bool(problem_sentence and explicit)
    if competitor and not explicit:
        unmet_need = False
    if existing_levels and not explicit:
        unmet_need = False

    if explicit:
        evidence_type = "Direct request"
        evidence_sentence = explicit_sentence
    elif unmet_need:
        evidence_type = "Problem-aware"
        evidence_sentence = problem_sentence
    elif competitor or existing_levels:
        evidence_type = "Existing solution"
        evidence_sentence = problem_sentence or first_match_sentence(text, EXISTING_LEVELS)
    elif generic or automated:
        evidence_type = "Generic/educational" if generic else "Automated"
        evidence_sentence = ""
    elif spam:
        evidence_type = "Spam"
        evidence_sentence = ""
    else:
        evidence_type = "Context-only"
        evidence_sentence = ""

    strength = evidence_strength(evidence_type, explicit, unmet_need, competitor, existing_levels)

    # Context-only is explicitly not a Daily Levels lead. This is the main recall/
    # precision correction: mentions of levels inside strategy, risk or recap posts
    # do not create a buying signal.
    true_need = explicit or unmet_need
    if evidence_type == "Context-only":
        true_need = False
    if evidence_type in {"Generic/educational", "Automated", "Spam"}:
        true_need = explicit and not automated and not spam
    if evidence_type == "Existing solution" and not explicit:
        true_need = False

    if true_need:
        problem = "Needs predefined support/resistance levels"
        solution = "Daily Levels can provide predefined daily support and resistance levels from the opening price."
    else:
        problem = "No clear Daily Levels problem detected"
        solution = "No direct Daily Levels solution match until a specific unmet levels need is expressed."

    # Relevance is evidence-led, not activity-led.
    relevance = 0
    if explicit: relevance += 75
    elif unmet_need: relevance += 60
    elif evidence_type == "Existing solution": relevance += 20
    elif evidence_type == "Context-only": relevance += 5
    if market_hits and true_need: relevance += 20
    if short_term and true_need: relevance += 5
    if generic or automated: relevance -= 35
    if spam: relevance -= 50
    if competitor and not explicit: relevance -= 20
    if recap and not explicit: relevance -= 20
    relevance = max(0, min(100, relevance))

    buying = 0
    if explicit: buying += 70
    elif unmet_need: buying += 45
    if direct and true_need and not (generic or automated): buying += 10
    if short_term and true_need: buying += 10
    if market_hits and true_need: buying += 10
    if competitor: buying -= 35
    if existing_levels and not explicit: buying -= 30
    if generic: buying -= 45
    if automated: buying -= 50
    if spam: buying -= 60
    if recap and not explicit: buying -= 35
    buying = max(0, min(100, buying))

    fit = 0
    if explicit: fit += 70
    elif unmet_need: fit += 60
    elif evidence_type == "Existing solution": fit += 20
    if market_hits and true_need: fit += 20
    if short_term and true_need: fit += 5
    if competitor: fit -= 20
    if existing_levels and not explicit: fit -= 20
    if generic or automated: fit -= 40
    if spam: fit -= 60
    if not true_need: fit = min(fit, 30)
    fit = max(0, min(100, fit))

    sales_ready = bool(
        evidence_type == "Direct request" and true_need and explicit and
        buying >= 70 and fit >= 75 and not competitor and not existing_levels and
        not generic and not automated and not spam
    )

    priority_score = round(0.40 * buying + 0.30 * relevance + 0.30 * fit)
    if sales_ready:
        priority_score = max(priority_score, 90)
    elif evidence_type == "Problem-aware":
        priority_score = min(priority_score, 89)
    else:
        priority_score = min(priority_score, 59 if evidence_type in {"Context-only", "Existing solution", "Generic/educational"} else 24 if evidence_type in {"Automated", "Spam"} else 74)
    if not true_need:
        priority_score = min(priority_score, 39 if evidence_type == "Existing solution" else 24 if evidence_type in {"Automated", "Spam"} else 39)
    if competitor and not sales_ready:
        priority_score = min(priority_score, 59)
    if existing_levels and not explicit:
        priority_score = min(priority_score, 39)

    if sales_ready:
        category = "HOT"
    elif evidence_type == "Problem-aware" and true_need and buying >= 45 and fit >= 60:
        category = "WARM"
    elif evidence_type == "Direct request" and true_need:
        category = "WARM"
    elif evidence_type == "Existing solution" and explicit:
        category = "POSSIBLE"
    else:
        category = "LOW"

    if sales_ready:
        action = "Review manually"
    elif evidence_type == "Problem-aware" and buying >= 45:
        action = "Reply with educational information"
    elif evidence_type == "Direct request":
        action = "Review manually"
    elif evidence_type in {"Context-only", "Existing solution"} and relevance >= 20:
        action = "Create relevant content"
    else:
        action = "Do not contact"

    reasons = []
    if explicit: reasons.append("Direct request for levels")
    elif unmet_need: reasons.append("Problem-aware levels need")
    elif evidence_type == "Context-only": reasons.append("Levels are context, not an expressed need")
    if market_hits and true_need: reasons.append("Supported market detected")
    if short_term and true_need: reasons.append("Short-term context")
    if competitor: reasons.append("Alternative level source detected")
    flags = []
    if evidence_type == "Context-only": flags.append("Context-only mention; no unmet Daily Levels need")
    if generic: flags.append("Generic discussion/educational content")
    if automated: flags.append("Automated/moderator content")
    if recap and not explicit: flags.append("Trade/market recap without explicit request")
    if competitor: flags.append("Existing alternative/competitor source")
    elif existing_levels and not explicit: flags.append("Already has or cites existing levels")
    if spam: flags.append("Promotional/spam indicators")

    signal_type = "Automated/moderator" if automated else ("Generic discussion" if generic else "User-intent signal")
    confidence = 0.45 + (0.15 if market_hits else 0) + (0.15 if true_need else 0) + (0.15 if explicit else 0)
    if evidence_type == "Context-only": confidence -= 0.10
    if generic or automated or recap: confidence -= 0.15
    if competitor: confidence += 0.05
    confidence = max(0.25, min(0.95, confidence))

    matched = []
    if explicit: matched.append("direct levels request")
    elif unmet_need: matched.append("problem-aware levels need")
    if trading_action: matched.append("trade/action")
    if short_term: matched.append("short-term")
    if direct: matched.append("question/request")
    if competitor: matched.append("alternative source")

    lead_reason = (
        "Direct unmet Daily Levels request with strong product fit; sales-ready for human review." if sales_ready else
        "A concrete problem finding/relying on support/resistance levels is expressed, but the signal is not sales-ready." if evidence_type == "Problem-aware" else
        "The post mentions trading/levels without expressing an unmet Daily Levels need." if evidence_type == "Context-only" else
        "The trader appears to already use or cite another levels source." if evidence_type == "Existing solution" else
        "Generic, educational, automated, or promotional content; not a direct lead." if evidence_type in {"Generic/educational", "Automated", "Spam"} else
        "No concrete Daily Levels need detected."
    )
    if sales_ready:
        content_angle = "Daily support/resistance from the opening price"
    elif evidence_type == "Problem-aware":
        content_angle = "How to get reliable daily support/resistance levels"
    elif evidence_type == "Existing solution":
        content_angle = "Compare level sources and explain a simple opening-price methodology"
    else:
        content_angle = "Educational content about identifying reliable daily levels"
    buyer_stage = "Ready to review" if sales_ready else ("Problem-aware" if evidence_type == "Problem-aware" else ("Exploring" if evidence_type == "Direct request" else "Not a lead"))
    explanation = " | ".join(reasons) if reasons else "No strong Daily Levels need detected"
    if flags: explanation += " | Qualification flags: " + ", ".join(flags)

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
        "unmet_need": bool(unmet_need), "evidence_type": evidence_type,
        "evidence_strength": strength, "evidence_sentence": evidence_sentence,
        "qualification_version": QUALIFICATION_VERSION,
    }
