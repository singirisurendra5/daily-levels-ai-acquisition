from datetime import datetime, timezone
from urllib.parse import quote_plus
import requests
import feedparser
import pandas as pd

DEFAULT_HEADERS = {
    'User-Agent': 'DailyLevelsAcquisition/3.3 (+public-rss-research)'
}


def fetch_rss(url, platform='RSS', timeout=20):
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if getattr(feed, 'bozo', False) and not feed.entries:
        raise ValueError('Feed could not be parsed as RSS/Atom')
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for entry in feed.entries:
        title = str(entry.get('title','')).strip()
        summary = str(entry.get('summary', entry.get('description',''))).strip()
        rows.append({
            'platform': platform,
            'url': entry.get('link',''),
            'text': title + (f' — {summary}' if summary else ''),
            'date': entry.get('published', entry.get('updated', '')),
            'source': url,
            'ingested_at': now,
        })
    return pd.DataFrame(rows)


def fetch_reddit_rss(subreddit, query='', sort='new', limit=25):
    subreddit = subreddit.strip().strip('/')
    base = f'https://www.reddit.com/r/{subreddit}/search.rss'
    params = {'q': query, 'restrict_sr': 'on', 'sort': sort, 'limit': min(int(limit), 100)} if query else {'limit': min(int(limit), 100), 'sort': sort}
    response = requests.get(base, params=params, headers=DEFAULT_HEADERS, timeout=20)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if getattr(feed, 'bozo', False) and not feed.entries:
        raise ValueError('Reddit public RSS feed could not be parsed')
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for entry in feed.entries:
        title = str(entry.get('title','')).strip()
        summary = str(entry.get('summary','')).strip()
        rows.append({'platform':'Reddit','url':entry.get('link',''),'text':title + (f' — {summary}' if summary else ''),
                     'date':entry.get('published',entry.get('updated','')),'source':f'reddit:r/{subreddit}','ingested_at':now})
    return pd.DataFrame(rows)


def fetch_youtube_channel(channel_id, limit=15):
    url = f'https://www.youtube.com/feeds/videos.xml?channel_id={quote_plus(channel_id.strip())}'
    return fetch_rss(url, platform='YouTube').head(int(limit))


def combine_frames(frames):
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=['platform','url','text','date','source','ingested_at'])
    result = pd.concat(frames, ignore_index=True)
    for c in ['platform','url','text']:
        if c not in result: result[c] = ''
        result[c] = result[c].fillna('').astype(str).str.strip()
    return result.drop_duplicates(subset=['platform','url','text']).reset_index(drop=True)
