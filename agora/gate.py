"""Mechanical gate for skill-mode AGORA.

The orchestrator (Claude Code) shells out to this CLI. All iron hooks that can
be code live here; the skill never trusts model output where this can check.

Subcommands:
  add            validate a debater's claim JSON (stdin) onto the board
  render         print the anonymized board for prompts
  judge          apply judge bands (stdin) with ceiling clamps + stats
  check-decision verify claim ids cited in the decision text (stdin)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

from agora.models import (
    CLASS_ROUTE,
    WARRANT_RANK,
    Claim,
    ClaimType,
    DisagreementClass,
    DisagreementRoute,
    DisagreementStatus,
    EvidenceKind,
    EvidenceRef,
    Provenance,
    Role,
    WarrantBand,
    clamp_band,
)

MIN_DIGEST = 12  # H5: evidence must quote real output, not a placeholder
CONFIDENCE_RE = re.compile(r"\b\d{1,3}\s*%|\bconfiden(t|ce)\b|\bcertain(ty)?\b", re.I)
ID_RE = re.compile(r"\b[0-9a-f]{12}\b")


def load_board(path: str) -> dict:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text())
    return {"claims": [], "endorsements": [], "disagreements": []}


def save_board(path: str, board: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(board, indent=2))


def emit(obj: dict) -> None:
    print(json.dumps(obj, indent=2))


def cmd_add(args: argparse.Namespace) -> None:
    board = load_board(args.board)
    known = {c["id"] for c in board["claims"]}
    payload = json.load(sys.stdin)
    accepted: list[Claim] = []
    rejected: list[dict] = []
    notes: list[str] = []

    for raw in payload.get("claims", []):
        if args.cap and len(accepted) >= args.cap:
            rejected.append({"statement": str(raw.get("statement", ""))[:80],
                             "reason": f"over per-turn cap of {args.cap}"})
            continue
        evidence: list[EvidenceRef] = []
        for e in raw.get("evidence", []):
            try:
                ref = EvidenceRef(kind=EvidenceKind(e["kind"]),
                                  ref=str(e["ref"]).strip(),
                                  digest=str(e["digest"]).strip())
            except Exception:
                notes.append("evidence stripped: malformed ref (H5)")
                continue
            if not ref.ref or len(ref.digest) < MIN_DIGEST:
                notes.append(f"evidence stripped: digest under {MIN_DIGEST} chars (H5)")
                continue
            evidence.append(ref)
        claimed_prov = str(raw.get("provenance", ""))
        try:
            claim = Claim(
                round=args.round,
                author_role=Role(args.role),
                author_anon=args.anon,
                statement=str(raw["statement"]).strip(),
                claim_type=ClaimType(raw["claim_type"]),
                provenance=Provenance(claimed_prov),
                evidence=evidence,
                depends_on=[i for i in raw.get("depends_on", []) if i in known],
                contradicts=[i for i in raw.get("contradicts", []) if i in known],
            )
        except Exception as exc:  # H3: fail closed
            rejected.append({"statement": str(raw.get("statement", ""))[:80],
                             "reason": str(exc)[:160]})
            continue
        if claim.provenance.value != claimed_prov:
            notes.append(f"{claim.id}: provenance collapsed to ASSERTION, no valid evidence (H1)")
        if CONFIDENCE_RE.search(claim.statement):
            notes.append(f"{claim.id}: confidence language flagged, will not be honored (H7)")
        accepted.append(claim)

    board["claims"].extend(json.loads(c.model_dump_json()) for c in accepted)
    for e in payload.get("endorsements", []):
        if not isinstance(e, dict):
            notes.append("endorsement stripped: not an object (H3)")
            continue
        if e.get("claim_id") in known and e.get("stance") in ("ENDORSE", "CHALLENGE"):
            board["endorsements"].append({
                "claim_id": e["claim_id"], "by": args.anon,
                "stance": e["stance"], "reason": str(e.get("reason", ""))[:240],
            })
    save_board(args.board, board)
    emit({
        "accepted": [{"id": c.id, "provenance": c.provenance, "statement": c.statement}
                     for c in accepted],
        "rejected": rejected,
        "gate_notes": notes,
    })


def _endorsement_score(board: dict, claim_id: str) -> tuple[int, int]:
    plus = sum(1 for e in board["endorsements"]
               if e["claim_id"] == claim_id and e["stance"] == "ENDORSE")
    minus = sum(1 for e in board["endorsements"]
                if e["claim_id"] == claim_id and e["stance"] == "CHALLENGE")
    return plus, minus


def cmd_render(args: argparse.Namespace) -> None:
    board = load_board(args.board)
    for c in board["claims"]:
        plus, minus = _endorsement_score(board, c["id"])
        band = f" band={c['warrant_band']}" if c.get("warrant_band") else ""
        ev = f" evidence={len(c['evidence'])}" if c["evidence"] else ""
        print(f"[{c['id']}] ({c['author_anon']}, r{c['round']}, {c['claim_type']}, "
              f"{c['provenance']}{ev}{band}, +{plus}/-{minus}) {c['statement']}")
    if board["disagreements"]:
        print("\nDISAGREEMENTS")
        for d in board["disagreements"]:
            print(f"[dis {d.get('id', '?')}] ({d['dclass']}, {d['status']}, "
                  f"claims={','.join(d['claim_ids'])}) {d.get('rationale', '')}")


def cmd_judge(args: argparse.Namespace) -> None:
    board = load_board(args.board)
    by_id = {c["id"]: c for c in board["claims"]}
    payload = json.load(sys.stdin)
    clamped: list[str] = []

    for a in payload.get("assessments", []):
        c = by_id.get(a.get("claim_id"))
        if c is None:
            continue  # H4: invented id
        try:
            band = WarrantBand(a["warrant_band"])
        except Exception:
            band = WarrantBand.WEAK
        final = clamp_band(band, Provenance(c["provenance"]))
        if final != band:
            clamped.append(f"{c['id']}: {band} -> {final} (ceiling, H6)")
        c["warrant_band"] = final.value
    for c in board["claims"]:  # never leave a claim unassessed
        if not c.get("warrant_band"):
            c["warrant_band"] = clamp_band(
                WarrantBand.WEAK, Provenance(c["provenance"])).value

    # Disagreements are a lifecycle, never wiped: existing entries persist
    # until an explicit resolution. The judge declares new clusters and may
    # resolve open ones; re-declaring an existing cluster updates rationale.
    disagreements = board["disagreements"]
    for d in disagreements:
        d.setdefault("id", uuid.uuid4().hex[:12])
    by_key = {(frozenset(d["claim_ids"]), d["dclass"]): d for d in disagreements}
    for d in payload.get("disagreements", []):
        ids = [i for i in d.get("claim_ids", []) if i in by_id]
        if len(ids) < 2:
            continue
        try:
            dclass = DisagreementClass(d["dclass"])
        except Exception:
            continue
        key = (frozenset(ids), dclass.value)
        if key in by_key:
            if d.get("rationale"):
                by_key[key]["rationale"] = str(d["rationale"])[:400]
            continue
        route = CLASS_ROUTE[dclass]
        status = (DisagreementStatus.PRESERVED
                  if route == DisagreementRoute.ESCALATE_HUMAN
                  else DisagreementStatus.OPEN)
        entry = {"id": uuid.uuid4().hex[:12], "claim_ids": ids,
                 "dclass": dclass.value, "route": route.value,
                 "status": status.value,
                 "rationale": str(d.get("rationale", ""))[:400]}
        disagreements.append(entry)
        by_key[key] = entry

    by_did = {d["id"]: d for d in disagreements}
    resolved: list[str] = []
    for r in payload.get("resolutions", []):
        d = by_did.get(r.get("disagreement_id")) if isinstance(r, dict) else None
        if d is None or d["status"] != DisagreementStatus.OPEN.value:
            continue
        if r.get("status") != DisagreementStatus.RESOLVED.value:
            continue
        d["status"] = DisagreementStatus.RESOLVED.value
        if r.get("rationale"):
            d["rationale"] = str(r["rationale"])[:400]
        resolved.append(d["id"])

    suspects = []  # H8: agreement is not evidence
    for c in board["claims"]:
        plus, minus = _endorsement_score(board, c["id"])
        if plus - minus >= 2 and WARRANT_RANK[WarrantBand(c["warrant_band"])] <= 1:
            suspects.append(c["id"])

    ranks = [WARRANT_RANK[WarrantBand(c["warrant_band"])] for c in board["claims"]]
    mean = sum(ranks) / len(ranks) if ranks else 0.0
    open_count = sum(1 for d in disagreements if d["status"] == "OPEN")
    save_board(args.board, board)
    emit({
        "mean_warrant_rank": round(mean, 2),
        "open_disagreements": open_count,
        "converged": open_count == 0 and mean >= 2.0,
        "empirical_open": [d for d in disagreements
                           if d["status"] == "OPEN" and d["dclass"] == "EMPIRICAL"],
        "suspect_consensus": suspects,
        "clamped": clamped,
        "resolved": resolved,
    })


def cmd_check_decision(args: argparse.Namespace) -> None:
    board = load_board(args.board)
    by_id = {c["id"]: c for c in board["claims"]}
    text = sys.stdin.read()
    found = set(ID_RE.findall(text))
    dis = board["disagreements"]
    dis_ids = {d["id"] for d in dis if d.get("id")}
    open_member: dict[str, list[str]] = {}
    for d in dis:
        if d["status"] == "OPEN":
            for i in d["claim_ids"]:
                open_member.setdefault(i, []).append(d.get("id", "?"))

    report, problems, warnings = [], [], []
    cited = sorted(found - dis_ids)
    for cid in cited:
        c = by_id.get(cid)
        if c is None:
            problems.append(f"{cid}: cited but NOT ON BOARD (H9)")
            continue
        band = c.get("warrant_band", "?")
        report.append({"id": cid, "band": band, "statement": c["statement"][:100]})
        if band == "CONTESTED":
            problems.append(f"{cid}: CONTESTED claim treated as load-bearing (H9)")
        if cid in open_member:
            problems.append(f"{cid}: inside OPEN disagreement "
                            f"{','.join(open_member[cid])}, not settled (H9)")
        plus, minus = _endorsement_score(board, cid)
        if plus + minus == 0:
            warnings.append(f"{cid}: UNSCRUTINIZED, no debater ever endorsed "
                            "or challenged this claim")
    for d in dis:
        if d["status"] != "PRESERVED":
            continue
        disclosed = (d.get("id") in found
                     or any(i in found for i in d["claim_ids"]))
        if not disclosed:
            problems.append(f"preserved disagreement {d.get('id', '?')} "
                            "not disclosed in decision (H10)")
    if not any(cid in by_id for cid in cited):
        problems.append("decision cites no claim ids at all (H9)")
    emit({"cited": report, "problems": problems, "warnings": warnings,
          "ok": not problems})


def main() -> None:
    p = argparse.ArgumentParser(prog="gate")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--board", required=True)
    a.add_argument("--anon", required=True)
    a.add_argument("--role", required=True)
    a.add_argument("--round", type=int, required=True)
    a.add_argument("--cap", type=int, default=5)
    a.set_defaults(fn=cmd_add)

    r = sub.add_parser("render")
    r.add_argument("--board", required=True)
    r.set_defaults(fn=cmd_render)

    j = sub.add_parser("judge")
    j.add_argument("--board", required=True)
    j.set_defaults(fn=cmd_judge)

    c = sub.add_parser("check-decision")
    c.add_argument("--board", required=True)
    c.set_defaults(fn=cmd_check_decision)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
