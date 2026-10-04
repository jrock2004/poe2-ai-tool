---
name: poe2-build-switch
description: Decide whether the player's Path of Exile 2 character is ready to switch from a guide's leveling version to its mid- or endgame version, and what has to happen first. Use when the player asks "when should I switch to the endgame build", "am I ready to swap", "should I respec into the mapping version", or is following a guide with separate leveling and endgame variants.
---
# poe2-build-switch

Load `poe2-core` first. One question: **is this character ready to move to the guide's next variant
(leveling → mid-game → endgame), and if not, what's in the way?** The answer is a readiness verdict
and an ordered plan, not a fix list.

This is not `poe2-build-review`. A leveling character compared to the endgame variant is "deviated"
everywhere — that's expected, not a mistake. Here the target is the *next* variant, and the question
is what blocks the jump.

It composes: `poe2-build-review` §1–3 (get the guide, structure it into stages and variants, read the
character), `price_unique` / `poe2-price-check` (cost of what's missing), `poe2-currency-tracker`
(what's affordable), and hands off to `poe2-gear-upgrade` for the shopping.

## 1. Get both variants and the character

**Check for the character first, before reading any guide.** Without it there's no verdict, only a
summary of the guide. Use the active (or named) character from `poe2-character`. If there isn't one,
ask for it and the guide in **one** message — a PoB code (best) or a screenshot of gems, gear, and
tree, plus the guide URL if it wasn't given. If the player has no character yet, say this skill
needs one and stop.

Then follow `poe2-build-review` §1–3 — same fetch routes, same PoB-first preference, same character
read. You need **two** guide stages: the **last stage of the current variant** and the **first stage of the
variant they'd switch to**. A variant can be a separate guide (leveling → endgame) or a tab inside
one guide (non-crit → crit).

**If the guide doesn't link the next variant, stop and ask the player which build they're moving
to** — a URL or its PoB code. Some leveling guides only say "swap to another endgame build" and leave
the choice open; picking it is the player's call. Don't search for one or guess from the guide's
name. Nothing else in this skill runs until you have both.

Tabbed guides (e.g. Mobalytics) only show the selected tab's gems and tree in the page text. Read
each stage's tab specifically — on Mobalytics each tab has its own URL (`?…=activeVariantId,N`).

If the target variant is a **different base class**, stop: that's a new character, not a switch.
A different **Ascendancy of the same class** is a switch — since 0.5 it can be respecced (see §4).

**If the two stages nearly match** — same main skill, a gem or two and a few nodes apart — say so up
front: the switch is small, and the answer is a short list, not the full report below.

## 2. Find the switch point

**If the guide states one, use it.** Authors usually do: "swap once you have X and are in early maps",
"respec at level N after the third ascendancy". Switches inside an endgame guide are often gated on
gear instead ("get a good crit bow and quiver before swapping to crit"). Quote the condition (short),
and check the character against each part of it. The guide's stated condition wins over anything you infer in §3.

**If the guide doesn't state one, infer it** from the blockers in §3, and say plainly that the guide
doesn't give a switch point and this is your read. That inference caps confidence at **Medium**.

## 3. Check readiness

Diff the character against the target variant's first stage, and sort every gap into one of three
buckets:

- **Hard blockers** — the variant doesn't work without them. Typical ones:
  - a **build-enabling unique** or specific base/rune the variant is built around,
  - the **main skill or key support gems** (and gem level/quality if the guide says it matters),
  - **ascendancy points** (`ascendancyCount`) or **ascendancy choices** the variant depends on — fewer
    points usually means a Trial not done yet; hand off to `poe2-trials-advisor`,
  - a **level requirement** on any of the above.
- **Soft risks** — the switch works but leaves the character weaker somewhere. Above all: **defenses
  after the swap.** If the leveling setup's resistances, life, or ES come from items or tree paths
  the variant drops, work out where they land after the swap (as in `poe2-gear-upgrade` §3b). A swap
  that uncaps resistances is a soft risk to fix *first*, not a reason to block forever.
- **Fine to finish after** — notables, minor gear, and gem levels the variant wants eventually but
  that don't stop it working on day one. List the next few in order, not the whole gap.

Judge "doesn't work without" from the guide's own words where it says so ("this build requires X").
Where it doesn't, reason from what the main skill needs; say it's your judgment.

## 4. Cost the switch

- **Missing uniques** → `price_unique`. **Missing rares** → `poe2-price-check`'s trade flow.
- **Respec** — passive refunds cost gold, and nothing here reads gold. Estimate the number of points
  that change (compare `tree` blocks if both sides are PoB) and **ask** whether the player can cover
  it; don't guess their gold.
- **Ascendancy change** (same class, different Ascendancy) — refund the ascendancy points for gold
  (5× a passive-point refund), then re-run a Trial that grants the points held and re-ascend into
  the new one. Name both costs: the gold, and the Trial run (hand off to `poe2-trials-advisor`).
- **Affordability** — compare the total against `poe2-currency-tracker`'s inventory, if there is one.
  If not, give the total and ask.
- **SSF** — ask if it isn't clear. In SSF, missing uniques can't be bought: the blocker is "until it
  drops", and the plan should say what to keep doing in the meantime.

## 5. Answer

Lead with the verdict:

- **Ready** — no hard blockers, defenses hold after the swap.
- **Ready, but expensive** — no hard blockers, but the switch spends most of the player's currency.
  Say what they'd be giving up.
- **Not yet** — name the hard blockers, smallest first.

Then the **order of operations**: acquire blockers → fix soft risks → respec → finish the rest. Gear
that doesn't need the respec should be bought and put on first, so the character isn't left half-swapped
and dying. One clear "do this next".

If the verdict is "not yet", say what to keep doing on the current variant until then — the player
shouldn't stall waiting.

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — the guide states the switch point, both variants and the character are PoB-sourced, and
  every hard blocker is clear-cut.
- **Medium** — **the guide gives no switch point (§2, always capped here)**, a variant was only
  partially fetched, or the cost rests on `price_unique` (a reference price with no listing volume).
- **Low** — a stage was read from prose only (no tab detail or PoB), the character's gear or tree was
  guessed, or the cost is unknown
  (no inventory, gold not given). Name the one thing that would raise it.

The market thresholds in `confidence.md` also apply to the cost, and the band is capped by the weakest
signal.

## Guardrails

- **No next variant, no answer.** If the guide doesn't link one, ask the player — don't pick a build
  for them.
- **The guide's stated switch point wins.** Don't overrule the author with an inference.
- **Never call leveling-vs-endgame differences "deviations."** They're the point of the switch.
- **Never recommend a swap that leaves resistances uncapped** without the fix in the plan, ahead of
  the respec.
- **Don't guess gold or currency.** Ask.
- **Respect the guide-fetch routes** — same as `poe2-build-review`.
- Never buy, list, or whisper. Output is a verdict, a plan, and trade links the player acts on.
