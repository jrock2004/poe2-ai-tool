---
name: poe2-new-league
description: Walk the player through starting a new Path of Exile 2 league — pick the league from get_leagues, point POE2_LEAGUE in .mcp.json at it, report which game-knowledge files the patch may have made stale, then hand off to onboarding the first character. Run when the player types /poe2-new-league.
disable-model-invocation: true
---
# poe2-new-league

Load `poe2-core` first. This is a **checklist**, run once per league start. It sets the one piece of
machine config that follows the league, tells the player what the patch may have made stale, and hands
off to `poe2-character` for the build itself. It does **not** refresh knowledge files, regenerate the
tree snapshot, or collect build guides — those belong to `CONTRIBUTING.md` and `poe2-character`.

Go one step at a time, and say which step you're on.

## 1. Pick the league

Call `get_leagues`. It doesn't depend on `POE2_LEAGUE`, so it works even while the config still names
last league.

Show the leagues marked `current` and ask which one the player is starting. **Don't pick for them from
`current` alone** — poe2scout marks softcore, hardcore, and event leagues current at once. Hardcore is
part of the league name they choose; SSF is **not** asked here — it's per character, and
`poe2-character` asks it.

Store the exact `league` value they choose, not the short name.

## 2. Point `POE2_LEAGUE` at it

`.mcp.json` sits at the repo root. It is git-ignored and machine-local: it holds this machine's absolute
path to `poe2-mcp`, so **never rewrite the file** — change only `mcpServers.poe2.env.POE2_LEAGUE`, and
add that key (and `env`) only if it's missing. Keep the rest byte-for-byte.

1. Read the file. Show the change in one line: `POE2_LEAGUE: "<old>" → "<new>"`.
2. Make the edit. Keep the file UTF-8 with `\n` line endings.
3. If `.mcp.json` doesn't exist, **don't create it** — the path inside it is machine-specific. Tell the
   player to run the setup script with the league (`scripts/setup.sh "<league>"`, or
   `scripts\setup.ps1 -League "<league>"` on Windows), which writes it.

Then say plainly: **the running MCP server still has the old league.** The new default applies after
the session restarts. Until then, pass `league="<new>"` explicitly on any tool call in this session.

If the player plays on more than one machine, remind them `.mcp.json` is per machine — each one needs
this step.

## 3. What the patch may have made stale

Report, don't fix. Each item points to its section of `CONTRIBUTING.md` → "Per-patch refresh".

- **Passive tree.** List the snapshots in `mcp/src/poe2_mcp/data/` (`tree_<version>.json`). Path of
  Building 2 usually ships the new tree days after league start, so there's normally nothing to check
  yet. Tell the player what to expect:
  > Until PoB2 ships the new tree, PoB-based reviews reflect last patch's tree — use screenshots or a
  > description for the campaign. The first PoB from the updated version will come back with
  > `tree.note` set; that's the signal to refresh the snapshot (CONTRIBUTING step 1).
- **Knowledge files.** Read the freshness stamp at the top of each and show it:
  - `skills/poe2-trials-advisor/references/trials-knowledge.md`
  - `skills/poe2-crafting/references/crafting-knowledge.md`
  - `skills/poe2-meta-strategy/references/farming-knowledge.md`

  Ask whether the patch notes touched Trials, crafting currencies or mod tiers, or league mechanics.
  For each yes, name the CONTRIBUTING step. If they haven't read the notes yet, say these files may be
  stale and that the skills built on them should be treated as last patch's knowledge until refreshed.
- **How-to steps** (`skills/poe2-core/references/how-to.md`) have no stamp; mention them only if the
  player says the game's or PoB's UI changed.

## 4. Existing state

- **Characters.** List any roster characters in the old league. Leave them as they are — when a temp
  league ends they move to Standard; the player can update them later with `poe2-character`.
- **Currency.** Leave the old league's inventory alone. Don't create an empty one for the new league —
  `poe2-currency-tracker` creates it on the first screenshot.

## 5. Hand off

Start `poe2-character`'s new-character interview for the first character of the league, with the league
already answered (the one from step 1). Build guide, goal, SSF, and how to read the build are all asked
there.

## Guardrails

- The only file this skill writes is `.mcp.json`, and only `POE2_LEAGUE` in it. Knowledge files and
  the tree snapshot are refreshed by following `CONTRIBUTING.md`, as a separate, reviewed change.
- Read-only toward GGG, like every poe2 skill.
- Beginner-friendly: if the player asks what a step means ("what's an MCP server?"), answer in a line
  and move on.
