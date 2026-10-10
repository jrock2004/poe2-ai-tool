---
name: poe2-meta-strategy
description: Read the Path of Exile 2 market's direction — what's rising or falling this week across fragments, essences, breach, delirium, ritual, expedition, abyss and runes — and turn it into sell/hold advice for the player's own currency and farming advice by mechanic. Use when the player asks "what's moving", "what's worth more lately", "should I sell or hold my X", "what's the market doing", or "what should I farm".
model: sonnet
---
# poe2-meta-strategy

**Before any other tool call, invoke the `poe2-core` skill** with the Skill tool; its rules apply here
and aren't restated. This skill answers "where is the market heading?" from data, not vibes: the
`market_movers` tool gives each category's biggest 7-day risers and fallers, measured **in divine**
so exalted's own drift doesn't fake a trend. It pairs with `poe2-currency-tracker` to turn that
into "sell this, hold that" for what the player actually owns.

What it is **not**: a profit-per-hour calculator. Nothing available reports drop rates or run
times, so never claim "X divine/hour". A mover is a price signal, not a farming yield.

## "What's moving?"

1. Call `market_movers()` — the default categories are the farming set. Pass `categories` when the
   player names one ("what's happening with omens?" → `["ritual"]`; plain currency → `["currency"]`).
2. **Lead with the context:** `divineChangePct` says how far divine itself moved in exalted this
   week. If it's large (say beyond ±10%), tell the player prices *quoted in exalted* all look
   inflated or deflated — the moves below already strip that out.
3. **Report per category, briefly:** the top couple of risers and fallers with `changePctVsDivine`
   and current price. Group the story where the data shows one ("refined catalysts are up 35–50%
   while basic ones fell 30–44%") rather than listing rows. For the price, each mover's `exchange`
   is what it traded for in the last hour: quote that range, with poe2scout's `priceExalted` as the
   reference (the rubric says how to read the two). Beside poe2scout's move, `exchange.changePctVsDivine`
   is the exchange's own 7-day move from actual trades. When the two point the same way, say so; when
   they don't ("poe2scout has it up 43%, but on the exchange it traded 29% lower than a week ago"), say
   that too — a riser only one source sees is a weak signal.
4. **Disregard cheap movers.** An item worth under ~2 exalted (`priceExalted`) can double on a
   fraction of an exalted — the percentage is noise. Leave it out, or mention it only as noise.
5. If a category comes back `unknownCategory`, say the name wasn't recognized and offer the valid
   ones (they're listed in the tool's description).

If `source` is "exchange", poe2scout was down: `exchangeMovers` ranks the exchange's own moves over
everything it trades, with no categories — report the ones in the player's categories or holdings.

`thin` counts items skipped for being listed fewer than 50 times — too thin to trust a move. If a
player asks about one of those, say the market is too thin to call, and offer `get_currency_prices`
for its current price.

## "Should I sell or hold?"

Needs the player's inventory from `poe2-currency-tracker` (their league + trade mode pool). If there's none, ask for
a currency-tab screenshot (one-line how-to from `poe2-core`).

1. For the categories their holdings fall in, call `market_movers(categories=[...])`; for a specific
   item that isn't a top mover, `get_currency_prices(category, search=name)` gives its own `trend`.
2. **Falling in divine terms** → lean *sell* (or spend it on their next upgrade) before it drops
   further. **Rising** → *hold* is reasonable; say it may reverse. **Flat (within ±10%)** → no
   market reason either way; let their needs decide. Lean only where poe2scout's move and the
   exchange's (`exchange.changePctVsDivine`) agree; when they point opposite ways, there's no market
   reason either way — say the sources disagree.
3. Weigh size: put the advice where the value is (`count × exchange.highExalted`, else `count ×
   priceExalted`), not on a 2-exalted stack.
4. **Never trade for them.** Output is advice plus, if they want, `poe2-price-check` for a listing
   price. They list and sell themselves.

**SSF characters** (`trade_mode`, see `poe2-core`) can't sell, so there's no sell/hold call to make —
say so in one line. Offer instead what their currency could do for the build: hand off to
`poe2-crafting` or `poe2-gear-upgrade`.

## "What should I farm?"

Call `get_knowledge('farming')` first — it maps each mechanic to its poe2scout category and
says what its outputs are for. Check its freshness stamp; if the patch has moved on, say so.

1. Call `market_movers()` (the default set covers the farming categories).
2. For each mechanic, summarize its outputs' direction and depth: mostly rising or falling in divine
   terms, and whether the valuable outputs are deep (high `quantityListed`) or thin. Name the
   outputs that drive it ("refined catalysts up 35–50%; basic catalysts down").
3. Recommend by **direction and depth of the outputs**, matched to the player's build and goal
   (from `poe2-character`): a mechanic their build clears comfortably, whose valuable outputs are
   rising and deep. Use the file's decision principles (crafting-meta splits, league phase).
4. **No rates.** Never say "X div/hour" or rank by yield — nothing reports drop rates or run times.
   Say that plainly if asked, and offer what *is* known: what the outputs are worth and where
   they're heading.
5. For the fragments the file marks as not researched (Crisis Fragments, Fates, Origin items, …),
   give the price and direction only; say the mechanic isn't covered.

**SSF characters:** market direction doesn't help — they can't sell what they farm. Recommend by what
the build needs instead: the currencies and crafting materials its next upgrades call for (from
`poe2-gear-upgrade` / `poe2-crafting`), mapped to the mechanics that produce them via the knowledge
file, among those the build clears comfortably. Skip `market_movers`. "What's moving?" can still be
answered if they ask, with a line that it doesn't affect them.

Confidence for farming advice tops out at **Medium**: prices are grounded, yields aren't.

## Confidence (per `poe2-core/references/confidence.md`)

Score each call on the rubric's **Market signals**: **Currency volatility** on `changePctVsDivine`,
**Currency depth** on `quantityListed`, and **Freshness** on `ageSeconds` (oldest input wins).
A big mover is, by definition, volatile — so "this is moving fast" can be High-confidence as a
*direction* while any specific *price* for it is Low. Say which one you're scoring. If
`divineChangePct` is null, there's no inflation-free move: don't fall back to raw exalted changes.

## Guardrails

- Divine-relative moves only; never present a raw exalted change as a trend.
- No profit-per-hour claims — no yield data exists.
- Skip thin and cheap movers rather than amplifying noise.
- Read-only: never buy, list, or whisper.
