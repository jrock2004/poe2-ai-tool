---
patch: 0.5.5d
refreshed: 2026-10-05
---
# Trials knowledge (patch-dependent — verify against the live game)

> **Freshness stamp: researched 2026-09-15; refreshed 2026-10-04 for patch 0.5.5 (Forbidden Rites);
> Trial of Chaos modifier list re-pulled from poe2db game data 2026-10-05.**
> Trial contents (afflictions, relics, boons, exact numbers) shift by patch. Treat everything below as
> **best-effort, not authoritative** — if the player quotes different wording in-game, trust the game
> and lower confidence (the confidence rubric counts knowledge recency). The *mechanics* and *decision
> principles* are stable; the *specific pools and numbers* are the parts most likely to drift.
> Sources: official 0.5.5 patch notes (pathofexile.com forum thread 4000864 — quoted lines below are
> verbatim) and its hotfixes through 0.5.5d; poe2db's Ultimatum page (poe2db.tw/us/Ultimatum — Trial
> of Chaos modifier text, verbatim, matches the 0.5.5 in-game tooltips); poe-vault, Fextralife wiki,
> conquestcapped for Sekhemas mechanics. Third-party guides still list the *pre-rework* Chaos numbers —
> don't take modifier text from them. (Maxroll has good data but its license forbids automated use —
> don't fetch it.)

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
name is the version, and the tier is in brackets below where it differs. Wagers (endgame) can push
already-chosen modifiers up a tier, so a mild pick now can grow later.

**Modifier pool (poe2db game data, 0.5.5 — text verbatim; verify the tooltip in-game).** Values listed
lowest → highest version.

*Monster buffs — they make monsters tougher or hit harder; you feel them through your weakest layer.*

| Modifier | Versions (I → V) | Hits builds that… |
|---|---|---|
| Resistant Monsters | Monsters have +10% / +20% / +30% / +40% / +50% to all Resistances | have marginal damage (fights drag) |
| Shielding Monsters | Monsters gain 10% / 20% / 30% / 40% / 50% of maximum Life as Extra maximum Energy Shield | have marginal damage |
| Enraged Bosses (I [1], II [3], III [5]) | Bosses have 30% / 60% / 100% increased Toughness and 10% / 20% / 30% increased Damage | are weak at bossing or can't take big boss hits |
| Lethal Rare Monsters ([1], [3], [5]; same name) | 30% / 60% increased Rare Monsters; [5]: Rare Monsters have an additional Modifier, 100% increased Rare Monsters | struggle with rares |
| Unstoppable Monsters (I [1], II [3], III [5]) | Monsters have 30% / 50% / 75% reduced Slowing Potency of Debuffs on them and 30% / 50% / 75% increased Stun Threshold | rely on slows, freeze-style control, or stun |
| Monster Speed (I [1], II [3], III [5]) | Monsters gain 10% / 15% / 20% increased Skill Speed and Movement Speed | are melee, slow, or get swarmed |
| Deadly Monsters | Monsters have 100% / 200% / 300% / 400% / 500% increased Critical Hit Chance | have low max hit / no armour (big spikes) |
| Chaotic Monsters | Monsters gain 5% / 11% / 17% / 23% / 29% of Damage as Extra Chaos Damage | have low chaos resistance |
| Prismatic Monsters | Monsters gain 10% / 15% / 20% / 25% / 30% of Damage as Extra Damage of a random Element | have an uncapped elemental resistance |
| Toxic Monsters | Monsters have 10% / 20% / 30% / 40% / 50% chance to inflict Bleed or Poison | get hit often with low recovery; ES builds (a damage-over-time ticking on you delays ES recharge) |
| Volatile Fiends | Monsters have a 10% / 20% / 30% / 40% / 50% chance to release deadly Volatiles on death. Rare monsters leave larger ones | are melee (standing where things die) |
| Entangling Monsters (one version) | Monsters inflict Grasping Vines on Hit | get hit often or rely on movement |

*Debuffs on you.*

| Modifier | Versions (I → V) | Hits builds that… |
|---|---|---|
| Reduced Resistances | −15% / −25% / −35% / −45% / −55% to Elemental Resistances; versions III–V also −5% / −10% / −15% to **Maximum** Elemental Resistances | have little resistance over the cap; III+ hurts every elemental build |
| Damaged Defences | 20% / 35% / 50% / 65% / 80% less Armour, Evasion and Energy Shield | stack armour / evasion / ES to survive |
| Reduced Recovery | 20% / 35% / 50% / 65% / 80% reduced Life, Mana, and Energy Shield Recovery Rate | lean on regen, leech, flasks, or ES recharge |
| Drought | Monsters grant 20% / 40% / 60% / 80% reduced (V: no) Flask and Charm Charges on death | depend on flasks or charms |
| Escalating Damage Taken (I [1], II [3], III [5]) | In each encounter room, damage taken will increase by 1% every 2.5 / 1.75 / 1 second(s), up to 50% | clear slowly (long rooms reach the cap) |
| Time Paradox (I [1], II [3], III [5]) | Buffs on you expire 50% / 100% / 200% faster and Debuffs on you expire 25% / 50% / 100% slower | rely on temporary buffs; makes every debuff (bleed, poison, curses) last longer |
| Lessened Reach | 20% / 35% / 50% / 65% / 80% less Area of Effect and Projectile Speed | clear with AoE or projectiles. The text doesn't say whether minions are affected — not researched |
| Random Projectiles (one version, [1]) | Your Projectiles fly in random directions | are projectile builds. Effect on minions not researched |
| Occasional Impotence (one version, [2]) | You and your Minions deal no damage for 2 seconds every 8 seconds | every build loses ~25% of its damage uptime — **minions included** |
| Heart Tethers (I [1], II [3], III [5]) | Bloody hearts appear that apply tethers, Slowing you for 3 / 4 / 5 seconds. Breaking the tether will Stun you and cause you to take 5% / 10% / 15% increased damage for 3 / 4 / 5 seconds | are melee or need to reposition |

