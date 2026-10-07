---
name: poe2-whats-new
description: Catch a returning Path of Exile 2 player up on what changed since they last played — the biggest changes, and every patch-note line about their own build — from the official patch notes. Use when the player asks "what changed since I last played", "I'm back after <league>", "what's new in <patch>", or "is my <build> still good after the patches".
---
# poe2-whats-new

Load `poe2-core` first. A returning player wants to know what changed while they were away — above all,
whether their build still works. This answers from the official patch notes only: quoted, with the
patch, never from memory or a community summary.

It doesn't set up a league; `/poe2-new-league` does that, and this points to it at the end.

## 1. When they last played

- **From the roster.** Characters in leagues `get_leagues` no longer marks `current` show where the
  player was. Use the newest of those leagues; its recorded `leagues[<league>].patch` (the shared model
  in `poe2-core`) is the patch they last played. If you can't tell which league is newest, ask.
- **Otherwise ask, as a choice:** the leagues `get_leagues` doesn't mark `current`, leaving out Standard
  and Hardcore (they never end), plus "Earlier than these / not sure".
- **Pin the patch.** With no recorded patch, find the content update that launched that league — its
  patch notes name the league. If it can't be pinned, ask for the version, offering "not sure", and say
  the catch-up starts from a guess.

The current patch is the newest content update in the official notes.

## 2. What they played

- **From the roster:** that league's character — class, ascendancy, archetype, guide. Several? Ask
  which, as a choice.
- **Otherwise ask once:** "What were you playing? Class and main skill is enough — or paste a PoB code."
  From a PoB code (`parse_pob_code`), take the main skill and its supports, the ascendancy, keystones,
  and equipped uniques.

From that, list the build's terms to look for: the main skill, its key supports, the ascendancy, key
uniques and keystones — about ten at most.

## 3. Read the patch notes

From the official PoE2 patch notes (`poe2-core/references/sources.md` → "Patch / hotfix notes"). The
forum lists threads newest first, 30 to a page; page back (`…/page/2`, `…/page/3`) until you reach the
patch they last played.

- **Content updates** — threads titled `<version> Patch Notes` with no letter, x.y.0 and point
  releases alike (0.4.0, 0.5.5): read each for its headline changes and every line naming one of the
  build's terms.
- **Lettered patches and hotfixes** ("0.5.5b Patch Notes", "0.5.5 Hotfix 3"): scan them for the
  build's terms only.
- **Quote, don't paraphrase,** every line you'll show about the build, and keep its patch and link.
- **Renames and removals** are in the notes. Search for the old name too, and say so if a skill was
  renamed, merged, or removed.

If the server fetch is blocked, open the page in the browser; if that's blocked too, use the fallback
source.

## 4. Answer

One message, short:

1. **What changed** — the 3–6 biggest changes across the gap (new classes or ascendancies, the
   campaign, the endgame, crafting, trading), one line each, with its patch. For a long gap, the
   biggest one or two per major release.
2. **Your build** — the quoted lines, grouped by patch, each with its link. Call a change a buff or a
   nerf only where the quoted numbers show it; for anything bigger, use the notes' own word
   ("reworked"). If nothing names the build: "The patch notes don't mention <skill>. That isn't proof
   it's unchanged — passive tree and support gem changes still affect it."
3. **What to do first** — two or three of:
   - re-import the character into Path of Building once it's updated for this patch (how-to: "Get your
     character into Path of Building");
   - if they followed a guide, check whether its creator has an updated one (`sources.md` → "Build
     creators"), or find a new one;
   - `/poe2-new-league` to set up the current league.
4. **Old characters** — see 5.

End with confidence (below).

## 5. Old characters

For roster characters in leagues that have ended, ask once, as a choice — per character when there are
a few, for all of them together when there are many:

- **"Keep as a record"** — nothing changes; it's still there to see how they built it.
- **"Remove from the roster"** — `update_state` with `{"characters": {"<name>": null}}`.

Don't move them to Standard unless the player asks: most returning players start fresh.

## Confidence (per `poe2-core/references/confidence.md`)

- **High** — every content update in the gap was read from the official notes, and the build is known.
- **Medium** — a patch was read only from the fallback, or the build is only partly known (a class, no
  skills).
- **Low** — a patch's notes couldn't be found, or the last-played patch is a guess. Say which.

## Guardrails

- **Official notes only** (or the fallback, per `sources.md`) — never memory, a video, or a community
  summary.
- **"Not mentioned" never means "unchanged."**
- **Quote the build lines;** summarize only the headlines, and always name the patch.
- **No tier lists or "the meta."** Whether a build is strong now isn't in the patch notes — point to the
  guide's creator instead.
- Read-only: the roster changes only when the player picks "Remove from the roster".
- Beginner-friendly, per `poe2-core`: a new system gets a one-line explanation.
