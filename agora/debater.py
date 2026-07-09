"""Debater turn: two-pass design.

Pass 1: free-form reasoning (complete) so the model thinks without schema
pressure. Pass 2: forced tool use extracting Claims from its own pass-1 text.
This solves the prose-to-Claim extraction gap in spec 6 without degrading
reasoning quality.
"""
from __future__ import annotations

from agora.llm import LLM
from agora.models import Claim, ClaimType, Provenance, Role

CLAIM_TOOL = {
    "name": "submit_claims",
    "description": (
        "Submit the discrete, checkable claims contained in your analysis. "
        "Each claim is one statement that could individually be supported or refuted."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "claim_type": {
                            "type": "string",
                            "enum": [c.value for c in ClaimType],
                        },
                        "provenance": {
                            "type": "string",
                            "enum": [p.value for p in Provenance],
                        },
                        "evidence_refs": {
                            "type": "array",
                            "description": (
                                "Evidence backing this claim. Leave empty if you have "
                                "none; the provenance will then be treated as ASSERTION."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "kind": {"type": "string"},
                                    "ref": {"type": "string"},
                                    "digest": {"type": "string"},
                                },
                                "required": ["kind", "ref", "digest"],
                            },
                        },
                        "depends_on": {"type": "array", "items": {"type": "string"}},
                        "contradicts": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["statement", "claim_type", "provenance"],
                },
            }
        },
        "required": ["claims"],
    },
}
# Note: no confidence field, by design (spec P2: confidence is derived, never elicited).


def parse_claims(
    payload: dict, *, round_: int, role: Role, anon: str, known_ids: set[str]
) -> list[Claim]:
    """Build Claims from tool output; drop hallucinated cross-references."""
    claims: list[Claim] = []
    for raw in payload.get("claims", []):
        evidence = []
        for e in raw.get("evidence_refs", []):
            try:
                from agora.models import EvidenceKind, EvidenceRef
                evidence.append(EvidenceRef(
                    kind=EvidenceKind(e["kind"]), ref=e["ref"], digest=e["digest"],
                ))
            except (KeyError, ValueError):
                continue  # malformed evidence is dropped, claim gate handles the rest
        claims.append(Claim(
            round=round_,
            author_role=role,
            author_anon=anon,
            statement=raw["statement"],
            claim_type=ClaimType(raw["claim_type"]),
            provenance=Provenance(raw["provenance"]),
            evidence=evidence,
            depends_on=[i for i in raw.get("depends_on", []) if i in known_ids],
            contradicts=[i for i in raw.get("contradicts", []) if i in known_ids],
        ))
    return claims


def run_debater(
    llm: LLM,
    *,
    model: str,
    system: str,
    claim_protocol: str,
    task: str,
    round_: int,
    role: Role,
    anon: str,
    known_ids: set[str],
) -> tuple[str, list[Claim]]:
    """Execute one two-pass debater turn. Returns (reasoning, claims)."""
    reasoning = llm.complete(model=model, system=system, user=task, label=role.value)
    extraction_prompt = (
        f"{claim_protocol}\n\n"
        f"Here is your analysis:\n\n<analysis>\n{reasoning}\n</analysis>\n\n"
        "Extract every discrete claim from it and submit via the tool."
    )
    payload = llm.structured(
        model=model, system=system, user=extraction_prompt,
        tool=CLAIM_TOOL, label=role.value,
    )
    claims = parse_claims(
        payload, round_=round_, role=role, anon=anon, known_ids=known_ids
    )
    return reasoning, claims
