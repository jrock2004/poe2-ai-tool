# Confidence rubric

Every answer ends with a band and a one-line reason. Example:
`Confidence: Medium — only 3 comparable listings, prices ranged ~2×.`

**Do not emit invented percentages.** Derive the band from signals you can actually observe:

| Signal | Raises confidence | Lowers confidence |
|---|---|---|
| Data freshness | fetched just now / cache < 5 min | stale or unknown age |
| Sample size | many comparable listings (10+) | few (1–3) or zero (extrapolating) |
| Input certainty | real character/currency from OAuth or a confirmed screenshot | guessed or assumed inputs |
| Source agreement | poe2scout and poe.ninja agree | sources diverge |
| Knowledge recency | knowledge file matches the live patch | possibly stale (patch changed) |

**Banding:**
- **High** — fresh data, healthy sample, certain inputs, sources agree.
- **Medium** — one or two weak signals (small sample, some assumption).
- **Low** — extrapolating, stale, or key inputs guessed. Say what would raise it.

Always add the single most important reason, not a list. When confidence is Low, name the one thing
that would make it High ("send a screenshot of your currency tab and I can price this exactly").
