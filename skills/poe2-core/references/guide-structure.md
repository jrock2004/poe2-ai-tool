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
- **Mobalytics trees** aren't in the page text, but every variant's tree is in the page's state, as
  PoB-compatible node ids. Mobalytics bot-blocks `fetch_guide`, so open it in the browser (the
  "browser" route in `poe2-build-review` §1). In the page, run:

  ```js
  const t = [...document.scripts].map(s => s.textContent)
    .find(x => x.startsWith("window.__PRELOADED_STATE__"));
  const objAt = (s, k) => { let d = 0;
    for (let i = k; i < s.length; i++) { if (s[i] == "{") d++; else if (s[i] == "}" && !--d) return s.slice(k, i + 1); } };
  const variants = JSON.parse(objAt(t, t.indexOf('"buildVariants":') + 16)).values;
  const titles = Object.fromEntries([...t.matchAll(/\{"id":"([^"]+)","title":"([^"]*)","description"/g)]
    .map(m => [m[1], m[2]]));
  const ids = l => (l?.selectedSlugs ?? []).map(s => +s.replace("node-", ""));  // null before weapon-set points
  variants.map(v => ({ id: v.id, title: titles[v.id] ?? null,
    main: ids(v.passiveTree.mainTree), set1: ids(v.passiveTree.set1Tree),
    set2: ids(v.passiveTree.set2Tree), ascendancy: ids(v.passiveTree.ascendancyTree),
    gems: (v.skillGems?.gems ?? []).map(g => ({ skill: g.activeSkill?.name,
      weaponSet: g.weaponSet, supports: (g.subSkills ?? []).map(s => s.gemSlug) })) }));
  ```

  Each variant's `id` is the tab's `activeVariantId`, and joining on it gives the tab title — join by
  `id`, not position. Pass each variant's lists to `summarize_tree` with the guide's patch as the
  tree version ("0.5.5" → `"0_5"`). If the guide doesn't say which patch it's for, use the stored
  `patch` of the character's league (see the shared model in `poe2-core`) and say the version was
  assumed — never a snapshot version just because it exists. If the guide's patch is older than the
  league's, say the guide may predate this patch's tree changes. That gives the same tree block as `parse_pob_code`, so trees
  compare id-to-id like a PoB guide. The state is Mobalytics' internal shape and can change: if a
  key is missing, say so, fall back to the tab text, and treat tree comparison as name-based.

  Gems come back as Mobalytics slugs, not names. Translate them to display names before showing the
  player (`supportfarcombatplayertwo` → Far Combat II: drop `support`/`player`, a trailing `two` /
  `three` is the support's tier — "Elemental Armament II", not a gem level); a support slug that is an active skill (`iceshotplayer`) is a
  gem socketed into a skill like Mirage Archer. `weaponSet` is `"set1"` / `"set2"`, or `null` for
  gems that aren't tied to a weapon set (spirit gems like Herald of Ice).
- **PoB codes** often hold every stage as separate tree specs, skill sets, and item sets.
  `parse_pob_code` parses the active ones and lists all three in `sets` (position, title, active).
  Read `sets` first to map stages, then call again with `tree_spec` / `skill_set` / `item_set` set
  to a position to read another stage. The three lists are independent: match them by title, and
  when titles don't line up (or are missing), ask the player which sets belong together rather
  than pairing them by position. Computed stats (resistances, life, DPS) exist only for the active
  sets — `statsNote` says so — so for any other stage, compare gems, tree, and gear, not stats.
- Tab labels are the author's — "Early" in one guide is "Midgame" in another. Order stages by the
  guide's sequence and entry conditions, not by the label.

## Using the model

- **Current stage** — the latest stage whose entry condition the character meets.
- **Next switch** — the stage after it.
- **Lookahead** — the stage after that, when the guide states it.

**When it isn't clear, ask.** If the order of tabs is ambiguous, or you can't tell a stage from an
alternative, name the tabs and ask the player which path they're on. Don't guess a progression.
