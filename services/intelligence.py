import re
import hashlib
import html
import pandas as pd

VERSION = '4.0.0'

MARKETS = {
    'India (NIFTY)': [r'\bnifty(?:\s*50)?\b'],
    'India (Bank Nifty)': [r'\bbank\s*nifty\b', r'\bbanknifty\b'],
    'India (Sensex)': [r'\bsensex\b'],
    'India (Options)': [r'\bindian\s+options?\b', r'\bnifty\s+(?:options?|calls?|puts?)\b', r'\bbank\s*nifty\s+(?:options?|calls?|puts?)\b'],
    'Crypto (BTC)': [r'\bbtc\b', r'\bbitcoin\b'],
    'Crypto (ETH)': [r'\bethereum\b', r'\beth\b(?=.*(?:crypto|ethereum|usdt|usd|price|trade|trading))'],
    'Crypto': [r'\bcrypto\b', r'\bcryptocurrency\b'],
    'US (S&P 500)': [r'\bs&p\s*500\b', r'\bspx\b'],
    'US (Nasdaq)': [r'\bnasdaq\b', r'\bqqq\b'],
    'US (Dow)': [r'\bdow\b(?=.*(?:jones|index|futures|trade|trading))'],
    'US Stocks': [r'\bus\s+stocks?\b', r'\bnyse\b'],
    'Forex (EUR/USD)': [r'\beur\s*/?\s*usd\b', r'\beurusd\b'],
    'Forex (GBP/USD)': [r'\bgbp\s*/?\s*usd\b', r'\bgbpusd\b'],
    'Gold / XAUUSD': [r'\bxau\s*/?\s*usd\b', r'\bxauusd\b', r'\bgold\b'],
    'Forex': [r'\bforex\b'],
}
SUPPORTED_MARKETS = set(MARKETS)

SPAM = [r'\bgiveaway\b', r'\bpromo code\b', r'\bairdrop\b', r'\bfree money\b', r'\bcasino\b', r'\bbetting\b', r'\baffiliate\b']
AUTOMATED = [r'\bautomoderator\b', r'\bmoderator\b', r'\bthis is the daily discussion\b', r'\bposted automatically\b', r'\bweekly thread\b']
GENERIC = [r'\bdaily discussion\b', r'\bmarket news\b', r'\bfor educational purposes\b', r'\bwhat is technical analysis\b', r'\brisk[- ]?reward\b']

# Direct trader requests for levels. These are intentionally simple: we only need
# enough evidence to find a trader, not to predict whether they will purchase.
DIRECT_LEVEL_REQUEST = [
    r'\b(?:where\s+(?:can|do)\s+i\s+(?:get|find)|where\s+(?:are|can\s+i\s+get)|what\s+(?:are|is)|what\'s|whats|need|give\s+me|share|show\s+me|tell\s+me|can\s+someone|anyone\s+(?:know|have)|does\s+anyone\s+(?:know|have)|help\s+me|how\s+do\s+i\s+(?:get|find)|best\s+(?:source|way))\b.{0,80}\b(?:support|resistance|levels?)\b',
    r'\b(?:support|resistance|levels?)\b.{0,45}\b(?:today|tomorrow|next\s+session|next\s+trading\s+day)\b',
    r'\b(?:looking\s+for|want|trying\s+to\s+get|trying\s+to\s+find)\b.{0,80}\b(?:support|resistance|levels?)\b',
    r'\b(?:does\s+anyone|can\s+anyone|anyone)\b.{0,55}\b(?:support|resistance|levels?)\b',
    r'\b(?:good|reliable|accurate|best)\s+(?:source|way)\b.{0,55}\b(?:support|resistance|levels?)\b',
]
LEVEL_WORDS = [r'\bsupport\b', r'\bresistance\b', r'\blevels?\b']
TRADING_WORDS = [r'\btrade\b', r'\btrader\b', r'\btrading\b', r'\bintraday\b', r'\bentry\b', r'\bposition\b', r'\bbuy\b', r'\bsell\b', r'\blong\b', r'\bshort\b', r'\bstop[- ]?loss\b', r'\btarget\b', r'\boption\b', r'\bfutures?\b']


