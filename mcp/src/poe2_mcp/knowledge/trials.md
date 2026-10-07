---
patch: 0.5.5e
refreshed: 2026-10-07
---
# Trials knowledge (patch-dependent — verify against the live game)

> **Freshness stamp: researched 2026-09-15; refreshed 2026-10-07 for patch 0.5.5, hotfixes through
> 0.5.5e (0.5.5e changed nothing in the trials).**
> This file holds how the trials *work* and how to *choose*. What each trial can offer — the Trial of
> Chaos modifiers and wagers, the Sekhemas afflictions, boons and pledges, with their exact text — comes
> from `trial_pool('chaos')` and `trial_pool('sekhemas')`, generated from the game's files. Quote those;
> they aren't copied here, because the pools and their numbers are what drifts between patches. If the
> player quotes different wording in-game, trust the game and lower confidence (the confidence rubric
> counts knowledge recency).
> Sources: official 0.5.5 patch notes (pathofexile.com forum thread 4000864 — quoted lines below are
> verbatim) and its hotfixes through 0.5.5d, plus 0.5.5e (thread 4009785; checked 2026-10-07);
> poe-vault, Fextralife wiki, conquestcapped for Sekhemas mechanics. Third-party guides still list the
> *pre-rework* Chaos numbers — take texts from `trial_pool`, not from them.

The two Ascendancy trials reward differently but the skill's job is the same: **match each choice to
this build's defensive layers and damage profile**, recommend what it can safely take, and flag what
would get it killed.

---

## Trial of the Sekhemas — the honour trial

**Core loop.** 4 floors, each ending in a boss + reward chests (final boss: Zarokh). The run is gated
by **Honour**, a per-trial resource: **you lose Honour when you get hit, and at 0 Honour the run
ends.** So survivability here is *not getting hit* and *honour buffer*, more than raw EHP.
0.5.5: *"The Trial of Sekhemas now has inherent bonuses starting at Area Level 65."* — more and
stronger magic/rare packs, better boss drops — *"to compensate for Atlas Passive Bonuses not applying
inside the Trial of Sekhemas."*

**Relics.** Equipped into the altar grid before entering (slots unlock as you beat Trial bosses, up to
~18). Sizes Small/Medium/Large (larger = stronger). They grant passive bonuses for the run:
- **Maximum Honour** and **Honour Resistance** — the safety relics (Honour Res caps at 75%, up to 90%
  with certain affixes). These are what keep a fragile build alive.
- Throughput relics — bosses take increased damage, increased movement speed, etc.

**Afflictions & Boons.** Between rooms you encounter **Afflictions** (negative: reduce Honour, damage,
or defence; come in Major/Minor; some are "back-breaking"). You can **see two rooms ahead including
their afflictions**, so you route around the dangerous ones. **Boons** (positive) come from Fountains
and from the Merchant, bought with **Sacred Water** (per-run currency). Avoid stacking duplicate
afflictions.

**The pool: `trial_pool('sekhemas')`.** Every affliction, boon and pledge, with its category (Minor or
Major Afflictions, Minor or Major Boons, Pledges) and exact text; a pledge also has the `cost` it
trades for its benefit. Look one up by the name the player sees. Some texts carry a `{0}` whose number
only the game shows — quote those as they are.

**Decision principles.**
- **Honour is the bottleneck for anything that gets hit** (melee, low-avoidance, low-life). For those:
  prioritize **Maximum Honour + Honour Resistance relics**, buy defensive/honour-sustain boons, and
  route *around* afflictions that drain honour or cut defence.
- **High-avoidance / ranged builds** take less honour pressure — they can afford throughput relics and
  can walk through more afflictions for the reward.
- Never take a room whose affliction attacks your known weakness (e.g. a defence-reduction affliction
  on an already-fragile build). Duplicates compound — decline them.

---

## Trial of Chaos — the tribulation trial

**Core loop.** Consecutive combat rooms (Ultimatum-style). **Before each round you pick 1 of 3
afflictions (tribulations) that last the whole run** and stack. Harder afflictions = better rewards.
Rewards: **Soul Cores** (3 guaranteed; socketable), **Ascendancy Points**, Currency.

