# AGORA ledger

Institutional memory across runs. The orchestrator reads this at SETUP and appends at LEDGER. Keep entries one line each, newest first, prefixed with the run id.

## Conclusions

20260711T160712Z: [gate-hardening] Ship three gate.py patches: stdin try/except (line 61/152), atomic write via tmp+os.replace (line 51), statement cap 2000 chars (line 90). Defer all other hardening. Band=VERIFIED x14 + STRONG x6 convergent across 6 debaters. Strongest rival (5 patches) loses: disallowedTools cannot override session-wide Bash(*), WEAK hard-block breaks legitimate normative claims.
20260711T160712Z: [security] Bash(*) in settings.local.json is session-wide, inherited by all subagents. Frontmatter tools: field is advisory name-only allowlist, NOT sandbox-enforced. Per-agent Write path scoping does not exist in Claude Code. Consequence: Write(runs/**) and Write(ledgers/**) let a prompt-injected debater bypass gate hooks entirely (board.json lives inside runs/**). Mitigate with post-run audit: diff board claim IDs against gate add logs.
20260711T114047Z: Cross-run ledger stays markdown; no SQLite. Band=VERIFIED x2 + STRONG x13 convergent across 4 debaters. Spec 10.3 prescribes Qdrant/pgvector for Phase 4; migrate there directly when triggered (>200 entries + recall miss >5%, or programmatic query need). Add [topic_key] prefixes past 50 entries. Ledger has THREE ops: whole-file read, append, in-place SUPERSEDED edit (no locking; accepted risk, low blast radius).
20260711T085819Z: The most interesting AI progress as of July 2026 is the collapse of the reasoning-to-natural-language gap (IMO gold in NL, Knuth open problem solve). Band=STRONG x4. Runner up: Rentosertib Phase IIa RCT (STRONG x2, Phase III pending).

## Open disagreements

20260711T114047Z: DEFINITIONAL (dis ee54b72157b0) — what token/entry threshold constitutes ledger degradation? Camps span 15K tokens to "negligible for a year". Cheapest test: stuff 200 irrelevant + 5 relevant entries, run SETUP, check frame.md recall.
20260711T114047Z: DEFINITIONAL (dis 18947a30a5d3) — degradation defined by functional recall miss rate vs token-count proxy. Same stuffing experiment settles both disputes.
20260711T085819Z: EMPIRICAL — does NL math reasoning transfer broadly or is it domain-narrow? (ARC-AGI-3 <1% vs IMO gold + Knuth). Cheapest test: multi-domain deduction battery outside math/code.
20260711T085819Z: VALUE_TRADEOFF (PRESERVED) — reasoning-gap collapse (breadth) vs Rentosertib (therapeutic impact). Human decides; Architect recommends reasoning-gap now, Rentosertib if Phase III succeeds.

## Mistakes

20260711T160712Z: D4 (9d22b9ddb79b) cited Bash restriction as "Bash(uv run python -m agora.gate:*)"; file was changed to Bash(*) mid-run by user. Adjudicated ERROR (dis f90a7fe4631a). Write-path component of the claim remained correct.
20260711T114047Z: D4 cited >30% lost-in-the-middle degradation; Liu et al. actual is 15-25pp for middle positions, and beginning-of-context (where the ledger sits) is the best-recall zone.
20260711T114047Z: D2 claimed the ledger has two operations; SKILL.md step 8 prescribes three (read, append, in-place SUPERSEDED edit). Adjudicated ERROR, demoted STRONG to MODERATE.
20260711T085819Z: D4 claimed ARC-AGI-2 human average >85%; actual is 60% per arcprize.org primary source.
20260711T085819Z: D2 conflated GPT-5.4 (73.3%) with GPT-5.4 Pro (83.3%) on ARC-AGI-2; these are distinct models.
