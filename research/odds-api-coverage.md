# The Odds API: EPL coverage, quota and historical/closing odds

Research for issue #2 (part of #1). Sources were read on 2026-10-04 from the-odds-api.com's own pages (listed at the end). Anything not stated directly by a primary source is marked **[unverified]** or **[inferred]**.

Where we are now: `vig/config.py` and `vig/sports/football.py` call `GET /v4/sports/soccer_epl/odds?regions=eu&markets=h2h,totals&oddsFormat=decimal`. That costs **2 credits per call** (1 region x 2 markets).

## 1. Which bookmakers are returned for `soccer_epl` in `uk` and `eu`

From the official bookmaker list [S1]:

| Book | In the API? | Region | Key | Notes |
|---|---|---|---|---|
| **Bet365** | **No (UK/EU)** | — | — | Only `bet365_au` (region `au`), paid plans only, and "limited to h2h, spreads and totals for AFL and NRL". So there is **no Bet365 EPL price** in this API. |
| **Sky Bet** | Yes | `uk` | `skybet` | |
| **Betfair Exchange** | Yes | `uk` / `eu` | `betfair_ex_uk` / `betfair_ex_eu` | Exchange. Lay prices come back automatically as an extra `h2h_lay` market [S2][S3]. |
| **Betfair Sportsbook** | Yes | `uk` | `betfair_sb_uk` | |
| **Pinnacle** | Yes | `eu` only | `pinnacle` | The API's own caveat: "Odds are from public website which may incur a delay". |
| Matchbook (exchange) | Yes | `uk` + `eu` | `matchbook` | Low-margin exchange; returns `h2h_lay` too. |
| Smarkets (exchange) | Yes | `uk` | `smarkets` | |
| Marathon Bet | Yes | `eu` | `marathonbet` | Usually treated as a lower-margin book **[unverified: margin claim is general market knowledge, not from the source]** |
| 1xBet | Yes | `eu` | `onexbet` | |
| Betdaq | **No** | — | — | Not listed in any region. |

Other `uk` books: 888sport, Betano, Betfred, BetVictor, Betway, BoyleSports, Casumo, Coral, Grosvenor, Ladbrokes, LeoVegas, LiveScore Bet, Paddy Power, Unibet, Virgin Bet, William Hill. Other `eu` books include Betclic, Betsson, Coolbet, Everygame, NordicBet, Tipico, Unibet (several countries), Winamax and William Hill [S1].

Caveats:
- The list is per region, not per sport. The page says "Some bookmakers may not list for less popular sports" and books can drop out for hours or days [S1]. That a given book actually returns EPL prices **is [unverified]** until we make a live call. Check the `bookmakers[].key` values in a real response.
- `totals` coverage: the markets page says "spreads and totals markets are mainly available for US sports and bookmakers at this time" [S3]. How many UK/EU books return EPL `totals` (and at which lines) **is [unverified]**. Expect fewer books on `totals` than on `h2h`.
- The free Starter plan has "Most bookmakers" [S4]. None of the UK/EU books above is marked "Only available on paid subscriptions" [S1], so the free tier should see them all **[inferred]**.

## 2. What each regions/markets combination costs

`/odds` costs **1 credit per market per region**: `cost = markets x regions` [S2]. `/sports` and `/events` are free. `/scores` costs 1, or 2 with `daysFrom` [S2].

You can pass `bookmakers=` **instead of** `regions=`. "Every group of 10 bookmakers is the equivalent of 1 region", and if both are given, `bookmakers` takes priority [S2]. This lets us pick books from the UK and EU lists and still pay for only one region.

| Request (soccer_epl) | Credits/call |
|---|---|
| `regions=eu&markets=h2h` | 1 |
| `regions=eu&markets=h2h,totals` (current) | 2 |
| `regions=uk&markets=h2h,totals` | 2 |
| `regions=uk,eu&markets=h2h,totals` | 4 |
| `bookmakers=<up to 10 keys>&markets=h2h,totals` | 2 |
| `bookmakers=<11-20 keys>&markets=h2h,totals` | 4 |
| Event odds `/events/{id}/odds` (e.g. `btts`, `draw_no_bet`, `double_chance`, `correct_score`) | unique markets **returned** x regions, **per event** [S2] |

- `h2h_lay` is "automatically included with h2h results" for exchanges [S2]. It appears to be **free on top of `h2h`** **[inferred]**: the cost formula counts markets *specified*, and we would not specify `h2h_lay`.
- Every response carries the headers `x-requests-remaining`, `x-requests-used` and `x-requests-last` [S2]. We should log these.
- For soccer, `btts`, `draw_no_bet`, `h2h_3_way`, `double_chance`, `correct_score` and similar markets are "additional markets". These can only be fetched one event at a time through the event-odds endpoint [S3]. That fits the code comment that btts is not available through our current call.
- Update intervals: featured markets refresh every 60 s pre-match, and exchanges every 20 s pre-match (10 s in-play). The interval tightens over the last 6 hours before kick-off [S5].

## 3. What the plans cost

From the home page [S4], prices in USD per month:

| Plan | Price | Credits/month | Historical odds |
|---|---|---|---|
| Starter | Free | 500 | **No** (struck through on the page) |
| 20K | $30 | 20,000 | Yes |
| 100K | $59 | 100,000 | Yes |
| 5M | $119 | 5,000,000 | Yes |
| 15M | $249 | 15,000,000 | Yes |