**0.5.5 changes** (verbatim):
- *"There is now a reward chest at the end of each room in the Trial of Chaos. This makes dying less
  punitive as you don't lose your entire set of rewards."*
- *"Now you can leave the Trial of Chaos at any point and resume your run at a later time from the
  same room."*
- *"The rewards for completing a Trial of Chaos run now consists of only Currency and Soul Cores.
  Corrupted items are no longer a reward outcome in the Trial of Chaos."*
- *"The Modifiers applied between rooms in the Trial of Chaos that add difficulty now always also
  increase the quality of drops from slain monsters."*
- *"The more significant, elite Monsters that spawn during the Trial of Chaos are now more dangerous,
  but more rewarding."*
- Endgame (Inscribed Ultimatum, 10 Trials): *"you are now able to continue your run immediately
  without providing another Inscribed Ultimatum item. You're able to do this twice per Inscribed
  Ultimatum"*; *"The Modifiers and quality of rewards will be carried over when continuing a run"*,
  and each continue offers *"an optional double or nothing wager of Currency"*.
- The Trial of Chaos *"now has various inherent bonuses depending on the level of the Area"*, since
  Atlas passives don't apply inside it.
- Hotfixes since (through 0.5.5d): Ascendancy Points go *"only [to] players in the instance at the
  time the boss dies"* (Hotfix 7 — no joining a finished run for a carry); the *"Wager of Chaos"*
  modifier's tier 2 now gives the intended *"+2"* minimum rewards (0.5.5c); a failed *"Chimeral
  Inscribed Ultimatum"* can be replaced from the Trialmaster at the Temple of Chaos entrance (0.5.5b).
  Sekhemas: *"Added an "Identify Items" option to Balbala"* (0.5.5c).

**How the choice works.** Before each room the Trialmaster offers **3 modifiers**; the one you pick
lasts the rest of the run and stacks with the others. Each offer's tooltip shows its **Item Rarity**
bonus (seen in 0.5.5: Toxic Monsters +4%, Blood Globules +12%, Escalating Damage Taken +15%) — the
harder the modifier, the bigger the bonus. Modifiers come in **tiers 1–5**; the roman numeral in the
name is the version, which isn't always the tier. Wagers (endgame) can push already-chosen modifiers
up a tier, so a mild pick now can grow later.

**The pool: `trial_pool('chaos')`.** Every modifier with each version's name, `tier` and exact text,
and its `kind`: a `modifier` (a monster buff or a debuff on you), a room `hazard`, or a `wager`. Look
one up by the name on the offer and quote it.

**Hits builds that…** — the judgment per modifier; the version decides how hard it hits.

*Monster buffs (`modifier`) — you feel them through your weakest layer.*
- **Resistant Monsters**, **Shielding Monsters** — have marginal damage (fights drag).
- **Enraged Bosses** — are weak at bossing or can't take big boss hits.
- **Lethal Rare Monsters** — struggle with rares.
- **Unstoppable Monsters** — rely on slows, freeze-style control, or stun.
- **Monster Speed** — are melee, slow, or get swarmed.
- **Deadly Monsters** — have a low max hit / no armour (big spikes).
- **Chaotic Monsters** — have low chaos resistance.
- **Prismatic Monsters** — have an uncapped elemental resistance.
- **Toxic Monsters** — get hit often with low recovery; ES builds (a damage over time ticking on you
  delays ES recharge).
- **Volatile Fiends** — are melee (standing where things die).
- **Entangling Monsters** — get hit often or rely on movement.

*Debuffs on you (`modifier`).*
- **Reduced Resistances** — have little resistance over the cap; the versions that also lower
  **Maximum** Elemental Resistances hurt every elemental build.
- **Damaged Defences** — stack armour / evasion / ES to survive.
- **Reduced Recovery** — lean on regen, leech, flasks, or ES recharge.
- **Drought** — depend on flasks or charms.
- **Escalating Damage Taken** — clear slowly (long rooms reach the cap).
- **Time Paradox** — rely on temporary buffs; it also makes every debuff (bleed, poison, curses) last
  longer.
