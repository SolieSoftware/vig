"""
SynthesisAgent — combines OddsAgent opportunities with community intel.

Uses Claude to cross-reference community picks against live odds, surfacing
bets where the value signal and community sentiment point the same direction.

Key rule: confidence is ALWAYS derived from odds data only. Community picks
are surfaced as context — never used to inflate the confidence score.
"""
import asyncio
from typing import List, Optional

from pydantic import BaseModel
from pydantic_ai import Agent

from vig.agents.odds_agent import BetOpportunity
from vig.sources.reddit import IntelItem


class SynthesizedBet(BaseModel):
    """A bet opportunity enriched with community context."""
    opportunity: BetOpportunity
    community_count: int = 0          # number of community picks matching this bet
    community_snippets: List[str] = [] # short summaries of matching community picks


class SynthesisResult(BaseModel):
    bets: List[SynthesizedBet]


class _MatchResult(BaseModel):
    """Internal: Claude's cross-reference output for one bet."""
    bet_index: int
    community_count: int
    community_snippets: List[str]


class _CrossRefOutput(BaseModel):
    matches: List[_MatchResult]


_SYSTEM_PROMPT = """
You are a sports betting research assistant. You cross-reference live odds data
with community betting tips, identifying where community picks align with specific
odds opportunities.

Rules:
- Match team names loosely (e.g. "Wolves" = "Wolverhampton Wanderers")
- Match markets loosely (e.g. "Over 2.5" = "O/U 2.5", "home win" = the home team pick)
- Only mark a match when the community tip clearly aligns with the specific bet
- Keep community_snippets under 100 characters each
- If no community picks match a bet, set community_count=0 and community_snippets=[]
"""


async def _cross_reference(
    bets: List[BetOpportunity],
    community_tips: List[IntelItem],
) -> List[SynthesizedBet]:
    if not community_tips:
        return [SynthesizedBet(opportunity=b) for b in bets]

    # Build compact representations to keep prompt small
    bets_text = "\n".join(
        f"[{i}] {b.match} | {b.market} | Pick: {b.pick} | Odds: {b.decimal_odds}"
        for i, b in enumerate(bets)
    )
    tips_text = "\n".join(f"- {t.text}" for t in community_tips)

    prompt = f"""
Below are live odds bet opportunities (indexed 0-{len(bets)-1}) and community tips.

ODDS BETS:
{bets_text}

COMMUNITY TIPS:
{tips_text}

For each bet index, identify which community tips (if any) align with that specific
bet (same match + same direction). Return community_count and up to 2 short snippets.
Only include bets that have at least one community match — omit bets with no matches.
"""

    agent: Agent[None, _CrossRefOutput] = Agent(
        "anthropic:claude-haiku-4-5-20251001",
        output_type=_CrossRefOutput,
        system_prompt=_SYSTEM_PROMPT,
    )
    result = await agent.run(prompt)

    # Build lookup from index → cross-ref data
    lookup = {m.bet_index: m for m in result.output.matches}

    return [
        SynthesizedBet(
            opportunity=b,
            community_count=lookup[i].community_count if i in lookup else 0,
            community_snippets=lookup[i].community_snippets if i in lookup else [],
        )
        for i, b in enumerate(bets)
    ]


def synthesize(
    bets: List[BetOpportunity],
    community_tips: List[IntelItem],
    top_n: int = 20,
) -> List[SynthesizedBet]:
    """
    Cross-reference the top N bets against community tips.
    Returns SynthesizedBet list sorted by:
      1. community_count desc (community-backed bets surface first)
      2. value_signal_pct desc (odds value within same community tier)
    """
    top_bets = bets[:top_n]
    synthesized = asyncio.run(_cross_reference(top_bets, community_tips))

    return sorted(
        synthesized,
        key=lambda s: (s.community_count, s.opportunity.value_signal_pct),
        reverse=True,
    )
