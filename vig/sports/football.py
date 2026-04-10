from typing import List

from vig.sports.base import SportAdapter


class FootballAdapter(SportAdapter):
    sport_key = "soccer_epl"
    display_name = "football"
    markets: List[str] = ["h2h", "totals"]  # btts is a premium market on the free tier
    default_subreddits: List[str] = ["r/soccerbetting", "r/soccer"]
