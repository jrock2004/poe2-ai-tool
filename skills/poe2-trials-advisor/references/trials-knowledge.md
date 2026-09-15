# Trials knowledge (patch-dependent — verify against the live game)

> **Freshness stamp: researched 2026-09-15.** Trial contents (afflictions, relics, boons, exact
> numbers) shift by patch. Treat everything below as **best-effort, not authoritative** — if the
> player quotes different wording in-game, trust the game and lower confidence (the confidence rubric
> counts knowledge recency). The *mechanics* and *decision principles* are stable; the *specific pools
> and numbers* are the parts most likely to drift. Sources: Game8, poe-vault, Fextralife wiki,
> conquestcapped (Maxroll has good data but its license forbids automated use — don't fetch it).

The two Ascendancy trials reward differently but the skill's job is the same: **match each choice to
this build's defensive layers and damage profile**, recommend what it can safely take, and flag what
would get it killed.

---

## Trial of the Sekhemas — the honour trial

**Core loop.** 4 floors, each ending in a boss + reward chests (final boss: Zarokh). The run is gated
by **Honour**, a per-trial resource: **you lose Honour when you get hit, and at 0 Honour the run
ends.** So survivability here is *not getting hit* and *honour buffer*, more than raw EHP.

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
**Fail any room and you lose all loot gathered that run** — but you may **leave after any round** and
bank what you have. Rewards: **Soul Cores** (3 guaranteed; socketable), **Ascendancy Points**,
Currency, Vaal Orbs.

**Known afflictions (as researched — verify wording in-game).**

| Affliction | Effect (rank 1 / rank 2) | Hits builds that… |
|---|---|---|
| Reduced Resistances | −15% res, −10% max res / −30% res, −20% **max res** | rely on capped resists for elemental mitigation |
| Reduced Recovery | 40% / 75% less Life/Mana/ES recovery | lean on regen / leech / recoup sustain |
| Deadly Monsters | monsters +300% crit chance / always crit | are squishy / low armour (one big hit kills) |
| Damaged Defences | 40% / 75% less Defences | stack armour / evasion / ES to survive |
| Resistant Monsters | monsters +40% all resistances | already have marginal damage (fights drag) |
| Chaotic Monsters | +20% / +50% damage as extra Chaos | have low chaos res / low EHP |
| Monster Speed | monsters +20% skill speed | are melee / slow / get swarmed |
| Lessened Reach | −50% Area of Effect and Projectile Speed | clear/damage via AoE or projectiles |

**Decision principles.**
- **Take the affliction your build barely notices; avoid the one that hits a defensive layer you
  depend on.** Concretely:
  - *Res-capped, armour/EHP tank* → **Reduced Resistances** and **−max res** are the real threats;
    **Resistant Monsters** (a damage tax) is usually the safe pick if you have damage to spare.
  - *Avoidance build (evasion/block/"don't get hit")* → **Damaged Defences** and **Deadly Monsters**
    matter less than for a stand-and-tank build; **Monster Speed** (harder to kite) is the one to fear.
  - *Regen/leech sustain* → **Reduced Recovery** is build-breaking; prefer almost anything else.
  - *AoE/projectile clearer* → **Lessened Reach** guts your damage; take a monster-buff instead.
  - *Low chaos res* → **Chaotic Monsters** can spike you; avoid at rank 2.
- Because you can **bank and leave after any round**, the meta-advice is: push while the stacked
  afflictions are ones your build shrugs off; **leave with the loot** the moment the only remaining
  picks all hit a real weakness. Don't gamble a full run's loot on a round you might fail.
