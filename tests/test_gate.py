"""The gate CLI must hold every iron hook regardless of what models emit.

Each cmd_* function is exercised the way the skill uses it: JSON on stdin,
a board file on disk, a JSON report on stdout.
"""
import io
import json
from argparse import Namespace

import pytest

from agora.gate import cmd_add, cmd_check_decision, cmd_judge, cmd_render


@pytest.fixture
def board(tmp_path):
    return str(tmp_path / "board.json")


def _claim(statement="the build passes on main", **kw):
    base = {"statement": statement, "claim_type": "EMPIRICAL",
            "provenance": "ASSERTION", "evidence": [],
            "depends_on": [], "contradicts": []}
    base.update(kw)
    return base


def _evidence(digest="pytest: 12 passed in 0.41s"):
    return {"kind": "TEST_RUN", "ref": "uv run pytest", "digest": digest}


def _json_out(capsys):
    return json.loads(capsys.readouterr().out)


def add(board, payload, monkeypatch, capsys, anon="D1", role="QA", rnd=0, cap=5):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    cmd_add(Namespace(board=board, anon=anon, role=role, round=rnd, cap=cap))
    return _json_out(capsys)


def judge(board, payload, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    cmd_judge(Namespace(board=board))
    return _json_out(capsys)


def check(board, text, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    cmd_check_decision(Namespace(board=board))
    return _json_out(capsys)


def load(board):
    with open(board) as f:
        return json.load(f)


# ---------------------------------------------------------------- add / H1-H7

def test_add_collapses_unevidenced_provenance(board, monkeypatch, capsys):
    res = add(board, {"claims": [_claim(provenance="RETRIEVED_SOURCE")]},
              monkeypatch, capsys)
    assert res["accepted"][0]["provenance"] == "ASSERTION"
    assert any("H1" in n for n in res["gate_notes"])


def test_add_keeps_provenance_backed_by_real_evidence(board, monkeypatch, capsys):
    res = add(board, {"claims": [_claim(provenance="TOOL_RESULT",
                                        evidence=[_evidence()])]},
              monkeypatch, capsys)
    assert res["accepted"][0]["provenance"] == "TOOL_RESULT"


def test_add_strips_evidence_with_placeholder_digest(board, monkeypatch, capsys):
    res = add(board, {"claims": [_claim(provenance="TOOL_RESULT",
                                        evidence=[_evidence(digest="ok")])]},
              monkeypatch, capsys)
    assert res["accepted"][0]["provenance"] == "ASSERTION"
    assert any("H5" in n for n in res["gate_notes"])


def test_add_strips_malformed_evidence(board, monkeypatch, capsys):
    res = add(board, {"claims": [_claim(provenance="TOOL_RESULT",
                                        evidence=[{"kind": "TEST_RUN"}])]},
              monkeypatch, capsys)
    assert res["accepted"][0]["provenance"] == "ASSERTION"
    assert any("H5" in n for n in res["gate_notes"])


def test_add_fails_closed_per_claim(board, monkeypatch, capsys):
    res = add(board, {"claims": [_claim(claim_type="OPINION"), _claim()]},
              monkeypatch, capsys)
    assert len(res["rejected"]) == 1
    assert len(res["accepted"]) == 1


def test_add_enforces_per_turn_cap(board, monkeypatch, capsys):
    res = add(board, {"claims": [_claim(f"claim {i}") for i in range(3)]},
              monkeypatch, capsys, cap=2)
    assert len(res["accepted"]) == 2
    assert "cap" in res["rejected"][0]["reason"]


def test_add_strips_links_to_unknown_ids(board, monkeypatch, capsys):
    add(board, {"claims": [_claim(depends_on=["ffffffffffff"],
                                  contradicts=["eeeeeeeeeeee"])]},
        monkeypatch, capsys)
    c = load(board)["claims"][0]
    assert c["depends_on"] == [] and c["contradicts"] == []


def test_add_keeps_links_to_board_ids(board, monkeypatch, capsys):
    first = add(board, {"claims": [_claim()]}, monkeypatch, capsys)
    cid = first["accepted"][0]["id"]
    add(board, {"claims": [_claim("a rebuttal", contradicts=[cid])]},
        monkeypatch, capsys, anon="D2")
    assert load(board)["claims"][1]["contradicts"] == [cid]


def test_add_flags_confidence_language(board, monkeypatch, capsys):
    res = add(board, {"claims": [_claim("I am 95% confident this holds")]},
              monkeypatch, capsys)
    assert any("H7" in n for n in res["gate_notes"])


def test_add_records_only_valid_endorsements(board, monkeypatch, capsys):
    cid = add(board, {"claims": [_claim()]},
              monkeypatch, capsys)["accepted"][0]["id"]
    res = add(board, {"claims": [], "endorsements": [
        {"claim_id": cid, "stance": "ENDORSE", "reason": "checked it"},
        "not an object",
        {"claim_id": "ffffffffffff", "stance": "ENDORSE", "reason": "fake id"},
        {"claim_id": cid, "stance": "MAYBE", "reason": "bad stance"},
    ]}, monkeypatch, capsys, anon="D2")
    assert any("H3" in n for n in res["gate_notes"])
    endorsements = load(board)["endorsements"]
    assert len(endorsements) == 1
    assert endorsements[0]["claim_id"] == cid


# --------------------------------------------------------------------- render

def test_render_shows_scores_bands_and_disagreements(board, monkeypatch, capsys):
    a = add(board, {"claims": [_claim("alpha")]}, monkeypatch, capsys)
    b = add(board, {"claims": [_claim("beta", contradicts=[a["accepted"][0]["id"]])]},
            monkeypatch, capsys, anon="D2")
    ids = [a["accepted"][0]["id"], b["accepted"][0]["id"]]
    add(board, {"claims": [], "endorsements": [
        {"claim_id": ids[0], "stance": "ENDORSE", "reason": "yes"}]},
        monkeypatch, capsys, anon="D3")
    judge(board, {"assessments": [{"claim_id": i, "warrant_band": "WEAK"}
                                  for i in ids],
                  "disagreements": [{"claim_ids": ids, "dclass": "EMPIRICAL",
                                     "rationale": "alpha vs beta"}]},
          monkeypatch, capsys)
    cmd_render(Namespace(board=board))
    out = capsys.readouterr().out
    assert "+1/-0" in out and "band=WEAK" in out
    assert "DISAGREEMENTS" in out and "EMPIRICAL, OPEN" in out


# ---------------------------------------------------------------- judge / H4-H8

def test_judge_clamps_bands_to_provenance_ceiling(board, monkeypatch, capsys):
    cid = add(board, {"claims": [_claim()]},
              monkeypatch, capsys)["accepted"][0]["id"]
    res = judge(board, {"assessments": [
        {"claim_id": cid, "warrant_band": "STRONG"}]}, monkeypatch, capsys)
    assert load(board)["claims"][0]["warrant_band"] == "WEAK"
    assert any("H6" in n for n in res["clamped"])


def test_judge_ignores_invented_claim_ids(board, monkeypatch, capsys):
    add(board, {"claims": [_claim()]}, monkeypatch, capsys)
    judge(board, {"assessments": [
        {"claim_id": "ffffffffffff", "warrant_band": "VERIFIED"}]},
          monkeypatch, capsys)
    assert load(board)["claims"][0]["warrant_band"] == "WEAK"


def test_judge_never_leaves_a_claim_unassessed(board, monkeypatch, capsys):
    add(board, {"claims": [_claim(provenance="TOOL_RESULT",
                                  evidence=[_evidence()])]},
        monkeypatch, capsys)
    judge(board, {"assessments": []}, monkeypatch, capsys)
    assert load(board)["claims"][0]["warrant_band"] == "WEAK"


def test_judge_routes_disagreements_by_class(board, monkeypatch, capsys):
    ids = [add(board, {"claims": [_claim(s)]}, monkeypatch, capsys,
               anon=f"D{i}")["accepted"][0]["id"]
           for i, s in enumerate(["fact a", "fact b", "value a", "value b"])]
    res = judge(board, {"assessments": [], "disagreements": [
        {"claim_ids": ids[:2], "dclass": "EMPIRICAL", "rationale": "facts clash"},
        {"claim_ids": ids[2:], "dclass": "VALUE_TRADEOFF", "rationale": "taste"},
    ]}, monkeypatch, capsys)
    by_class = {d["dclass"]: d for d in load(board)["disagreements"]}
    assert by_class["EMPIRICAL"]["status"] == "OPEN"
    assert by_class["VALUE_TRADEOFF"]["status"] == "PRESERVED"
    assert len(res["empirical_open"]) == 1
    assert res["open_disagreements"] == 1


def test_judge_flags_suspect_consensus(board, monkeypatch, capsys):
    cid = add(board, {"claims": [_claim()]},
              monkeypatch, capsys)["accepted"][0]["id"]
    for anon in ("D2", "D3"):
        add(board, {"claims": [], "endorsements": [
            {"claim_id": cid, "stance": "ENDORSE", "reason": "sounds right"}]},
            monkeypatch, capsys, anon=anon)
    res = judge(board, {"assessments": []}, monkeypatch, capsys)
    assert cid in res["suspect_consensus"]


# ------------------------------------------------- disagreement lifecycle

def _two_claim_dispute(board, monkeypatch, capsys):
    ids = [add(board, {"claims": [_claim(s)]}, monkeypatch, capsys,
               anon=f"D{i + 1}")["accepted"][0]["id"]
           for i, s in enumerate(["it is fast", "it is slow"])]
    judge(board, {"assessments": [], "disagreements": [
        {"claim_ids": ids, "dclass": "EMPIRICAL", "rationale": "speed dispute"}]},
          monkeypatch, capsys)
    return load(board)["disagreements"][0]


def test_judge_persists_undeclared_disagreements(board, monkeypatch, capsys):
    before = _two_claim_dispute(board, monkeypatch, capsys)
    judge(board, {"assessments": [], "disagreements": []}, monkeypatch, capsys)
    after = load(board)["disagreements"]
    assert len(after) == 1
    assert after[0]["id"] == before["id"] and after[0]["status"] == "OPEN"


def test_judge_merges_redeclared_cluster_without_duplicating(board, monkeypatch,
                                                             capsys):
    before = _two_claim_dispute(board, monkeypatch, capsys)
    judge(board, {"assessments": [], "disagreements": [
        {"claim_ids": before["claim_ids"], "dclass": "EMPIRICAL",
         "rationale": "still disputed"}]}, monkeypatch, capsys)
    after = load(board)["disagreements"]
    assert len(after) == 1
    assert after[0]["rationale"] == "still disputed"


def test_judge_applies_explicit_resolutions(board, monkeypatch, capsys):
    dis = _two_claim_dispute(board, monkeypatch, capsys)
    res = judge(board, {"assessments": [], "resolutions": [
        {"disagreement_id": dis["id"], "status": "RESOLVED",
         "rationale": "resolver produced the benchmark"}]}, monkeypatch, capsys)
    assert dis["id"] in res["resolved"]
    assert load(board)["disagreements"][0]["status"] == "RESOLVED"
    assert res["open_disagreements"] == 0


# --------------------------------------------------- check-decision / H9-H10

def test_check_decision_flags_unknown_and_contested_ids(board, monkeypatch,
                                                        capsys):
    cid = add(board, {"claims": [_claim()]},
              monkeypatch, capsys)["accepted"][0]["id"]
    judge(board, {"assessments": [
        {"claim_id": cid, "warrant_band": "CONTESTED"}]}, monkeypatch, capsys)
    res = check(board, f"Decide per {cid} and ffffffffffff.", monkeypatch, capsys)
    assert not res["ok"]
    assert any("NOT ON BOARD" in p for p in res["problems"])
    assert any("CONTESTED" in p for p in res["problems"])


def test_check_decision_requires_claim_citations(board, monkeypatch, capsys):
    add(board, {"claims": [_claim()]}, monkeypatch, capsys)
    res = check(board, "We should do the thing.", monkeypatch, capsys)
    assert not res["ok"]
    assert any("no claim ids" in p for p in res["problems"])


def test_check_decision_rejects_claims_inside_open_disagreements(board,
                                                                 monkeypatch,
                                                                 capsys):
    dis = _two_claim_dispute(board, monkeypatch, capsys)
    res = check(board, f"Decide per {dis['claim_ids'][0]}.", monkeypatch, capsys)
    assert not res["ok"]
    assert any("OPEN disagreement" in p for p in res["problems"])


def test_check_decision_warns_on_unscrutinized_claims(board, monkeypatch,
                                                      capsys):
    cid = add(board, {"claims": [_claim()]},
              monkeypatch, capsys)["accepted"][0]["id"]
    judge(board, {"assessments": []}, monkeypatch, capsys)
    res = check(board, f"Decide per {cid}.", monkeypatch, capsys)
    assert res["ok"]
    assert any("UNSCRUTINIZED" in w for w in res["warnings"])


def test_check_decision_requires_preserved_disclosure(board, monkeypatch,
                                                      capsys):
    ids = [add(board, {"claims": [_claim(s)]}, monkeypatch, capsys,
               anon=f"D{i + 1}")["accepted"][0]["id"]
           for i, s in enumerate(["value a", "value b", "a settled fact"])]
    judge(board, {"assessments": [], "disagreements": [
        {"claim_ids": ids[:2], "dclass": "VALUE_TRADEOFF",
         "rationale": "taste"}]}, monkeypatch, capsys)
    dis_id = load(board)["disagreements"][0]["id"]

    silent = check(board, f"Decide per {ids[2]}.", monkeypatch, capsys)
    assert not silent["ok"]
    assert any("H10" in p for p in silent["problems"])

    disclosed = check(board, f"Decide per {ids[2]}. Preserved trade-off "
                             f"{dis_id} belongs to the human.",
                      monkeypatch, capsys)
    assert disclosed["ok"]
