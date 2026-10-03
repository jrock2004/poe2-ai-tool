# Path of Exile 2 Decision Assistant — Build Plan

*Draft v10 (Oct 2026) — Phases 1–3 built, plus a hardening pass: confidence is now grounded in fields the tools return (§6), PoB parsing fixed (§9), and the client caches/rate limits are tested. Two v8 assumptions were overturned by live checks and are noted inline. Personal-use tool running inside Claude. **OAuth is currently unobtainable** — GGG isn't issuing new API clients — so character reading is screenshot/description-based (§3), not OAuth-primary as v8 assumed. Screenshots for currency (§2); one `poe2-character` skill owns the roster (§4.1); guides modeled as staged progressions (§5.1); beginner-friendly by default (§7). Reuse-vs-build: reuse poe2scout for currency/uniques, built a thin /trade2 adapter for rare search, and a robots/license-aware guide fetcher (§9). Build status is tracked in §9.*

---

## 1. What we're building

A personal assistant inside Claude that helps you make better PoE2 decisions across trade, gear, builds, and meta strategy — using live market data, your own character data, and packaged reasoning. Every answer states how confident it is and why.

**Guiding principle (unchanged from v1):** Fetching data is mostly solved. The value is *judgment*. So most effort goes into decision **Skills**; the **MCP** stays thin and reusable.

**What changed since v1:** You're open to auth, and you gave seven concrete features. Research turned up one hard constraint that shapes everything (§2). The feature-to-skill mapping is now the core of the plan (§5).

---

## 2. The hard constraint you need to know first

**There is no stash API for Path of Exile 2.** Confirmed by GGG's developer docs (stash endpoints are PoE1-only) and a June 2026 forum thread ("2026 here, still no Stash API"). This is true *even if we do OAuth*.

**What this means for "track what currency I have" (your feature 5):** it can't be read automatically from the game. But we don't need the API — **you send screenshots of your currency and crafting tabs, and the skill reads them into an inventory.** This is the primary mechanism (your call), and it's a good one: those tabs are fixed grids with stack counts printed on each icon, and Claude reads images natively. The flow:
- You screenshot each relevant tab (currency, crafting, etc.) and drop them in.
- The skill parses icon → currency name and the printed stack count into a structured inventory, per tab.
- It's stored in Claude's memory, so it persists across questions and sessions.
- To resync after trading, you send a fresh screenshot; that tab's counts are replaced.

- ~~Official stash API~~ — not available for PoE2.
- ~~Reading your publicly-listed items~~ — only shows what you've *listed for sale*, not your stash.

**Engineering caveats (so you trust the numbers):**
1. **Vision isn't perfect.** Small stack numbers and look-alike icons can misread. So after parsing, the skill *shows you what it read* ("Exalted ×342, Divine ×11, Chaos ×80 …") and you confirm or correct before it's saved. Cheap insurance against a silent wrong count.
2. **Confidence per item.** Each parsed line carries the confidence rubric (§6) — a crisp, high-res tab screenshot reads High; a compressed or partially-hovered one reads Low and gets flagged for you to verify.
3. **Multi-tab merge.** Each screenshot maps to a named tab; re-sending a tab replaces it rather than double-counting. You can keep several tabs (currency, crafting, essences, etc.) as separate buckets that sum to your total.
4. **Drift is expected.** The inventory goes stale the moment you trade. Rather than trying to track every transaction perfectly, the design leans on quick re-screenshots as the source of truth, with optional manual "spent 2 divine" adjustments between syncs.

This turns the one game-limited feature into a smooth paste-a-screenshot flow. Everything else on your list was already very doable.

---

## 3. Auth: OAuth is blocked — screenshot/description primary

