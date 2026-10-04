# Source for EPL match results

Research for [#4](https://github.com/SolieSoftware/vig/issues/4), part of #1. Researched 2026-10-04.

**Question:** which source should supply final EPL results (and kickoff times) to settle Flags and Bets for `h2h` and `totals` 2.5? Compare coverage, latency, quota/cost, and how each maps to The Odds API event ids.

## Answer

Use **The Odds API `/scores` endpoint** as the main source, with **football-data.org (free tier)** as a backfill for anything that falls outside the 3-day window.

- `/scores` returns the **same `id` as `/odds`**, so you never have to match fixtures to events.
- Final scores are all you need to settle both markets: `h2h` from home goals vs away goals, `totals 2.5` from the goal total. An EPL match is always 90 minutes plus stoppage time, with no extra time, so the full-time score is the settlement score.
- Kickoff times come from `commence_time` on `/scores`, or from `/events`, which uses no credits.
- Cost: one call with `daysFrom=3` costs 2 credits. Running it once a day uses about 60 of the 500 free monthly credits. Running it every 2–3 days uses about 20–30.

## Comparison

| | The Odds API `/scores` | football-data.org v4 | API-Football (api-sports.io) | openfootball `football.json` |
|---|---|---|---|---|
| EPL coverage | Yes, `soccer_epl` has scores ✔ [3] | Yes, EPL is in the free tier ("free. Forever.") [4] | Yes [7] | Yes, `2025-26/en.1.json` etc. [8] |
| Kickoff time | `commence_time` (UTC) [1] | `utcDate` [6] | Yes (fixture date/time) — *unverified, docs 403'd* | **Date only, no kickoff time** [8] |
| Latency | Live scores update about every 30 s [1] | Free tier scores are **delayed** (paid €12/mo add-on for live) [5]; exact delay *unverified* | Near-live — *unverified* | Updated once a day at 05:00 UTC [8] |
| History window | **Completed games from the last 3 days only** (`daysFrom` 1–3) [1] | Full current season | Free plan: recent seasons only [7] | Many seasons back |
| Quota / cost | Shares the existing key: free plan has 500 credits/mo [2]; `/scores` costs 1 credit, or 2 with `daysFrom` [1] | Free: 10 calls/min with a free key [5] | Free: 100 req/day [7] | Free, public domain; plain HTTP GET of raw GitHub file |
| Maps to Odds API id | **Yes, same `id`** [1] | No. Has its own match `id`; you would match on `utcDate` + team names | No, same problem | No, and it has no time or id either |
| Settlement fields | `completed` bool + `scores[]` per team (score is a string) [1] | `status` (FINISHED/POSTPONED/CANCELLED/AWARDED…), `score.fullTime`, `score.winner`, `score.duration` [6] | `fixture.status` + goals — *unverified* | `score.ft` [8] |
| Extra signup | None | Free API key (email) | Free API key | None |

## Notes and caveats

1. **3-day window is the main risk.** If the settle job does not run within 3 days of a match, `/scores` will not return it any more. Backfill from football-data.org by matching on kickoff date plus normalised team names. Team names differ between providers, e.g. "Brighton and Hove Albion" vs "Brighton & Hove Albion FC". That is the only place a name-mapping table is needed. *(The exact team-name spellings were not checked against live responses.)*
2. **Postponed or abandoned matches.** `/scores` only has `completed: true/false` [1]. A postponed match never becomes `completed`, and it stops appearing once it falls out of the window. If a Flag or Bet is still unsettled N days after `commence_time`, either void it or check football-data.org, whose `status` has explicit POSTPONED / CANCELLED / AWARDED values [6]. *(How `/scores` represents a postponed soccer match was not checked.)*
3. **Scores are strings.** In `/scores`, `scores[].score` is a string (e.g. `"113"` in the docs example) [1], so parse it to int. Each score is keyed by team **name**, so match it to `home_team` / `away_team` rather than relying on array order.
4. **Credit sharing.** `/scores` uses the same 500/mo free allowance as `/odds`. `/odds` costs about markets × regions per call, so the odds polling, not results, is what uses most of the budget. Running results once a day costs very little.
5. API-Football was a close alternative but adds nothing over football-data.org here, and has a tighter daily cap. Its docs and pricing pages returned 403 to automated fetches, so the figures above come from its blog and should be treated as *partly unverified*.
6. openfootball cannot be the main source: it has no kickoff times, no ids, and updates once a day. It is fine for one-off historical backfills.

## Suggested shape

- Daily job: `GET /v4/sports/soccer_epl/scores?daysFrom=3&dateFormat=iso` → for each `completed` event, upsert a `Result(event_id, home_goals, away_goals, final_at=last_update)` row → settle open Flags and Bets with that `event_id`.
- Fallback: for Flags and Bets whose `commence_time` is more than 3 days old and still unsettled, look them up in football-data.org `/v4/competitions/PL/matches?dateFrom=…&dateTo=…`.

## Sources

1. The Odds API v4 docs — `/scores`, `/events`: https://the-odds-api.com/liveapi/guides/v4/ ("The game `id` field in the scores response matches the game `id` field in the odds response"; `daysFrom` 1–3; cost 2 with `daysFrom`, else 1; `/events` does not count against quota)
2. The Odds API plans: https://the-odds-api.com/#get-access (Starter free, 500 credits/mo; 20K $30/mo)
3. The Odds API sports list (scores column): https://the-odds-api.com/sports-odds-data/sports-apis.html
4. football-data.org coverage: https://www.football-data.org/coverage
5. football-data.org pricing: https://www.football-data.org/pricing (free 10 calls/min, delayed scores; €12/mo adds live scores)
6. football-data.org v4 Match resource: https://docs.football-data.org/general/v4/match.html
7. API-Football (secondary, primary pages 403'd): https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide
8. openfootball/football.json: https://github.com/openfootball/football.json