- **Lessened Reach** — clear with AoE or projectiles. The text doesn't say whether minions are
  affected — not researched.
- **Random Projectiles** — are projectile builds. Effect on minions not researched.
- **Occasional Impotence** — every build loses damage uptime — **minions included**.

*Room hazards (`hazard`) — dodgeable if you keep moving; dangerous for builds that stand still.*
- **Blood Globules** — stand still; have a low physical max hit.
- **Impending Doom** — stand still.
- **Temple Traps** — are melee / move a lot through packs.
- **Stormcaller Runes** — stand still; have low lightning res.
- **Burning Turrets** / **Shocking Turrets** — stand still; have low fire / lightning res.
- **Pyramid Beams** — have low recovery (Corrupted Blood is a physical damage over time).
- **Petrification Statues** — stand still or channel.
- **Vaal Omnitect** — stand still; have low EHP.
- **Heart Tethers** — are melee or need to reposition.
- **Blood Mist** — can't pull monsters out of an area (minions chase into it).
- **Stalking Shade** — get hit by anything that chases you. Ruin **ends the run** at a threshold (7 per
  pre-0.5.5 guides — check the in-game counter).

**Wagers** (Inscribed Ultimatum runs) are offered like a modifier and trade danger for reward; their
texts are `trial_pool('chaos', 'wager')`. Every wager is tier 1 in the game's files, so read a wager's
version order, not its `tier`: the 0.5.5c hotfix's "tier 2" is the second Wager of Chaos version, the
one with 2 additional rewards.

**Decision principles.**
- **Take the modifier your build barely notices; avoid the one that hits a layer you depend on.** Read
  the *version* — a version I of a scary name is often milder than a version III of a harmless one.
  Concretely:
  - *Res-capped, armour/EHP tank* → **Reduced Resistances** at the versions that lower maximum res,
    and **Prismatic Monsters**, are the real threats; the lower versions only cost resistance above the
    cap, so they're free if you're overcapped by that much. **Resistant / Shielding Monsters** (a damage
    tax) are the safe picks if you have damage to spare.
  - *Avoidance build (evasion/block/"don't get hit")* → **Damaged Defences** and **Deadly Monsters**
    matter less than for a stand-and-tank build; **Monster Speed** and **Heart Tethers** (harder to
    kite) are the ones to fear.
  - *ES build* → **Damaged Defences** cuts the pool; **Reduced Recovery** slows recharge; **Toxic
    Monsters** and **Pyramid Beams** put damage over time on you, which delays recharge.
  - *Regen/leech/flask sustain* → **Reduced Recovery** and **Drought** are build-breaking.
  - *AoE/projectile clearer* → **Lessened Reach** and **Random Projectiles** gut your damage; take a
    monster-buff instead.
  - *Low chaos res* → **Chaotic Monsters** spikes you; it's mild at the low versions and real at the
    top ones.
  - *Minion build* → **Occasional Impotence** stops your minions too; **Blood Mist** is worse when
    minions chase into it. Hazards that track *you* (Blood Globules, Stalking Shade) are easy while
    minions fight and you keep moving.
  - *Slow clearer / weak bossing* → **Escalating Damage Taken** and **Enraged Bosses** punish long
    fights.
  - *Never* stack a second Ruin source (**Stalking Shade**, *Wager of Ruin*) without a plan — Ruin ends
    the run outright, not just a room.
- Weigh the **rarity bonus** on the tooltip only after safety: early rooms, take the safe pick even if
  it pays less; the margin you save is what lets later, worse offers stay survivable.
- Since 0.5.5 each room pays its own chest, so a death no longer costs the whole run's loot — only
  what the run would still have earned. Push while the stacked modifiers are ones your build shrugs
  off; **stop** the moment the only remaining picks all hit a real weakness. Need a break or to trade?
  Leave and resume later from the same room instead of forcing it.
- **Wagers** that upgrade previously chosen modifiers are only as safe as your *worst* chosen modifier
  one tier higher — check that before taking one. At endgame, the **double-or-nothing wager** on a
  continue is a pure gamble: take it only if the carried-over modifiers are ones the build has already
  shown it handles.
