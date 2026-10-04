---
name: poe2-character
description: Manage the player's Path of Exile 2 character roster — onboard a new character, list characters, update a build, and set which one is active. Use when the player starts a new character, switches characters, or first uses the assistant.
argument-hint: "[new]"
---
# poe2-character

Load `poe2-core` first. This one skill owns the whole roster lifecycle — onboard, list, update, and set
active — so the other skills always know *who* they're working on and *what* their build is trying to
do. Switching the active character is a state update here, **not** a separate skill.

## State model

Two things live in memory (see the shared model in `poe2-core`):

```
player = { experience_level }            # account-level; tunes verbosity (poe2-core §7). Set once.

characters = [ {
  name,                 # character name (the id)
  league,              # which league they're in -> ties to currency[league]
  clazz, ascendancy,   # e.g. Ranger / Deadeye
  archetype,           # the build in plain words, e.g. "Ice Shot Deadeye", "minion army"
  goal,                # bossing | mapping | league-start | leveling | ...
  guide,               # optional: a guide link or PoB reference
  build_source,        # how we read the actual gear/skills: "screenshot" | "description" | "pob"
  build_snapshot,      # optional: the last screenshot read / pasted build, for gear-upgrade/build-review
  active,              # exactly one character is active at a time
  created_at, updated_at
} ]
```

Currency is **league-scoped, not character-scoped** — all characters in a league share one currency
pool (`poe2-currency-tracker`). Don't attach currency to a character.

## First-run onboarding (interview, one question at a time)

The first time the player uses any poe2 skill with no roster yet, run the interview. Ask **one thing at
a time**, in plain language, and **write each answer to state as it comes in** (don't hold it all to the
end). Keep it short:

1. **Which character are we working on?** (name)
2. **What is it?** Class + ascendancy and the build in plain words ("Ice Shot Deadeye", "minion army").
   Fine if they only know some of it.
3. **What's the goal right now?** Bossing, mapping, league-start, just leveling?
4. **Following a guide?** If yes, take the link or PoB reference (optional).
5. **Which league?** (so currency and trade prices resolve correctly). Check the answer against
   `get_leagues` and store the exact league name it lists. If their league isn't marked `current`, or
   a newer league is, say so: temp leagues end and fold into Standard, and the tools default to the
   league pinned in `POE2_LEAGUE` — see "League rotation" in `poe2-core`.
6. **How should I read your gear when we need it?** See "Reading a build" below.

Set this first character **active**. Then confirm the profile back in one line.

**Experience level (first onboarding only, account-level):** early on, gauge whether jargon is
familiar — e.g. "Are terms like *PoB*, *exalt*, *resist cap* familiar, or should I explain as I go?"
Store `experience_level`; `poe2-core` uses it to tune verbosity. The player can change it any time
("stop explaining basics" / "explain more").

**Each new character** triggers a *short* version (steps 1–6); experience level is already set, so skip
it. **`/poe2-character new`** goes straight to this short interview, without asking what the player
wants to do first. If the league is already known — e.g. handed over by `poe2-new-league` — skip
step 5. When it's done, set the new character active and say which one it replaced.

## Reading a build (what actually works today)

Gear/skill reading feeds `poe2-gear-upgrade` and `poe2-build-review`. Order of preference:

- **PoB code** — best fidelity. `parse_pob_code` (MCP) decodes a Path of Building 2 export code into
  computed stats (resistances, life/ES, DPS), gems, and equipped items. Prefer this when the player
  has a PoB open. It takes the code itself, not a pobb.in share link — if they paste a link, ask them
  to copy the code from that page. Record `build_source: "pob"` and the parsed summary.
- **Character screenshot** — the player screenshots their character/inventory panel; vision reads it.
  Good when there's no PoB.
- **Plain description** — "level 84 Deadeye, Ice Shot, resists capped, ~2.4k life" — lowest fidelity,
  fine to start.

**Note on OAuth:** the official character API would read gear automatically, but **GGG isn't issuing new
API keys** right now, so there's no auto-import — PoB/screenshot/description are the path. If
registration reopens, this upgrades transparently (see `docs/ggg-oauth-application.md`).

## Listing, updating, switching

- **List** the roster on request: name, class/archetype, goal, league, and which is active.
- **Update** a build: re-take a screenshot or edit goal/guide/archetype; bump `updated_at`.
- **Set active** — a one-line state update ("work on my Deadeye now"). Exactly one active at a time.
- **Per-request override** — "check my *minion build's* boots" names a character inline for that one
  answer **without** changing the default active. This plus a default active is the whole of "switching"
  — deliberately not its own skill.

## Guardrails

- The active character is the **tool's** context only. It does **not** and cannot reflect who the player
  is logged in as in-game (no API for that) — never imply it does.
- Ask, don't assume: if a request is ambiguous about which character, and there's more than one, ask or
  use the active one and say which you used.
- Beginner-friendly: if the player doesn't know a term ("what's a PoB code?"), answer from
  `poe2-core/references/how-to.md`. One question at a time; never dump the whole interview at once.
