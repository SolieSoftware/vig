# vig

Football betting research for real-money bets: finds prices that beat the market's fair view and measures whether doing so pays.

## Language

### Prices

**Fair price**:
The market's best estimate of an outcome's true probability, with bookmaker margin removed.
_Avoid_: true odds, consensus (the current way of computing it, not the concept)

**Sharp reference**:
A price source treated as the most accurate input to the Fair price, such as the Betfair Exchange.
_Avoid_: sharp book (unless it is literally a bookmaker)

**Available price**:
A price at a book the user can actually bet with (Bet365, Sky Bet, Betfair Exchange). Other books only feed the Fair price.
_Avoid_: best price (ambiguous about whether it can be taken)

**Value signal**:
How far an Available price beats the Fair price, as a probability gap.
_Avoid_: edge (reserve for proven, measured advantage)

### Outcomes

**Flag**:
A record that the tool identified an Available price with a positive Value signal at a moment in time.
_Avoid_: tip, pick, recommendation

**Bet**:
A wager the user actually placed, optionally linked to the Flag that prompted it.
_Avoid_: position, trade

**Closing price**:
The Fair price at kickoff, used as the benchmark a Flag or Bet is measured against.
_Avoid_: SP, final odds

**CLV (closing line value)**:
How much a Flag's or Bet's price beat the Closing price; the primary measure of whether the signal works.

**Edge**:
An advantage demonstrated by CLV over enough Flags, as opposed to a single Value signal.
