from typing import Dict, List

from vig.sports.base import SportAdapter


# Maps team name (as returned by The Odds API) to their primary subreddit.
# Used by TipsterAgent match mode to find team-specific pre-match discussion.
EPL_TEAM_SUBREDDITS: Dict[str, str] = {
    "Arsenal": "Gunners",
    "Aston Villa": "avfc",
    "Bournemouth": "AFCBournemouth",
    "Brentford": "Brentford",
    "Brighton and Hove Albion": "BrightonHoveAlbion",
    "Chelsea": "chelseafc",
    "Crystal Palace": "crystalpalace",
    "Everton": "Everton",
    "Fulham": "fulhamfc",
    "Ipswich Town": "IpswichTown",
    "Leeds United": "LeedsUnited",
    "Leicester City": "leicestercity",
    "Liverpool": "LiverpoolFC",
    "Manchester City": "MCFC",
    "Manchester United": "reddevils",
    "Newcastle United": "NUFC",
    "Nottingham Forest": "nffc",
    "Southampton": "SaintsFC",
    "Tottenham Hotspur": "coys",
    "West Ham United": "Hammers",
    "Wolverhampton Wanderers": "WWFC",
}


class FootballAdapter(SportAdapter):
    sport_key = "soccer_epl"
    display_name = "football"
    markets: List[str] = ["h2h", "totals"]  # btts is a premium market on the free tier
    default_subreddits: List[str] = ["r/soccerbetting", "r/soccer"]
    team_subreddits: Dict[str, str] = EPL_TEAM_SUBREDDITS
