---
name: poe2-new-league
description: Walk the player through starting a new Path of Exile 2 league — pick the league from get_leagues, find its patch from the patch notes, save it as the default league, refresh the game knowledge the patch made stale, then hand off to onboarding the first character. Run when the player types /poe2-new-league.
disable-model-invocation: true
---
# poe2-new-league

**Before any other tool call, invoke the `poe2-core` skill** with the Skill tool; its rules apply here
and aren't restated. This is a **checklist**, run once per league start. It saves the new league as the
default, reads the patch notes, refreshes the knowledge they made
stale, and hands off to `poe2-character` for the build itself. It does **not** regenerate the tree
snapshot or collect build guides — those belong to `CONTRIBUTING.md` and `poe2-character`.

Go one step at a time, and say which step you're on.

**Report only what changed or needs the player.** A step that found nothing to do gets no line of its
own. If the whole run changed nothing — league already saved, patch already recorded, knowledge
current — the summary is one line ("Forbidden Rites is set up and everything's current for 0.5.5d."),
then step 5's question. No per-topic list, no source links; keep confidence to a short clause.

## 1. Pick the league

Call `get_leagues`. It doesn't depend on the saved league, so it works even while that still names
last league.

Show the leagues marked `current` as choices and ask which one the player is starting. **Don't pick for them from
`current` alone** — poe2scout marks softcore, hardcore, and event leagues current at once. Hardcore is
part of the league name they choose; SSF is **not** asked here — it's per character, and
`poe2-character` asks it.

Store the exact `league` value they choose, not the short name.

Then find the **patch** the league launched with — `get_leagues` doesn't report it, so look it up:

