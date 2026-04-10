from typing import List

from vig.sources.reddit import IntelItem, get_general_tips, get_match_intel
from vig.sports.base import SportAdapter


class TipsterAgent:
    def __init__(self, sport: SportAdapter):
        self.sport = sport

    def general(self) -> List[IntelItem]:
        """Pull today's tip threads from the sport's default subreddits."""
        return get_general_tips(self.sport.default_subreddits)

    def match(self, home_team: str, away_team: str) -> List[IntelItem]:
        """Pull pre-match discussion for a specific fixture."""
        return get_match_intel(home_team, away_team)