**Reality check (verified against GGG's live docs):** OAuth is *not currently available*. GGG's
developer docs say under *Registering your Application*: **"We are currently unable to process new
applications."** There is no self-serve registration, and the forum record shows GGG discourages
third-party tools and issues clients at its discretion. So the v8 plan's "OAuth primary" is off the
table until registration reopens.

| What you want | Best path today | Auth |
|---|---|---|
| Read your gear/skills/passives (features 1, 2) | **Character screenshot / description** (vision) | None |
| Price items, currency rates | poe2scout / poe.ninja | None |
| Generate trade search filters (feature 6) | Unofficial `/trade2` query params | None (a POESESSID cookie extends it) |
| Track your currency (feature 5) | Screenshot tabs → vision parse → memory | None |
| Guides, trials knowledge (features 3, 4) | Fetch where permitted + game knowledge | None |

**What this means:** character reading is done from a **character-panel screenshot** or a plain
description, the same way currency tracking uses screenshots. This is now the primary path, not a
fallback. A ready-to-send OAuth client request is parked in `docs/ggg-oauth-application.md`; if GGG
reopens registration, the official character read (`account:characters`, `poe2` realm, public/PKCE
client) slots in transparently with no change to the skills.

Reading a build has three inputs, best fidelity first: a **PoB code** (`parse_pob_code` decodes it into
computed stats + gems + gear), a **character screenshot** (vision), or a **plain description**.

---

## 4. Architecture: thin MCP + fat Skills + persistent state

```
┌──────────────────────────────────────────────────────────┐
│  YOU (in Claude)                                           │
└───────────────┬──────────────────────────────────────────┘
                │
        ┌───────▼─────────┐        ┌───────────────────────────┐
        │  SKILLS          │  call  │  MCP SERVER               │
        │  (judgment +     │───────▶│  (data plumbing)          │
        │   confidence)    │        │   get_leagues             │
        │                  │        │   get_currency_prices     │
        │ • price-check    │        │   price_unique            │
        │ • gear-upgrade   │        │   value_currency          │
        │ • build-review   │        │   find_stat_filters       │
        │ • trials-advisor │        │   build_trade_filter      │
        │ • character      │        │   search_trade            │
        │ • currency-track │        │   fetch_guide             │
        │ (meta-strategy:  │        │   parse_pob_code          │
        │   not built)     │        └───────────┬───────────────┘
        └───────┬──────────┘                    │
                │                     poe2scout / trade2 /
        ┌───────▼──────────┐          guide sites (robots-aware)
        │  PERSISTENT STATE │         (all cached + rate-limited)
        │  (Claude memory)  │
        │ • characters[]    │  ← multiple, per §4.1
        │ • currency (per league)
        │ • recent trade context
        └──────────────────┘
```

The **persistent state** layer is what makes features 5 and 6 work: your characters, currency inventory, and active trade context live in memory, so the assistant carries context across questions instead of asking you to re-state everything.

### 4.1 Multiple characters + first-run onboarding

You play more than one build (Ice Shot Deadeye, minions, …), and so does everyone — so character isn't a single value, it's a **roster**. The state model:

- **Account → characters[]** — each character has a name, class/ascendancy, build archetype, goal, and its gear/skills read from a character screenshot or description (OAuth being unavailable, §3). You pick which one is *active* for a given question ("check upgrades for my Deadeye").
- **Currency is league-scoped, not character-scoped** — in PoE2 your currency stash is shared across characters in a league, so the inventory attaches to the *league*, and all characters in that league draw on the same pool. (A subtle but important correctness detail — otherwise the tool would think your minion build is broke while your Deadeye is rich.)

**First-run onboarding flow** (a real part of the design, not an afterthought): the first time you use the skill it interviews you — "Which character are we working on? What's the build's goal — bossing, mapping, league-start? Are you following a guide? Paste a PoB code or a character screenshot?" — and saves that as a character profile. It also gauges **experience level** early (are terms like "PoB", "exalt", "resist cap" familiar, or should it explain as it goes?) and stores that, so verbosity is tuned to you from then on. Each new character triggers a short version of the same. After onboarding, day-to-day use is just "check my Deadeye's boots" and it already knows the context. The interview is short, asks one thing at a time, and writes each answer to state as it goes.

**Skill granularity decision (create vs. switch):** the roster lifecycle is **one skill, `poe2-character`**, not several. It owns onboarding a new character, listing the roster, updating a build, and setting the active character. Rationale: those all touch the same data model, and the substantive content (the onboarding interview) justifies exactly one skill.

*Switching the active character is deliberately NOT its own skill* — it's a one-line state update, and a separate "switcher" skill would only create trigger collisions with "new character." Switching is handled two ways instead: a **default active character** (set once, so "check my boots" resolves to it) and a **per-request override** ("check my *minion build's* boots") that names a character inline without changing the default. That gives you everything a switcher would, minus the extra skill. Note: the active character is the *tool's* context only — it does not and cannot mirror who you're logged in as in-game (no API for that).

---

## 5. Your seven features → how each is built

**F1. "Look at my gear and tell me how to improve it."** *(built — PoB code or screenshot)*
Skill: `poe2-gear-upgrade`. Input = your character from a **PoB code** (`parse_pob_code`), a
**screenshot**, or a description (OAuth being unavailable). It identifies your weakest stats vs. your build's needs
(resistances capped? life/ES low? damage bottleneck?), survivability first, then for each weak slot
queries `/trade2` for realistic upgrades and ranks them by *value per currency*, bounded by your
currency budget. Confidence: high with a clear gear read + good market data; lower when guessing intent.

**F2. "Look at my skills, gear, and compare to a build guide."**
Skill: `poe2-build-review`. Pulls your character, ingests the target guide (§F3), figures out *which stage of the guide you're at* (by your character level — see the guide model in §5.1), and produces a stage-aware diff: what you're missing *for where you are right now*, what's off-spec, and a priority-ordered fix list. Explicitly separates "you've *deviated* from the plan" from "you're just *behind on gearing* for your level."

**F3. "Support guides from Maxroll, Mobalytics, poe-vault."** *(fetch tool built)*
MCP tool: `fetch_guide`, which **gates before it fetches** (robots.txt, no-AI licenses, prohibited
hosts) and only then fetches + cleans. **Re-verified Sep 2026 — this overturns the v8 spike:**
- **Mobalytics:** ❌ now **Cloudflare-403s** server fetches even with a browser UA (was "clean static").
  → browser-assisted read, or paste a PoB code.
- **poe-vault:** ✅ static and readable now → plain fetch works.
- **Maxroll:** ⚠️ reachable, but its robots.txt (Ziff Davis) **explicitly prohibits automated/AI use** of
  the content. We **respect that and refuse** → paste the PoB code / content. (This is a *licensing*
  block, stronger than the v8 "robots Disallow" reading.)

So it's still a tiered approach, and `fetch_guide` encodes it by returning a **route** when it won't
fetch: **(a)** static fetch where permitted (poe-vault); **(b)** `route: browser` — the assistant reads
the page in *your own browser session*, which is just you viewing a page you're allowed to view
(Mobalytics); **(c)** `route: paste` — the always-reliable path, the guide's **exported PoB code** or
pasted content (Maxroll, and anything blocked). Order of preference: PoB code > static fetch > browser
read > paste. See §5.1 for how a fetched guide is structured once we have it.

**F4. "In Trial of Sekhemas / Trial of Chaos, what should I select?"**
Skill: `poe2-trials-advisor`. Knowledge-driven: it knows the boon/affliction/reward pools and, given your build context (from state), recommends picks — e.g. "take the honour-resistance relic, your build is honour-fragile" or "avoid the -max-res affliction, you're already at a defensive floor." Needs a maintained knowledge file since trial contents shift by patch.

**F5. "Keep an understanding of what currency I have."**
Persistent state + `poe2-currency-tracker` skill. You send screenshots of your currency/crafting tabs; the skill reads them into a structured inventory (confirming counts with you), remembers it, and updates it as you resync or spend. It uses this to answer "can I afford this upgrade?" and "what's my net worth in divine right now?" and to set realistic price ceilings in trade filters (F6). See §2 for the full mechanism and caveats — no stash API exists, so screenshots are the input.

**F6. "When it says I need better boots, give me the trade filters — and iterate."**
MCP tool: `build_trade_filter` + the iterative loop is the skill's job. It outputs a ready-to-use trade2 search (either a link you click, or the exact filters to set: item type, required mods with min values, socket/rune needs, price ceiling based on your currency). Then: you paste back what the search returned, it critiques the results ("these are overpriced, loosen the crit filter") and refines. This tight loop is arguably the single most useful thing in the whole tool.

**F7. "Every answer states the AI's confidence."**
Cross-cutting requirement — see §6. This is a real engineering problem, not a formatting one, so it gets its own section.

### 5.1 How a guide is modeled (stages + variants)

Your two structural notes are dead-on and change the data model — a guide isn't a flat document, it's a **staged progression with links**. Confirmed across all three of your examples: Mobalytics uses six level brackets (1–14, 15–23, 24–30, 31–41, 42–59, 60+), poe-vault is organized act-by-act (Act 1 → 2 → 3 → 4+) with the Trial milestones as turning points. So a guide is stored as:

- **An ordered list of stages**, each keyed by a level range and/or act, and each carrying its own gems, gear targets, and passive-tree state. "The guide" is never one blob — it's "what this guide says *at level 28*."
- **Variant links** — a leveling guide points to its endgame version (Mobalytics's leveling page links straight to `ice-shot-deadeye`). The tool tracks both and knows they're the same build at different phases, so it can say "you're near the end of the leveling guide — here's the endgame variant to switch to."
- **Milestone hooks** — stage transitions often coincide with Trials (poe-vault swaps to full minion play after the Act 3 Trial of Chaos). These hooks tie the guide model to the trials-advisor (F4) and to detecting your progression stage.

**The payoff (an emergent feature worth calling out):** because the character read (PoB code, screenshot, or description) gives us your **level**, the tool can auto-select the right stage for you — "you're level 28, so here's your 24–30 gear/gem targets, and here's exactly what changes when you hit 31." You never have to figure out which tab of the guide applies; it meets you where your character actually is. This falls out for free once we combine the staged guide model with the character data, and it's a much better experience than handing someone a wall of tabs.

---

## 6. Confidence, done properly (senior-engineer pushback)

You asked for a confidence rating on every answer. The trap: an LLM saying "I'm 85% confident" is usually just vibes — models are famously miscalibrated and will produce a confident-sounding number with no grounding. If we do it naively, the confidence score is worse than useless because it *looks* trustworthy.

So we ground confidence in **observable signals**, not the model's feelings. Each skill computes a confidence band from concrete inputs:

- **Data freshness** — how old is the price data? (poe2scout caches ~5 min; stale = lower.)
- **Sample size** — how many comparable listings did we find? 40 listings = high; 2 = low; 0 = we're extrapolating, flag it loudly.
- **Input certainty** — do we have your *actual* character/currency, or are we assuming?
- **Source agreement** — do two price sources agree? *Not available: only poe2scout is integrated
  (poe.ninja never was), so the rubric doesn't claim agreement.*
- **Knowledge recency** — for trials/meta, is our knowledge file current with the live patch, or possibly stale?

Output format for every answer: a band (**High / Medium / Low**), plus a one-line *why* ("Medium — only 3 listings matched and prices ranged 2×"). That way the confidence is auditable and actually means something. This rubric lives in the shared `poe2-core` reference so all skills score the same way.

**Built (Oct 2026):** the tools return the signals as fields, so skills score from numbers rather
than eyeballing listings — `search_trade` returns `priceStats` (listings converted to exalted via
poe2scout rates: count, min/median/max, spread ratio, unconvertable currencies) and the real match
count; every market tool returns `fetchedAt`/`ageSeconds` (oldest input wins); currency returns
`quantityListed`. The thresholds that map fields → bands live in one table in
`poe2-core/references/confidence.md` (band = weakest signal). They are first-guess defaults — tune
them from real use.

---

## 7. Beginner-friendly by default (progressive disclosure)

**Requirement:** never assume the player knows the jargon or how to get the data we ask for. A newer player doesn't know what a "PoB code" is, how to export one, which tab to screenshot, or what "cap your resists" means. The tool has to meet them where they are — without drowning experienced players in tutorials.

**How we do it — three layers, so help scales to the person:**

1. **Every ask carries a one-line "how" hint.** When the tool needs something, the ask includes a short parenthetical on how to get it — e.g. *"Paste your build's PoB code (in Path of Building, click **Import/Export → Generate** and copy the code — or just say 'how?' and I'll walk you through it)."* Short enough that a veteran ignores it, present enough that a beginner isn't stuck.

2. **"How do I get that for you?" is always answered.** At any point the player can ask "how do I get that?" / "what's a PoB code?" / "which tab?" and the skill gives clear, current, step-by-step instructions with the exact clicks. These live as a shared **how-to reference in `poe2-core`** so every skill answers consistently. Core how-tos to cover: exporting a PoB code, copying an item in-game (Ctrl+C on hover), screenshotting a currency/crafting tab, finding your character on the trade site, and finding a build guide.

3. **Experience level tunes verbosity automatically.** Onboarding gauges whether jargon is familiar (§4.1) and stores it. Newer players get terms defined inline and more how-to offered proactively; experienced players get terse asks. The player can change this any time ("stop explaining basics" / "explain more").

**Design guardrails so this doesn't backfire:**
- **Plain language first, jargon second.** Say "your cold-damage skill" before "your primary skill gem," and define a term the first time it's used in a session.
- **Offer, don't force.** Hints and "ask me how" affordances are opt-in; the tool doesn't dump a wall of instructions unless asked or unless experience level says to.
- **Keep how-tos current.** Game UI changes across patches, so the how-to reference is part of the patch-churn maintenance (§10), not a write-once doc.
- **Confidence stays honest for beginners too.** If a newer player gives us fuzzy info, the answer says so (Low confidence + what would sharpen it) rather than pretending certainty.

This is cross-cutting: it applies to every skill, which is exactly why the how-to content and the experience-level flag live in `poe2-core` rather than being re-written per skill.

---

## 8. The skills (seven + a shared core)

1. `poe2-core` — shared game knowledge (currencies, mods, item text parsing) + the confidence rubric + the **how-to reference and experience-level handling** (§7).
2. `poe2-character` — roster lifecycle: onboard a new character, list, update, set active (§4.1). One skill, not one-per-action.
3. `poe2-price-check` — price any item, with confidence.
4. `poe2-gear-upgrade` — F1: weak-slot analysis + ranked market upgrades.
5. `poe2-build-review` — F2: your character vs. a guide.
6. `poe2-trials-advisor` — F4: Sekhemas/Chaos pick recommendations.
7. `poe2-currency-tracker` — F5: screenshot → parsed inventory (confirmed) + affordability.

Two things deliberately *not* separate skills: **trade-filter generation** (lives inside price-check/gear-upgrade) and **character switching** (a one-line state update inside `poe2-character`, plus per-request override). `poe2-meta-strategy` (league-start / what-to-farm) folds in later once the data layer is proven.

---

## 9. Phased delivery

**Phase 0 — Reuse-vs-build decision ✅ done (both spikes complete).**
- *Guide-fetch spike (§F3), re-verified Sep 2026:* poe-vault static-fetchable; Mobalytics Cloudflare-403
  (browser/paste); Maxroll reachable but license-prohibited for AI use (paste). `fetch_guide` gates and
  routes accordingly.
- *poe2scout coverage (read from source):* its API is a **price reference for currencies and unique items** (routes are all `/{realm}/Leagues/{league}/Currencies|Items|Uniques...` returning name/category/price/history). **There is no rare-item-by-affix search** — the `/Items` handler returns a flat list of currencies + uniques with a `CurrentPrice`, no stat filters.
- **Verdict:** *reuse* poe2scout for currency rates, unique prices, price history, and net-worth/economy; *build our own thin `/trade2` adapter* for rare-gear search + trade-filter generation, which poe2scout structurally cannot do. This is the split the rest of the build assumes.

**Phase 1 — First working loop. ✅ shipped.**
`poe2-core` (confidence rubric + how-to reference + currency glossary + experience-level handling, §7)
+ `poe2-price-check` + the `/trade2` adapter (`find_stat_filters` / `build_trade_filter` / `search_trade`).
Price-check and trade filters work in Claude, beginner-friendly, live-validated. Daily-useful.

**Phase 2 — Roster + currency + gear upgrade. ✅ built (minus OAuth, which is blocked).**
`poe2-character` (onboarding + roster + active-character state, §4.1), `poe2-currency-tracker` (F5,
screenshots) with the `value_currency` tool, and `poe2-gear-upgrade` (F1). The one v8 item that *can't*
be done: OAuth character import (`get_my_characters`) — GGG isn't issuing clients (§3), so character
reading is screenshot/description instead. It knows *you* — your roster, and your currency per league.

**Phase 3 — Guides + comparison + trials. ✅ built.**
`fetch_guide` (robots/license-aware, §F3), `poe2-build-review` (F2), `poe2-trials-advisor` (F4, with a
freshness-stamped trials knowledge file), and `parse_pob_code` (decode a PoB export into stats/gems/
gear, so a pasted code feeds gear-upgrade/build-review without a screenshot).

**Hardening pass (Sep–Oct 2026). ✅ done.**
- *Grounded confidence (F7):* `priceStats`, freshness, and the real `matched` count (above, §6);
  rubric thresholds in `confidence.md`, consumed by price-check, gear-upgrade, currency-tracker.
- *PoB parsing:* reads only the active skill set; splits item mods into `implicitMods` /
  `explicitMods`; **pobb.in links are not supported** — they hold an id, not the code, and resolving
  one would mean a network call from an offline tool, so a pasted link gets a clear "paste the code"
  error instead.
- *Client correctness:* trade2 stat index now refreshes with its 6h cache (it was stuck at first
  load); fetch cache keyed by hashes (a larger `limit` was served a smaller cached batch); `ttl=0`
  honored. Offline tests (httpx `MockTransport`, injected via `transport=`) cover caching,
  `resolve_league` fallback order, and rate-limit backoff.

**Remaining work, in rough priority order:**
1. **Passive tree from PoB** — build-review compares tree state against guide stages (§5.1), but
   `parse_pob_code` doesn't read `<Tree>` (or tree-socketed jewels) yet. Needs design.
2. **Currency trend** — poe2scout's `PriceLogs` (7 daily points) as a volatility signal for currency.
3. **League rotation** — `POE2_LEAGUE` is pinned per machine; a new league fails loudly ("not found")
   until it's updated. Fine, but worth a reminder in the onboarding flow.
4. **Phase 4 — meta.** `poe2-meta-strategy`. "Replace weak reused plumbing" is moot: the reused
   pieces (poe2scout) held up.

---

## 10. Risks & open questions

- **No stash API (F5)** — accepted; screenshot parsing into remembered state is the design. Vision misreads are caught by the confirm-before-save step. If GGG ever ships a stash API, currency tracking becomes automatic with no rework to the skill interface.
- **OAuth character read is blocked (F1/F2).** GGG isn't issuing new API clients ("unable to process
  new applications"), and discourages third-party tools. Character reading is screenshot/description
  instead (§3). Not an open risk — a known constraint with a working path; upgrades transparently if
  registration reopens (request parked in `docs/ggg-oauth-application.md`).
- **Guide access is site-specific (F3) and shifts over time.** Re-verified Sep 2026: poe-vault fetches
  static; **Mobalytics now Cloudflare-403s** plain fetches; **Maxroll's license (Ziff Davis) prohibits
  automated/AI use**, so we refuse it. `fetch_guide` gates on robots + licenses and returns a route
  (browser/paste) when it won't fetch. No single "fetch a guide" solution — it's the tiered approach in
  §F3 (PoB code > static fetch > browser read > paste). Expect this to drift with site changes.
- **`/trade2` is unofficial & rate-limited (F6)** — cache hard, never auto-purchase, treat it as read-only filter generation. Your account safety comes first.
- **Confidence calibration (F7)** — grounded in signals, not model vibes (§6), and now built on tool
  fields. Remaining risk: the band thresholds are guesses until checked against real trades.
- **Patch churn** — trials contents, currencies, meta, *and the game UI in the how-to steps* shift per patch. `poe2-core` (knowledge + how-to reference) and the trials knowledge need scheduled refreshes. Plan for maintenance.

**Resolved:** test set = Ice Shot Deadeye + minion gear; character reading is screenshot/description
(OAuth blocked, §3), screenshots also for currency; multi-character roster + onboarding are core (§4.1);
guide fetch is robots/license-aware and re-verified (§F3). Guides are modeled as staged progressions
with variant links (§5.1).

**Open:** how to model the passive tree for build-review (§9, remaining work #1).

---

## 11. Recommendation

**Skills first, against a reused MCP, value in days.** Sequence by usefulness — price-check + trade-filter loop (F6) first because you'll use it every session, then character-aware gear analysis across your roster (F1/F2), then guides and trials (F3/F4). Character data comes from screenshots/description (OAuth blocked, §3); screenshots also cover currency. Multi-character onboarding is built in from Phase 2, not retrofitted. Confidence gets engineered as a grounded signal from day one, not bolted on as a vibe. And the whole thing is beginner-friendly by default (§7) — plain language, "how do I get that?" always answered, verbosity tuned to the player — because a tool that assumes you already know the jargon isn't much help to the people who need it most.
