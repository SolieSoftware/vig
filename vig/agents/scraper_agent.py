"""
ScraperAgent — uses Claude (PydanticAI) to extract structured tips from raw text.

Rather than fighting Cloudflare with a headless browser, this agent fetches raw
Reddit tip thread content (which the JSON API serves freely) and uses Claude to
parse structured bets from the comments. AI-powered extraction handles the varied
comment formats that CSS selectors can't.
"""
import asyncio
import time
from typing import List

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent

from vig.sources.reddit import IntelItem

HEADERS = {"User-Agent": "vig/0.1 (personal research tool)"}


class TipExtractorUnavailable(Exception):
    pass


# Keep the old name so __main__.py import still works
OddscheckerUnavailable = TipExtractorUnavailable


class _ExtractedTip(BaseModel):
    match: str        # e.g. "West Ham vs Wolves"
    market: str       # e.g. "Over 2.5", "BTTS Yes", "Home Win"
    odds: str         # e.g. "1.80" — as string since format varies
    reasoning: str    # brief reason from the commenter, or "" if none given


class _ExtractionResult(BaseModel):
    tips: List[_ExtractedTip]


_SYSTEM_PROMPT = """
You are a structured data extraction agent. You read raw Reddit comment text from
a football betting tips thread and extract structured bet tips. Be precise — only
extract tips that are clearly stated. Never invent or guess odds or reasoning.
If a field is not present, use an empty string.
"""


def _fetch_tip_thread_comments() -> str:
    """Fetch the top daily tip thread from r/soccerbetting and return its comments as text."""
    r = httpx.get(
        "https://www.reddit.com/r/soccerbetting/top.json",
        params={"limit": 10, "t": "day"},
        headers=HEADERS,
        timeout=10,
    )
    if r.status_code != 200:
        raise TipExtractorUnavailable(f"Reddit API error: {r.status_code}")

    posts = r.json()["data"]["children"]
    tip_thread = next(
        (
            p for p in posts
            if any(kw in p["data"]["title"] for kw in ["Daily Picks", "Pick Thread", "Tips Thread", "Predictions"])
        ),
        None,
    )
    if not tip_thread:
        raise TipExtractorUnavailable("No daily tip thread found today.")

    thread_url = "https://www.reddit.com" + tip_thread["data"]["permalink"] + ".json"
    r2 = httpx.get(thread_url, params={"limit": 30}, headers=HEADERS, timeout=10)
    if r2.status_code != 200:
        raise TipExtractorUnavailable(f"Reddit thread fetch error: {r2.status_code}")

    comments = r2.json()[1]["data"]["children"]
    thread_title = tip_thread["data"]["title"]

    parts = [f"Thread: {thread_title}\n"]
    for c in comments:
        body = c["data"].get("body", "").strip()
        if body and body not in ("[deleted]", "[removed]") and len(body) > 20:
            parts.append(body[:600])  # cap each comment to keep prompt reasonable

    return "\n\n---\n\n".join(parts)


async def _extract_tips(raw_text: str) -> List[IntelItem]:
    agent: Agent[None, _ExtractionResult] = Agent(
        "anthropic:claude-haiku-4-5-20251001",
        output_type=_ExtractionResult,
        system_prompt=_SYSTEM_PROMPT,
    )

    prompt = f"""
Extract all clearly stated football bet tips from the following Reddit tip thread comments.
For each tip include: match, market (bet type), odds (if stated), and a one-sentence
summary of the reasoning given (if any).

{raw_text}
"""
    result = await agent.run(prompt)
    now = time.time()

    items = []
    for tip in result.output.tips:
        parts = [tip.match, tip.market]
        if tip.odds:
            parts.append(f"@ {tip.odds}")
        label = " — ".join(parts)
        if tip.reasoning:
            label += f" | {tip.reasoning[:120]}"
        items.append(IntelItem(
            source="r/soccerbetting (AI-extracted)",
            text=label,
            url="https://www.reddit.com/r/soccerbetting",
            scraped_at=now,
        ))

    return items


def get_oddschecker_tips() -> List[IntelItem]:
    """Fetch and AI-extract tips from the daily Reddit tip thread. Returns [] on failure."""
    try:
        raw = _fetch_tip_thread_comments()
        return asyncio.run(_extract_tips(raw))
    except TipExtractorUnavailable as e:
        raise
    except Exception as e:
        raise TipExtractorUnavailable(f"Tip extraction failed: {e}") from e
