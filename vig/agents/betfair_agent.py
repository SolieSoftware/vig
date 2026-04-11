"""
BetfairAgent — fetches EPL exchange prices and returns BetOpportunity objects.

Exchange prices are set by other punters (not bookmakers) so they represent
a sharper, more efficient market. The value signal here measures deviation
from the exchange's own implied probability — it'll be smaller than bookmaker
signals, but exchange prices can be directly compared against bookmaker odds
to spot where bookmakers are offering better value than the exchange.
"""
import time
from typing import List

from vig.agents.odds_agent import BetOpportunity, _confidence
from vig.sources.betfair import BetfairMarket, BetfairUnavailable, get_epl_markets

MARKET_LABEL = {
    "MATCH_ODDS": "Match Result",
    "OVER_UNDER_25": "O/U 2.5",
}


def _parse_market(market: BetfairMarket, now: float) -> List[BetOpportunity]:
    runners = [r for r in market.runners if r.best_back_price and r.best_back_price > 1.01]
    if len(runners) < 2:
        return []

    implied = {r.name: 1 / r.best_back_price for r in runners}
    total_implied = sum(implied.values())
    no_vig = {name: imp / total_implied for name, imp in implied.items()}

    label = MARKET_LABEL.get(market.market_type, market.market_type)

    bets = []
    for runner in runners:
        imp = implied[runner.name]
        nv = no_vig[runner.name]
        signal = nv - imp

        bets.append(BetOpportunity(
            match=market.event_name,
            market=label,
            pick=runner.name,
            decimal_odds=runner.best_back_price,
            implied_prob=round(imp, 4),
            no_vig_prob=round(nv, 4),
            value_signal_pct=round(signal, 4),
            confidence=_confidence(signal),
            timestamp=now,
            source="Betfair Exchange",
        ))

    return bets


def get_betfair_opportunities() -> List[BetOpportunity]:
    """Fetch EPL exchange prices as BetOpportunity objects, sorted by value signal."""
    markets = get_epl_markets()
    now = time.time()
    bets: List[BetOpportunity] = []
    for market in markets:
        bets.extend(_parse_market(market, now))
    return sorted(bets, key=lambda b: b.value_signal_pct, reverse=True)
