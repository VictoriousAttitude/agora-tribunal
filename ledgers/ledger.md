# AGORA ledger

Institutional memory across runs. The orchestrator reads this at SETUP and appends at LEDGER. Keep entries one line each, newest first, prefixed with the run id.

## Conclusions

20260711T114047Z: Cross-run ledger stays markdown; no SQLite. Band=VERIFIED x2 + STRONG x13 convergent across 4 debaters. Spec 10.3 prescribes Qdrant/pgvector for Phase 4; migrate there directly when triggered (>200 entries + recall miss >5%, or programmatic query need). Add [topic_key] prefixes past 50 entries. Ledger has THREE ops: whole-file read, append, in-place SUPERSEDED edit (no locking; accepted risk, low blast radius).
20260711T085819Z: The most interesting AI progress as of July 2026 is the collapse of the reasoning-to-natural-language gap (IMO gold in NL, Knuth open problem solve). Band=STRONG x4. Runner up: Rentosertib Phase IIa RCT (STRONG x2, Phase III pending).

## Open disagreements

20260711T114047Z: DEFINITIONAL (dis ee54b72157b0) — what token/entry threshold constitutes ledger degradation? Camps span 15K tokens to "negligible for a year". Cheapest test: stuff 200 irrelevant + 5 relevant entries, run SETUP, check frame.md recall.
20260711T114047Z: DEFINITIONAL (dis 18947a30a5d3) — degradation defined by functional recall miss rate vs token-count proxy. Same stuffing experiment settles both disputes.
20260711T085819Z: EMPIRICAL — does NL math reasoning transfer broadly or is it domain-narrow? (ARC-AGI-3 <1% vs IMO gold + Knuth). Cheapest test: multi-domain deduction battery outside math/code.
20260711T085819Z: VALUE_TRADEOFF (PRESERVED) — reasoning-gap collapse (breadth) vs Rentosertib (therapeutic impact). Human decides; Architect recommends reasoning-gap now, Rentosertib if Phase III succeeds.

## Mistakes

20260711T114047Z: D4 cited >30% lost-in-the-middle degradation; Liu et al. actual is 15-25pp for middle positions, and beginning-of-context (where the ledger sits) is the best-recall zone.
20260711T114047Z: D2 claimed the ledger has two operations; SKILL.md step 8 prescribes three (read, append, in-place SUPERSEDED edit). Adjudicated ERROR, demoted STRONG to MODERATE.
20260711T085819Z: D4 claimed ARC-AGI-2 human average >85%; actual is 60% per arcprize.org primary source.
20260711T085819Z: D2 conflated GPT-5.4 (73.3%) with GPT-5.4 Pro (83.3%) on ARC-AGI-2; these are distinct models.
