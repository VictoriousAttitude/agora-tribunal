"""Core data models.

Spec references: section 6 (claims and evidence), 7.2 (warrant bands),
8 (disagreements), 10.2 (ledger entries).
"""
from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Role(StrEnum):
    ARCHITECT = "ARCHITECT"
    QA = "QA"
    SCIENTIST = "SCIENTIST"
    HACKER = "HACKER"
    SRE = "SRE"
    EMPIRICIST = "EMPIRICIST"
    PRAGMATIST = "PRAGMATIST"


class ClaimType(StrEnum):
    EMPIRICAL = "EMPIRICAL"          # a fact could settle it
    DEFINITIONAL = "DEFINITIONAL"    # about the meaning of terms
    NORMATIVE = "NORMATIVE"          # value or priority judgment
    PROCEDURAL = "PROCEDURAL"        # about process or method


class Provenance(StrEnum):
    TOOL_RESULT = "TOOL_RESULT"
    RETRIEVED_SOURCE = "RETRIEVED_SOURCE"
    EXTERNAL_CITATION = "EXTERNAL_CITATION"
    ASSERTION = "ASSERTION"


class WarrantBand(StrEnum):
    CONTESTED = "CONTESTED"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERIFIED = "VERIFIED"


WARRANT_RANK: dict[WarrantBand, int] = {
    WarrantBand.CONTESTED: 0,
    WarrantBand.WEAK: 1,
    WarrantBand.MODERATE: 2,
    WarrantBand.STRONG: 3,
    WarrantBand.VERIFIED: 4,
}

# Provenance ceilings (spec 6.3). Confidence is derived, never elicited (P2).
WARRANT_CEILING: dict[Provenance, WarrantBand] = {
    Provenance.TOOL_RESULT: WarrantBand.VERIFIED,
    Provenance.RETRIEVED_SOURCE: WarrantBand.STRONG,
    Provenance.EXTERNAL_CITATION: WarrantBand.STRONG,
    Provenance.ASSERTION: WarrantBand.WEAK,
}


def clamp_band(band: WarrantBand, provenance: Provenance) -> WarrantBand:
    """Mechanically enforce the provenance ceiling regardless of judge output."""
    ceiling = WARRANT_CEILING[provenance]
    return band if WARRANT_RANK[band] <= WARRANT_RANK[ceiling] else ceiling


class ClaimStatus(StrEnum):
    OPEN = "OPEN"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    SUPERSEDED = "SUPERSEDED"


class EvidenceKind(StrEnum):
    TEST_RUN = "TEST_RUN"
    EVAL_RESULT = "EVAL_RESULT"
    BENCHMARK = "BENCHMARK"
    RETRIEVAL_HIT = "RETRIEVAL_HIT"
    WEB_SOURCE = "WEB_SOURCE"
    PRIOR_LEDGER = "PRIOR_LEDGER"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"


class Metric(BaseModel):
    name: str
    value: float
    unit: str
    ci: str | None = None


class EvidenceRef(BaseModel):
    kind: EvidenceKind
    ref: str      # run id / doc id / url / ledger id
    digest: str   # short hash or summary for audit and dedup
    metric: Metric | None = None


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Claim(BaseModel):
    id: str = Field(default_factory=_new_id)
    round: int
    author_role: Role          # visible to Judge/Orchestrator only (spec 6.1)
    author_anon: str           # stable per-session handle shown to peers
    statement: str
    claim_type: ClaimType
    provenance: Provenance
    evidence: list[EvidenceRef] = Field(default_factory=list)
    warrant_band: WarrantBand | None = None  # set by Judge
    depends_on: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.OPEN

    @model_validator(mode="after")
    def _gate_provenance(self) -> Claim:
        # Mechanical part of the gate (spec 6.4): claimed provenance without
        # evidence collapses to ASSERTION (capped at WEAK by the ceiling).
        if self.provenance != Provenance.ASSERTION and not self.evidence:
            self.provenance = Provenance.ASSERTION
        return self


class DisagreementClass(StrEnum):
    EMPIRICAL = "EMPIRICAL"
    DEFINITIONAL = "DEFINITIONAL"
    VALUE_TRADEOFF = "VALUE_TRADEOFF"
    ERROR = "ERROR"


class DisagreementRoute(StrEnum):
    DISPATCH_RESOLVER = "DISPATCH_RESOLVER"
    OPERATIONALIZE = "OPERATIONALIZE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    ADJUDICATE = "ADJUDICATE"


# Routing table (spec 8.2).
CLASS_ROUTE: dict[DisagreementClass, DisagreementRoute] = {
    DisagreementClass.EMPIRICAL: DisagreementRoute.DISPATCH_RESOLVER,
    DisagreementClass.DEFINITIONAL: DisagreementRoute.OPERATIONALIZE,
    DisagreementClass.VALUE_TRADEOFF: DisagreementRoute.ESCALATE_HUMAN,
    DisagreementClass.ERROR: DisagreementRoute.ADJUDICATE,
}


class DisagreementStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    PRESERVED = "PRESERVED"


class Disagreement(BaseModel):
    id: str = Field(default_factory=_new_id)
    claim_ids: list[str]  # cluster, not just a pair
    dclass: DisagreementClass
    route: DisagreementRoute
    status: DisagreementStatus = DisagreementStatus.OPEN
    rationale: str = ""
    resolution: EvidenceRef | None = None


class Frame(BaseModel):
    """FRAME output (spec 9.1): decomposition shown before any debate round."""
    question: str
    sub_questions: list[str]
    success_criteria: list[str]
    roster: list[Role]
    anon_handles: dict[str, str]  # role value -> handle; judge/orchestrator only


class Verdict(BaseModel):
    decision: str  # neutral write-up by the Synthesizer
    preserved_disagreements: list[str] = Field(default_factory=list)
    mean_warrant_rank: float = 0.0
    termination: str = ""


class LedgerKind(StrEnum):
    CONCLUSION = "CONCLUSION"
    OPEN_DISAGREEMENT = "OPEN_DISAGREEMENT"
    MISTAKE = "MISTAKE"


class LedgerEntry(BaseModel):
    """Cross-session memory entry (spec 10.2). Unused until Phase 4."""
    id: str = Field(default_factory=_new_id)
    topic_key: str
    kind: LedgerKind
    statement: str
    warrant_band: WarrantBand
    evidence_digest: str
    session_id: str
    timestamp: str
    status: str = "ACTIVE"  # ACTIVE | CHALLENGED | SUPERSEDED
    supersedes: str | None = None
