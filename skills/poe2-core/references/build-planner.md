# The in-game Build Planner

`write_build_plan` turns a guide's PoB code into plans for the game's Build Planner: one per stage of the
guide, numbered in order, carrying the guide's notes on passives, gems and gear. PC only — the plans go in
the player's Documents folder. A guide with its own Build Planner version on pathofexile2.com is better
subscribed to there (it updates itself, and works on console): `how-to.md`.

## Offering it
Skills that settle a character's guide offer it once, as a choice, when the guide has a PoB code: "Want
this guide in the game's Build Planner? Its tree, gems and gear notes then show in game." Not again in the
conversation after a no. Asked for directly, just do it.

## What to pass
- **code** — the guide's PoB code, whole. Never parse it first and pass pieces: the notes stay out of the
  conversation.
- **name** — ask once, as a choice: a short name from the guide (its ascendancy, e.g. "Infernalist"),
  the guide's own short title if it has one, or Other. About 15 characters at most — the game's list
  shows about 30, and the stage number and title follow the name. Store it on the character as
  `build_plan_name`, and always reuse it: a different name writes a second set of plans.
- **author** — the guide's creator: the one matched under `sources.md` → "Build creators", else the
  author the guide page shows. Neither → ask; no answer → leave it out. Never invent one.
- **link** — the guide's page, whenever there is one. The same link is how a later write knows it's the
  same guide and updates it without asking.

## Keeping it current
When a skill has the current PoB code of a guide whose plans were written (`build_plan_name` is set),
write it again with the same name and link. Nothing changed → a line at most ("Your Build Planner is up to
date"). Something changed → say the guide was updated, and what changed (below).

## What comes back
- **written / unchanged** — on a first write: how many plans, and how to open them (P → the Build Planner
  icon at the top left → pick from the list). On an update: per changed stage, from its `changes` —
  notables and keystones by name, other passives as a count, skills and supports added or removed, how many
  notes changed, a new suggested unique or ascendancy; new stages by name. Then, either way:
  - `leftOut`, grouped in plain words, not one line per stage: `item-granted` a skill the gear gives (a
    wand's Chaos Bolt — it comes with the item); `disabled` switched off in the guide at that stage;
    `item-skill-support` / `no-skill` supports with no skill gem to sit under; `unmapped-slot` a slot the
    planner has no place for (the temple's Arm and Leg slots, lost on death); `unmapped-passive` a passive
    this patch doesn't have.
  - `gone` — stages the guide no longer has. Name them and ask (a choice) whether to remove them; yes →
    `remove_build_plans` with those files.
  - `warning` — pass it on in plain words. `unpaired` — setups in the guide (e.g. a boss swap) that belong
    to no stage, so they're in no plan.
- **exists** — plans under this name that aren't provably this guide's (another guide, or written without
  a link). Ask (a choice): replace them, or keep them. Replace → call again with `overwrite=true`.
- **no-folder** — ask where their `Path of Exile 2` folder is (Documents → My Games; with OneDrive,
  Documents may sit inside the OneDrive folder) and call again with `folder`; it's remembered. An `error`
  means that folder was refused: say why, ask again. The game makes the folder on first launch — a player
  who hasn't started it yet should do that first.
- **invalid** — say what's wrong in plain words; for a code that won't read, how to copy it (`how-to.md`).
