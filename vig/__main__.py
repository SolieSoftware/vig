import sys
import termios
import tty

from rich.console import Console

from vig.agents.betfair_agent import get_betfair_opportunities
from vig.agents.odds_agent import OddsAPIUnavailable, get_opportunities
from vig.agents.scraper_agent import OddscheckerUnavailable, get_oddschecker_tips
from vig.agents.synthesis_agent import synthesize
from vig.agents.tipster_agent import TipsterAgent
from vig.sources.betfair import BetfairUnavailable
from vig.sports.football import FootballAdapter
from vig.ui.dashboard import render

console = Console()
sport = FootballAdapter()
tipster = TipsterAgent(sport)


def _getkey() -> str:
    """Read a single keypress from stdin without requiring Enter."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _run() -> None:
    """Fetch all data, synthesize, and render one full dashboard update."""
    try:
        bets = get_opportunities(sport)
    except OddsAPIUnavailable as e:
        console.print(f"[bold red]Odds API unavailable:[/bold red] {e}")
        return

    # Merge in Betfair exchange prices
    try:
        betfair_bets = get_betfair_opportunities()
        if betfair_bets:
            console.print(f"[dim]Betfair: {len(betfair_bets)} exchange prices loaded[/dim]")
        bets = sorted(bets + betfair_bets, key=lambda b: b.value_signal_pct, reverse=True)
    except BetfairUnavailable as e:
        console.print(f"[dim]Betfair unavailable: {e}[/dim]")

    general_intel = tipster.general()

    match_intel = []
    if bets:
        parts = bets[0].match.split(" v ", 1)
        if len(parts) == 2:
            match_intel = tipster.match(parts[0].strip(), parts[1].strip())

    community_tips = []
    try:
        community_tips = get_oddschecker_tips()
    except OddscheckerUnavailable:
        pass

    synthesized = synthesize(bets, community_tips)

    render(
        sport=sport,
        synthesized=synthesized,
        general_intel=general_intel,
        match_intel=match_intel,
        community_tips=community_tips,
        top_match=bets[0].match if bets else None,
    )


def main() -> None:
    _run()
    while True:
        console.print("[dim]  r = refresh   q = quit[/dim]")
        try:
            key = _getkey()
        except (KeyboardInterrupt, EOFError):
            break

        if key in ("q", "Q", "\x03"):  # q, Q, or Ctrl+C
            break
        if key in ("r", "R"):
            console.clear()
            _run()


if __name__ == "__main__":
    main()
