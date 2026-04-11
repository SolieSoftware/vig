"""
Polymarket API client — no authentication required for read-only access.

Uses the Gamma events endpoint which includes tag-based categories and
aggregated volume. Each event may contain multiple markets (outcomes).
"""
import json
from typing import List, Optional

import httpx
from pydantic import BaseModel

GAMMA_API = "https://gamma-api.polymarket.com"

# Top-level categories we track (excludes Soccer/Football — that's Betfair's job)
TRACKED_TAGS = {"Crypto", "Politics", "AI", "Business", "Finance", "Science", "Elections"}


class PolymarketUnavailable(Exception):
    pass


class PolyMarket(BaseModel):
    title: str
    category: str
    top_outcome: str       # label of leading outcome e.g. "Yes", "Harris", "Over $100k"
    top_prob: float        # 0.0–1.0
    volume_usd: float
    end_date: Optional[str] = None


def _parse_event(event: dict) -> Optional[PolyMarket]:
    """Extract the most informative signal from an event."""
    tags = [t.get("label", "") for t in (event.get("tags") or [])]
    category = next((t for t in tags if t in TRACKED_TAGS), tags[0] if tags else "Other")

    volume = float(event.get("volume") or 0)
    title = event.get("title", "").strip()
    if not title:
        return None

    markets = event.get("markets") or []

    # Binary event: single market with Yes/No
    if len(markets) == 1:
        m = markets[0]
        try:
            prices = json.loads(m.get("outcomePrices", "[]"))
            outcomes = json.loads(m.get("outcomes", "[]"))
            if prices and outcomes:
                yes_prob = float(prices[0])
                return PolyMarket(
                    title=title,
                    category=category,
                    top_outcome="Yes",
                    top_prob=yes_prob,
                    volume_usd=volume,
                    end_date=event.get("endDate"),
                )
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    # Multi-outcome event: each market = one outcome (e.g. candidate)
    # Find the leading outcome by highest probability
    best = None
    best_prob = -1.0
    for m in markets:
        try:
            prices = json.loads(m.get("outcomePrices", "[]"))
            prob = float(prices[0]) if prices else 0.0
            label = m.get("groupItemTitle") or m.get("question", "")
            if prob > best_prob and label:
                best_prob = prob
                best = (label, prob)
        except (json.JSONDecodeError, ValueError):
            continue

    if best:
        return PolyMarket(
            title=title,
            category=category,
            top_outcome=best[0],
            top_prob=best[1],
            volume_usd=volume,
            end_date=event.get("endDate"),
        )

    return None


def get_top_markets(limit: int = 12) -> List[PolyMarket]:
    """Fetch top active Polymarket events by volume across tracked categories."""
    try:
        resp = httpx.get(
            f"{GAMMA_API}/events",
            params={
                "active": "true",
                "closed": "false",
                "limit": "200",
                "order": "volume",
                "ascending": "false",
            },
            timeout=10,
        )
    except httpx.RequestError as e:
        raise PolymarketUnavailable(f"Network error: {e}") from e

    if resp.status_code != 200:
        raise PolymarketUnavailable(f"Polymarket API error: {resp.status_code}")

    results = []
    for event in resp.json():
        tags = [t.get("label", "") for t in (event.get("tags") or [])]
        if not any(t in TRACKED_TAGS for t in tags):
            continue
        parsed = _parse_event(event)
        if parsed:
            results.append(parsed)

    results.sort(key=lambda x: x.volume_usd, reverse=True)
    return results[:limit]
