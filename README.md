# vig

A terminal dashboard for football betting research. Pulls live odds from multiple sources, strips the bookmaker margin, and surfaces value signals — ranked by how far the best available price beats the consensus no-vig probability.

```
┌─ Value Bets ────────────────────────────────────────────────────────────┐
│  Arsenal v Chelsea    1X2 · Arsenal   2.10  HIGH  +6.2%  Bet365        │
│  Liverpool v Man Utd  O/U 2.5 · Over  1.87  MED   +3.1%  Betfair Exch  │
│  ...                                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## What it does

1. **Fetches live odds** from The Odds API (multiple bookmakers) and the Betfair Exchange
2. **Strips the vig** — computes a consensus no-vig probability across all bookmakers for each outcome
3. **Calculates value signal** — the gap between the consensus fair price and the best available decimal odds
4. **Cross-references community tips** — scrapes Reddit and Oddschecker, then uses Claude to match community sentiment to specific odds opportunities
5. **Shows Polymarket prediction markets** for the same fixtures as a second-opinion signal
6. **Renders a live terminal dashboard** using Rich, refreshable with `r`

Value signal and confidence are derived from odds data only. Community tips are shown as context — they never inflate the confidence rating.

---

## Data sources

| Source | What it provides |
|---|---|
| [The Odds API](https://the-odds-api.com) | Live bookmaker odds (1X2, BTTS, O/U 2.5) |
| [Betfair Exchange](https://www.betfair.com) | Exchange prices (no bookmaker margin) |
| Reddit (`r/soccer`, `r/sportsbook`) | Community picks and sentiment |
| Oddschecker | Aggregated tipster picks |
| [Polymarket](https://polymarket.com) | Prediction market probabilities |

---

## Setup

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv)

```bash
git clone https://github.com/SolieSoftware/vig
cd vig
uv sync
```

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
# Required
ODDS_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Optional — Betfair Exchange prices
BETFAIR_API_KEY=your_key_here
BETFAIR_USERNAME=your_username
BETFAIR_PASSWORD=your_password

# Optional — Reddit community tips
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=vig/0.1
```

Get an Odds API key at [the-odds-api.com](https://the-odds-api.com). The free tier covers development use. `ANTHROPIC_API_KEY` is used by the Claude-powered tip matching.

Betfair uses certificate login: place `betfair.crt` and `betfair.pem` in `.certs/` (gitignored). See Betfair's [non-interactive login guide](https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/Non-Interactive+%28bot%29+login).

---

## Usage

```bash
uv run vig
```

Inside the dashboard:

| Key | Action |
|---|---|
| `r` | Refresh all data |
| `q` or `Ctrl+C` | Quit |

---

## How value signal works

For each outcome (e.g. Arsenal to win):

1. Collect all bookmakers' prices for that outcome
2. Strip each bookmaker's margin to get their implied fair probability
3. Average those fair probabilities across all bookmakers → **consensus no-vig prob**
4. Find the best (highest) decimal odds available → **implied prob = 1 / best_odds**
5. **Value signal = consensus_no_vig_prob − implied_prob**

A positive signal means the best available price is better than the market consensus says it should be. Confidence thresholds:

| Confidence | Signal |
|---|---|
| HIGH | > 5% |
| MEDIUM | 2–5% |
| LOW | < 2% |

---

## Caching

Odds data is cached locally in `.vig_cache/` for 2 hours to avoid burning API quota during development.

---

## Project structure

```
vig/
  agents/
    odds_agent.py        # fetches + parses odds, calculates value signal
    betfair_agent.py     # Betfair Exchange prices
    scraper_agent.py     # Oddschecker tipster scraping
    tipster_agent.py     # Claude-powered match intel
    synthesis_agent.py   # cross-references odds with community tips via Claude
  sources/
    betfair.py           # Betfair API client
    polymarket.py        # Polymarket API client
    reddit.py            # Reddit PRAW client
  sports/
    base.py              # SportAdapter abstract class
    football.py          # FootballAdapter (EPL, markets config)
  ui/
    dashboard.py         # Rich terminal dashboard renderer
  config.py              # env vars, thresholds, cache settings
  __main__.py            # entry point + keyboard loop
```
