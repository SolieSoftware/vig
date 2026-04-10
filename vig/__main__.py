from rich.console import Console

from vig.agents.odds_agent import OddsAPIUnavailable, get_opportunities
from vig.agents.scraper_agent import OddscheckerUnavailable, get_oddschecker_tips
from vig.agents.synthesis_agent import synthesize
from vig.agents.tipster_agent import TipsterAgent
from vig.sports.football import FootballAdapter
from vig.ui.dashboard import render

console = Console()
sport = FootballAdapter()
tipster = TipsterAgent(sport)

# --- Data collection ---

try:
    bets = get_opportunities(sport)
except OddsAPIUnavailable as e:
    console.print(f"[bold red]Odds API unavailable:[/bold red] {e}")
    raise SystemExit(1)

general_intel = tipster.general()

match_intel = []
if bets:
    parts = bets[0].match.split(" v ", 1)
    if len(parts) == 2:
        match_intel = tipster.match(parts[0].strip(), parts[1].strip())

community_tips = []
try:
    community_tips = get_oddschecker_tips()
except OddscheckerUnavailable as e:
    console.print(f"[dim]Community tips unavailable: {e}[/dim]")

# --- Synthesis ---

synthesized = synthesize(bets, community_tips)

# --- Render ---

render(
    sport=sport,
    synthesized=synthesized,
    general_intel=general_intel,
    match_intel=match_intel,
    community_tips=community_tips,
    top_match=bets[0].match if bets else None,
)
