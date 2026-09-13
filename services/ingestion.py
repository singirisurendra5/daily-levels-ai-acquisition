from datetime import datetime, timezone
from urllib.parse import quote_plus
import requests
import feedparser
import pandas as pd

DEFAULT_HEADERS = {
    "User-Agent": "DailyLevelsAcquisition/3.1 (+public-signal-research; contact=project-owner)"
}


def fetch_rss(url, platform="RSS", timeout=15):
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    rows = []
    for entry in feed.entries:
        rows.append({
            "platform": platform,
            "url": entry.get("link", ""),
            "text": entry.get("title", "") + (" — " + entry.get("summary", "") if entry.get("summary") else ""),
            "date": entry.get("published", entry.get("updated", "")),
            "source": url,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows)


def fetch_reddit_rss(subreddit, query="", sort="new", limit=25):
    subreddit = subreddit.strip().strip("/")
    base = f"https://www.reddit.com/r/{subreddit}/search.rss"
    params = {"q": query, "restrict_sr": "on", "sort": sort, "limit": min(limit, 100)} if query else {"limit": min(limit, 100), "sort": sort}
    response = requests.get(base, params=params, headers=DEFAULT_HEADERS, timeout=15)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    rows = []
    for entry in feed.entries:
        rows.append({
            "platform": "Reddit",
            "url": entry.get("link", ""),
            "text": entry.get("title", "") + (" — " + entry.get("summary", "") if entry.get("summary") else ""),
            "date": entry.get("published", entry.get("updated", "")),
            "source": f"reddit:r/{subreddit}",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows)


def fetch_youtube_channel(channel_id, limit=15):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={quote_plus(channel_id.strip())}"
    df = fetch_rss(url, platform="YouTube")
    return df.head(limit)


def combine_frames(frames):
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["platform", "url", "text", "date", "source", "ingested_at"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["platform", "url", "text"])
