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
- **`route: "browser"`** (e.g. Mobalytics/Cloudflare) → the page can't be server-fetched. Open it
  yourself in the browser you have (the client's built-in browser, Playwright, or Chrome) and read it
  there — the player doesn't need it open. If the page shows a bot check (CAPTCHA, "verify you are
  human"), **don't solve it**: ask the player to open the guide in their own browser, then read it
  from there, or take its PoB code.
- **`route: "paste"`** (e.g. Maxroll — its license prohibits automated use) → ask the player to paste
  the guide's PoB code or its text. Don't try to fetch it another way.

Best fidelity always comes from the guide's **exported PoB code** — prefer it when offered.

### Who wrote it

Check the guide against `poe2-core/references/sources.md` → "Build creators", following its rules.
Take the candidate from the author shown on the guide page; if it's a listed creator, confirm the
guide's URL is on their build list (open it in the browser if `fetch_guide` routes it there). Don't
open every creator's list looking for a match. A bare PoB code or pasted text with no author is
unknown unless the player says who made it.

Say it in one line at the top of the review, then move on:

- **Trusted, in scope** — "Guide by Fubgun — a trusted creator for bow builds."
- **Trusted, out of scope** — "Fubgun is trusted for bow builds; this isn't one, so it's judged like
  any other guide."
- **Unknown** — "Not from a trusted creator — judging it on its own."
- If the live patch is newer than the creator's "Last verified", add that their track record is from
  that patch.

Use the creator's **Notes** where they apply: e.g. "endgame variants are separate guides" means §3's
endgame hand-off should look for that guide on their build list, not inside this one; a twink build
assumes gear a fresh character won't have — say so before calling the player "behind".

Creator trust is about whether the guide is worth following, not how well this review matches the
character to it — it doesn't change the confidence band below.

## 2. Structure the guide into stages (the §5.1 model)

A guide is **not** one blob — it's an ordered progression. Structure it per
`poe2-core/references/guide-structure.md`: ordered stages with entry conditions, linked variants
joined into one list, and off-path tabs (reference gear, alternatives, situational setups) kept out
of the stages. Review only against stages — never mark a player "behind" on an off-path tab.

Stage transitions that coincide with Trials tie into `poe2-trials-advisor`.

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

`parse_pob_code` returns a `tree` block. A guide with no PoB but with node ids in its page (e.g.
Mobalytics — see `poe2-core/references/guide-structure.md`) gets the same block from
`summarize_tree`. When both the character and the guide stage have a tree block, compare the two —
this is the most precise part of the review:

- **Keystones** (`tree.keystones`) the guide has and the character lacks, or vice versa → **Deviated**.
  Keystones change how the build works; flag them first.
- **Ascendancy choices** (`tree.ascendancyChoices`) that differ — e.g. *Point Blank* where the guide
  takes *Far Shot* → **Deviated**. Name both options.
- **Fewer ascendancy points** (`ascendancyCount`) than the guide's stage → **Behind**: usually a Trial
  not done yet. Hand off to `poe2-trials-advisor`.
- **Notables** (`tree.notables`): if the character has spent about as many points (`passiveCount`) as
  the guide but holds different notables → **Deviated**. If they've simply spent fewer points →
  **Behind**; list the guide's next few notables in order, not the whole gap.
- **Socketed jewels** (`tree.jewels`) — compare like gear. A `summarize_tree` block has no jewels;
  take them from the guide's gear section instead.

Don't work out "unspent points" from the character's level: available points also depend on quest
rewards, which nothing here reads. Compare `passiveCount` against the guide's tree for the same stage.

When the guide is **prose only** (no PoB, no node ids in the page), match the notables and keystones it names against
`tree.notables` / `tree.keystones` by name. That's weaker — say the comparison is name-based.

If `tree.note` is set (no snapshot for that tree version), you only have node ids: compare the id
sets for how much overlaps, but don't claim which notables are missing. If the character and the
guide have different `treeVersion`s, node ids may not line up across patches — say so.

## 5. Hand off acquisition

For each fix that needs an item, hand off to `poe2-gear-upgrade` / `poe2-price-check` to turn it into a
real, budget-bounded `/trade2` search (using the player's currency as the ceiling). For an SSF character
(`trade_mode`, see `poe2-core`), hand off to `poe2-gear-upgrade` only — it turns the fix into a craft or
farm route instead of a search. For gems/tree, say
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
- **Respect the guide-fetch routes.** "browser" means reading the page as a visitor would, in a real
  browser — never solving a bot check or working around one. "paste" means ask; don't fetch it any
  other way.
- Survivability before damage in the fix list; one priority at a time.
- Never buy, list, or whisper. Output is a diff + advice + trade links the player acts on.
