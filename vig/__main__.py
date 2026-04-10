from vig.agents.odds_agent import OddsAPIUnavailable, get_opportunities
from vig.agents.tipster_agent import TipsterAgent
from vig.sports.football import FootballAdapter
from vig.ui.dashboard import render

sport = FootballAdapter()
tipster = TipsterAgent(sport)

try:
    bets = get_opportunities(sport)
except OddsAPIUnavailable as e:
    from rich.console import Console
    Console().print(f"[bold red]Odds API unavailable:[/bold red] {e}")
    raise SystemExit(1)

# General intel from tip subreddits
general_intel = tipster.general()

# Match-specific intel for the top-ranked fixture
match_intel = []
if bets:
    top = bets[0]
    # Parse "Home v Away" back into team names
    parts = top.match.split(" v ", 1)
    if len(parts) == 2:
        match_intel = tipster.match(parts[0].strip(), parts[1].strip())

render(sport, bets, general_intel, match_intel, top_match=bets[0].match if bets else None)
