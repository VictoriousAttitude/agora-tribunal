# Claim extraction protocol

Turn your analysis into discrete, checkable claims. Rules:

1. One claim = one statement that could individually be supported or refuted. Split compound statements.
2. Classify each claim:
   - EMPIRICAL: a fact, test, or measurement could settle it
   - DEFINITIONAL: it is about the meaning of terms
   - NORMATIVE: a value or priority judgment
   - PROCEDURAL: about process or method
3. Declare provenance honestly:
   - TOOL_RESULT: you ran something and observed the output
   - RETRIEVED_SOURCE: backed by a retrieved document
   - EXTERNAL_CITATION: backed by a named external source
   - ASSERTION: your expert judgment without evidence
4. Provenance above ASSERTION requires evidence_refs. If you attach none, the claim is mechanically downgraded to ASSERTION and capped at a WEAK warrant. Do not inflate provenance; it costs you credibility and changes nothing.
5. Never state confidence percentages. Confidence is derived from evidence by the Judge, not self-reported.
6. Use depends_on / contradicts with existing claim ids where genuine logical relations exist. Do not invent ids.
