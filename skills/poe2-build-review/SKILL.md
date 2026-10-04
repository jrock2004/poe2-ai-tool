---
name: poe2-build-review
description: Compare the player's Path of Exile 2 character to a build guide and produce a stage-aware, prioritized fix list. Use when the player wants to know how their skills/gear stack up against a guide they're following.
---
# poe2-build-review

Load `poe2-core` first. This skill answers "how do I stack up against the guide I'm following?" — it
reads the guide, reads the character, figures out **which stage of the guide the character is actually
at** (by level), and produces a diff that separates *"you've deviated from the plan"* from *"you're
just behind on gearing for your level."* Those two are very different advice and must not be conflated.

It composes: `fetch_guide` (get the guide), `poe2-character` (whose character + its level), and hands
off to `poe2-gear-upgrade` / `poe2-price-check` to actually acquire what's missing.

## 1. Get the guide

Take a guide URL, a PoB code, or pasted content. If a URL, call `fetch_guide(url)` and handle its
result honestly — it won't scrape around a block:

- **`fetched: true`** → use the text. If **`partial: true`**, some detail (gem/gear tables) loaded
  client-side and may be missing — say so, and offer to fill gaps from a pasted PoB code.
- **`route: "browser"`** (e.g. Mobalytics/Cloudflare) → the page can't be server-fetched; offer to read
  it in the player's own browser, or ask for the PoB code.
- **`route: "paste"`** (e.g. Maxroll — its license prohibits automated use) → ask the player to paste
  the guide's PoB code or its text. Don't try to fetch it another way.

Best fidelity always comes from the guide's **exported PoB code** — prefer it when offered.

## 2. Structure the guide into stages (the §5.1 model)

A guide is **not** one blob — it's an ordered progression. Structure what you got into:

- **Ordered stages**, each keyed by a level range and/or act (guides use brackets like 1–14, 15–23, …
  or Act 1→2→3), each carrying its own **gems/links, gear targets, and passive-tree state**.
- **Variant links** — a leveling guide usually points to its endgame version. Track both and that
  they're the same build at different phases.
- **Milestone hooks** — stage transitions often coincide with Trials (e.g. minion play comes online
  after the Act 3 Trial of Chaos). These tie into `poe2-trials-advisor` when it exists.

If the guide only gave you partial structure, review against what you *do* have and flag the gaps
rather than inventing stage targets.

## 3. Read the character and pick the stage

Resolve the character via `poe2-character` (active or named). Read it best-fidelity first: a **PoB
code** via `parse_pob_code` (clean level, stats, gems, gear), else a **screenshot or description**
(OAuth is unavailable). **The character's level is the key**: it auto-selects the stage. A PoB code is
especially handy here since both the guide and the character can be PoB-sourced and compared directly.

The payoff feature: "you're level 28 → here are your 24–30 gem/gear targets, and here's exactly what
changes when you hit 31." The player never has to figure out which tab of the guide applies. Also: if
they're near the end of the leveling guide, say the **endgame variant** exists and hand off to
`poe2-build-switch` for whether they're ready to move to it.

## 4. Produce the stage-aware diff

Compare the character to *its current stage's* targets and split findings into two clearly-labeled
buckets:

- **Deviated from the plan** — genuinely off-spec: a different main skill or support gem than the guide,
  a wrong/ineffective item choice, a passive path that doesn't match. This is a *correctness* issue.
- **Behind on gearing for your level** — right plan, just not there yet: a slot the guide wants upgraded
  that you haven't, resistances not yet capped, a gem you haven't leveled. This is a *progress* issue,
  not a mistake — say so, so the player doesn't panic-reroll.

Then a **priority-ordered fix list**, survivability first (uncapped resists, low life/ES) before damage
or convenience, consistent with `poe2-gear-upgrade`. One clear "do this next," not a wall.

### The passive tree

`parse_pob_code` returns a `tree` block. When both the character and the guide stage come from PoB
codes, compare the two blocks — this is the most precise part of the review:

- **Keystones** (`tree.keystones`) the guide has and the character lacks, or vice versa → **Deviated**.
  Keystones change how the build works; flag them first.
- **Ascendancy choices** (`tree.ascendancyChoices`) that differ — e.g. *Point Blank* where the guide
  takes *Far Shot* → **Deviated**. Name both options.
- **Fewer ascendancy points** (`ascendancyCount`) than the guide's stage → **Behind**: usually a Trial
  not done yet. Hand off to `poe2-trials-advisor`.
- **Notables** (`tree.notables`): if the character has spent about as many points (`passiveCount`) as
  the guide but holds different notables → **Deviated**. If they've simply spent fewer points →
  **Behind**; list the guide's next few notables in order, not the whole gap.
- **Socketed jewels** (`tree.jewels`) — compare like gear.

Don't work out "unspent points" from the character's level: available points also depend on quest
rewards, which nothing here reads. Compare `passiveCount` against the guide's PoB for the same stage.

When the guide is **prose only** (no PoB), match the notables and keystones it names against
`tree.notables` / `tree.keystones` by name. That's weaker — say the comparison is name-based.

If `tree.note` is set (no snapshot for that tree version), you only have node ids: compare the id
sets for how much overlaps, but don't claim which notables are missing. If the character and the
guide have different `treeVersion`s, node ids may not line up across patches — say so.

## 5. Hand off acquisition

For each fix that needs an item, hand off to `poe2-gear-upgrade` / `poe2-price-check` to turn it into a
real, budget-bounded `/trade2` search (using the player's currency as the ceiling). For gems/tree, say
where/how to get them. The player acts — never auto-buy or auto-whisper.

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — clear character read + a fully-fetched or PoB-sourced guide, stage unambiguous.
- **Medium** — partial guide (dynamic/paste gaps) or some character detail inferred.
- **Low** — guide only loosely known, or level/gear guessed. Name what would raise it (the guide's PoB
  code, a clearer character screenshot).

For the tree specifically: both sides from PoB with names available supports High; name-matching a
prose guide, or ids only (`tree.note` set), is Medium at best; mismatched `treeVersion`s is Low.

## Guardrails

- **Never conflate "deviated" with "behind."** Behind-on-gearing is normal progress, not a mistake.
- **Respect the guide-fetch routes.** If `fetch_guide` says paste/browser, ask — don't scrape around it.
- Survivability before damage in the fix list; one priority at a time.
- Never buy, list, or whisper. Output is a diff + advice + trade links the player acts on.
