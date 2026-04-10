import time
from typing import List

import httpx
from pydantic import BaseModel

HEADERS = {"User-Agent": "vig/0.1 (personal research tool)"}
REQUEST_TIMEOUT = 10


class RedditUnavailable(Exception):
    pass


class IntelItem(BaseModel):
    source: str        # e.g. "r/soccerbetting"
    text: str          # post title or snippet
    url: str
    scraped_at: float


def _fetch_subreddit(subreddit: str, limit: int = 25, timeframe: str = "day") -> List[IntelItem]:
    """Fetch top posts from a subreddit via the public JSON API (no auth needed)."""
    clean = subreddit.lstrip("r/")
    url = f"https://www.reddit.com/r/{clean}/top.json"
    params = {"limit": limit, "t": timeframe}

    try:
        resp = httpx.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except httpx.RequestError as e:
        raise RedditUnavailable(f"Network error fetching {subreddit}: {e}") from e

    if resp.status_code == 403:
        raise RedditUnavailable(f"{subreddit} is private or quarantined.")
    if resp.status_code == 404:
        raise RedditUnavailable(f"{subreddit} not found.")
    if resp.status_code != 200:
        raise RedditUnavailable(f"Reddit API error {resp.status_code} for {subreddit}.")

    try:
        posts = resp.json()["data"]["children"]
    except (KeyError, ValueError) as e:
        raise RedditUnavailable(f"Unexpected Reddit response shape: {e}") from e

    now = time.time()
    items = []
    for post in posts:
        d = post.get("data", {})
        title = d.get("title", "").strip()
        permalink = d.get("permalink", "")
        if not title or not permalink:
            continue
        items.append(IntelItem(
            source=f"r/{clean}",
            text=title,
            url=f"https://www.reddit.com{permalink}",
            scraped_at=now,
        ))

    return items


def get_general_tips(subreddits: List[str]) -> List[IntelItem]:
    """Scrape daily tip threads from a list of subreddits."""
    items: List[IntelItem] = []
    for sub in subreddits:
        try:
            items.extend(_fetch_subreddit(sub))
        except RedditUnavailable:
            # Skip unavailable subreddits gracefully
            pass
    return items


def get_match_intel(home_team: str, away_team: str) -> List[IntelItem]:
    """Search for pre-match discussion relevant to a specific fixture."""
    # Search r/soccer for fixture-specific posts
    query = f"{home_team} {away_team}"
    url = "https://www.reddit.com/r/soccer/search.json"
    params = {"q": query, "sort": "new", "limit": 10, "restrict_sr": "1", "t": "week"}

    items: List[IntelItem] = []
    try:
        resp = httpx.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            posts = resp.json()["data"]["children"]
            now = time.time()
            for post in posts:
                d = post.get("data", {})
                title = d.get("title", "").strip()
                permalink = d.get("permalink", "")
                if title and permalink:
                    items.append(IntelItem(
                        source="r/soccer",
                        text=title,
                        url=f"https://www.reddit.com{permalink}",
                        scraped_at=now,
                    ))
    except (httpx.RequestError, KeyError, ValueError):
        pass

    return items
