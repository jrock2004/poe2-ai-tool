# Confidence rubric

Every answer ends with a band and a one-line reason. Example:
`Confidence: Medium — only 3 comparable listings, prices ranged ~2×.`

**Do not emit invented percentages.** Derive the band from signals you can actually observe:

| Signal | Raises confidence | Lowers confidence |
|---|---|---|
| Data freshness | fetched just now / cache < 5 min | stale or unknown age |
| Sample size | enough comparable listings (see thresholds below) | few (1–3) or zero (extrapolating) |
| Price spread | cheapest listings cluster tightly | a wide range, or a lone cheap outlier |
| Input certainty | real character/currency from a PoB code or a confirmed screenshot | guessed or assumed inputs |
| Knowledge recency | knowledge file matches the live patch | possibly stale (patch changed) |
| Source agreement (currency) | poe2scout's price falls inside the exchange's last hour | poe2scout far outside it |

*(The only two price sources are poe2scout and GGG's Currency Exchange, and only for currency. Don't
claim agreement with anything else.)*

**Banding:**
- **High** — fresh data, healthy sample, tight spread, certain inputs.
- **Medium** — one or two weak signals (small sample, some assumption).
- **Low** — extrapolating, stale, or key inputs guessed. Say what would raise it.

Always add the single most important reason, not a list. When confidence is Low, name the one thing
that would make it High ("send a screenshot of your currency tab and I can price this exactly").

## Market signals: read them from the tool output

The market tools return these signals as fields, so score them from the numbers, not by eyeballing
listings. **The band is capped by the weakest signal** — a tight spread doesn't rescue a sample of 2.
These thresholds are starting defaults; tune them here, not in individual skills.

| Signal | Field | High | Medium | Low |
|---|---|---|---|---|
| Sample size (rares) | `search_trade` → `priceStats.converted` | ≥ 8 | 4–7 | 1–3 (0 → don't price; widen) |
| Price spread (rares) | `priceStats.spreadRatio` | ≤ 1.5 | 1.5–3 | > 3 |
| Currency depth | `get_currency_prices` → `quantityListed` | ≥ 1,000 | 50–999 | < 50 |
| Currency volatility | `trend.changePctVsDivine` (7-day) | within ±10% | ±10–30% | beyond ±30% |
| Freshness | `ageSeconds` (every market tool) | ≤ 300 | 300–3,600 | > 3,600 → re-query first |
| Exchange volume | `exchange.volume` (units traded, last hour) | ≥ 100 | 10–99 | < 10 |
| Exchange range | `exchange.highExalted` ÷ `exchange.lowExalted` | ≤ 1.5 | 1.5–3 | > 3 |
| Source agreement | `priceExalted` vs `exchange` low–high | within 1.25× of the range | 1.25–2× | > 2× outside |
| Move agreement | `changePctVsDivine` vs the `exchange` one | same way, within 15 points | same way | opposite ways |
| Conversion coverage | `priceStats.unconvertedCurrencies` | empty | some, < 25% of `count` | ≥ 25% of `count` |

How to read them:
- **Sample size is `converted`, not `matched`.** `matched` is market depth (how many exist);
  `converted` is how many prices you actually have. `converted` can't exceed `shown`, so search with
  `limit` ≥ 10 when you intend to price. `matched: 10000` means "10,000 or more" — trade2 caps it.
- **The stats describe the cheap end of the market.** Results are price-ascending, so `priceStats`
  covers the cheapest `count` listings (`basis` says so) — that is what a buyer would realistically pay.
  Quote the range as `minExalted`–`medianExalted`, and lead with the median.
- **A lone cheap outlier is not the price.** If `medianExalted` is more than 2× `minExalted`, the
  cheapest listing is likely a price-fixer or a mispriced bait listing — price from the median, and
  say why you ignored the floor.
- **Freshness is a lower bound.** `ageSeconds` is how old *our* copy is (the oldest input to the
  answer); poe2scout's own prices are aggregates that may be older. It matters most on **reuse**: if
  you're about to repeat a price from earlier in the conversation, compare its `fetchedAt` to now and
  re-query if it's past the High threshold, rather than restating an old number as current.
- **Unconverted currencies are excluded from the stats.** Name them ("2 listings priced in an
  unrecognized currency were left out") rather than letting them silently shrink the sample.
- **For currency, the exchange is the market; poe2scout is the reference.** `exchange` is what GGG's
  Currency Exchange traded in its last hour. Buying costs about `highExalted`: the game's market ratio
  sat at the high end in an in-game check (2026-10-08). `lowExalted` is the cheapest that traded —
  roughly what a quick sale fetches (not yet checked in game). `averageExalted` mixes the two, so on
  cheap bulk items it lands far below what a buyer pays: quote the range, never the average alone.
  One stray trade can stretch an end (a 1:135 divine beside 1:715): if the range is wide but
  `averageExalted` sits near one end on high volume, call the far end a stray rather than the market.
  When poe2scout sits above `highExalted`, it's reading high — lead with the exchange and say so ("the
  exchange traded it at 1–5 ex last hour; poe2scout's 11.9 is above anything that traded").
- **The exchange hour has its own age.** It's history by design: `exchange.ageSeconds` up to ~3,600 is
  normal, so don't score it with the Freshness row. Top-level `ageSeconds` is poe2scout's alone. If
  `exchange.error` is set, the exchange was down: price from poe2scout alone and skip the exchange rows.
- **No `exchange` on an item means it didn't trade that hour** — a thin market. Skip the exchange rows
  and let `quantityListed` carry depth; don't treat the gap as a disagreement.
- **The exchange's move is its own measure.** `market_movers` gives each mover the exchange's 7-day
  move (`exchange.changePctVsDivine`): the last 12 hours of trades against the same hours a week
  before, for items with 100+ units traded in each. A None move means too thin — skip Move agreement.
  The sources often disagree (about a third of items moved opposite ways, 2026-10-08): poe2scout's
  figures aren't the exchange's trades, so a move only one source sees is a weak signal.
- **Unique prices have no sample size.** `price_unique` is a poe2scout reference price with no
  listing volume, so it tops out at **Medium** ("reference price; listing volume unknown").
- **Judge currency volatility in divine, not exalted.** Prices are quoted in exalted, so when exalted
  weakens every `trend.changePct` rises together. Score on `changePctVsDivine` — the item's own move —
  and treat the raw `changePct` as context ("up 54% in exalted, ~20% of that is real; exalted itself
  is weakening"). A fast mover's price is a snapshot: say which way it's heading. If
  `changePctVsDivine` is None (divine's history unavailable), skip this signal rather than scoring
  the raw number.
