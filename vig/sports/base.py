from abc import ABC, abstractmethod
from typing import Dict, List


class SportAdapter(ABC):
    """Abstract base for sport-specific configuration."""

    @property
    @abstractmethod
    def sport_key(self) -> str:
        """The Odds API sport key (e.g. 'soccer_england_premier_league')."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for the UI (e.g. 'football')."""

    @property
    @abstractmethod
    def markets(self) -> List[str]:
        """Odds API market keys to fetch (e.g. ['h2h', 'btts', 'totals'])."""

    @property
    @abstractmethod
    def default_subreddits(self) -> List[str]:
        """Subreddits for general tip scraping."""

    @property
    @abstractmethod
    def team_subreddits(self) -> Dict[str, str]:
        """Maps team name → subreddit name for match-specific intel."""
