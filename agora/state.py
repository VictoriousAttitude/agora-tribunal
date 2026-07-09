"""LangGraph state.

Plain keys, no reducers: the Judge mutates warrant bands on existing claims,
which an operator.add reducer cannot express. Nodes that append must return
the full new list (state["claims"] + new); nodes that mutate return a full
replacement list.
"""
from __future__ import annotations

from typing import TypedDict

from agora.models import Claim, Disagreement, Frame, Verdict


class DeliberationState(TypedDict, total=False):
    question: str
    round: int
    frame: Frame
    claims: list[Claim]
    reasoning: dict[str, str]      # "handle rN" -> free-form pass for that round
    disagreements: list[Disagreement]
    verdict: Verdict
    termination: str               # CONVERGENCE | MAX_ROUNDS | BUDGET
