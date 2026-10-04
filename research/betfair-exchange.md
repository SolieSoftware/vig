# Betfair Exchange: commission, liquidity, closing prices

Research for [#3](https://github.com/SolieSoftware/vig/issues/3) (part of #1). Researched 2026-10-04 from Betfair's developer docs (now hosted on `betfair-developer-docs.atlassian.net`; the old `docs.developer.betfair.com` URLs 301 there) and Betfair's support/charges pages. No authenticated Betfair calls were made, so nothing here was checked against live responses. Claims marked **[unverified]** came from secondary sources or from inference, and should be confirmed with one call on the user's account.

Context: `vig/sources/betfair.py` logs in with a certificate, calls `listMarketCatalogue` and then `listMarketBook` with `priceData: ["EX_BEST_OFFERS"]` and `bestPricesDepth: 1`, and keeps only `ex.availableToBack[0].price`.

## 1. Commission for a standard UK account

- **UK accounts are on "My Betfair Rewards".** The official Betfair Charges page says these terms apply to customers in the United Kingdom, Ireland and a few other regions. On those accounts, "Your commission rate is determined by your package choice in the 'My Betfair Rewards' section of My Account", not by the Market Base Rate and Discount Rate. [S5]
  - **Basic package: 2%** on net winnings per market. This number comes from the official worked example: "opted into the Basic package … The commission rate in this package is 2%". [S5]
  - **Rewards: 5%. Rewards+: 8%**, plus a 10% monthly loss refund and promotions. **[unverified]**: these come from secondary sources [S10]; the official page I could reach does not list them.
  - On Rewards accounts the Discount Rate (Betfair Points) applies only to Australasian markets. [S7]
- **Commission is charged per market on net winnings.** If a market loses you money overall, you pay nothing on it. [S5][S6] Outside Rewards, the formula is `Net Winnings × Market Base Rate × (1 − Discount Rate)`. [S6]
- **API fields:** `listMarketCatalogue` with `MARKET_DESCRIPTION` returns `description.marketBaseRate` ("The commission rate applicable to the market") and `description.discountAllowed`. [S2] **[unverified]**: whether `marketBaseRate` shows the account's Rewards package rate or the generic base rate (probably 5). Do not rely on it for the commission rate. Use a config value instead.
- **Expert Fee:** only applies once gross profit over the last 52 active weeks is above £25,000. That is irrelevant at this project's stakes, but worth knowing. [S5] (The tiers of 20% for £25k–£100k and 40% above £100k come from secondary sources and are **[unverified]**.)
- **Transaction charges:** only above 5,000 bets in an hour. Not relevant here. [S5]

**Net-of-commission prices** (c = commission rate, for example 0.02 or 0.05):
- Back at decimal price `p`: effective price = `1 + (p − 1)(1 − c)`.
- Lay at price `p`: you risk `(p − 1)` per unit and win `(1 − c)` per unit. As back odds on "not this outcome", that is `1 + (1 − c)/(p − 1)`.
- This is exact for a single bet in a market. Commission is netted per market, so several bets in the same market are charged on the market's net result, not bet by bet.

## 2. Reading liquidity at best back/lay

`listMarketBook` already returns both sides of the book. The current code just throws the lay side away.

- Each runner has `ex: ExchangePrices` with `availableToBack`, `availableToLay` and `tradedVolume`. Each of those is a list of `PriceSize {price, size}`, best price first. [S2]
- `size` is the amount in the account currency available at that `price`. **[unverified]** On the lay side, `size` is the backer's stake you would be matching, so your liability is `size × (price − 1)`. This is the standard reading and matches the website ladder, but I did not find it stated in the type definitions.
- `exBestOffersOverrides.bestPricesDepth`: "If unspecified defaults to 3. The maximum returned price depth returned is 10." [S2] A **delayed key returns at most 3 levels**. [S1]
- `priceProjection.virtualise`: "must be set to 'true' [to] replicate the display of prices on the Betfair Exchange website". Virtual (cross-matched) prices can be taken, so set it to `true` for MATCH_ODDS. [S2]
- Rollup: by default sizes are rolled up at the minimum stake (`rollupModel` STAKE). [S2]
- Market-level fields: `totalMatched`, `totalAvailable`, `isMarketDataDelayed`, `status`, `inplay`, `lastMatchTime`. [S2] Runner-level fields: `lastPriceTraded`, `totalMatched`, `status`. [S2] **A delayed key does not return runner-level `totalMatched`**, but it does return the market total. [S1]
- **Request weight:** the limit is `sum(weight) × number of marketIds ≤ 200` per request. Above that you get `TOO_MUCH_DATA`. [S3] Weights:
  - `EX_BEST_OFFERS` = 5, scaled by `depth/3` when `exBestOffersOverrides` is set.
  - `EX_TRADED` = 17. `EX_BEST_OFFERS + EX_TRADED` = 20.
  - `SP_AVAILABLE` = 3. `SP_TRADED` = 7.

  At depth 3, one request covers 40 markets. A full EPL round (10 fixtures × 2 market types = 20 markets) fits in one call. [S3]
- **Rate:** "up to a maximum of 5 times per second to a single marketId". [S4]

**Liquidity check proposal:** treat a Betfair Available price as takeable only if `availableToBack[0].size` (or the lay equivalent) is at least the intended stake. Optionally also require the back/lay spread to be within N ticks. A wide spread is the clearest sign of a thin book.

## 3. Getting lay prices

No extra call or parameter is needed. Read `runner.ex.availableToLay[0]` from the same `listMarketBook` response, alongside `availableToBack[0]`. [S2]

For the **Sharp reference**, a mid of best back and best lay is a better Fair-price input than the back price alone: back alone is biased toward longer odds. Only use the mid when the spread is tight. **[unverified]**: this is a modelling choice, not a Betfair fact.

## 4. BSP and closing prices after kickoff

- **The market goes in-play at kickoff.** Poll `listMarketBook` and watch `inplay` and `status` (`OPEN`, `SUSPENDED`, `CLOSED`; `CLOSED` means settled). [S2][S8] To get the **Closing price** (CONTEXT.md: Fair price at kickoff), store the **last snapshot taken while `inplay == false`**. Poll more often in the final minutes before the scheduled `marketStartTime`.
- **Closed markets:** `listMarketBook` requests for CLOSED markets have to be made separately: "Requests that include both OPEN & CLOSED markets will only return those markets that are OPEN." [S4] Runner `status` (WINNER/LOSER/…) stays available for 90 days after settlement. [S2] **[unverified]**: whether `lastPriceTraded` or offers are still populated after the market closes. Most likely the ladder is empty. Don't depend on getting pre-off prices after the fact; capture them live.
- **BSP:**
  - Runner `sp: StartingPrices` has `nearPrice` and `farPrice` (projections, cached for 60s), `backStakeTaken`, `layLiabilityTaken`, and `actualSP`. `actualSP` is "The final BSP price for this runner. Only available for a BSP market that has been reconciled". It can be `NaN` (removed runner) or `Infinity` (no BSP could be calculated). [S2][S9]
  - To get `sp`, request `SP_AVAILABLE` and/or `SP_TRADED` in `priceData`. [S8]
  - Whether a market has BSP is shown by `description.bspMarket` in `listMarketCatalogue`. [S2]
  - **[unverified]**: whether current EPL MATCH_ODDS and OVER_UNDER_25 markets are BSP markets. Betfair announced football SP on Premier League and Champions League markets (2014 blog, which I could not fetch). Check `bspMarket` once.
  - A delayed key does **not** get BSP near and far prices. [S1] **[unverified]**: whether it gets `actualSP` after reconciliation.
- **Backfill:** historicdata.betfair.com has a free **BASIC** plan with last-traded price at 1-minute intervals (no volume). That is enough to rebuild an approximate pre-off price for past matches. [S11] (Secondary source; **[unverified]** whether it includes BSP for football.)

## 5. Delayed vs live app keys

Per the official Application Keys page [S1]:

| | Delayed key | Live key |
|---|---|---|
| Cost | Free | **£499** one-off activation; requires full KYC |
| Price data | Snapshots delayed **1–180 s**, varying | Real-time |
| Price levels | **3** | All (`bestPricesDepth` up to 10) |
| `EX_ALL_OFFERS` | Not returned | Yes |
| Runner `totalMatched` | Not returned | Yes |
| Market `totalMatched` | Yes | Yes |
| BSP near/far | Not available | Yes |
| Read-only use | **Allowed** | **Not permitted** ("read-only access using the Live App Key isn't permitted") |
| Bet placement | Yes | Yes |
| Stream API | Yes: 2 connections and 200 markets (keys created after 2020-04-08) | Yes |

Both keys are for "personal betting purposes only", and commercial use needs Betfair's approval. Each account gets one pair of keys. `MarketBook.isMarketDataDelayed` tells you at runtime which kind of data you are getting. [S1][S2]

## Recommendation

1. **Stay on the delayed key.** vig only reads data, and Betfair does not permit read-only use of a live key, so the £499 buys nothing here. Live keys are for apps that place bets. Accept the 1–180 s delay. Treat a Betfair Value signal as a prompt to check the price on the site before betting, not as a price you can take as-is.
2. **Change the request** in `get_epl_markets`:
   - Set `priceData: ["EX_BEST_OFFERS"]`, `exBestOffersOverrides: {bestPricesDepth: 3}` and `virtualise: true`. That is weight 5 per market, so up to 40 markets per call.
   - Parse `availableToBack[0]` and `availableToLay[0]` (price and size), plus `lastPriceTraded`.
   - Also parse market-level `inplay`, `status`, `totalMatched` and `isMarketDataDelayed`.
   - Add `MARKET_START_TIME` to the catalogue projection.
3. **Model Betfair in both roles:**
   - **Sharp reference:** the back/lay mid when the spread is tight, otherwise exclude it.
   - **Available price:** best back converted to a net-of-commission price with `1 + (p − 1)(1 − c)`, and gated by `size ≥ stake`.
   - Add a `BETFAIR_COMMISSION` config value. The user should set it to the rate of their My Betfair Rewards package (2% on Basic). Don't read it from `marketBaseRate`.
4. **Closing price:** poll more often from about T−10 min before `marketStartTime`, and persist the last book with `inplay == false` as the closing snapshot. Don't plan on BSP. It may not exist for these markets, it is partly withheld from delayed keys, and CONTEXT.md defines the Closing price as the Fair price, not SP.
5. **One-off check on the account, when convenient:**
   - The `marketBaseRate` and `bspMarket` values on one EPL MATCH_ODDS market.
   - What a CLOSED market's `listMarketBook` returns.

## Sources

- [S1] Application Keys: https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687105/Application+Keys
- [S2] Betting Type Definitions (MarketBook, Runner, ExchangePrices, StartingPrices, PriceProjection, ExBestOffersOverrides, MarketDescription): https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687465/Betting+Type+Definitions
- [S3] Market Data Request Limits: https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687478/Market+Data+Request+Limits
- [S4] listMarketBook: https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687510/listMarketBook
- [S5] Betfair Charges (sections 4, 7, 9). The live page returns 403 to scripts, so I read the Wayback snapshot from 2025-07-17: https://support.betfair.com/app/answers/detail/betfair-charges/ (https://web.archive.org/web/20250717193515/https://support.betfair.com/app/answers/detail/betfair-charges/)
- [S6] Exchange: What is Commission and how is it calculated? (snapshot 2025-10-06): https://support.betfair.com/app/answers/detail/413-exchange-what-is-commission-and-how-is-it-calculated/
- [S7] Exchange: What is the Discount Rate? (snapshot 2025-12-25): https://support.betfair.com/app/answers/detail/414-exchange-what-is-the-discount-rate/
- [S8] Betting Enums (PriceData, MarketStatus): https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687455
- [S9] Why is 'Infinity' returned as actualSp: https://support.developer.betfair.com/hc/en-us/articles/360017860698-Why-is-Infinity-being-returned-as-the-actualSp-value
- [S10] Secondary, for the Rewards/Rewards+ rates: https://bet4bettor.com/my-betfair-rewards/ , https://www.oddsmonkey.com/blog/matched-betting/betfair-launch-my-betfair-rewards-to-uk-customers/
- [S11] Secondary, for the historic data BASIC plan: https://betfair-datascientists.github.io/data/usingHistoricDataSite/ ; official site: https://historicdata.betfair.com/
