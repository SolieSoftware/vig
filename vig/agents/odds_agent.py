import json
import time
from pathlib import Path
from typing import List, Literal, Optional

import httpx
from pydantic import BaseModel, computed_field

from vig import config
from vig.sports.base import SportAdapter


class OddsAPIUnavailable(Exception):
    pass


class BetOpportunity(BaseModel):
    match: str
    market: str
    pick: str
    decimal_odds: float
    implied_prob: float
    no_vig_prob: float
    value_signal_pct: float
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    timestamp: float
    source: str = "The Odds API"

    @computed_field
    @property
    def is_stale(self) -> bool:
        return (time.time() - self.timestamp) > config.STALE_THRESHOLD_SECONDS


def _confidence(value_signal_pct: float) -> Literal["HIGH", "MEDIUM", "LOW"]:
    if value_signal_pct > config.CONFIDENCE_THRESHOLDS["HIGH"]:
        return "HIGH"
    if value_signal_pct > config.CONFIDENCE_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _cache_path(sport_key: str) -> Path:
    config.CACHE_DIR.mkdir(exist_ok=True)
    return config.CACHE_DIR / f"{sport_key}.json"


def _load_cache(sport_key: str) -> Optional[List[dict]]:
    path = _cache_path(sport_key)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    age = time.time() - data.get("fetched_at", 0)
    if age > config.CACHE_TTL_SECONDS:
        return None
    return data.get("events", [])


def _save_cache(sport_key: str, events: List[dict]) -> None:
    path = _cache_path(sport_key)
    path.write_text(json.dumps({"fetched_at": time.time(), "events": events}))


def _fetch_odds(sport_key: str, markets: List[str]) -> List[dict]:
    cached = _load_cache(sport_key)
    if cached is not None:
        return cached

    markets_param = ",".join(markets)
    url = f"{config.ODDS_API_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey": config.ODDS_API_KEY,
        "regions": config.ODDS_API_REGIONS,
        "markets": markets_param,
        "oddsFormat": config.ODDS_API_ODDS_FORMAT,
    }

    try:
        resp = httpx.get(url, params=params, timeout=10)
    except httpx.RequestError as e:
        raise OddsAPIUnavailable(f"Network error: {e}") from e

    if resp.status_code == 429:
        raise OddsAPIUnavailable("Odds API rate limit reached.")
    if resp.status_code >= 500:
        raise OddsAPIUnavailable(f"Odds API server error: {resp.status_code}")
    if resp.status_code != 200:
        raise OddsAPIUnavailable(f"Odds API error: {resp.status_code} {resp.text}")

    events = resp.json()
    _save_cache(sport_key, events)
    return events


def _parse_h2h(event: dict, now: float) -> List[BetOpportunity]:
    home = event.get("home_team", "?")
    away = event.get("away_team", "?")
    match_name = f"{home} v {away}"

    # Collect all bookmakers' prices and no-vig probs
    outcome_odds: dict = {}          # name -> [(bookmaker_title, price)]
    no_vig_by_book: dict = {}        # bookmaker_title -> {name: no_vig_prob}

    for bookmaker in event.get("bookmakers", []):
        bk = bookmaker["title"]
        for market in bookmaker.get("markets", []):
            if market["key"] != "h2h":
                continue
            outcomes = market.get("outcomes", [])
            if not outcomes:
                continue

            implied = {o["name"]: 1 / o["price"] for o in outcomes}
            total_implied = sum(implied.values())
            no_vig_by_book[bk] = {n: v / total_implied for n, v in implied.items()}

            for o in outcomes:
                outcome_odds.setdefault(o["name"], []).append((bk, o["price"]))

    if not outcome_odds or not no_vig_by_book:
        return []

    # Consensus no-vig: average across all bookmakers per outcome
    consensus = {
        name: sum(bk[name] for bk in no_vig_by_book.values() if name in bk)
               / sum(1 for bk in no_vig_by_book.values() if name in bk)
        for name in outcome_odds
    }

    # Best-value bookmaker per pick (highest odds = lowest implied prob)
    bets = []
    for name, offers in outcome_odds.items():
        best_bk, best_odds = max(offers, key=lambda x: x[1])
        imp = 1 / best_odds
        signal = consensus[name] - imp

        bets.append(BetOpportunity(
            match=match_name,
            market="1X2",
            pick=name,
            decimal_odds=best_odds,
            implied_prob=round(imp, 4),
            no_vig_prob=round(consensus[name], 4),
            value_signal_pct=round(signal, 4),
            confidence=_confidence(signal),
            timestamp=now,
            source=best_bk,
        ))

    return bets