1. Find the patch notes for the content update that launched this league, from the sources in
   `poe2-core/references/sources.md` → "Patch / hotfix notes": `patch_notes(kinds=["content"])` lists
   content updates, newest first, with the version in the title, e.g. `0.6.0`. Confirm the newest one
   is this league's with `patch_notes(version=<v>, sections=[<the league's name, without "HC">])`:
   it returns the lines under headings naming the league, and the update's `outline` — every heading
   with its line count. If no heading names the league, try the next content update down. Keep the
   outline; step 3 reads by it.
2. Confirm it as a choice: **"<version> (from the patch notes)"** first, and "Other" for the player to
   type one. If nothing turned up, ask for it directly, still offering "skip".

Store it with `update_state` as `leagues["<league>"].patch` (see the shared model in `poe2-core`); it's what tree lookups fall
back to when a guide doesn't say which patch it's for.

## 2. Make it the default league

Call `set_league` with the chosen league. It checks the name and saves it; every tool uses it from the
next call on — no restart. If it returns an error, the name didn't match `get_leagues`: go back to the
choice in step 1.

## 3. Refresh what the patch made stale

Use the patch notes from step 1, plus any hotfix notes posted since. Each item follows its section of
`CONTRIBUTING.md` → "Per-patch refresh" — its rules (quote patch notes verbatim, no odds or drop rates)
apply here as written, and `poe2-core/references/sources.md` says where to look.

**Never read a content update whole** — 0.5.0 runs to ~900 lines. Read it two ways, only for what
needs it:

- **By heading:** `patch_notes(version=<patch>, sections=[<words>])`, picking words from the step 1
  outline's own headings. A heading too long to need whole (Bug Fixes, Item Changes) is read by term
  instead.
- **By term:** one call for the lines under every other heading, and for every lettered patch and
  hotfix since: `patch_notes(since=<patch>, search=[<terms>])`. It includes the launch thread itself.
  `matched: 0` means a thread was read and nothing matched; a thread with `error` wasn't read — name
  it and lower confidence. A cold read takes a minute or two, so tell the player you're reading the
  notes first.

- **Knowledge.** Call `get_knowledge` for each topic and read its `patch`/`refreshed`:
  - `trials` (CONTRIBUTING step 2) — headings with "Trial" or "Sekhema"; terms "Trial", "Sekhema",
    "Honour", "relic", "affliction", "boon"
  - `farming` (step 3) — headings naming a mechanic (Breach, Delirium, Ritual, Expedition, Abyss),
    "Endgame", "Atlas", "League"; terms "Tablet", "Breach", "Delirium", "Ritual", "Expedition",
    "Abyss", "Splinter"
  - `crafting` (step 4) — headings with "Crafting" or "Currency"; terms "Divine", "corrupt", "affix",
    "modifier level", "Greater", "Perfect"

  A topic's `patch` says how far its notes were read; `patch_notes(since=<patch>)` lists the threads
  since launch, and hotfixes carry their base version ("0.5.5 Hotfix 3" is 0.5.5).
  - Stamped with the newest listed version or later: current — read nothing for it.
  - Stamped this patch or later, but older than the newest (0.5.5c when 0.5.5e is out): only its
    terms, in a by-term call from the version after its stamp.
  - Older than this patch: its headings, and its terms in the by-term call.

  Gather the terms of every topic that reads from the same version into one call. Then check whether
  the lines touch the topic's area (the "Needed when" line of its step). If they do, refresh the
  text, set the header's `patch` to the newest version you read and `refreshed` to today, re-stamp
  the prose stamp's date, patch, and sources, and call `save_knowledge` with the full text. If not,
  leave it alone.
  If `save_knowledge` refuses because the shipped copy is already as new, that topic is current —
  nothing to do.

  Tell the player one line per topic that changed ("Trials: two new relics, Chaos afflictions
  reworded"); say nothing about unaffected topics. If anything was saved, add once: these refreshes are
  the player's own copy and survive updates; an update that ships newer knowledge takes over from them
  automatically.
- **How-to steps.** They ship with plugin updates; the player can't refresh them. If the notes change
  the game UI they describe (menus, the export flow, hotkeys), tell the player those steps may be out
  of date until an update. The outline's "User Interface" heading is where they'd be.
- **Stash-tab layouts.** Also shipped with updates. Call `get_stash_layout("currency")`; if its
  `patch` is older than this patch, tell the player stash screenshots may name a slot wrong until an
  update, so they should check any line that looks off.
- **Passive tree.** The player can't refresh it; tree data ships with plugin updates. Check whether
  this patch's tree is in: call `summarize_tree` with an empty `main` and the patch's tree version
  (its first two numbers, e.g. `"0.6.0"` → `"0_6"`). If `note` is null, it's in — nothing to say. If
  `note` is set, tell the player:
  > I don't have this patch's passive tree yet, so tree comparisons will show passive ids instead of
  > names until an update brings it (`claude plugin update poe2@poe2-ai-tool`, then restart Claude).
  > If Path of Building hasn't updated for this patch either, a PoB code still holds last patch's
  > tree, and its life and resistance totals can be off.

  Making the tree is a maintainer task (CONTRIBUTING step 1, which can work from GGG's own export
  before Path of Building ships) — don't attempt it here.

If the patch notes couldn't be found, say these skills are working from last patch's knowledge until
they can be refreshed, and lower confidence accordingly.

## 4. Existing state

- **Characters.** List any roster characters in the old league. Leave them as they are — when a temp
  league ends they move to Standard; the player can update them later with `poe2-character`.
- **Catch-up.** If roster characters are from an earlier release — their league's recorded patch has
  different first two numbers from this one's (0.4.x before 0.5.x) — offer as a choice: "Catch me up
  on what changed" (runs `poe2-whats-new` from that league) or "Skip".
- **Currency.** Leave the old league's inventory alone. Don't create an empty one for the new league —
  `poe2-currency-tracker` creates it on the first screenshot.

## 5. Hand off

If the roster has no character in this league, run `/poe2-character new` for the league's first
character, with the league already answered (the one from step 1). The rest of the character questions
are asked there.

If it already has one or more, ask as a choice instead of in prose: **"Start a new character"** first,
then **"Keep working on <name>"** for each existing character in this league (the active one first).
- *Start a new character* → `/poe2-character new` as above.
- *Keep working on <name>* → if it isn't active, make it active (`poe2-character` → "Set active", which
  also moves the default league); then you're done.

## Guardrails

- It writes nothing directly: the league goes through `set_league`, the patch through `update_state`,
  and knowledge refreshes through `save_knowledge`. It never stages or commits, and doesn't suggest `git` commands; the tree snapshot is left
  to `CONTRIBUTING.md`.
- Read-only toward GGG, like every poe2 skill.
- Beginner-friendly: if the player asks what a step means ("what's an MCP server?"), answer in a line
  and move on.
