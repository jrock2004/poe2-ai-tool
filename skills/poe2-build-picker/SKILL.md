---
name: poe2-build-picker
description: Help the player choose a Path of Exile 2 build to play — a shortlist of current guides from trusted creators that fit their playstyle, trade or SSF, and starting point. Use when the player asks "what should I play", "pick a build for me", "what's a good league starter", or has no guide when starting a character.
---
# poe2-build-picker

**Before any other tool call, invoke the `poe2-core` skill** with the Skill tool; its rules apply here
and aren't restated. One question: **what should the player play?** The answer is a shortlist of 2–3
current guides that fit them, each with why, and then the player picks — the skill never picks for them.
The pick goes to `poe2-character`, which starts the character from the guide.

Nothing here reads what other players play, so this skill never ranks by popularity or calls a build
"the strongest" or "meta". It matches guides to the player.

## 1. Ask what they want

One question at a time, as choices (`poe2-core` rule 6). Skip any the player already answered ("an SSF
minion build" answers two).

1. **Playstyle.** Build the choices from `poe2-core/references/sources.md` → "Build creators", one per
   "Good for" entry, plus **"Something else"**. If they're not sure, describe each choice in one plain
   line (minions: "an army fights for you while you stay back") and ask again.
2. **Trade or SSF.** Ask even when other characters have a `trade_mode` — a new character can differ.
3. **Fresh start, or a stash to draw on?** A fresh start needs a guide that levels from scratch; a
   stash can carry a build that wants a unique or currency early.

## 2. Find candidates from trusted creators

Take only the creators whose "Good for" matches the playstyle, and follow `sources.md`'s rules for
them.

- **Open each matching creator's build list** — the "Build list" link in `sources.md`, through
  `fetch_guide` and its routes as `poe2-build-review` §1 handles them. Pick the guides on it that fit
  the playstyle; a creator's list holds builds outside their "Good for" too. A Mobalytics list shows
  each guide's patch tag (`0.5.5 FR`), "Updated on" date, class and ascendancy, and tags like
  **Starter** (a league starter) and **End Game** — narrow by those before opening any guide. A
  title's "0.5" names the patch line; the tag is the exact patch.
- **A creator with no per-author list** (a site root in `sources.md`): don't hunt for their guides
  page by page. Give the player the site and the creator's channel from `sources.md`, and ask them to
  paste the guide they like.
- **Open each candidate guide** — at most five — the same way, and read:
  - the **patch** it states, against the league's patch (`get_state` → `leagues[league].patch`; if
    it isn't there, follow the shared model in `poe2-core`);
  - whether it **levels from scratch** (leveling stages or a "league starter" label) or starts from
    endgame gear;
  - whether it's a **twink build** (it assumes gear a fresh character won't have);
  - the **uniques it's built around** — the ones the guide calls required or build-enabling.

Don't search the web for guides, and don't open a creator's list outside the playstyle.

## 3. When no trusted creator fits

"Something else", or a playstyle no listed creator covers: say so plainly — no trusted creator covers
it yet — and offer choices:

- **"Show me what's popular"** → give the player `https://poe.ninja/poe2/builds` and say what to
  look at: pick their league, filter by class or skill, and see which ascendancies and skills people
  play. Ask them to come back with the build they like and its guide link — or its PoB code, which a
  character's page on poe.ninja exports for them to copy. **Never open, fetch, or search poe.ninja
  yourself** (`sources.md` → "Avoid"); the player looks.
- **"I have a guide in mind"** → take the link or PoB code and judge it as in §4: who wrote it (per
  `poe2-build-review` §1, "Who wrote it"), its patch, and its fit.
- **"Pick from what you cover"** → back to the playstyle choices.

## 4. The shortlist

Two or three guides, best fit first; on an equal fit, one on the league's patch goes ahead of one
that's behind. Each gets:

- the guide's name, its creator and what they're trusted for, and its stated patch;
- **why it fits** — one line tying it to the answers in §1;
- **the catch** — one line: what it asks of the player, or what could go wrong.

Flag, don't hide:

- **Patch behind** — the guide states an older patch than the league's: say it may predate this
  patch's changes, and lower confidence. No stated patch: say it's unknown.
- **Twink build** on a fresh start — leave it off the shortlist; name it as "for later" if it fits
  otherwise.
- **SSF and a build-enabling unique** — in SSF the build waits until it drops. Leave it off on a
  fresh SSF start; otherwise flag it.

Fewer than two fit? Say so and show what's left; don't pad the list. If nothing fits, go to §3.

**"What's the strongest build?"** — say nothing here can read what's strongest or most played, and
offer to pick by fit (§1). If they want to see what people play, give them the poe.ninja link as in §3.

## 5. Hand off

When the player picks, hand the guide to `poe2-character`: its onboarding (or `/poe2-character new`
for another character) takes the guide in step 2 and reads class and ascendancy from it. This skill
writes nothing to state itself.

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — every guide on the shortlist states the league's patch, comes from a creator trusted for
  that playstyle, and was read in full.
- **Medium** — a guide is a patch behind or doesn't state one, was only partly read, or its fit
  (SSF, fresh start) is your judgment rather than the guide's own words.
- **Low** — the build list couldn't be read and the candidates came only from titles, or the player's
  answers in §1 were guessed. Name the one thing that would raise it.

## Guardrails

- **The player picks.** A shortlist with reasons, never a single "play this".
- **Only listed creators' build lists, or what the player brings.** No web search for guides.
- **Never read poe.ninja's builds pages.** Give the player the link (§3).
- **No "best", "strongest" or "meta".** Nothing here measures it.
- **Respect the guide-fetch routes** — same as `poe2-build-review` §1. Don't solve a bot check.
- Trust covers a creator's "Good for" only (`sources.md`).