def _parse_btts(event: dict, now: float) -> List[BetOpportunity]:
    home = event.get("home_team", "?")
    away = event.get("away_team", "?")
    match_name = f"{home} v {away}"
    bets = []

    for bookmaker in event.get("bookmakers", [])[:1]:
        for market in bookmaker.get("markets", []):
            if market["key"] != "btts":
                continue
            outcomes = market.get("outcomes", [])
            if not outcomes:
                continue

            implied = {o["name"]: 1 / o["price"] for o in outcomes}
            total_implied = sum(implied.values())

            for outcome in outcomes:
                name = outcome["name"]
                odds = outcome["price"]
                imp = implied[name]
                no_vig = imp / total_implied
                signal = no_vig - imp

                bets.append(BetOpportunity(
                    match=match_name,
                    market="BTTS",
                    pick=name,
                    decimal_odds=odds,
                    implied_prob=round(imp, 4),
                    no_vig_prob=round(no_vig, 4),
                    value_signal_pct=round(signal, 4),
                    confidence=_confidence(signal),
                    timestamp=now,
                ))

    return bets


def _parse_totals(event: dict, now: float) -> List[BetOpportunity]:
    home = event.get("home_team", "?")
    away = event.get("away_team", "?")
    match_name = f"{home} v {away}"

    outcome_odds: dict = {}
    no_vig_by_book: dict = {}

    for bookmaker in event.get("bookmakers", []):
        bk = bookmaker["title"]
        for market in bookmaker.get("markets", []):
            if market["key"] != "totals":
                continue
            outcomes = [o for o in market.get("outcomes", []) if o.get("point") == 2.5]
            if not outcomes:
                continue

            implied = {o["name"]: 1 / o["price"] for o in outcomes}
            total_implied = sum(implied.values())
            no_vig_by_book[bk] = {n: v / total_implied for n, v in implied.items()}

            for o in outcomes:
                outcome_odds.setdefault(o["name"], []).append((bk, o["price"]))

    if not outcome_odds or not no_vig_by_book:
        return []

    consensus = {
        name: sum(bk[name] for bk in no_vig_by_book.values() if name in bk)
               / sum(1 for bk in no_vig_by_book.values() if name in bk)
        for name in outcome_odds
    }

    bets = []
    for name, offers in outcome_odds.items():
        best_bk, best_odds = max(offers, key=lambda x: x[1])
        imp = 1 / best_odds
        signal = consensus[name] - imp

        bets.append(BetOpportunity(
            match=match_name,
            market="O/U 2.5",
            pick=name,
            decimal_odds=best_odds,
            implied_prob=round(imp, 4),
            no_vig_prob=round(consensus[name], 4),
            value_signal_pct=round(signal, 4),
            confidence=_confidence(signal),
            timestamp=now,
            source=best_bk,
        ))

    return bets


def get_opportunities(sport: SportAdapter) -> List[BetOpportunity]:
    """Fetch and parse all bet opportunities for a sport, sorted by value signal."""
    events = _fetch_odds(sport.sport_key, sport.markets)
    now = time.time()
    bets: list[BetOpportunity] = []

    for event in events:
        bets.extend(_parse_h2h(event, now))
        bets.extend(_parse_btts(event, now))
        bets.extend(_parse_totals(event, now))

    # Sort descending by value signal
    return sorted(bets, key=lambda b: b.value_signal_pct, reverse=True)
