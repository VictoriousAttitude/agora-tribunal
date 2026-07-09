"""Gate mechanics must hold regardless of what any model outputs."""
from agora.models import (
    Claim,
    ClaimType,
    EvidenceKind,
    EvidenceRef,
    Provenance,
    Role,
    WarrantBand,
    clamp_band,
)


def _claim(**kw) -> Claim:
    base = dict(
        round=0,
        author_role=Role.QA,
        author_anon="D2",
        statement="x",
        claim_type=ClaimType.EMPIRICAL,
        provenance=Provenance.ASSERTION,
    )
    base.update(kw)
    return Claim(**base)


def test_provenance_without_evidence_collapses_to_assertion():
    c = _claim(provenance=Provenance.TOOL_RESULT)  # no evidence attached
    assert c.provenance == Provenance.ASSERTION


def test_provenance_with_evidence_is_kept():
    ev = EvidenceRef(kind=EvidenceKind.TEST_RUN, ref="run1", digest="abc")
    c = _claim(provenance=Provenance.TOOL_RESULT, evidence=[ev])
    assert c.provenance == Provenance.TOOL_RESULT


def test_assertion_band_capped_at_weak():
    assert clamp_band(WarrantBand.VERIFIED, Provenance.ASSERTION) == WarrantBand.WEAK
    assert clamp_band(WarrantBand.CONTESTED, Provenance.ASSERTION) == WarrantBand.CONTESTED


def test_retrieved_source_capped_at_strong():
    assert clamp_band(WarrantBand.VERIFIED, Provenance.RETRIEVED_SOURCE) == WarrantBand.STRONG


def test_tool_result_uncapped():
    assert clamp_band(WarrantBand.VERIFIED, Provenance.TOOL_RESULT) == WarrantBand.VERIFIED
