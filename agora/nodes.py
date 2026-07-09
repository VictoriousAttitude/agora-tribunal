"""Graph nodes. Each method is a LangGraph node over DeliberationState.

Flow (spec 9, Phase 1 subset): FRAME -> GROUND (independent, parallel-in-spirit)
-> CRITIQUE (simultaneous, against round snapshot) -> JUDGE -> CONVERGENCE
-> SYNTHESIZE.
"""
from __future__ import annotations

from pathlib import Path

from agora.config import AgoraConfig
from agora.debater import run_debater
from agora.llm import LLM
from agora.models import (
    CLASS_ROUTE,
    WARRANT_RANK,
    Claim,
    Disagreement,
    DisagreementClass,
    DisagreementRoute,
    DisagreementStatus,
    Frame,
    Verdict,
    WarrantBand,
    clamp_band,
)
from agora.state import DeliberationState

FRAME_TOOL = {
    "name": "submit_frame",
    "description": "Submit the problem decomposition before debate begins.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sub_questions": {"type": "array", "items": {"type": "string"}},
            "success_criteria": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["sub_questions", "success_criteria"],
    },
}

JUDGE_TOOL = {
    "name": "submit_assessment",
    "description": "Assess every claim and identify disagreement clusters.",
    "input_schema": {
        "type": "object",
        "properties": {
            "assessments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string"},
                        "warrant_band": {
                            "type": "string",
                            "enum": [b.value for b in WarrantBand],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["claim_id", "warrant_band"],
                },
            },
            "disagreements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_ids": {"type": "array", "items": {"type": "string"}},
                        "dclass": {
                            "type": "string",
                            "enum": [c.value for c in DisagreementClass],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["claim_ids", "dclass", "rationale"],
                },
            },
        },
        "required": ["assessments", "disagreements"],
    },
}


def _render_claims(claims: list[Claim]) -> str:
    """Anonymized claim listing shown to peers and judge."""
    lines = []
    for c in claims:
        ev = f" evidence={len(c.evidence)}" if c.evidence else ""
        band = f" band={c.warrant_band}" if c.warrant_band else ""
        lines.append(
            f"[{c.id}] ({c.author_anon}, r{c.round}, {c.claim_type}, "
            f"{c.provenance}{ev}{band}) {c.statement}"
        )
    return "\n".join(lines) or "(no claims yet)"


