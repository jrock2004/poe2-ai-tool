---
type: llm
focus: mock_calls
---

Judge the input sent to build_vendor_regex (the last call, if there are several). Valid keys per the tool: mods movement_speed (n), spirit, minion_skills, max_energy_shield, increased_energy_shield, resistance, max_life (n), minion_life_recovery, charges_per_second, flask_removes_recovery; classes sceptre, amulet, ring, belt, wand, staff, quarterstaff, spear, crossbow, bow, quiver, one_hand_mace, two_hand_mace; the only defence is energy_shield. The build is an evasion bow Deadeye with uncapped fire and cold resistance and 10% movement speed boots.

PASS if all of these hold:
- `want` puts survivability first: resistance (and/or max_life) ahead of movement_speed.
- movement_speed has a min_value above 10 and any_base: true.
- `hide_classes` hides weapon classes a bow build can't use, and does NOT hide bow or quiver.
- No slot gate: slot_classes and slot_defences are omitted or empty (evasion isn't a supported defence, so a gate would hide the evasion armour).
- item_level is 26.
- Flasks: charges_per_second is wanted with any_base, and flask_removes_recovery is in `avoid`.

FAIL if any of those is wrong, including setting slot_defences to energy_shield or hiding quiver.
