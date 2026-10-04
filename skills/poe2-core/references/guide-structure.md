# Reading a build guide's structure

Guides split a build up in many ways. Whatever the shape, turn it into the same model before using
it, so `poe2-build-review` and `poe2-build-switch` read guides the same way.

## The model

**An ordered list of stages.** Each stage has:

- **Entry condition** — what moves the player into it. One or more of:
  - **level** ("lvl 31–41"),
  - **act / campaign point** ("after campaign", "Act 3"),
  - **Trial / ascendancy** ("after the third ascendancy"),
  - **gear** ("once you have a crit bow and quiver"),
  - **stated** — the author's own words, when they don't fit the above ("once mapping feels slow").
- **What it changes** — gems (and which weapon set), passive tree, gear, ascendancy.

**Off-path tabs** — anything that isn't a step in the progression. Label them and **never treat them
as stages**, or the player gets told they're "behind" on something they were never meant to follow:

- **Reference** — the author's current gear ("Live Gear"), a showcase, a "mirror tier" example.
- **Alternatives** — a parallel path for a different situation: an SSF version, an other-Ascendancy
  option, a budget vs. expensive route.
- **Situational setups** — swaps used for one kind of content (a boss setup vs. a mapping setup).
  These change what the player swaps *to* for a fight, not where they are in the guide.

## Shapes you'll see

| Shape | How to read it |
|---|---|
| Separate guides, linked ("swap to the endgame guide after campaign") | Two stage lists joined end to end; the link is the switch. |
| Separate guide, not named ("swap to another endgame build") | The stage list ends there. **Ask the player** which build comes next — don't pick one. |
| Tabs by level bracket (lvl 1–14 … lvl 60+) | One stage per tab; entry condition is the bracket. |
| Tabs by gear or budget tier (Early → Midgame → Crit → Uber) | One stage per tab; entry condition is the gear the guide's text names. |
| A skill swap inside leveling ("mini skill swap at 24", "Ice Shot at 31") | A stage boundary even if the tabs don't split there. |
| Ascendancy change ("level as Infernalist, then respec to Lich") | A stage boundary with an ascendancy change in "what it changes". |
| Prose only (acts or sections, no tabs) | Build the stages from the headings; entry conditions from the text. |

Mixed shapes are normal: a leveling guide with level tabs that links to an endgame guide with gear tabs
is one stage list.

## Reading the source

- **Tabbed pages** (e.g. Mobalytics) only show the selected tab's gems and tree in the page text. Read
  each tab you need specifically — on Mobalytics each tab has its own URL (`?…=activeVariantId,N`).
- **PoB codes** often hold every stage as separate tree specs, skill sets, and item sets, but
  `parse_pob_code` returns only the **active** one. A guide PoB gives you one stage per export; say
  which stage it is, and ask for a re-export with another set active if you need a different one.
- Tab labels are the author's — "Early" in one guide is "Midgame" in another. Order stages by the
  guide's sequence and entry conditions, not by the label.

## Using the model

- **Current stage** — the latest stage whose entry condition the character meets.
- **Next switch** — the stage after it.
- **Lookahead** — the stage after that, when the guide states it.

**When it isn't clear, ask.** If the order of tabs is ambiguous, or you can't tell a stage from an
alternative, name the tabs and ask the player which path they're on. Don't guess a progression.
