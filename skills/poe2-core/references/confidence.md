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

*(Source agreement — poe2scout vs poe.ninja — would belong here, but only poe2scout is integrated, so
there's nothing to compare against yet. Don't claim sources agree.)*

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
| Freshness | `ageSeconds` (every market tool) | ≤ 300 | 300–3,600 | > 3,600 → re-query first |
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
- **Unique prices have no sample size.** `price_unique` is a poe2scout reference price with no
  listing volume, so it tops out at **Medium** ("reference price; listing volume unknown").
