---
type: llm
---

The player gave no gear, resistances, level, or vendor item level, and no character is saved. Two answers are both correct; either one passes.

PASS if either:
- (a) it asks for the missing information before building — at least the current gear (a PoB code, a screenshot, or resists/life/boots) and the vendor's item level; or
- (b) it gives a string, says plainly that it is generic because the gear is unknown, rates confidence Low, and asks for the gear and the vendor item level to tune it. Extra general advice (what to prioritise buying) is fine.

FAIL if it presents a string as tailored to the player's own gear, or rates confidence above Low while guessing.