Higher tiers are shown after sign-up ("Create an account to discover higher usage plans").

Rough budget for our use **[inferred: my own arithmetic]**:
- If the 2-hour cache (`CACHE_TTL_SECONDS = 7200`) refreshed around the clock at 2 credits per call, that would be about 12 x 2 x 30 = **720 credits/month**. That is more than the free 500. In practice we only fetch on demand, so real use is lower.
- At 2 credits per call, the 20K plan allows about 10,000 calls a month. That is plenty for on-demand use plus a scheduled "near kick-off" snapshot of every EPL fixture.

## 4. Historical and closing odds

- **Endpoint:** `GET /v4/historical/sports/soccer_epl/odds?regions=…&markets=…&date=<ISO8601>`. It returns the closest snapshot **at or before** `date`. The response also gives `timestamp`, `previous_timestamp` and `next_timestamp` so you can step through snapshots [S2][S6].
- **Per-event additional markets:** `GET /v4/historical/sports/{sport}/events/{eventId}/odds`, with additional markets available from 2023-05-03. Event IDs come from `GET /v4/historical/sports/{sport}/events`, which costs 1 credit, or nothing if no events are found [S2][S6].
- **Granularity:** snapshots every 10 minutes from 2020-06-06, and **every 5 minutes from September 2022** [S2][S6]. EPL's earliest timestamp is `2020-06-06T10:05:00Z` [S6].
- **Cost:** `10 x markets x regions` per call. The `bookmakers` parameter counts the same way (up to 10 books = 1 region) [S2]. One snapshot covers **all** EPL events listed at that moment, not just one match.
- **Plans:** paid plans only. "Historical data is only available on paid usage plans" [S6], and Starter has it struck through [S4].
- **Closing line:** the API has no explicit "closing odds" field. A "close" for CLV has to be built in one of two ways:
  1. **Live capture (cheapest):** call `/odds` a few minutes before each kick-off and store the result. That costs 2 credits per kick-off slot for h2h+totals with one region or up to 10 books. EPL games share kick-off times (Saturday 15:00 etc.), so one call covers every game in that slot.
  2. **Historical backfill:** call `/historical/.../odds` with `date` set to the kick-off time. That costs 20 credits per slot for h2h+totals. A season has roughly 200-250 distinct EPL kick-off slots **[unverified estimate]**, so about **4-5k credits per season** for a closing-line backfill. That fits within the 20K plan.
  - Precision: with 5-minute snapshots, the "close" can be up to 5 minutes before kick-off. Pinnacle's price also carries the "public website ... delay" caveat [S1]. That is good enough for CLV **[inferred]**, but it is not a true tick-level close. For Betfair Exchange, the most precise close is Betfair's own API or Betfair historical data. The repo already has `BETFAIR_*` config for this.

## Recommendation

1. **Replace `regions=eu` with an explicit `bookmakers=` list of at most 10 keys**, so it still costs 1 region. Use this list: `pinnacle,betfair_ex_uk,matchbook,smarkets,skybet,betfair_sb_uk,marathonbet,onexbet,williamhill,paddypower`. That gives us:
   - the sharp/fair-price inputs: Pinnacle, plus Betfair, Matchbook and Smarkets back/lay mid-prices;
   - two of the user's three books: Sky Bet, plus Betfair Exchange/Sportsbook;
   - some soft-book context.

   Cost is unchanged at **2 credits per call** for `h2h,totals`. Adjust the last two or three entries after a live call shows which books really return EPL `totals`.
2. **Bet365 cannot come from this API.** Price Bet365 manually (the user types in the price), or treat Sky Bet as a stand-in for UK soft books. Don't wait on The Odds API adding it.
3. **Build a fair price from Pinnacle plus the exchange mid**, and keep Pinnacle's own margin-free price as a check. Pinnacle prices may lag (scraped from its public website), so check `last_update` before trusting it.
4. **For CLV, capture closing odds live.** Schedule one `/odds` call per EPL kick-off slot, about 5 minutes before kick-off, and store the result. That costs about 2 credits per slot, around 500 credits per season. Use the historical endpoint only to backfill past bets.
5. **Plan:** the free tier (500 credits, no historical) is fine for prototyping. Move to **20K ($30/mo)** when we want historical backfill or comfortable headroom. Log `x-requests-remaining` on every call.

## Open questions to settle with one live call

- Which of the 10 books above actually return `soccer_epl` `h2h` **and** `totals`, and at which totals lines.
- Whether `h2h_lay` changes `x-requests-last`. We expect it not to.

## Sources

- [S1] Bookmaker list by region: https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
- [S2] API v4 docs (odds, event odds, historical, quota costs, headers): https://the-odds-api.com/liveapi/guides/v4/
- [S3] Betting markets (featured vs additional, `h2h_lay`, soccer markets): https://the-odds-api.com/sports-odds-data/betting-markets.html
- [S4] Plans and pricing: https://the-odds-api.com/#get-access
- [S5] Update intervals: https://the-odds-api.com/sports-odds-data/update-intervals.html
- [S6] Historical odds data (granularity, plan restriction, earliest timestamps per sport): https://the-odds-api.com/historical-odds-data/
