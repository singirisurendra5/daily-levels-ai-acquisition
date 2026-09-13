import re
import pandas as pd
from difflib import SequenceMatcher
from .intelligence import near_duplicate_key


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def deduplicate_signals(df, similarity_threshold=0.92):
    if df.empty:
        return df.copy(), 0
    work = df.copy()
    work["duplicate_group"] = ""
    work["is_duplicate"] = False
    seen = []
    duplicate_count = 0
    for idx, row in work.iterrows():
        text = normalize_text(row.get("text", ""))
        url = normalize_text(row.get("url", ""))
        exact_key = near_duplicate_key(text)
        matched = None
        for prev_idx, prev_text, prev_url, prev_key in seen:
            if url and prev_url and url == prev_url:
                matched = prev_idx
                break
            if exact_key == prev_key:
                matched = prev_idx
                break
            if text and prev_text and SequenceMatcher(None, text, prev_text).ratio() >= similarity_threshold:
                matched = prev_idx
                break
        if matched is not None:
            work.at[idx, "is_duplicate"] = True
            work.at[idx, "duplicate_group"] = str(matched)
            duplicate_count += 1
        else:
            seen.append((idx, text, url, exact_key))
            work.at[idx, "duplicate_group"] = str(idx)
    return work, duplicate_count