class Nodes:
    def __init__(self, cfg: AgoraConfig, llm: LLM):
        self.cfg = cfg
        self.llm = llm
        self.prompts = {
            p.stem: p.read_text() for p in Path(cfg.paths.prompts_dir).glob("*.md")
        }
        self._anon = {
            entry.role.value: f"D{i + 1}" for i, entry in enumerate(cfg.roster)
        }
        # Set by should_continue; conditional edges cannot write state in LangGraph.
        self._termination = "MAX_ROUNDS"

    # ---- FRAME (spec 9.1) ----
    def frame(self, state: DeliberationState) -> dict:
        payload = self.llm.structured(
            model=self.cfg.model_for(self.cfg.meta.frame_tier),
            system=self.prompts["frame"],
            user=f"Question under deliberation:\n{state['question']}",
            tool=FRAME_TOOL,
            label="FRAME",
        )
        frame = Frame(
            question=state["question"],
            sub_questions=payload["sub_questions"],
            success_criteria=payload["success_criteria"],
            roster=[e.role for e in self.cfg.roster],
            anon_handles=self._anon,
        )
        return {"frame": frame, "round": 0, "claims": [], "disagreements": []}

    # ---- GROUND: independent initial positions (spec 9.2, anti-anchoring) ----
    def ground(self, state: DeliberationState) -> dict:
        frame = state["frame"]
        task = (
            f"Question: {frame.question}\n\n"
            f"Sub-questions:\n" + "\n".join(f"- {q}" for q in frame.sub_questions)
            + "\n\nSuccess criteria:\n"
            + "\n".join(f"- {c}" for c in frame.success_criteria)
            + "\n\nGive your independent expert position. You have not seen any "
            "other debater's output."
        )
        claims: list[Claim] = []
        reasoning: dict[str, str] = {}
        for entry in self.cfg.roster:
            anon = self._anon[entry.role.value]
            text, new = run_debater(
                self.llm,
                model=self.cfg.model_for(entry.tier),
                system=self.prompts[entry.role.value.lower()],
                claim_protocol=self.prompts["_claim_protocol"],
                task=task,
                round_=0,
                role=entry.role,
                anon=anon,
                known_ids=set(),
            )
            claims.extend(new)
            reasoning[f"{anon} r0"] = text
        return {"claims": claims, "reasoning": reasoning, "round": 1}

    # ---- CRITIQUE: simultaneous, all against the same snapshot ----
    def critique(self, state: DeliberationState) -> dict:
        snapshot = list(state["claims"])  # round-0 snapshot, same for everyone
        known_ids = {c.id for c in snapshot}
        rendered = _render_claims(snapshot)
        claims = list(snapshot)
        reasoning = dict(state.get("reasoning", {}))
        for entry in self.cfg.roster:
            anon = self._anon[entry.role.value]
            task = (
                f"Question: {state['frame'].question}\n\n"
                f"All claims on the board (you are {anon}):\n{rendered}\n\n"
                "Critique the claims of others: attack weak provenance, surface "
                "contradictions, concede where the evidence beats yours. Reference "
                "claim ids. New claims may contradict or depend on existing ids."
            )
            text, new = run_debater(
                self.llm,
                model=self.cfg.model_for(entry.tier),
                system=self.prompts[entry.role.value.lower()],
                claim_protocol=self.prompts["_claim_protocol"],
                task=task,
                round_=state["round"],
                role=entry.role,
                anon=anon,
                known_ids=known_ids,
            )
            claims.extend(new)
            reasoning[f"{anon} r{state['round']}"] = text
        return {"claims": claims, "reasoning": reasoning}

    # ---- JUDGE (spec 7): bands + disagreement clusters, ceilings enforced ----
    def judge(self, state: DeliberationState) -> dict:
        claims = [c.model_copy() for c in state["claims"]]
        by_id = {c.id: c for c in claims}
        payload = self.llm.structured(
            model=self.cfg.model_for(self.cfg.meta.judge_tier),
            system=self.prompts["judge"],
            user=(
                f"Question: {state['frame'].question}\n\n"
                f"Claims:\n{_render_claims(claims)}\n\n"
                "Assess every claim id exactly once, then list disagreement clusters."
            ),
            tool=JUDGE_TOOL,
            label="JUDGE",
        )
        for a in payload["assessments"]:
            claim = by_id.get(a["claim_id"])
            if claim is None:
                continue  # hallucinated id
            claim.warrant_band = clamp_band(
                WarrantBand(a["warrant_band"]), claim.provenance
            )
        for c in claims:  # judge skipped it: default to WEAK, never unassessed
            if c.warrant_band is None:
                c.warrant_band = clamp_band(WarrantBand.WEAK, c.provenance)

        disagreements: list[Disagreement] = []
        for d in payload["disagreements"]:
            ids = [i for i in d["claim_ids"] if i in by_id]
            if len(ids) < 2:
                continue
            dclass = DisagreementClass(d["dclass"])
            route = CLASS_ROUTE[dclass]
            status = (
                DisagreementStatus.PRESERVED  # v0: no human loop, preserve (spec 8.3)
                if route == DisagreementRoute.ESCALATE_HUMAN
                else DisagreementStatus.OPEN
            )
            disagreements.append(Disagreement(
                claim_ids=ids, dclass=dclass, route=route,
                status=status, rationale=d["rationale"],
            ))
        return {"claims": claims, "disagreements": disagreements}

    # ---- CONVERGENCE_CHECK (spec 9.3) ----
    def should_continue(self, state: DeliberationState) -> str:
        if self.llm.meter.total >= self.cfg.budget.max_total_tokens:
            self._termination = "BUDGET"
            return "synthesize"
        open_disagreements = [
            d for d in state["disagreements"] if d.status == DisagreementStatus.OPEN
        ]
        mean = self._mean_warrant(state["claims"])
        threshold = WARRANT_RANK[self.cfg.thresholds.min_mean_warrant]
        if not open_disagreements and mean >= threshold:
            self._termination = "CONVERGENCE"
            return "synthesize"
        if state["round"] >= self.cfg.budget.max_rounds:
            self._termination = "MAX_ROUNDS"
            return "synthesize"
        return "critique"

    @staticmethod
    def _mean_warrant(claims: list[Claim]) -> float:
        ranks = [WARRANT_RANK[c.warrant_band] for c in claims if c.warrant_band]
        return sum(ranks) / len(ranks) if ranks else 0.0

    # ---- SYNTHESIZE (spec 4: neutral write-up, preserves disagreements) ----
    def synthesize(self, state: DeliberationState) -> dict:
        unresolved = [
            d for d in state["disagreements"]
            if d.status in (DisagreementStatus.OPEN, DisagreementStatus.PRESERVED)
        ]
        dis_text = "\n".join(
            f"- [{d.dclass}] {d.rationale} (claims: {', '.join(d.claim_ids)})"
            for d in unresolved
        ) or "(none)"
        decision = self.llm.complete(
            model=self.cfg.model_for(self.cfg.meta.synthesizer_tier),
            system=self.prompts["synthesizer"],
            user=(
                f"Question: {state['frame'].question}\n\n"
                f"Assessed claims:\n{_render_claims(state['claims'])}\n\n"
                f"Unresolved disagreements:\n{dis_text}\n\n"
                "Write the verdict. Weight claims by warrant band. Do not paper "
                "over the unresolved disagreements; state them explicitly."
            ),
            label="SYNTHESIZER",
        )
        verdict = Verdict(
            decision=decision,
            preserved_disagreements=[d.id for d in unresolved],
            mean_warrant_rank=self._mean_warrant(state["claims"]),
            termination=self._termination,
        )
        return {"verdict": verdict, "termination": self._termination}
