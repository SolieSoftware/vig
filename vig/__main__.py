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

# Intel is best-effort — never blocks the main output
intel = tipster.general()

render(sport, bets, intel)
