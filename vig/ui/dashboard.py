import time
from datetime import datetime, timezone
from typing import List

from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from vig.agents.odds_agent import BetOpportunity
from vig.sources.reddit import IntelItem
from vig.sports.base import SportAdapter

console = Console()

CONFIDENCE_STYLE = {
    "HIGH": "bold green",
    "MEDIUM": "yellow",
    "LOW": "dim",
}

CONFIDENCE_ICON = {
    "HIGH": "⚡",
    "MEDIUM": "~",
    "LOW": "·",
}


def _bet_card(bet: BetOpportunity) -> Panel:
    stale_warning = " [bold red][STALE][/bold red]" if bet.is_stale else ""
    conf_style = CONFIDENCE_STYLE[bet.confidence]
    conf_icon = CONFIDENCE_ICON[bet.confidence]

    table = Table.grid(padding=(0, 1))
    table.add_column(style="dim", width=14)
    table.add_column()

    table.add_row("Match", Text(bet.match, style="bold"))
    table.add_row("Market", bet.market)
    table.add_row("Pick", Text(bet.pick, style="bold white"))
    table.add_row("Odds", f"{bet.decimal_odds:.2f}")
    table.add_row("Implied prob", f"{bet.implied_prob * 100:.1f}%")
    table.add_row("No-vig prob", f"{bet.no_vig_prob * 100:.1f}%")
    table.add_row(
        "Value signal",
        Text(f"{bet.value_signal_pct * 100:+.2f}%", style="green" if bet.value_signal_pct > 0 else "red"),
    )
    table.add_row(
        "Confidence",
        Text(f"{conf_icon} {bet.confidence}", style=conf_style),
    )
    table.add_row("Source", Text(bet.source, style="dim"))

    updated_str = datetime.fromtimestamp(bet.timestamp, tz=timezone.utc).strftime("%H:%M UTC")
    table.add_row("Updated", f"{updated_str}{stale_warning}")

    border_style = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "grey50"}[bet.confidence]
    return Panel(table, border_style=border_style, padding=(0, 1))


def render(
    sport: SportAdapter,
    bets: List[BetOpportunity],
    intel: List[IntelItem] = None,
    match_intel: List[IntelItem] = None,
    oddschecker_intel: List[IntelItem] = None,
    top_match: str = None,
) -> None:
    now_str = datetime.now(tz=timezone.utc).strftime("%H:%M UTC")

    console.print()
    console.rule(f"[bold]vig[/bold] — {sport.display_name}  │  {now_str}  │  press [bold]r[/bold] to refresh")
    console.print()

    if not bets:
        console.print("[dim]No opportunities found for current fixtures.[/dim]")
        return

    # Show top 6 cards (or all if fewer)
    top = bets[:6]
    cards = [_bet_card(b) for b in top]

    # Display in 2-column grid
    for i in range(0, len(cards), 2):
        row = cards[i:i + 2]
        console.print(Columns(row, equal=True, expand=True))

    # Match-specific intel pane
    if match_intel:
        label = f"INTEL — {top_match}" if top_match else "INTEL — top fixture"
        console.print()
        console.rule(f"[dim]{label} (context only, not signal)[/dim]", style="dim")
        for item in match_intel[:6]:
            console.print(
                f"  [dim]{item.source}[/dim]  {item.text[:90]}{'…' if len(item.text) > 90 else ''}"
            )

    # General intel pane
    console.print()
    console.rule("[dim]INTEL — general tips (context only, not signal)[/dim]", style="dim")
    if not intel:
        console.print("[dim]  No Reddit context loaded.[/dim]")
    else:
        for item in intel[:6]:
            console.print(
                f"  [dim]{item.source}[/dim]  {item.text[:90]}{'…' if len(item.text) > 90 else ''}"
            )

    # Oddschecker pane
    if oddschecker_intel:
        console.print()
        console.rule("[dim]INTEL — Community picks, AI-extracted (context only, not signal)[/dim]", style="dim")
        for item in oddschecker_intel:
            console.print(f"  [dim]{item.source}[/dim]  {item.text[:90]}{'…' if len(item.text) > 90 else ''}")

    console.print()