def clean(x):
    if pd.isna(x): return ''
    text = html.unescape(str(x))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return re.sub(r'\s+', ' ', text).strip()


def found(text, patterns):
    return any(re.search(p, text, re.I | re.S) for p in patterns)


def sentence(text, patterns):
    for s in re.split(r'(?<=[.!?])\s+|\n+', clean(text)):
        s = re.sub(r'\s+', ' ', s).strip(' -•')
        if s and found(s, patterns): return s[:300]
    return ''


def signal_id(platform, url, text):
    key = f'{clean(platform).lower()}|{clean(url).lower()}|{clean(text).lower()}'
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _markets(text):
    return [m for m,pats in MARKETS.items() if found(text,pats)]


def analyze(text):
    text = clean(text)
    markets = _markets(text)
    spam = found(text, SPAM)
    automated = found(text, AUTOMATED)
    generic = found(text, GENERIC)
    trading = found(text, TRADING_WORDS)
    level = found(text, LEVEL_WORDS)
    direct_sentence = sentence(text, DIRECT_LEVEL_REQUEST)
    direct = bool(direct_sentence)

    # A clear public trader request gets HIGH. An active trader discussing levels
    # gets MEDIUM. Everything else is LOW. No purchase prediction is attempted.
    if spam or automated:
        level_name, score = 'LOW', 10
        evidence_type = 'Spam/automated'
        evidence_sentence = ''
        reason = 'Automated or promotional content.'
    elif direct and markets:
        level_name, score = 'HIGH', 90
        evidence_type = 'Direct level interest'
        evidence_sentence = direct_sentence
        reason = 'Trader is publicly asking for support/resistance levels.'
    elif trading and level and markets:
        level_name, score = 'MEDIUM', 65
        evidence_type = 'Trader + levels context'
        evidence_sentence = sentence(text, TRADING_WORDS) or sentence(text, LEVEL_WORDS)
        reason = 'Active trading context with support/resistance or levels.'
    elif markets and trading:
        level_name, score = 'MEDIUM', 55
        evidence_type = 'Trader signal'
        evidence_sentence = sentence(text, TRADING_WORDS)
        reason = 'Public post appears to be from an active trader in a supported market.'
    else:
        level_name, score = 'LOW', 15
        evidence_type = 'General market context' if markets else 'Irrelevant'
        evidence_sentence = ''
        reason = 'Not enough evidence to identify a relevant trader.'

    market = markets[0] if markets else 'Other / Unknown'
    action = 'Share Daily Levels landing page' if level_name in {'HIGH','MEDIUM'} else 'Do not contact'
    return {
        'market': market,
        'markets_found': ', '.join(markets),
        'interest_level': level_name,
        'interest_score': score,
        'evidence_type': evidence_type,
        'evidence_sentence': evidence_sentence,
        'reason': reason,
        'recommended_action': action,
        'landing_page': 'https://dailylevels-app.vercel.app/',
        'is_trader': bool(markets and (trading or direct)),
        'qualification_version': VERSION,
        # Compatibility fields for the existing SQLite schema.
        'intent_score': score,
        'customer_fit_score': score if market != 'Other / Unknown' else 0,
        'category': level_name,
        'problem': 'Wants/uses market levels' if level_name in {'HIGH','MEDIUM'} else '',
        'daily_levels_solution': 'Opening Price → Daily Support & Resistance Levels',
        'matched_terms': ', '.join(markets),
        'signal_explanation': reason,
        'spam_probability': 1.0 if spam else 0.0,
        'confidence': 0.9 if direct else (0.7 if level_name == 'MEDIUM' else 0.4),
        'signal_type': 'Public trader signal',
        'explicit_need': direct,
        'quality_flags': evidence_type,
        'relevance_score': score,
        'buying_intent_score': score,
        'product_fit_score': score if market != 'Other / Unknown' else 0,
        'priority_score': score,
        'competition_detected': 0,
        'sales_ready': 0,
        'buyer_stage': 'Trader identified' if level_name in {'HIGH','MEDIUM'} else 'Not a trader',
        'lead_reason': reason,
        'content_angle': 'Daily Levels landing page',
        'unmet_need': direct,
        'evidence_strength': 'Strong' if direct else ('Moderate' if level_name == 'MEDIUM' else 'Weak'),
    }
