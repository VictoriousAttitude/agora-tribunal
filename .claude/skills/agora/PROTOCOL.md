# AGORA protocol reference

Single source of truth for contracts the orchestrator injects into spawn prompts, and for the iron hooks the gate enforces.

## Evidence rules (put in every debater/resolver prompt together with a contract)

Provenance declares how a claim is backed; the gate enforces honesty:
- TOOL_RESULT — you ran something and quote its real output
- RETRIEVED_SOURCE — a document you actually fetched and quote
- EXTERNAL_CITATION — a named source you can point at
- ASSERTION — expert judgment, no evidence

Each evidence item: `{"kind": one of TEST_RUN|EVAL_RESULT|BENCHMARK|RETRIEVAL_HIT|WEB_SOURCE|PRIOR_LEDGER|STATIC_ANALYSIS, "ref": the exact command or URL, "digest": at least 12 chars of the actual output or quote}`. The gate strips evidence with placeholder digests, then collapses evidence-less provenance to ASSERTION (capped at a WEAK warrant). Declaring honestly costs nothing; inflating gets clamped anyway. Confidence percentages are flagged and never honored — warrant is derived from evidence by the judge.

## CLAIM CONTRACT (ground round)

End your reply with exactly one fenced ```json block:
{"claims": [{"statement": "one checkable statement",
  "claim_type": "EMPIRICAL|DEFINITIONAL|NORMATIVE|PROCEDURAL",
  "provenance": "TOOL_RESULT|RETRIEVED_SOURCE|EXTERNAL_CITATION|ASSERTION",
  "evidence": [], "depends_on": [], "contradicts": []}]}
At most 5 claims; split compound statements; only claims that could change the decision.

## CRITIQUE CONTRACT (critique rounds)

End your reply with exactly one fenced ```json block:
{"claims": [ ...at most 3 NEW claims, same shape as above, using contradicts/depends_on with real board ids... ],
 "endorsements": [{"claim_id": "board id", "stance": "ENDORSE|CHALLENGE", "reason": "one sentence"}]}
Endorse or challenge existing ids instead of restating them — a restated claim is a wasted slot. Endorsements never raise warrant; only evidence does.

## JUDGE CONTRACT

You receive the claim board only. End with exactly one fenced ```json block:
{"assessments": [{"claim_id": "...", "warrant_band": "VERIFIED|STRONG|MODERATE|WEAK|CONTESTED"}],
 "disagreements": [{"claim_ids": ["...", "..."], "dclass": "EMPIRICAL|DEFINITIONAL|VALUE_TRADEOFF|ERROR", "rationale": "1-2 sentences"}]}
Assess every id exactly once. Judge the evidence, not the eloquence; agreement counts (+n/-n) are context, never evidence.

## RESOLVER CONTRACT

You receive one disagreement cluster. Settle it: run the command, fetch the source, produce the fact. End with the ground-round JSON block; every claim carries TOOL_RESULT or RETRIEVED_SOURCE provenance with real quoted output in the digest. An honest "could not settle: <why>" with zero claims beats a manufactured result.

## VERDICT CONTRACT (architect deciding)

The debate is over; decide. Structure: (a) the decision, one committed course of action; (b) the load-bearing claims, cited by board id, VERIFIED/STRONG carrying the weight and CONTESTED never treated as settled; (c) what would change your mind; (d) each open or preserved disagreement with the cheapest way to settle it. Value trade-offs are stated as choices that belong to the human, with your recommendation.

## Iron hooks (gate-enforced; for the orchestrator's awareness)

H1 evidence-less provenance collapses to ASSERTION; H2 ceilings ASSERTION<=WEAK, CITATION/SOURCE<=STRONG, TOOL_RESULT<=VERIFIED; H3 invalid claim JSON is discarded after one retry; H4 invented claim ids are stripped; H5 evidence without a real digest (>=12 chars) is stripped; H6 judge bands are clamped to ceilings; H7 confidence language is flagged; H8 agreement + low warrant = SUSPECT_CONSENSUS, triggers a challenge; H9 decisions citing unknown or CONTESTED ids bounce back.

## Gate command reference

- add:   `uv run python -m agora.gate add --board B --anon Dx --role ROLE --round N --cap K < claims.json`
- render:`uv run python -m agora.gate render --board B`
- judge: `uv run python -m agora.gate judge --board B < judge.json`
- check: `uv run python -m agora.gate check-decision --board B < decision.md`

Roles for --role: ARCHITECT, QA, SCIENTIST, PRAGMATIST, HACKER, SRE, EMPIRICIST (resolver).
