---
name: poe2-whats-new
description: Catch a returning Path of Exile 2 player up on what changed since they last played — the biggest changes, and every patch-note line about their own build — from the official patch notes. Use when the player asks "what changed since I last played", "I'm back after <league>", "what's new in <patch>", or "is my <build> still good after the patches".
model: sonnet
---
# poe2-whats-new

**Before any other tool call, invoke the `poe2-core` skill** with the Skill tool; its rules apply here
and aren't restated. A returning player wants to know what changed while they were away — above all,
what changed for their build. This answers from the official patch notes only: quoted, with the
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

With `patch_notes` (`poe2-core/references/sources.md` → "Patch / hotfix notes" says what to do if it
fails).

- **The threads in the gap:** `patch_notes(since=<the patch they last played>)` — every thread from
  that patch to now. Each has a `kind`: content updates (x.y.0 and point releases alike, 0.5.0 and
  0.5.5), lettered patches (0.5.5b), hotfixes. The content update they last played is what they already
  had: leave it out of both the headlines and the build lines. Its lettered patches and hotfixes stay
  in — you can't tell how far into that league they played; say so in confidence.
- **Headlines** — for each content update in the gap, `patch_notes(version=<v>, sections=[<the
  thread's title>])`: the `outline` lists its sections, and its title's section is the overview; read a
  section in full with `sections` when a headline needs it. Never read a content update whole — 0.5.0
  runs to ~900 lines.
- **Build lines** — one call for the whole gap: `patch_notes(since=<the patch they last played>,
  search=<the build's terms>)`. Every thread comes back with its matching `lines`; `matched: 0` means
  it was read and nothing named the build, and a thread with `error` wasn't read — name it, and lower
  confidence. A cold read takes a minute or two, so tell the player you're reading the notes first.
- **Quote, don't paraphrase,** every line you'll show about the build — its `text` exactly — and keep
  its patch and the thread's `url`.
- **Renames and removals** are in the notes. Search for the old name too, and say so if a skill was
  renamed, merged, or removed.

## 4. Answer

One message, short. The notes say what changed, never how good the build is now, so give no verdict
of your own — not at the top, not on the build, not on one part of it: no "barely touched", "still
works", "mostly nerfs", "no changes to <ascendancy>". When the player asks whether it's still good,
the first line says the patch notes can't tell, and step 3 points to who can.

1. **What changed** — the 3–6 biggest changes across the gap (new classes or ascendancies, the
   campaign, the endgame, crafting, trading), one line each, with its patch. A long gap — one that
   spans more than one x.y.0 release (0.3.x to 0.5.x) — gets the biggest one or two per x.y.0 release
   instead.
2. **Your build** — the quoted lines, grouped by patch, each with its link.
   - Each line is the notes' own text in quotation marks, whole. No paraphrase inside, around or
     instead of a quote. Only if a line came from the fallback cut off: end it in "…" where it was cut,
     followed by "(full line in the notes)"; never finish it from memory.
   - Call a change a buff or a nerf only where the text inside your quote shows both values — not a
     value from the cut-off part, or from your own reading. Otherwise use the notes' own word
     ("reworked") or none. Put the label straight after its quote; don't restate the change in your
     own words, there or in a summary. Don't say what a line does to damage, or any effect it doesn't
     state.
   - Each build term no line names gets: "The patch notes don't mention <term>. That isn't proof it's
     unchanged — passive tree and support gem changes still affect it."
   A quoted line that names a rune, soul core, idol or augment: before you explain it, Read
   `poe2-core/references/currency-glossary.md` → "Socketables" and take its kind and where it's kept
   from there. They are not kept in the currency tab.
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
- Beginner-friendly, per `poe2-core`: a new system gets a one-line explanation, taken from the notes or
  `poe2-core/references/`, not memory.
