from vig.agents.odds_agent import OddsAPIUnavailable, get_opportunities
from vig.sports.football import FootballAdapter
from vig.ui.dashboard import render

sport = FootballAdapter()

try:
    bets = get_opportunities(sport)
    render(sport, bets)
except OddsAPIUnavailable as e:
    from rich.console import Console
    Console().print(f"[bold red]Odds API unavailable:[/bold red] {e}")
