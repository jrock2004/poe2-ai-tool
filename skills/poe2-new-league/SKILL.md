---
name: poe2-new-league
description: Walk the player through starting a new Path of Exile 2 league — pick the league from get_leagues, find its patch from the patch notes, point POE2_LEAGUE in .mcp.json at it, refresh the game knowledge the patch made stale, then hand off to onboarding the first character. Run when the player types /poe2-new-league.
disable-model-invocation: true
---
# poe2-new-league

Load `poe2-core` first. This is a **checklist**, run once per league start. It sets the one piece of
machine config that follows the league, reads the patch notes, refreshes the knowledge they made
stale, and hands off to `poe2-character` for the build itself. It does **not** regenerate the tree
snapshot or collect build guides — those belong to `CONTRIBUTING.md` and `poe2-character`.

Go one step at a time, and say which step you're on.

## 1. Pick the league

Call `get_leagues`. It doesn't depend on `POE2_LEAGUE`, so it works even while the config still names
last league.

Show the leagues marked `current` as choices and ask which one the player is starting. **Don't pick for them from
`current` alone** — poe2scout marks softcore, hardcore, and event leagues current at once. Hardcore is
part of the league name they choose; SSF is **not** asked here — it's per character, and
`poe2-character` asks it.

Store the exact `league` value they choose, not the short name.

Then find the **patch** the league launched with — `get_leagues` doesn't report it, so look it up:

1. Find the official PoE2 patch notes on pathofexile.com (the forum's patch-notes section) for the
   content update that launched this league. If the server fetch is blocked, open it in the browser; if
   that's blocked too, use poe2db's patch-notes page. The version is in the title, e.g. `0.6.0` — take
   the launch patch, not a later hotfix.
2. Confirm it as a choice: **"<version> (from the patch notes)"** first, and "Other" for the player to
   type one. If nothing turned up, ask for it directly, still offering "skip".

Store it with `update_state` as `leagues["<league>"].patch` (see the shared model in `poe2-core`); it's what tree lookups fall
back to when a guide doesn't say which patch it's for. Keep the patch notes you found — step 3 reads
them, along with any hotfix notes posted since.

## 2. Point `POE2_LEAGUE` at it

`.mcp.json` sits at the repo root. It is git-ignored and machine-local: it holds this machine's absolute
path to `poe2-mcp`, so **never rewrite the file** — change only `mcpServers.poe2.env.POE2_LEAGUE`, and
add that key (and `env`) only if it's missing. Keep the rest byte-for-byte.

1. Read the file. If `POE2_LEAGUE` already names the chosen league, say so in a line and move on.
2. Otherwise make the edit. Keep the file UTF-8 with `\n` line endings.
3. If `.mcp.json` doesn't exist, **don't create it** — the path inside it is machine-specific. Tell the
   player to run the setup script with the league (`scripts/setup.sh "<league>"`, or
   `scripts\setup.ps1 -League "<league>"` on Windows), which writes it.

Then tell the player to **restart Claude to finish switching leagues**. Until then, pass
`league="<new>"` explicitly on any tool call in this session — that's yours to handle, not theirs.

## 3. Refresh what the patch made stale

Use the patch notes from step 1, plus any hotfix notes posted since. Each item follows its section of
`CONTRIBUTING.md` → "Per-patch refresh" — its sources and rules (quote patch notes verbatim, no Maxroll,
no odds or drop rates) apply here as written.

- **Knowledge.** Call `get_knowledge` for each topic and read its `patch`/`refreshed`:
  - `trials` (CONTRIBUTING step 2)
  - `farming` (step 3)
  - `crafting` (step 4)

  For each, check whether the notes touch its area (the "Needed when" line of its step). If they do,
  refresh the text, set the header's `patch` to this patch and `refreshed` to today, re-stamp the prose
  stamp's date, patch, and sources, and call `save_knowledge` with the full text. If not, leave it alone.
  If `save_knowledge` refuses because the shipped copy is already as new, that topic is current —
  nothing to do.

  Tell the player in one line per topic what changed ("Trials: two new relics, Chaos afflictions
  reworded") or that it was unaffected. Saved refreshes are the player's own copy and survive updates;
  an update that ships newer knowledge takes over from them automatically.
- **How-to steps** (`skills/poe2-core/references/how-to.md`): refresh only if the notes change the
  game's UI it describes (CONTRIBUTING step 5).
- **Passive tree.** Not refreshable yet — Path of Building 2 ships the new tree days after league
  start. List the snapshots in `mcp/src/poe2_mcp/data/` for yourself; tell the player only what affects
  them:
  > Until Path of Building 2 updates for this patch, reviews from a PoB code reflect last patch's tree —
  > use screenshots or a description for the campaign.

  The first PoB from the updated version comes back with `tree.note` set; that's the signal for
  CONTRIBUTING step 1 (a maintainer task — don't attempt it here).

If the patch notes couldn't be found, say these skills are working from last patch's knowledge until
they can be refreshed, and lower confidence accordingly.

## 4. Existing state

- **Characters.** List any roster characters in the old league. Leave them as they are — when a temp
  league ends they move to Standard; the player can update them later with `poe2-character`.
- **Currency.** Leave the old league's inventory alone. Don't create an empty one for the new league —
  `poe2-currency-tracker` creates it on the first screenshot.

## 5. Hand off

Run `/poe2-character new` for the first character of the league, with the league already answered (the
one from step 1). The rest of the character questions are asked there.

## Guardrails

- The only file this skill writes is `.mcp.json` (only `POE2_LEAGUE` in it); knowledge refreshes in
  step 3 go through `save_knowledge`. It never stages or commits, and doesn't suggest `git` commands; the tree snapshot is left
  to `CONTRIBUTING.md`.
- Read-only toward GGG, like every poe2 skill.
- Beginner-friendly: if the player asks what a step means ("what's an MCP server?"), answer in a line
  and move on.