*Room hazards — dodgeable if you keep moving; dangerous for builds that stand still.*

| Modifier | Versions | Hits builds that… |
|---|---|---|
| Blood Globules (I, II) | Globules of blood manifest nearby, tracking you. When above you they will fall, dealing Physical damage (II: *and creating damaging blood ground*) | stand still; have a low physical max hit |
| Impending Doom (I, II) | Rings (II: *Rings and circles*) of Doom appear on the ground which grow over time, exploding for Physical damage once they reach a maximum area | stand still |
| Temple Traps (I, II) | Challenge area contains (II: *many*) spikes that deal Physical damage to those who step on them | are melee / move a lot through packs |
| Stormcaller Runes (I [1], II [3], III [5]) | Runes (II: *Large runes*; III: *Many large runes*) will appear that will call deadly Lightning storms if you remain in them | stand still; have low lightning res |
| Burning / Shocking Turrets (I [1], II [3], III [5]) | Challenge area contains (II: *more*; III: *even more*) Fire / Lightning turrets that will periodically fire Projectiles ahead | stand still; low fire / lightning res |
| Pyramid Beams (I, II) | Pyramid objects appear, projecting four (II: *fast*) rotating lasers that inflict Corrupted Blood on Hit | have low recovery (Corrupted Blood is a physical damage over time) |
| Petrification Statues ([1], [3], [5]; same text) | Challenge area contains several statues that Petrify you if you stand within their gaze for a duration | stand still or channel |
| Vaal Omnitect (I [1], II [3], III [5]) | An ancient Vaal machination will deploy attacks (II: *an array of attacks*; III: *a powerful array of attacks*) against nearby intruders | stand still; low EHP |
| Blood Mist (one version) | Challenge area is enshrouded by a blood mist which makes monsters within it immune to damage | can't pull monsters out of an area (minions chase into it) |
| Stalking Shade (I, II, III) | An invulnerable shade stalks you, inflicting Ruin with its hits, it gains additional skills at higher tiers | get hit by anything that chases you. Ruin **ends the run** at a threshold (7 per pre-0.5.5 guides — check the in-game counter) |

**Wagers (Inscribed Ultimatum runs; verbatim).** Offered as a choice like a modifier; each trades
danger for reward:
- *Wager of the Present* — "All previously chosen Modifiers gain +1 Tier", "All pending Currency Item
  Rewards are Doubled".
- *Wager of the Future* — "All offered Modifiers gain +1 Tier", "All offered Currency Item Rewards
  have their Stack Size Doubled".
- *Wager of Upgrades* — "When any offered Modifier is chosen, a previously chosen Modifier also gains
  +1 Tier", "When a Room is Completed, a pending Currency Item or Soul Core Reward gains +1 to its Stack
  Size".
- *Wager of Rerolling* (two versions) — "Upgrade 2 previously chosen Modifiers", and all pending
  Currency Item (or Soul Core) Rewards are Rerolled.
- *Wager of Chaos* (two versions) — "Upgrade 2 previously chosen Modifiers" / "All Rooms offer an
  additional Reward"; or "Upgrade all previously chosen Modifiers" / "All Rooms offer 2 additional
  Rewards".
- *Wager of Danger* — "Modifiers offered at Boss Rooms are offered at their Maximum Tier", "Boss Rooms
  offer an additional Reward".
- *Wager of Mystery* — "All offered Modifiers are Hidden", "All offered Rewards are Lucky".
- *Wager of Rarity* — "All pending Rewards are Destroyed", "100% more Item Rarity".
- *Wager of Ruin* — "An invulnerable Shade stalks you, inflicting Ruin with its Hits", "Your current
  Ruin is set to 5", "Unique Trial Bosses drop a Rare Unique Item".

**Decision principles.**
- **Take the modifier your build barely notices; avoid the one that hits a layer you depend on.** Read
  the *version* — a version I of a scary name is often milder than a version III of a harmless one.
  Concretely:
  - *Res-capped, armour/EHP tank* → **Reduced Resistances** III+ (−max res) and **Prismatic Monsters**
    are the real threats; versions I–II only cost resistance above the cap, so they're free if you're
    overcapped by that much. **Resistant / Shielding Monsters** (a damage tax) are the safe picks if you
    have damage to spare.
  - *Avoidance build (evasion/block/"don't get hit")* → **Damaged Defences** and **Deadly Monsters**
    matter less than for a stand-and-tank build; **Monster Speed** and **Heart Tethers** (harder to
    kite) are the ones to fear.
  - *ES build* → **Damaged Defences** cuts the pool; **Reduced Recovery** slows recharge; **Toxic
    Monsters** and **Pyramid Beams** put damage over time on you, which delays recharge.
  - *Regen/leech/flask sustain* → **Reduced Recovery** and **Drought** are build-breaking.
  - *AoE/projectile clearer* → **Lessened Reach** and **Random Projectiles** gut your damage; take a
    monster-buff instead.
  - *Low chaos res* → **Chaotic Monsters** spikes you; it's mild at I–II (5–11%) and real at IV–V.
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
