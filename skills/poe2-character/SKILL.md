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
  league,              # which league they're in (the trade league's name, even for SSF)
  trade_mode,          # "trade" | "ssf" -> with league, picks the currency pool (poe2-core)
  clazz, ascendancy,   # e.g. Ranger / Deadeye
  archetype,           # the build in plain words, e.g. "Ice Shot Deadeye", "minion army"
  goal,                # bossing | mapping | league-start | leveling | ... (new characters: leveling)
  guide,               # optional: a guide link or PoB reference
  build_source,        # how we read the actual gear/skills: "screenshot" | "description" | "pob"
  build_snapshot,      # optional: the last screenshot read / pasted build, for gear-upgrade/build-review
  active,              # exactly one character is active at a time
  created_at, updated_at
} ]
```

Currency is **pooled by league + trade mode, not by character** — all trade characters in a league
share one pool, and all SSF characters in it share another (`poe2-currency-tracker`). Don't attach
currency to a character.

## First-run onboarding (interview, one question at a time)

The first time the player uses any poe2 skill with no roster yet, run the interview. Ask **one thing at
a time**, in plain language, and **write each answer to state as it comes in** (don't hold it all to the
end). Keep it short:

1. **Which character are we working on?** (name)
2. **Following a guide?** Choices: "Yes — I'll paste a link or PoB code" / "No". If yes, take it and
   read class, ascendancy, and archetype from it (`fetch_guide` / `parse_pob_code`, handling routes as
   `poe2-build-review` §1 does). Confirm them in one line ("Ice Shot Deadeye — right?") and store the
   guide.
3. **What is it?** Only if there's no guide, or the guide didn't say: class + ascendancy and the build
   in plain words ("Ice Shot Deadeye", "minion army"). Fine if they only know some of it.
4. **Which league?** (so currency and trade prices resolve correctly). Offer the leagues `get_leagues`
   marks `current` as choices and store the exact league name it lists. If they name one that isn't
   `current`, say so: temp leagues end and fold into Standard, and the tools default to the league
   pinned in `POE2_LEAGUE` — see "League rotation" in `poe2-core`.
5. **Trade or SSF?** Choices: "Trade" / "SSF (Solo Self-Found)". Store `trade_mode`. It decides whether
   advice can say "buy it", and which currency pool is theirs.
6. **First character this league?** Ask only when state can't tell — no other roster character in this
   league + trade mode, and no currency pool for it. Choices: "Yes, fresh start" / "No, I have currency
   or gear stashed". This isn't stored; it picks the next tip:
   - **Fresh start** → a line of league-start advice suited to the build (what to pick up early).
   - **Has a stash** → offer to read a currency-tab screenshot (`poe2-currency-tracker`) and to check
     the stash for leveling uniques or gear worth handing to the new character.
7. **How should I read your gear when we need it?** Choices, from "Reading a build" below, with
   "Character screenshot" recommended during the campaign.

Don't ask for a goal: a new character's `goal` starts as `leveling`. Ask for it later, when it starts to
matter — see "Listing, updating, switching".

Set this first character **active**. Then confirm the profile back in one line.

**Experience level (first onboarding only, account-level):** early on, gauge whether jargon is
familiar — e.g. "Are terms like *PoB*, *exalt*, *resist cap* familiar, or should I explain as I go?"
Store `experience_level`; `poe2-core` uses it to tune verbosity. The player can change it any time
("stop explaining basics" / "explain more").

**Each new character** triggers a *short* version (steps 1–7); experience level is already set, so skip
it. **`/poe2-character new`** goes straight to this short interview, without asking what the player
wants to do first. If the league is already known — e.g. handed over by `poe2-new-league` — skip
step 4. When it's done, set the new character active and say which one it replaced.

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

- **List** the roster on request: name, class/archetype, goal, league, trade or SSF, and which is
  active.
- **Update** a build: re-take a screenshot or edit goal/guide/archetype; bump `updated_at`.
- **Goal past leveling** — when a character with `goal: leveling` has clearly finished the campaign
  (maps, endgame gear, a build-switch question), ask once as a choice — bossing, mapping, or something
  else — and store it.
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
